"""One exact, failure-closed PostgreSQL column retirement action."""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol, cast

from retirement_conductor.canonical import digest_json, verify_digest, with_digest
from retirement_conductor.clock import parse_timestamp
from retirement_conductor.errors import Refusal
from retirement_conductor.postgres_producer_config import (
    PostgresConnectionSettings,
    PostgresProducerSettings,
    PostgresTarget,
)
from retirement_conductor.vocabulary import RefusalCode

ADAPTER_VERSION = "0.1.0"
ACTION_TYPE = "postgres_drop_column_v1"

POSTGRES_ACTION_COUNT_INVALID = "POSTGRES_ACTION_COUNT_INVALID"
POSTGRES_ACTION_DIGEST_MISMATCH = "POSTGRES_ACTION_DIGEST_MISMATCH"
POSTGRES_ACTION_EXPIRED = "POSTGRES_ACTION_EXPIRED"
POSTGRES_ACTION_REPLAYED = "POSTGRES_ACTION_REPLAYED"
POSTGRES_APPLY_DISABLED = "POSTGRES_APPLY_DISABLED"
POSTGRES_CONNECTION_UNAVAILABLE = "POSTGRES_CONNECTION_UNAVAILABLE"
POSTGRES_DEPENDENCY_REQUIRES_CASCADE = "POSTGRES_DEPENDENCY_REQUIRES_CASCADE"
POSTGRES_LEGACY_COLUMN_MISSING = "POSTGRES_LEGACY_COLUMN_MISSING"
POSTGRES_MUTATION_PERMISSION_DENIED = "POSTGRES_MUTATION_PERMISSION_DENIED"
POSTGRES_OBSERVER_MUTATOR_NOT_SEPARATE = "POSTGRES_OBSERVER_MUTATOR_NOT_SEPARATE"
POSTGRES_OUTCOME_UNKNOWN = "POSTGRES_OUTCOME_UNKNOWN"
POSTGRES_REPLACEMENT_COLUMN_MISSING = "POSTGRES_REPLACEMENT_COLUMN_MISSING"
POSTGRES_REPLACEMENT_INCOMPATIBLE = "POSTGRES_REPLACEMENT_INCOMPATIBLE"
POSTGRES_SCHEMA_FINGERPRINT_DRIFT = "POSTGRES_SCHEMA_FINGERPRINT_DRIFT"
POSTGRES_TABLE_IDENTITY_DRIFT = "POSTGRES_TABLE_IDENTITY_DRIFT"
POSTGRES_TARGET_NOT_ALLOWED = "POSTGRES_TARGET_NOT_ALLOWED"


class PostgresActionOutcome(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    COMMITTED = "COMMITTED"
    NOT_COMMITTED = "NOT_COMMITTED"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"


class PostgresClientProtocol(Protocol):
    """The narrow native operations required by the producer boundary."""

    @property
    def connection(self) -> PostgresConnectionSettings: ...

    def observe(self, target: PostgresTarget) -> dict[str, Any]: ...

    def execute_drop(self, plan: Mapping[str, Any]) -> dict[str, Any]: ...


class MutationTransportLost(Exception):
    """The connection was lost without a trustworthy action response."""

    def __init__(self, phase: str) -> None:
        super().__init__(phase)
        self.phase = phase


@dataclass(frozen=True)
class PostgresCliClient:
    """A psql-backed client with no general query method in its public contract."""

    connection: PostgresConnectionSettings
    psql_command: tuple[str, ...] = ("psql",)

    def observe(self, target: PostgresTarget) -> dict[str, Any]:
        raw = self._run(observation_sql(target), mutation=False)
        return normalize_observation(raw, target)

    def execute_drop(self, plan: Mapping[str, Any]) -> dict[str, Any]:
        result = self._run(
            drop_sql(plan, self.connection.lock_timeout_seconds), mutation=True
        )
        if result.get("status") != "committed":
            raise MutationTransportLost("after_intent")
        return {
            "destructive_statements_attempted": 1,
            "destructive_statements_committed": 1,
        }

    def _run(self, sql: str, *, mutation: bool) -> dict[str, Any]:
        command = (
            *self.psql_command,
            "--no-psqlrc",
            "--quiet",
            "--tuples-only",
            "--no-align",
            "--set",
            "ON_ERROR_STOP=1",
            "--host",
            self.connection.host,
            "--port",
            str(self.connection.port),
            "--dbname",
            self.connection.database,
            "--username",
            self.connection.username,
            "--command",
            sql,
        )
        environment = {
            **os.environ,
            "PGPASSWORD": self.connection.password,
            "PGCONNECT_TIMEOUT": str(self.connection.connect_timeout_seconds),
        }
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                env=environment,
                timeout=(
                    self.connection.connect_timeout_seconds
                    + self.connection.lock_timeout_seconds
                    + 10
                ),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            if mutation:
                raise MutationTransportLost("unknown") from exc
            raise Refusal(
                POSTGRES_CONNECTION_UNAVAILABLE,
                "The PostgreSQL observer could not establish native state.",
            ) from exc
        if completed.returncode != 0:
            if mutation:
                native_refusal = refusal_from_stderr(completed.stderr)
                if native_refusal is not None:
                    raise native_refusal
                raise MutationTransportLost("unknown")
            raise Refusal(
                POSTGRES_CONNECTION_UNAVAILABLE,
                "The PostgreSQL observer could not establish native state.",
            )
        lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
        if not lines:
            if mutation:
                raise MutationTransportLost("after_intent")
            raise Refusal(
                POSTGRES_CONNECTION_UNAVAILABLE,
                "The PostgreSQL observer returned no native state.",
            )
        try:
            value = json.loads(lines[-1])
        except json.JSONDecodeError as exc:
            if mutation:
                raise MutationTransportLost("after_intent") from exc
            raise Refusal(
                POSTGRES_CONNECTION_UNAVAILABLE,
                "The PostgreSQL observer returned malformed native state.",
            ) from exc
        if not isinstance(value, dict):
            raise Refusal(
                POSTGRES_CONNECTION_UNAVAILABLE,
                "The PostgreSQL native response was not an object.",
            )
        return cast(dict[str, Any], value)


class PostgresProducerAction:
    """Plan and execute one allowlisted DROP COLUMN without campaign authority."""

    def __init__(
        self,
        settings: PostgresProducerSettings,
        observer_client: PostgresClientProtocol,
    ) -> None:
        self.settings = settings
        self.observer_client = observer_client

    def observe(self, target: PostgresTarget) -> dict[str, Any]:
        observation = self.observer_client.observe(target)
        return with_digest(
            {
                **observation,
                "adapter_version": ADAPTER_VERSION,
                "endpoint_identity": self.settings.endpoint_identity(),
                "allowlist_configuration_digest": self.settings.allowlist_digest(),
            },
            "observation_digest",
        )

    def plan(
        self,
        observation: Mapping[str, Any],
        *,
        actions: Sequence[PostgresTarget],
        action_expires_at: str,
    ) -> dict[str, Any]:
        verify_digest(dict(observation), "observation_digest")
        if len(actions) != 1:
            raise Refusal(
                POSTGRES_ACTION_COUNT_INVALID,
                "Exactly one PostgreSQL producer action is supported.",
                {"requested_action_count": len(actions)},
            )
        target = actions[0]
        self._require_allowed(target)
        if target.as_dict() != observation.get("target"):
            raise Refusal(
                POSTGRES_TARGET_NOT_ALLOWED,
                "The requested action does not match the observed native tuple.",
            )
        if observation.get("endpoint_identity") != self.settings.endpoint_identity():
            raise Refusal(
                POSTGRES_TARGET_NOT_ALLOWED,
                "The observation came from another PostgreSQL endpoint.",
            )
        database_identity = observation.get("database_identity")
        if (
            not isinstance(database_identity, dict)
            or database_identity.get("name") != target.database
        ):
            raise Refusal(
                POSTGRES_TARGET_NOT_ALLOWED,
                "The observed PostgreSQL database does not match the target.",
            )
        if not observation.get("table_exists"):
            raise Refusal(
                POSTGRES_TABLE_IDENTITY_DRIFT,
                "The exact PostgreSQL table does not exist.",
            )
        legacy = observation.get("legacy_column")
        replacement = observation.get("replacement_column")
        if not isinstance(legacy, dict):
            raise Refusal(
                POSTGRES_LEGACY_COLUMN_MISSING,
                "The exact legacy column does not exist.",
            )
        if not isinstance(replacement, dict):
            raise Refusal(
                POSTGRES_REPLACEMENT_COLUMN_MISSING,
                "The exact replacement column does not exist.",
            )
        compatibility = compatibility_result(legacy, replacement)
        if not compatibility["compatible"]:
            raise Refusal(
                POSTGRES_REPLACEMENT_INCOMPATIBLE,
                "The replacement column is not structurally compatible.",
                {"mismatches": compatibility["mismatches"]},
            )
        dependencies = observation.get("legacy_dependencies")
        if not isinstance(dependencies, list):
            raise Refusal(
                POSTGRES_CONNECTION_UNAVAILABLE,
                "The dependency check was not available.",
            )
        if dependencies:
            raise Refusal(
                POSTGRES_DEPENDENCY_REQUIRES_CASCADE,
                "Native dependencies prevent DROP COLUMN without CASCADE.",
                {"dependency_count": len(dependencies)},
            )
        parse_timestamp(action_expires_at)
        plan = with_digest(
            {
                "schema_version": "1.0.0",
                "adapter_version": ADAPTER_VERSION,
                "action_type": ACTION_TYPE,
                "action_count": 1,
                "target": target.as_dict(),
                "endpoint_identity": observation["endpoint_identity"],
                "database_identity": observation["database_identity"],
                "postgres_version": observation["postgres_version"],
                "table_identity": observation["table_identity"],
                "before_schema_fingerprint": observation["schema_fingerprint"],
                "before_columns": observation["columns"],
                "legacy_column": legacy,
                "replacement_column": replacement,
                "compatibility": compatibility,
                "dependency_check": {
                    "requires_cascade": False,
                    "dependency_count": 0,
                    "dependencies_digest": digest_json(dependencies),
                },
                "allowlist_configuration_digest": observation[
                    "allowlist_configuration_digest"
                ],
                "observer_principal": observation["principal"]["current_user"],
                "action_expires_at": action_expires_at,
                "sql_shape": (
                    "ALTER TABLE <quoted-schema>.<quoted-table> "
                    "DROP COLUMN <quoted-column>"
                ),
                "cascade": False,
            },
            "action_digest",
        )
        return plan

    def apply(
        self,
        plan: Mapping[str, Any],
        *,
        mutation_client: PostgresClientProtocol,
        confirmed_action_digest: str,
        attempt_id: str,
        trusted_now: datetime,
        prior_attempt: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        verify_digest(dict(plan), "action_digest")
        if prior_attempt is not None and prior_attempt.get("outcome") == str(
            PostgresActionOutcome.OUTCOME_UNKNOWN
        ):
            raise Refusal(
                POSTGRES_OUTCOME_UNKNOWN,
                "An earlier unknown attempt must be resolved explicitly before retry.",
                {"prior_attempt_digest": prior_attempt.get("attempt_digest")},
            )
        if not self.settings.allow_apply:
            raise Refusal(
                POSTGRES_APPLY_DISABLED,
                "PostgreSQL producer apply is disabled by configuration.",
            )
        if plan.get("action_count") != 1:
            raise Refusal(
                POSTGRES_ACTION_COUNT_INVALID,
                "The confirmed PostgreSQL plan must contain exactly one action.",
            )
        if confirmed_action_digest != plan.get("action_digest"):
            raise Refusal(
                POSTGRES_ACTION_DIGEST_MISMATCH,
                "The confirmed digest does not match the exact PostgreSQL action.",
            )
        expires_at = parse_timestamp(str(plan["action_expires_at"]))
        if trusted_now.tzinfo is None:
            raise Refusal(
                RefusalCode.RUNTIME_CLOCK_INVALID,
                "The trusted PostgreSQL action time must include a timezone.",
            )
        if trusted_now >= expires_at:
            raise Refusal(
                POSTGRES_ACTION_EXPIRED,
                "The PostgreSQL producer action has expired.",
            )
        target = target_from_mapping(cast(Mapping[str, Any], plan["target"]))
        self._require_allowed(target)
        if (
            plan.get("allowlist_configuration_digest")
            != self.settings.allowlist_digest()
        ):
            raise Refusal(
                POSTGRES_TARGET_NOT_ALLOWED,
                "The PostgreSQL allowlist changed after planning.",
            )
        if mutation_client is self.observer_client:
            raise Refusal(
                POSTGRES_OBSERVER_MUTATOR_NOT_SEPARATE,
                (
                    "The mutation client must be instantiated separately "
                    "from the observer."
                ),
            )
        connection = mutation_client.connection
        if (
            connection.host != self.settings.host
            or connection.port != self.settings.port
            or connection.database != self.settings.database
        ):
            raise Refusal(
                POSTGRES_TARGET_NOT_ALLOWED,
                "The mutation client points at another PostgreSQL endpoint.",
            )
        before = mutation_client.observe(target)
        self._verify_preconditions(plan, before, require_legacy=True)
        principal = cast(Mapping[str, Any], before["principal"])
        if principal.get("current_user") == plan.get("observer_principal"):
            raise Refusal(
                POSTGRES_OBSERVER_MUTATOR_NOT_SEPARATE,
                "The observer principal cannot execute the producer mutation.",
            )
        if not principal.get("can_alter_table"):
            raise Refusal(
                POSTGRES_MUTATION_PERMISSION_DENIED,
                "The mutation principal lacks exact authority over the table.",
            )
        intent = {
            "attempt_id": attempt_id,
            "action_digest": plan["action_digest"],
            "trusted_at": trusted_now.isoformat().replace("+00:00", "Z"),
        }
        intent_digest = digest_json(intent)
        try:
            native = mutation_client.execute_drop(plan)
        except MutationTransportLost as exc:
            return self._resolve_after_transport_loss(
                plan,
                target=target,
                attempt_id=attempt_id,
                intent_digest=intent_digest,
                transport_phase=exc.phase,
            )
        after = self.observer_client.observe(target)
        self._verify_committed(plan, after)
        return outcome_record(
            plan,
            attempt_id=attempt_id,
            intent_digest=intent_digest,
            outcome=PostgresActionOutcome.COMMITTED,
            observation=after,
            destructive_statements_attempted=int(
                native.get("destructive_statements_attempted", 1)
            ),
            destructive_statements_committed=int(
                native.get("destructive_statements_committed", 1)
            ),
            recovery="post_commit_native_reread",
        )

    def resolve_outcome(
        self,
        plan: Mapping[str, Any],
        attempt: Mapping[str, Any],
    ) -> dict[str, Any]:
        verify_digest(dict(plan), "action_digest")
        verify_digest(dict(attempt), "attempt_digest")
        if attempt.get("action_digest") != plan.get("action_digest"):
            raise Refusal(
                POSTGRES_ACTION_DIGEST_MISMATCH,
                "The unknown attempt belongs to another PostgreSQL action.",
            )
        if attempt.get("outcome") != str(PostgresActionOutcome.OUTCOME_UNKNOWN):
            return dict(attempt)
        target = target_from_mapping(cast(Mapping[str, Any], plan["target"]))
        observation = self.observer_client.observe(target)
        return self._classify_observed_outcome(
            plan,
            observation,
            attempt_id=str(attempt["attempt_id"]),
            intent_digest=str(attempt["intent_digest"]),
            transport_phase=str(attempt.get("transport_phase", "unknown")),
        )

    def _resolve_after_transport_loss(
        self,
        plan: Mapping[str, Any],
        *,
        target: PostgresTarget,
        attempt_id: str,
        intent_digest: str,
        transport_phase: str,
    ) -> dict[str, Any]:
        try:
            observation = self.observer_client.observe(target)
        except Refusal:
            attempted = 0 if transport_phase == "before_execution" else 1
            return outcome_record(
                plan,
                attempt_id=attempt_id,
                intent_digest=intent_digest,
                outcome=PostgresActionOutcome.OUTCOME_UNKNOWN,
                observation=None,
                destructive_statements_attempted=attempted,
                destructive_statements_committed=0,
                recovery="explicit_native_observation_required",
                transport_phase=transport_phase,
            )
        return self._classify_observed_outcome(
            plan,
            observation,
            attempt_id=attempt_id,
            intent_digest=intent_digest,
            transport_phase=transport_phase,
        )

    def _classify_observed_outcome(
        self,
        plan: Mapping[str, Any],
        observation: Mapping[str, Any],
        *,
        attempt_id: str,
        intent_digest: str,
        transport_phase: str,
    ) -> dict[str, Any]:
        attempted = 0 if transport_phase == "before_execution" else 1
        legacy = observation.get("legacy_column")
        if legacy is None:
            self._verify_committed(plan, observation)
            outcome = PostgresActionOutcome.COMMITTED
            committed = 1
        elif observation.get("schema_fingerprint") == plan.get(
            "before_schema_fingerprint"
        ):
            outcome = PostgresActionOutcome.NOT_COMMITTED
            committed = 0
        else:
            return outcome_record(
                plan,
                attempt_id=attempt_id,
                intent_digest=intent_digest,
                outcome=PostgresActionOutcome.OUTCOME_UNKNOWN,
                observation=observation,
                destructive_statements_attempted=attempted,
                destructive_statements_committed=0,
                recovery="explicit_operator_investigation_required",
                transport_phase=transport_phase,
            )
        return outcome_record(
            plan,
            attempt_id=attempt_id,
            intent_digest=intent_digest,
            outcome=outcome,
            observation=observation,
            destructive_statements_attempted=attempted,
            destructive_statements_committed=committed,
            recovery="resolved_by_native_schema_reread_without_retry",
            transport_phase=transport_phase,
        )

    def _verify_preconditions(
        self,
        plan: Mapping[str, Any],
        observation: Mapping[str, Any],
        *,
        require_legacy: bool,
    ) -> None:
        if observation.get("database_identity") != plan.get("database_identity"):
            raise Refusal(
                POSTGRES_TABLE_IDENTITY_DRIFT,
                "The PostgreSQL database identity changed after planning.",
            )
        if observation.get("table_identity") != plan.get("table_identity"):
            raise Refusal(
                POSTGRES_TABLE_IDENTITY_DRIFT,
                "The PostgreSQL table identity changed after planning.",
            )
        if require_legacy and observation.get("legacy_column") is None:
            raise Refusal(
                POSTGRES_ACTION_REPLAYED,
                "The legacy column is already absent; the action cannot be replayed.",
            )
        if observation.get("schema_fingerprint") != plan.get(
            "before_schema_fingerprint"
        ):
            raise Refusal(
                POSTGRES_SCHEMA_FINGERPRINT_DRIFT,
                "The ordered PostgreSQL schema changed after planning.",
            )
        dependencies = observation.get("legacy_dependencies")
        if dependencies:
            raise Refusal(
                POSTGRES_DEPENDENCY_REQUIRES_CASCADE,
                "A new native dependency would require CASCADE.",
                {"dependency_count": len(cast(list[Any], dependencies))},
            )

    def _verify_committed(
        self, plan: Mapping[str, Any], observation: Mapping[str, Any]
    ) -> None:
        if observation.get("table_identity") != plan.get("table_identity"):
            raise Refusal(
                POSTGRES_OUTCOME_UNKNOWN,
                "Post-commit reread found another table identity.",
            )
        if observation.get("legacy_column") is not None:
            raise Refusal(
                POSTGRES_OUTCOME_UNKNOWN,
                "Post-commit reread did not prove the legacy column absent.",
            )
        if observation.get("replacement_column") != plan.get("replacement_column"):
            raise Refusal(
                POSTGRES_OUTCOME_UNKNOWN,
                "Post-commit reread did not preserve the replacement column.",
            )

    def _require_allowed(self, target: PostgresTarget) -> None:
        if (
            target.database != self.settings.database
            or target not in self.settings.allowed_targets
        ):
            raise Refusal(
                POSTGRES_TARGET_NOT_ALLOWED,
                "The exact PostgreSQL tuple is not allowlisted.",
                {"target": target.as_dict()},
            )


def normalize_observation(
    raw: Mapping[str, Any], target: PostgresTarget
) -> dict[str, Any]:
    table = raw.get("table")
    database = raw.get("database")
    if not isinstance(database, dict):
        raise Refusal(
            POSTGRES_CONNECTION_UNAVAILABLE,
            "PostgreSQL did not return database identity.",
        )
    base: dict[str, Any] = {
        "schema_version": "1.0.0",
        "target": target.as_dict(),
        "database_identity": {
            "name": database.get("name"),
            "oid": database.get("oid"),
        },
        "postgres_version": {
            "server_version": database.get("server_version"),
            "server_version_num": database.get("server_version_num"),
        },
        "principal": raw.get("principal"),
        "table_exists": isinstance(table, dict),
    }
    if not isinstance(table, dict):
        return {
            **base,
            "table_identity": None,
            "columns": [],
            "schema_fingerprint": None,
            "legacy_column": None,
            "replacement_column": None,
            "legacy_dependencies": [],
        }
    columns = table.get("columns")
    dependencies = table.get("legacy_dependencies")
    if not isinstance(columns, list) or not isinstance(dependencies, list):
        raise Refusal(
            POSTGRES_CONNECTION_UNAVAILABLE,
            "PostgreSQL returned incomplete schema facts.",
        )
    identity = {
        "database_oid": database.get("oid"),
        "schema_oid": table.get("schema_oid"),
        "relation_oid": table.get("relation_oid"),
    }
    legacy = next(
        (column for column in columns if column.get("name") == target.legacy_column),
        None,
    )
    replacement = next(
        (
            column
            for column in columns
            if column.get("name") == target.replacement_column
        ),
        None,
    )
    return {
        **base,
        "table_identity": identity,
        "columns": columns,
        "schema_fingerprint": digest_json(
            {"table_identity": identity, "columns": columns}
        ),
        "legacy_column": legacy,
        "replacement_column": replacement,
        "legacy_dependencies": dependencies,
    }


def compatibility_result(
    legacy: Mapping[str, Any], replacement: Mapping[str, Any]
) -> dict[str, Any]:
    compared = ("type_oid", "type_modifier", "not_null", "default_expression")
    mismatches = [
        name for name in compared if legacy.get(name) != replacement.get(name)
    ]
    return {
        "compatible": not mismatches,
        "compared_facts": list(compared),
        "mismatches": mismatches,
    }


def target_from_mapping(value: Mapping[str, Any]) -> PostgresTarget:
    return PostgresTarget(
        database=str(value["database"]),
        schema=str(value["schema"]),
        table=str(value["table"]),
        legacy_column=str(value["legacy_column"]),
        replacement_column=str(value["replacement_column"]),
    )


def outcome_record(
    plan: Mapping[str, Any],
    *,
    attempt_id: str,
    intent_digest: str,
    outcome: PostgresActionOutcome,
    observation: Mapping[str, Any] | None,
    destructive_statements_attempted: int,
    destructive_statements_committed: int,
    recovery: str,
    transport_phase: str | None = None,
) -> dict[str, Any]:
    return with_digest(
        {
            "schema_version": "1.0.0",
            "action_type": ACTION_TYPE,
            "action_digest": plan["action_digest"],
            "attempt_id": attempt_id,
            "intent_digest": intent_digest,
            "outcome": str(outcome),
            "target": plan["target"],
            "before_schema_fingerprint": plan["before_schema_fingerprint"],
            "after_schema_fingerprint": (
                None if observation is None else observation.get("schema_fingerprint")
            ),
            "legacy_column_present": (
                None
                if observation is None
                else observation.get("legacy_column") is not None
            ),
            "replacement_column_preserved": (
                None
                if observation is None
                else observation.get("replacement_column")
                == plan.get("replacement_column")
            ),
            "destructive_statements_attempted": destructive_statements_attempted,
            "destructive_statements_committed": destructive_statements_committed,
            "transport_phase": transport_phase,
            "recovery": recovery,
        },
        "attempt_digest",
    )


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def quote_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def observation_sql(target: PostgresTarget) -> str:
    schema = quote_literal(target.schema)
    table = quote_literal(target.table)
    legacy = quote_literal(target.legacy_column)
    return f"""
WITH table_info AS (
  SELECT c.oid AS relation_oid,
         n.oid AS schema_oid,
         c.relowner AS owner_oid,
         pg_get_userbyid(c.relowner) AS owner_name
  FROM pg_catalog.pg_class AS c
  JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
  WHERE n.nspname = {schema}
    AND c.relname = {table}
    AND c.relkind IN ('r', 'p')
), columns AS (
  SELECT a.attnum AS position,
         a.attname AS name,
         a.atttypid::integer AS type_oid,
         a.atttypmod AS type_modifier,
         pg_catalog.format_type(a.atttypid, a.atttypmod) AS formatted_type,
         a.attnotnull AS not_null,
         pg_catalog.pg_get_expr(d.adbin, d.adrelid) AS default_expression,
         a.attidentity AS identity_kind,
         a.attgenerated AS generated_kind
  FROM table_info AS t
  JOIN pg_catalog.pg_attribute AS a ON a.attrelid = t.relation_oid
  LEFT JOIN pg_catalog.pg_attrdef AS d
    ON d.adrelid = a.attrelid AND d.adnum = a.attnum
  WHERE a.attnum > 0 AND NOT a.attisdropped
), dependencies AS (
  SELECT dep.classid::integer AS class_id,
         dep.objid::integer AS object_id,
         dep.objsubid AS object_sub_id,
         dep.deptype AS dependency_type,
         pg_catalog.pg_describe_object(dep.classid, dep.objid, dep.objsubid)
           AS object_identity
  FROM table_info AS t
  JOIN pg_catalog.pg_attribute AS a
    ON a.attrelid = t.relation_oid AND a.attname = {legacy}
  JOIN pg_catalog.pg_depend AS dep
    ON dep.refclassid = 'pg_catalog.pg_class'::pg_catalog.regclass
   AND dep.refobjid = t.relation_oid
   AND dep.refobjsubid = a.attnum
)
SELECT pg_catalog.json_build_object(
  'database', pg_catalog.json_build_object(
    'name', pg_catalog.current_database(),
    'oid', (SELECT oid::integer FROM pg_catalog.pg_database
            WHERE datname = pg_catalog.current_database()),
    'server_version', pg_catalog.current_setting('server_version'),
    'server_version_num', pg_catalog.current_setting('server_version_num')
  ),
  'principal', pg_catalog.json_build_object(
    'session_user', session_user,
    'current_user', current_user,
    'table_owner', (SELECT owner_name FROM table_info),
    'can_alter_table', COALESCE(
      (SELECT pg_catalog.pg_has_role(current_user, owner_oid, 'USAGE')
       FROM table_info), false)
  ),
  'table', (SELECT pg_catalog.json_build_object(
    'relation_oid', relation_oid::integer,
    'schema_oid', schema_oid::integer,
    'columns', (SELECT COALESCE(
      pg_catalog.json_agg(pg_catalog.json_build_object(
        'position', position,
        'name', name,
        'type_oid', type_oid,
        'type_modifier', type_modifier,
        'formatted_type', formatted_type,
        'not_null', not_null,
        'default_expression', default_expression,
        'identity_kind', identity_kind,
        'generated_kind', generated_kind
      ) ORDER BY position), '[]'::json) FROM columns),
    'legacy_dependencies', (SELECT COALESCE(
      pg_catalog.json_agg(pg_catalog.json_build_object(
        'class_id', class_id,
        'object_id', object_id,
        'object_sub_id', object_sub_id,
        'dependency_type', dependency_type,
        'object_identity', object_identity
      ) ORDER BY class_id, object_id, object_sub_id), '[]'::json)
      FROM dependencies)
  ) FROM table_info)
)::text;
""".strip()


def drop_sql(plan: Mapping[str, Any], lock_timeout_seconds: int) -> str:
    target = target_from_mapping(cast(Mapping[str, Any], plan["target"]))
    schema_literal = quote_literal(target.schema)
    table_literal = quote_literal(target.table)
    legacy_literal = quote_literal(target.legacy_column)
    replacement_literal = quote_literal(target.replacement_column)
    qualified_table = (
        f"{quote_identifier(target.schema)}.{quote_identifier(target.table)}"
    )
    legacy_identifier = quote_identifier(target.legacy_column)
    expected_oid = int(cast(Mapping[str, Any], plan["table_identity"])["relation_oid"])
    expected_columns = quote_literal(
        json.dumps(plan["before_columns"], separators=(",", ":"), sort_keys=True)
    )
    expected_replacement = quote_literal(
        json.dumps(plan["replacement_column"], separators=(",", ":"), sort_keys=True)
    )
    return f"""
BEGIN;
SET LOCAL lock_timeout = '{lock_timeout_seconds}s';
LOCK TABLE {qualified_table} IN ACCESS EXCLUSIVE MODE;
DO $rc$
DECLARE
  relation_id oid;
  actual_columns jsonb;
  dependency_count integer;
BEGIN
  SELECT c.oid INTO relation_id
  FROM pg_catalog.pg_class AS c
  JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
  WHERE n.nspname = {schema_literal}
    AND c.relname = {table_literal}
    AND c.relkind IN ('r', 'p');
  IF relation_id IS NULL OR relation_id::integer <> {expected_oid} THEN
    RAISE EXCEPTION USING MESSAGE = 'RC_POSTGRES_TABLE_IDENTITY_DRIFT';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_attribute
    WHERE attrelid = relation_id AND attname = {legacy_literal}
      AND attnum > 0 AND NOT attisdropped
  ) THEN
    RAISE EXCEPTION USING MESSAGE = 'RC_POSTGRES_ACTION_REPLAYED';
  END IF;
  SELECT COALESCE(pg_catalog.jsonb_agg(pg_catalog.jsonb_build_object(
    'position', a.attnum,
    'name', a.attname,
    'type_oid', a.atttypid::integer,
    'type_modifier', a.atttypmod,
    'formatted_type', pg_catalog.format_type(a.atttypid, a.atttypmod),
    'not_null', a.attnotnull,
    'default_expression', pg_catalog.pg_get_expr(d.adbin, d.adrelid),
    'identity_kind', a.attidentity,
    'generated_kind', a.attgenerated
  ) ORDER BY a.attnum), '[]'::jsonb) INTO actual_columns
  FROM pg_catalog.pg_attribute AS a
  LEFT JOIN pg_catalog.pg_attrdef AS d
    ON d.adrelid = a.attrelid AND d.adnum = a.attnum
  WHERE a.attrelid = relation_id AND a.attnum > 0 AND NOT a.attisdropped;
  IF actual_columns <> {expected_columns}::jsonb THEN
    RAISE EXCEPTION USING MESSAGE = 'RC_POSTGRES_SCHEMA_FINGERPRINT_DRIFT';
  END IF;
  SELECT count(*) INTO dependency_count
  FROM pg_catalog.pg_depend AS dep
  JOIN pg_catalog.pg_attribute AS a
    ON a.attrelid = relation_id AND a.attname = {legacy_literal}
  WHERE dep.refclassid = 'pg_catalog.pg_class'::pg_catalog.regclass
    AND dep.refobjid = relation_id
    AND dep.refobjsubid = a.attnum;
  IF dependency_count <> 0 THEN
    RAISE EXCEPTION USING MESSAGE = 'RC_POSTGRES_DEPENDENCY_REQUIRES_CASCADE';
  END IF;
  IF NOT pg_catalog.pg_has_role(current_user,
      (SELECT relowner FROM pg_catalog.pg_class WHERE oid = relation_id), 'USAGE') THEN
    RAISE EXCEPTION USING MESSAGE = 'RC_POSTGRES_MUTATION_PERMISSION_DENIED';
  END IF;
END
$rc$;
ALTER TABLE {qualified_table} DROP COLUMN {legacy_identifier};
DO $rc$
DECLARE
  replacement jsonb;
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_catalog.pg_attribute
    WHERE attrelid = {expected_oid} AND attname = {legacy_literal}
      AND attnum > 0 AND NOT attisdropped
  ) THEN
    RAISE EXCEPTION USING MESSAGE = 'RC_POSTGRES_LEGACY_COLUMN_REMAINS';
  END IF;
  SELECT pg_catalog.jsonb_build_object(
    'position', a.attnum,
    'name', a.attname,
    'type_oid', a.atttypid::integer,
    'type_modifier', a.atttypmod,
    'formatted_type', pg_catalog.format_type(a.atttypid, a.atttypmod),
    'not_null', a.attnotnull,
    'default_expression', pg_catalog.pg_get_expr(d.adbin, d.adrelid),
    'identity_kind', a.attidentity,
    'generated_kind', a.attgenerated
  ) INTO replacement
  FROM pg_catalog.pg_attribute AS a
  LEFT JOIN pg_catalog.pg_attrdef AS d
    ON d.adrelid = a.attrelid AND d.adnum = a.attnum
  WHERE a.attrelid = {expected_oid} AND a.attname = {replacement_literal}
    AND a.attnum > 0 AND NOT a.attisdropped;
  IF replacement IS NULL OR replacement <> {expected_replacement}::jsonb THEN
    RAISE EXCEPTION USING MESSAGE = 'RC_POSTGRES_REPLACEMENT_DRIFT';
  END IF;
END
$rc$;
COMMIT;
SELECT pg_catalog.json_build_object('status', 'committed')::text;
""".strip()


def refusal_from_stderr(stderr: str) -> Refusal | None:
    markers = {
        "RC_POSTGRES_ACTION_REPLAYED": (
            POSTGRES_ACTION_REPLAYED,
            "The legacy column is already absent; the action cannot be replayed.",
        ),
        "RC_POSTGRES_TABLE_IDENTITY_DRIFT": (
            POSTGRES_TABLE_IDENTITY_DRIFT,
            "The PostgreSQL table identity changed under the transaction lock.",
        ),
        "RC_POSTGRES_SCHEMA_FINGERPRINT_DRIFT": (
            POSTGRES_SCHEMA_FINGERPRINT_DRIFT,
            "The ordered PostgreSQL schema changed under the transaction lock.",
        ),
        "RC_POSTGRES_DEPENDENCY_REQUIRES_CASCADE": (
            POSTGRES_DEPENDENCY_REQUIRES_CASCADE,
            "A native dependency appeared under the transaction lock.",
        ),
        "RC_POSTGRES_MUTATION_PERMISSION_DENIED": (
            POSTGRES_MUTATION_PERMISSION_DENIED,
            "The mutation principal lacks exact authority over the table.",
        ),
        "RC_POSTGRES_LEGACY_COLUMN_REMAINS": (
            POSTGRES_OUTCOME_UNKNOWN,
            "In-transaction verification did not prove the legacy column absent.",
        ),
        "RC_POSTGRES_REPLACEMENT_DRIFT": (
            POSTGRES_OUTCOME_UNKNOWN,
            "In-transaction verification did not preserve the replacement column.",
        ),
    }
    for marker, (code, message) in markers.items():
        if marker in stderr:
            return Refusal(code, message)
    if "permission denied" in stderr.lower() or "must be owner" in stderr.lower():
        return Refusal(
            POSTGRES_MUTATION_PERMISSION_DENIED,
            "The mutation principal lacks exact authority over the table.",
        )
    return None

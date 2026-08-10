from __future__ import annotations

import copy
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import pytest

from retirement_conductor.canonical import digest_json
from retirement_conductor.errors import Refusal
from retirement_conductor.postgres_producer import (
    POSTGRES_ACTION_COUNT_INVALID,
    POSTGRES_ACTION_DIGEST_MISMATCH,
    POSTGRES_ACTION_REPLAYED,
    POSTGRES_APPLY_DISABLED,
    POSTGRES_DEPENDENCY_REQUIRES_CASCADE,
    POSTGRES_LEGACY_COLUMN_MISSING,
    POSTGRES_MUTATION_PERMISSION_DENIED,
    POSTGRES_OBSERVER_MUTATOR_NOT_SEPARATE,
    POSTGRES_OUTCOME_UNKNOWN,
    POSTGRES_REPLACEMENT_COLUMN_MISSING,
    POSTGRES_REPLACEMENT_INCOMPATIBLE,
    POSTGRES_SCHEMA_FINGERPRINT_DRIFT,
    POSTGRES_TARGET_NOT_ALLOWED,
    MutationTransportLost,
    PostgresActionOutcome,
    PostgresProducerAction,
    drop_sql,
    normalize_observation,
    quote_identifier,
)
from retirement_conductor.postgres_producer_config import (
    PostgresConnectionSettings,
    PostgresProducerSettings,
    PostgresTarget,
)

TARGET = PostgresTarget(
    database="rc_cp01_producer",
    schema="retirement_lab",
    table="orders",
    legacy_column="legacy_status",
    replacement_column="order_status",
)


def column(position: int, name: str, *, type_oid: int = 25) -> dict[str, Any]:
    return {
        "position": position,
        "name": name,
        "type_oid": type_oid,
        "type_modifier": -1,
        "formatted_type": "text" if type_oid == 25 else "integer",
        "not_null": True,
        "default_expression": None,
        "identity_kind": "",
        "generated_kind": "",
    }


def raw_observation(
    *,
    principal: str,
    can_alter: bool,
    legacy_present: bool = True,
    replacement_type_oid: int = 25,
    dependencies: list[dict[str, Any]] | None = None,
    extra_column: bool = False,
) -> dict[str, Any]:
    columns = [column(1, "order_id", type_oid=20)]
    if legacy_present:
        columns.append(column(2, "legacy_status"))
    columns.extend(
        [
            column(3, "order_status", type_oid=replacement_type_oid),
            column(4, "amount_cents", type_oid=20),
        ]
    )
    if extra_column:
        columns.append(column(5, "intervening_note"))
    return {
        "database": {
            "name": TARGET.database,
            "oid": 5,
            "server_version": "16.10",
            "server_version_num": "160010",
        },
        "principal": {
            "session_user": principal,
            "current_user": principal,
            "table_owner": "rc_cp01_mutator",
            "can_alter_table": can_alter,
        },
        "table": {
            "relation_oid": 16390,
            "schema_oid": 16389,
            "columns": columns,
            "legacy_dependencies": dependencies or [],
        },
    }


def settings(
    *, allow_apply: bool = True, allowlisted: bool = True
) -> PostgresProducerSettings:
    return PostgresProducerSettings(
        host="127.0.0.1",
        port=25432,
        database=TARGET.database,
        observer_username="rc_cp01_observer",
        observer_password="observer-secret",
        mutation_username="rc_cp01_mutator",
        mutation_password="mutation-secret",
        allow_apply=allow_apply,
        allowed_targets=(TARGET,) if allowlisted else (),
    )


def connection(principal: str) -> PostgresConnectionSettings:
    return PostgresConnectionSettings(
        host="127.0.0.1",
        port=25432,
        database=TARGET.database,
        username=principal,
        password="secret",
        connect_timeout_seconds=5,
        lock_timeout_seconds=5,
    )


class FakeClient:
    def __init__(
        self,
        principal: str,
        *,
        can_alter: bool,
        behavior: str = "commit",
    ) -> None:
        self.connection = connection(principal)
        self.current = normalize_observation(
            raw_observation(principal=principal, can_alter=can_alter), TARGET
        )
        self.behavior = behavior
        self.execute_calls = 0
        self.mirror: FakeClient | None = None

    def observe(self, target: PostgresTarget) -> dict[str, Any]:
        assert target == TARGET
        if self.behavior == "observer_unavailable":
            raise Refusal("POSTGRES_CONNECTION_UNAVAILABLE", "unavailable")
        return copy.deepcopy(self.current)

    def execute_drop(self, plan: Mapping[str, Any]) -> dict[str, Any]:
        self.execute_calls += 1
        if self.behavior == "loss_before":
            raise MutationTransportLost("before_execution")
        self.current = normalize_observation(
            raw_observation(
                principal=self.connection.username,
                can_alter=True,
                legacy_present=False,
            ),
            TARGET,
        )
        if self.mirror is not None:
            self.mirror.current = copy.deepcopy(self.current)
        if self.behavior == "loss_after":
            raise MutationTransportLost("after_intent")
        return {
            "destructive_statements_attempted": 1,
            "destructive_statements_committed": 1,
        }


def planned(
    *,
    allow_apply: bool = True,
    observation: dict[str, Any] | None = None,
) -> tuple[PostgresProducerAction, FakeClient, dict[str, Any]]:
    observer = FakeClient("rc_cp01_observer", can_alter=False)
    if observation is not None:
        observer.current = observation
    action = PostgresProducerAction(settings(allow_apply=allow_apply), observer)
    plan = action.plan(
        action.observe(TARGET),
        actions=[TARGET],
        action_expires_at="2026-08-10T01:00:00Z",
    )
    return action, observer, plan


def apply(
    action: PostgresProducerAction,
    plan: dict[str, Any],
    mutator: FakeClient,
    **overrides: Any,
) -> dict[str, Any]:
    arguments: dict[str, Any] = {
        "mutation_client": mutator,
        "confirmed_action_digest": plan["action_digest"],
        "attempt_id": "attempt-1",
        "trusted_now": datetime(2026, 8, 10, 0, 30, tzinfo=UTC),
    }
    arguments.update(overrides)
    return action.apply(plan, **arguments)


def test_plan_binds_native_identity_schema_and_compatibility() -> None:
    _, _, plan = planned(allow_apply=False)

    assert plan["action_type"] == "postgres_drop_column_v1"
    assert plan["action_count"] == 1
    assert plan["target"] == TARGET.as_dict()
    assert plan["compatibility"]["compatible"] is True
    assert plan["dependency_check"]["requires_cascade"] is False
    assert plan["cascade"] is False


def test_plan_refuses_missing_allowlist_and_multiple_actions() -> None:
    observer = FakeClient("rc_cp01_observer", can_alter=False)
    action = PostgresProducerAction(settings(allowlisted=False), observer)
    observation = action.observe(TARGET)

    with pytest.raises(Refusal) as missing:
        action.plan(
            observation,
            actions=[TARGET],
            action_expires_at="2026-08-10T01:00:00Z",
        )
    assert missing.value.code == POSTGRES_TARGET_NOT_ALLOWED

    allowed = PostgresProducerAction(settings(), observer)
    with pytest.raises(Refusal) as multiple:
        allowed.plan(
            allowed.observe(TARGET),
            actions=[TARGET, TARGET],
            action_expires_at="2026-08-10T01:00:00Z",
        )
    assert multiple.value.code == POSTGRES_ACTION_COUNT_INVALID


def test_plan_refuses_incompatible_replacement_and_dependencies() -> None:
    incompatible = normalize_observation(
        raw_observation(
            principal="rc_cp01_observer",
            can_alter=False,
            replacement_type_oid=23,
        ),
        TARGET,
    )
    with pytest.raises(Refusal) as type_drift:
        planned(observation=incompatible)
    assert type_drift.value.code == POSTGRES_REPLACEMENT_INCOMPATIBLE

    dependent = normalize_observation(
        raw_observation(
            principal="rc_cp01_observer",
            can_alter=False,
            dependencies=[{"object_identity": "rule _RETURN on view legacy_orders"}],
        ),
        TARGET,
    )
    with pytest.raises(Refusal) as dependency:
        planned(observation=dependent)
    assert dependency.value.code == POSTGRES_DEPENDENCY_REQUIRES_CASCADE


@pytest.mark.parametrize(
    ("legacy_present", "replacement_present", "expected_code"),
    [
        (False, True, POSTGRES_LEGACY_COLUMN_MISSING),
        (True, False, POSTGRES_REPLACEMENT_COLUMN_MISSING),
    ],
)
def test_plan_refuses_missing_fields(
    legacy_present: bool, replacement_present: bool, expected_code: str
) -> None:
    raw = raw_observation(
        principal="rc_cp01_observer",
        can_alter=False,
        legacy_present=legacy_present,
    )
    if not replacement_present:
        raw["table"]["columns"] = [
            item
            for item in raw["table"]["columns"]
            if item["name"] != TARGET.replacement_column
        ]
    observation = normalize_observation(raw, TARGET)

    with pytest.raises(Refusal) as exc_info:
        planned(observation=observation)

    assert exc_info.value.code == expected_code


def test_apply_is_off_by_default_and_digest_bound() -> None:
    action, _, plan = planned(allow_apply=False)
    mutator = FakeClient("rc_cp01_mutator", can_alter=True)

    with pytest.raises(Refusal) as disabled:
        apply(action, plan, mutator)
    assert disabled.value.code == POSTGRES_APPLY_DISABLED
    assert mutator.execute_calls == 0

    action, _, plan = planned()
    with pytest.raises(Refusal) as digest:
        apply(action, plan, mutator, confirmed_action_digest=digest_json({"wrong": 1}))
    assert digest.value.code == POSTGRES_ACTION_DIGEST_MISMATCH
    assert mutator.execute_calls == 0


def test_apply_requires_separate_client_and_principal() -> None:
    action, observer, plan = planned()

    with pytest.raises(Refusal) as same_client:
        apply(action, plan, observer)
    assert same_client.value.code == POSTGRES_OBSERVER_MUTATOR_NOT_SEPARATE

    observer_principal = FakeClient("rc_cp01_observer", can_alter=True)
    with pytest.raises(Refusal) as same_principal:
        apply(action, plan, observer_principal)
    assert same_principal.value.code == POSTGRES_OBSERVER_MUTATOR_NOT_SEPARATE


def test_apply_refuses_permission_and_schema_drift_before_sql() -> None:
    action, _, plan = planned()
    denied = FakeClient("rc_cp01_unprivileged", can_alter=False)
    with pytest.raises(Refusal) as permission:
        apply(action, plan, denied)
    assert permission.value.code == POSTGRES_MUTATION_PERMISSION_DENIED
    assert denied.execute_calls == 0

    drifted = FakeClient("rc_cp01_mutator", can_alter=True)
    drifted.current = normalize_observation(
        raw_observation(principal="rc_cp01_mutator", can_alter=True, extra_column=True),
        TARGET,
    )
    with pytest.raises(Refusal) as drift:
        apply(action, plan, drifted)
    assert drift.value.code == POSTGRES_SCHEMA_FINGERPRINT_DRIFT
    assert drifted.execute_calls == 0


def test_clean_commit_and_replay_are_classified() -> None:
    action, observer, plan = planned()
    mutator = FakeClient("rc_cp01_mutator", can_alter=True)
    observer.current = mutator.current
    mutator.mirror = observer

    result = apply(action, plan, mutator)

    assert result["outcome"] == PostgresActionOutcome.COMMITTED
    assert result["legacy_column_present"] is False
    assert result["replacement_column_preserved"] is True
    with pytest.raises(Refusal) as replay:
        apply(action, plan, mutator, attempt_id="attempt-2")
    assert replay.value.code == POSTGRES_ACTION_REPLAYED
    assert mutator.execute_calls == 1


def test_transport_loss_is_resolved_by_observation_without_retry() -> None:
    action, observer, plan = planned()
    before_loss = FakeClient("rc_cp01_mutator", can_alter=True, behavior="loss_before")
    observer.current = before_loss.current
    not_committed = apply(action, plan, before_loss)
    assert not_committed["outcome"] == PostgresActionOutcome.NOT_COMMITTED
    assert not_committed["destructive_statements_attempted"] == 0
    assert before_loss.execute_calls == 1

    after_loss = FakeClient("rc_cp01_mutator", can_alter=True, behavior="loss_after")
    observer.current = after_loss.current
    after_loss.mirror = observer
    committed = apply(action, plan, after_loss, attempt_id="attempt-2")

    assert committed["outcome"] == PostgresActionOutcome.COMMITTED
    assert committed["recovery"] == "resolved_by_native_schema_reread_without_retry"
    assert after_loss.execute_calls == 1


def test_unknown_attempt_refuses_blind_retry() -> None:
    action, observer, plan = planned()
    mutator = FakeClient("rc_cp01_mutator", can_alter=True, behavior="loss_after")
    observer.behavior = "observer_unavailable"

    unknown = apply(action, plan, mutator)
    assert unknown["outcome"] == PostgresActionOutcome.OUTCOME_UNKNOWN

    with pytest.raises(Refusal) as retry:
        apply(action, plan, mutator, prior_attempt=unknown)
    assert retry.value.code == POSTGRES_OUTCOME_UNKNOWN
    assert mutator.execute_calls == 1


def test_generated_sql_quotes_identifiers_and_never_uses_cascade() -> None:
    _, _, plan = planned()
    sql = drop_sql(plan, 5)

    assert 'ALTER TABLE "retirement_lab"."orders" DROP COLUMN "legacy_status"' in sql
    assert " CASCADE" not in sql.upper()
    assert quote_identifier('odd"name') == '"odd""name"'

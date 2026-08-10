"""Secret-safe configuration for the bounded PostgreSQL producer action."""

from __future__ import annotations

import ipaddress
import os
from collections.abc import Mapping
from dataclasses import dataclass

from retirement_conductor.canonical import digest_json
from retirement_conductor.errors import Refusal

POSTGRES_CONFIGURATION_INCOMPLETE = "POSTGRES_CONFIGURATION_INCOMPLETE"
POSTGRES_ENDPOINT_NOT_LOOPBACK = "POSTGRES_ENDPOINT_NOT_LOOPBACK"


@dataclass(frozen=True, order=True)
class PostgresTarget:
    """The only native tuple that the action can address."""

    database: str
    schema: str
    table: str
    legacy_column: str
    replacement_column: str

    def as_dict(self) -> dict[str, str]:
        return {
            "database": self.database,
            "schema": self.schema,
            "table": self.table,
            "legacy_column": self.legacy_column,
            "replacement_column": self.replacement_column,
        }

    @classmethod
    def parse(cls, value: str) -> PostgresTarget:
        parts = tuple(part.strip() for part in value.split("/"))
        if len(parts) != 5 or any(not part for part in parts):
            raise Refusal(
                POSTGRES_CONFIGURATION_INCOMPLETE,
                (
                    "POSTGRES_PRODUCER_ALLOWED_TARGET must be "
                    "database/schema/table/legacy-column/replacement-column."
                ),
            )
        return cls(*parts)


@dataclass(frozen=True)
class PostgresConnectionSettings:
    """One principal's connection material, kept out of public summaries."""

    host: str
    port: int
    database: str
    username: str
    password: str
    connect_timeout_seconds: int
    lock_timeout_seconds: int


@dataclass(frozen=True)
class PostgresProducerSettings:
    """Runtime scope for one exact disposable producer action."""

    host: str
    port: int
    database: str
    observer_username: str
    observer_password: str
    mutation_username: str
    mutation_password: str
    allow_apply: bool
    allowed_targets: tuple[PostgresTarget, ...]
    connect_timeout_seconds: int = 5
    lock_timeout_seconds: int = 5

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
        *,
        require_mutation_credential: bool = True,
    ) -> PostgresProducerSettings:
        values = os.environ if environment is None else environment
        host = values.get("POSTGRES_PRODUCER_HOST", "").strip()
        database = values.get("POSTGRES_PRODUCER_DATABASE", "").strip()
        observer_username = values.get("POSTGRES_PRODUCER_OBSERVER_USER", "").strip()
        observer_password = values.get("POSTGRES_PRODUCER_OBSERVER_PASSWORD", "")
        mutation_username = values.get("POSTGRES_PRODUCER_MUTATION_USER", "").strip()
        mutation_password = values.get("POSTGRES_PRODUCER_MUTATION_PASSWORD", "")
        required_values = (
            host,
            database,
            observer_username,
            observer_password,
            mutation_username,
        )
        if not all(required_values) or (
            require_mutation_credential and not mutation_password
        ):
            raise Refusal(
                POSTGRES_CONFIGURATION_INCOMPLETE,
                (
                    "PostgreSQL endpoint, database, observer credential, and "
                    "mutation principal are required; the separately privileged "
                    "execution process must also supply the mutation credential."
                ),
            )
        if not host_is_loopback(host):
            raise Refusal(
                POSTGRES_ENDPOINT_NOT_LOOPBACK,
                "The CP-01 producer action is confined to a loopback endpoint.",
            )
        port = _bounded_integer(values, "POSTGRES_PRODUCER_PORT", 1, 65535)
        connect_timeout = _bounded_integer(
            values,
            "POSTGRES_PRODUCER_CONNECT_TIMEOUT_SECONDS",
            1,
            30,
            default=5,
        )
        lock_timeout = _bounded_integer(
            values,
            "POSTGRES_PRODUCER_LOCK_TIMEOUT_SECONDS",
            1,
            30,
            default=5,
        )
        allow_apply_text = (
            values.get("POSTGRES_PRODUCER_ALLOW_APPLY", "false").strip().lower()
        )
        if allow_apply_text not in {"true", "false"}:
            raise Refusal(
                POSTGRES_CONFIGURATION_INCOMPLETE,
                "POSTGRES_PRODUCER_ALLOW_APPLY must be true or false.",
            )
        target_text = values.get("POSTGRES_PRODUCER_ALLOWED_TARGET", "").strip()
        targets = () if not target_text else (PostgresTarget.parse(target_text),)
        if targets and targets[0].database != database:
            raise Refusal(
                POSTGRES_CONFIGURATION_INCOMPLETE,
                "The allowlisted target must use the configured database.",
            )
        return cls(
            host=host,
            port=port,
            database=database,
            observer_username=observer_username,
            observer_password=observer_password,
            mutation_username=mutation_username,
            mutation_password=mutation_password,
            allow_apply=allow_apply_text == "true",
            allowed_targets=targets,
            connect_timeout_seconds=connect_timeout,
            lock_timeout_seconds=lock_timeout,
        )

    def observer_connection(self) -> PostgresConnectionSettings:
        return self._connection(self.observer_username, self.observer_password)

    def mutation_connection(self) -> PostgresConnectionSettings:
        return self._connection(self.mutation_username, self.mutation_password)

    def allowlist_digest(self) -> str:
        return digest_json(
            {
                "endpoint_identity": self.endpoint_identity(),
                "database": self.database,
                "allowed_targets": [
                    target.as_dict() for target in self.allowed_targets
                ],
                "observer_principal": self.observer_username,
                "mutation_principal": self.mutation_username,
            }
        )

    def endpoint_identity(self) -> str:
        return digest_json(
            {"host": self.host, "port": self.port, "database": self.database}
        )

    def safe_summary(self) -> dict[str, object]:
        return {
            "scope": "loopback disposable PostgreSQL",
            "endpoint_identity": self.endpoint_identity(),
            "database": self.database,
            "credential_references_present": {
                "observer": bool(self.observer_username and self.observer_password),
                "mutation": bool(self.mutation_username and self.mutation_password),
            },
            "configured_principals": {
                "observer": self.observer_username,
                "mutation": self.mutation_username,
            },
            "allow_apply": self.allow_apply,
            "allowed_targets": [target.as_dict() for target in self.allowed_targets],
            "allowlist_configuration_digest": self.allowlist_digest(),
            "connect_timeout_seconds": self.connect_timeout_seconds,
            "lock_timeout_seconds": self.lock_timeout_seconds,
        }

    def _connection(self, username: str, password: str) -> PostgresConnectionSettings:
        return PostgresConnectionSettings(
            host=self.host,
            port=self.port,
            database=self.database,
            username=username,
            password=password,
            connect_timeout_seconds=self.connect_timeout_seconds,
            lock_timeout_seconds=self.lock_timeout_seconds,
        )


def host_is_loopback(host: str) -> bool:
    normalized = host.strip().lower().rstrip(".")
    if normalized == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def _bounded_integer(
    values: Mapping[str, str],
    name: str,
    minimum: int,
    maximum: int,
    *,
    default: int | None = None,
) -> int:
    raw = values.get(name, "" if default is None else str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise Refusal(
            POSTGRES_CONFIGURATION_INCOMPLETE,
            f"{name} must be an integer.",
        ) from exc
    if value < minimum or value > maximum:
        raise Refusal(
            POSTGRES_CONFIGURATION_INCOMPLETE,
            f"{name} must be between {minimum} and {maximum}.",
        )
    return value

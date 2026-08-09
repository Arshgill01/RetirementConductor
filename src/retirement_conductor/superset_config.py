"""Secret-safe configuration for one bounded Apache Superset executor."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

from retirement_conductor.canonical import digest_json
from retirement_conductor.errors import Refusal
from retirement_conductor.vocabulary import RefusalCode


@dataclass(frozen=True)
class SupersetSettings:
    """Runtime coordinates and capabilities for one disposable Superset."""

    base_url: str
    username: str
    password: str
    provider: str
    principal: str
    version: str
    allow_apply: bool
    allowed_dataset_ids: tuple[int, ...]
    timeout_seconds: int

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
    ) -> SupersetSettings:
        values = os.environ if environment is None else environment
        base_url = values.get("SUPERSET_URL", "").strip().rstrip("/")
        username = values.get("SUPERSET_USERNAME", "").strip()
        password = values.get("SUPERSET_PASSWORD", "")
        provider = values.get("SUPERSET_PROVIDER", "db").strip()
        principal = values.get(
            "SUPERSET_PRINCIPAL", "local-disposable-operator"
        ).strip()
        version = values.get("SUPERSET_VERSION", "").strip()
        if not all((base_url, username, password, provider, principal, version)):
            raise Refusal(
                RefusalCode.RUNTIME_CONFIGURATION_INCOMPLETE,
                (
                    "Superset URL, credential references, principal, and version "
                    "are required."
                ),
            )
        if not base_url.startswith(("http://127.0.0.1:", "http://localhost:")):
            raise Refusal(
                RefusalCode.RUNTIME_CONFIGURATION_INCOMPLETE,
                (
                    "The initial Superset executor is confined to a loopback "
                    "disposable instance."
                ),
            )
        allow_text = values.get("SUPERSET_ALLOW_APPLY", "false").strip().lower()
        if allow_text not in {"true", "false"}:
            raise Refusal(
                RefusalCode.SPEC_SCHEMA_INVALID,
                "SUPERSET_ALLOW_APPLY must be true or false.",
            )
        timeout_text = values.get("SUPERSET_TIMEOUT_SECONDS", "30").strip()
        try:
            timeout = int(timeout_text)
        except ValueError as exc:
            raise Refusal(
                RefusalCode.SPEC_SCHEMA_INVALID,
                "SUPERSET_TIMEOUT_SECONDS must be an integer.",
            ) from exc
        if timeout < 1 or timeout > 120:
            raise Refusal(
                RefusalCode.SPEC_SCHEMA_INVALID,
                "SUPERSET_TIMEOUT_SECONDS must be between 1 and 120.",
            )
        ids_text = values.get("SUPERSET_ALLOWED_DATASET_IDS", "").strip()
        try:
            ids = tuple(
                sorted(
                    {int(item.strip()) for item in ids_text.split(",") if item.strip()}
                )
            )
        except ValueError as exc:
            raise Refusal(
                RefusalCode.SPEC_SCHEMA_INVALID,
                "SUPERSET_ALLOWED_DATASET_IDS must contain comma-separated integers.",
            ) from exc
        if any(value < 1 for value in ids):
            raise Refusal(
                RefusalCode.SPEC_SCHEMA_INVALID,
                "Superset allowlisted dataset IDs must be positive.",
            )
        return cls(
            base_url=base_url,
            username=username,
            password=password,
            provider=provider,
            principal=principal,
            version=version,
            allow_apply=allow_text == "true",
            allowed_dataset_ids=ids,
            timeout_seconds=timeout,
        )

    def safe_summary(self) -> dict[str, object]:
        """Return configuration evidence without credential values."""

        return {
            "endpoint_identity": digest_json(self.base_url),
            "authentication_mode": "database login to JWT bearer plus CSRF",
            "credential_references_present": bool(self.username and self.password),
            "provider": self.provider,
            "principal": self.principal,
            "version": self.version,
            "allow_apply": self.allow_apply,
            "allowed_dataset_ids": list(self.allowed_dataset_ids),
            "timeout_seconds": self.timeout_seconds,
            "scope": "loopback disposable Superset",
        }

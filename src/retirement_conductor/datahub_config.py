"""Secret-safe configuration for the DataHub evidence boundary."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit

from retirement_conductor.errors import Refusal
from retirement_conductor.vocabulary import RefusalCode


@dataclass(frozen=True)
class DataHubSettings:
    """Resolved non-secret settings plus an in-memory optional bearer token."""

    gms_url: str
    mcp_url: str
    token: str | None
    token_reference: str
    principal: str
    environment: str
    page_size: int
    timeout_seconds: float

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
    ) -> DataHubSettings:
        values = os.environ if environment is None else environment
        gms_url = _safe_endpoint(
            values.get("DATAHUB_GMS_URL", ""),
            "DATAHUB_GMS_URL",
        )
        if not gms_url:
            raise Refusal(
                RefusalCode.SOURCE_DATAHUB_UNAVAILABLE,
                "DATAHUB_GMS_URL must identify the disposable DataHub GMS endpoint.",
                {"required_reference": "DATAHUB_GMS_URL"},
            )
        token_reference = values.get(
            "DATAHUB_GMS_TOKEN_REFERENCE", "DATAHUB_GMS_TOKEN"
        ).strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", token_reference):
            raise Refusal(
                RefusalCode.SPEC_SCHEMA_INVALID,
                "The DataHub token reference must be an environment variable name.",
            )
        page_size = _positive_integer(
            values.get("DATAHUB_PAGE_SIZE", "10"), "page size"
        )
        timeout = _positive_float(
            values.get("DATAHUB_TIMEOUT_SECONDS", "30"), "timeout"
        )
        return cls(
            gms_url=gms_url,
            mcp_url=_safe_endpoint(
                values.get(
                    "DATAHUB_MCP_URL",
                    "http://127.0.0.1:8000/mcp",
                ),
                "DATAHUB_MCP_URL",
            ),
            token=values.get(token_reference) or None,
            token_reference=token_reference,
            principal=values.get(
                "DATAHUB_PRINCIPAL", "anonymous-disposable-core"
            ).strip(),
            environment=values.get("DATAHUB_ENVIRONMENT", "PROD").strip(),
            page_size=page_size,
            timeout_seconds=timeout,
        )

    def safe_summary(self) -> dict[str, object]:
        """Return configuration metadata that can be retained without a secret."""

        return {
            "gms_url": self.gms_url,
            "mcp_url": self.mcp_url,
            "token_reference": self.token_reference,
            "token_present": self.token is not None,
            "principal": self.principal,
            "environment": self.environment,
            "page_size": self.page_size,
            "timeout_seconds": self.timeout_seconds,
        }


def _safe_endpoint(value: str, variable: str) -> str:
    endpoint = value.strip().rstrip("/")
    if not endpoint:
        return ""
    parsed = urlsplit(endpoint)
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise Refusal(
            RefusalCode.SPEC_SCHEMA_INVALID,
            f"{variable} must be an HTTP endpoint without credentials or a query.",
            {"variable": variable},
        )
    return endpoint


def _positive_integer(value: str, label: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise Refusal(
            RefusalCode.SPEC_SCHEMA_INVALID,
            f"The DataHub {label} must be an integer.",
        ) from exc
    if parsed < 1:
        raise Refusal(
            RefusalCode.SPEC_SCHEMA_INVALID,
            f"The DataHub {label} must be positive.",
        )
    return parsed


def _positive_float(value: str, label: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise Refusal(
            RefusalCode.SPEC_SCHEMA_INVALID,
            f"The DataHub {label} must be numeric.",
        ) from exc
    if parsed <= 0:
        raise Refusal(
            RefusalCode.SPEC_SCHEMA_INVALID,
            f"The DataHub {label} must be positive.",
        )
    return parsed

"""Secret-safe configuration for one bounded Looker saved-content operation."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from retirement_conductor.canonical import digest_json
from retirement_conductor.errors import Refusal
from retirement_conductor.vocabulary import EvidenceMode, RefusalCode

_LOOK_TARGET = re.compile(r"^look:([1-9][0-9]*)$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


@dataclass(frozen=True)
class LookerSettings:
    """Exact native identity, credentials, and safety limits for one saved Look."""

    base_url: str
    client_id: str = field(repr=False)
    client_secret: str = field(repr=False)
    platform_instance: str
    project_id: str
    model_id: str
    explore_id: str
    folder_id: str
    content_target: str
    legacy_reference: str
    replacement_reference: str
    datahub_urn: str
    graph_snapshot_digest: str
    mode: EvidenceMode = EvidenceMode.LIVE
    allow_apply: bool = False
    verify_tls: bool = True
    page_size: int = 100
    max_pages: int = 100
    max_retries: int = 2
    timeout_seconds: float = 30.0
    query_limit: int = 100

    def __post_init__(self) -> None:
        parsed = urlsplit(self.base_url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise Refusal(
                RefusalCode.SPEC_SCHEMA_INVALID,
                "The Looker base URL must be an absolute HTTP(S) origin without "
                "credentials, query, or fragment.",
            )
        if self.mode == EvidenceMode.LIVE and (
            parsed.scheme != "https" or not self.verify_tls
        ):
            raise Refusal(
                RefusalCode.SOURCE_LOOKER_UNAVAILABLE,
                "Live Looker evidence requires HTTPS with TLS verification enabled.",
            )
        if not _LOOK_TARGET.fullmatch(self.content_target):
            raise Refusal(
                RefusalCode.SCOPE_TARGET_NOT_ALLOWED,
                "Looker scope must contain exactly one numeric look:<id> target.",
                {"required_format": "look:<numeric-id>"},
            )
        required = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "platform_instance": self.platform_instance,
            "project_id": self.project_id,
            "model_id": self.model_id,
            "explore_id": self.explore_id,
            "folder_id": self.folder_id,
            "legacy_reference": self.legacy_reference,
            "replacement_reference": self.replacement_reference,
            "datahub_urn": self.datahub_urn,
        }
        missing = sorted(key for key, value in required.items() if not value.strip())
        if missing:
            raise Refusal(
                RefusalCode.SPEC_SCHEMA_INVALID,
                "Required Looker identity configuration is missing.",
                {"missing_settings": missing},
            )
        if self.legacy_reference == self.replacement_reference:
            raise Refusal(
                RefusalCode.SPEC_IDENTICAL_FIELDS,
                "The Looker replacement reference must differ from the legacy "
                "reference.",
            )
        if "." not in self.legacy_reference or "." not in self.replacement_reference:
            raise Refusal(
                RefusalCode.SPEC_SCHEMA_INVALID,
                "Looker field references must use view.field identity.",
            )
        if not self.datahub_urn.startswith("urn:li:"):
            raise Refusal(
                RefusalCode.IDENTITY_NOT_FOUND,
                "LOOKER_DATAHUB_URN must identify one exact DataHub entity.",
            )
        if not _DIGEST.fullmatch(self.graph_snapshot_digest):
            raise Refusal(
                RefusalCode.INTEGRITY_DIGEST_MISMATCH,
                "LOOKER_GRAPH_SNAPSHOT_DIGEST must be a canonical SHA-256 digest.",
            )
        _bounded_integer("page_size", self.page_size, minimum=1, maximum=500)
        _bounded_integer("max_pages", self.max_pages, minimum=1, maximum=1000)
        _bounded_integer("max_retries", self.max_retries, minimum=0, maximum=5)
        _bounded_integer("query_limit", self.query_limit, minimum=1, maximum=500)
        if not 0.1 <= self.timeout_seconds <= 120:
            raise Refusal(
                RefusalCode.SPEC_SCHEMA_INVALID,
                "The Looker timeout must be between 0.1 and 120 seconds.",
            )

    @property
    def look_id(self) -> str:
        match = _LOOK_TARGET.fullmatch(self.content_target)
        if match is None:  # pragma: no cover - guarded by __post_init__
            raise AssertionError("validated Look target did not parse")
        return match.group(1)

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
    ) -> LookerSettings:
        values = os.environ if environment is None else environment
        base_url = _aliased_value(
            values,
            "LOOKER_BASE_URL",
            "LOOKERSDK_BASE_URL",
        )
        client_id = _aliased_value(
            values,
            "LOOKER_CLIENT_ID",
            "LOOKERSDK_CLIENT_ID",
        )
        client_secret = _aliased_value(
            values,
            "LOOKER_CLIENT_SECRET",
            "LOOKERSDK_CLIENT_SECRET",
        )
        mode_text = values.get("LOOKER_MODE", EvidenceMode.LIVE).strip().lower()
        try:
            mode = EvidenceMode(mode_text)
        except ValueError as exc:
            raise Refusal(
                RefusalCode.SPEC_SCHEMA_INVALID,
                "LOOKER_MODE must be live, fixture, replay, or analysis.",
            ) from exc
        allow_apply = _boolean(values, "LOOKER_ALLOW_APPLY", default=False)
        verify_tls = _aliased_boolean(
            values,
            "LOOKER_VERIFY_TLS",
            "LOOKERSDK_VERIFY_SSL",
            default=True,
        )
        return cls(
            base_url=base_url,
            client_id=client_id,
            client_secret=client_secret,
            platform_instance=values.get("LOOKER_PLATFORM_INSTANCE", "").strip(),
            project_id=values.get("LOOKER_PROJECT_ID", "").strip(),
            model_id=values.get("LOOKER_MODEL_ID", "").strip(),
            explore_id=values.get("LOOKER_EXPLORE_ID", "").strip(),
            folder_id=values.get("LOOKER_FOLDER_ID", "").strip(),
            content_target=values.get("LOOKER_CONTENT_TARGET", "").strip(),
            legacy_reference=values.get("LOOKER_LEGACY_REFERENCE", "").strip(),
            replacement_reference=values.get(
                "LOOKER_REPLACEMENT_REFERENCE",
                "",
            ).strip(),
            datahub_urn=values.get("LOOKER_DATAHUB_URN", "").strip(),
            graph_snapshot_digest=values.get(
                "LOOKER_GRAPH_SNAPSHOT_DIGEST",
                "",
            ).strip(),
            mode=mode,
            allow_apply=allow_apply,
            verify_tls=verify_tls,
            page_size=_integer(values, "LOOKER_PAGE_SIZE", 100),
            max_pages=_integer(values, "LOOKER_MAX_PAGES", 100),
            max_retries=_integer(values, "LOOKER_MAX_RETRIES", 2),
            timeout_seconds=_number(values, "LOOKER_TIMEOUT_SECONDS", 30.0),
            query_limit=_integer(values, "LOOKER_QUERY_LIMIT", 100),
        )

    def safe_summary(self) -> dict[str, object]:
        """Return only non-secret, bounded configuration evidence."""

        parsed = urlsplit(self.base_url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        return {
            "base_url_identity": digest_json(origin),
            "platform_instance": self.platform_instance,
            "project_id": self.project_id,
            "model_id": self.model_id,
            "explore_id": self.explore_id,
            "folder_id": self.folder_id,
            "content_target": self.content_target,
            "datahub_urn": self.datahub_urn,
            "graph_snapshot_digest": self.graph_snapshot_digest,
            "mode": self.mode,
            "allow_apply": self.allow_apply,
            "verify_tls": self.verify_tls,
            "page_size": self.page_size,
            "max_pages": self.max_pages,
            "max_retries": self.max_retries,
            "timeout_seconds": self.timeout_seconds,
            "query_limit": self.query_limit,
            "credentials_configured": bool(self.client_id and self.client_secret),
        }


def _aliased_value(
    values: Mapping[str, str],
    primary: str,
    alias: str,
) -> str:
    candidates = {
        value.strip()
        for key in (primary, alias)
        if (value := values.get(key, "")).strip()
    }
    if len(candidates) > 1:
        raise Refusal(
            RefusalCode.SPEC_SCHEMA_INVALID,
            "Conflicting Looker environment aliases are configured.",
            {"settings": sorted([primary, alias])},
        )
    return next(iter(candidates), "")


def _boolean(
    values: Mapping[str, str],
    name: str,
    *,
    default: bool,
) -> bool:
    text = values.get(name, str(default)).strip().lower()
    if text not in {"true", "false"}:
        raise Refusal(
            RefusalCode.SPEC_SCHEMA_INVALID,
            f"{name} must be true or false.",
        )
    return text == "true"


def _aliased_boolean(
    values: Mapping[str, str],
    primary: str,
    alias: str,
    *,
    default: bool,
) -> bool:
    present = {
        key: values[key].strip().lower()
        for key in (primary, alias)
        if values.get(key, "").strip()
    }
    if any(value not in {"true", "false"} for value in present.values()):
        raise Refusal(
            RefusalCode.SPEC_SCHEMA_INVALID,
            "Looker TLS verification settings must be true or false.",
        )
    if len(set(present.values())) > 1:
        raise Refusal(
            RefusalCode.SPEC_SCHEMA_INVALID,
            "Conflicting Looker TLS environment aliases are configured.",
            {"settings": sorted(present)},
        )
    if not present:
        return default
    return next(iter(present.values())) == "true"


def _integer(values: Mapping[str, str], name: str, default: int) -> int:
    try:
        return int(values.get(name, str(default)))
    except ValueError as exc:
        raise Refusal(
            RefusalCode.SPEC_SCHEMA_INVALID,
            f"{name} must be an integer.",
        ) from exc


def _number(values: Mapping[str, str], name: str, default: float) -> float:
    try:
        return float(values.get(name, str(default)))
    except ValueError as exc:
        raise Refusal(
            RefusalCode.SPEC_SCHEMA_INVALID,
            f"{name} must be a number.",
        ) from exc


def _bounded_integer(
    name: str,
    value: int,
    *,
    minimum: int,
    maximum: int,
) -> None:
    if not minimum <= value <= maximum:
        raise Refusal(
            RefusalCode.SPEC_SCHEMA_INVALID,
            f"Looker {name} must be between {minimum} and {maximum}.",
        )

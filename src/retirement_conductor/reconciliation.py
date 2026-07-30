"""Fresh equivalent reconciliation across DataHub and the Git/dbt source."""

from __future__ import annotations

import time
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any

from retirement_conductor.canonical import (
    digest_json,
    verify_digest,
    with_digest,
)
from retirement_conductor.clock import parse_timestamp
from retirement_conductor.datahub import DataHubBoundary, utc_now
from retirement_conductor.errors import Refusal
from retirement_conductor.git_dbt import (
    GitDbtAdapter,
    load_object,
    merge_repository_reconciliation_evidence,
    write_versioned_artifact,
)
from retirement_conductor.looker import (
    LookerAdapter,
    merge_looker_reconciliation_evidence,
)
from retirement_conductor.store import CampaignStore
from retirement_conductor.vocabulary import ConsumerDisposition, RefusalCode

_LOOKER_INVALIDATION_CODES = {
    RefusalCode.AUTH_APPROVAL_WRONG_PLAN,
    RefusalCode.EVIDENCE_MODE_NOT_LIVE,
    RefusalCode.EVIDENCE_RECEIPT_EXPIRED,
    RefusalCode.EVIDENCE_RECEIPT_MODE_NOT_LIVE,
    RefusalCode.IDENTITY_NATIVE_OBJECT_RECREATED,
    RefusalCode.INTEGRITY_DIGEST_MISMATCH,
    RefusalCode.RECONCILIATION_SCOPE_MISMATCH,
    RefusalCode.SCOPE_RECEIPT_TARGET_MISMATCH,
    RefusalCode.SOURCE_FINGERPRINT_MISMATCH,
    RefusalCode.SOURCE_LOOKER_PERMISSION_DENIED,
    RefusalCode.SOURCE_LOOKER_UNAVAILABLE,
    RefusalCode.SOURCE_RECEIPT_VERSION_MISMATCH,
    RefusalCode.SPEC_REPLACEMENT_INCOMPATIBLE,
    RefusalCode.VALIDATION_RECEIPT_FAILED,
    RefusalCode.VALIDATION_RECEIPT_INCONCLUSIVE,
}


class ReconciliationWorkflow:
    """Reread equivalent live sources and deterministically compare membership."""

    def __init__(
        self,
        *,
        store: CampaignStore,
        boundary: DataHubBoundary,
        git_dbt: GitDbtAdapter,
        looker: LookerAdapter | None = None,
        artifact_directory: Path,
        refresh_receipt: Path,
        indexing_timeout_seconds: float = 30,
    ) -> None:
        self.store = store
        self.boundary = boundary
        self.git_dbt = git_dbt
        self.looker = looker
        self.artifact_directory = artifact_directory
        self.refresh_receipt = refresh_receipt
        self.indexing_timeout_seconds = indexing_timeout_seconds

    def reconcile(self, campaign_id: str) -> dict[str, Any]:
        specification = self.store.specification(campaign_id)
        projection = self.store.projection(campaign_id)
        baseline_envelope = projection.evidence_envelope
        if baseline_envelope is None:
            raise Refusal(
                RefusalCode.EVIDENCE_REQUIRED_SOURCE_INCOMPLETE,
                "Reconciliation requires a recorded baseline envelope.",
            )
        verify_digest(dict(baseline_envelope), "envelope_digest")
        refresh = load_object(self.refresh_receipt)
        verify_digest(refresh, "refresh_digest")
        if refresh.get("mode") != "live" or str(refresh.get("gms_url", "")).rstrip(
            "/"
        ) != self.boundary.settings.gms_url.rstrip("/"):
            raise Refusal(
                RefusalCode.INTEGRITY_DIGEST_MISMATCH,
                "The refresh receipt is not bound to this live DataHub source.",
            )
        snapshot, indexing = self._wait_for_indexing(
            specification,
            campaign_id=campaign_id,
            refresh=refresh,
        )
        plan = load_object(self._git_root(campaign_id) / "plan.json")
        apply_record = load_object(self._git_root(campaign_id) / "apply.json")
        receipt = load_object(self._git_root(campaign_id) / "receipt.json")
        consumer_id = str(plan["consumer_id"])
        baseline_git = _source(
            baseline_envelope, f"git:{self.git_dbt.settings.repository_id}"
        )
        invalidated_receipts: list[dict[str, Any]] = []
        git_observation: dict[str, Any] | None = None
        try:
            git_observation = self.git_dbt.reconcile_source(
                specification,
                plan,
                apply_record,
                receipt,
                datahub_resolution=snapshot["resolution"],
                artifact_root=self._reconciliation_root(campaign_id),
            )
            envelope = merge_repository_reconciliation_evidence(
                snapshot["evidence_envelope"],
                git_observation,
                baseline_source=baseline_git,
            )
        except Refusal as exc:
            if exc.code not in {
                RefusalCode.SOURCE_GIT_BRANCH_MOVED,
                RefusalCode.SOURCE_GIT_FILE_CHANGED,
                RefusalCode.SOURCE_GIT_UNAVAILABLE,
                RefusalCode.SCOPE_RECEIPT_TARGET_MISMATCH,
                RefusalCode.SPEC_REPLACEMENT_INCOMPATIBLE,
            }:
                raise
            invalidation = with_digest(
                {
                    "schema_version": "1.0.0",
                    "captured_at": utc_now(),
                    "consumer_id": consumer_id,
                    "receipt_digest": receipt["receipt_digest"],
                    "refusal_code": str(exc.code),
                    "reason": exc.message,
                },
                "invalidation_digest",
            )
            write_versioned_artifact(
                self._reconciliation_root(campaign_id),
                "receipt-invalidation",
                invalidation,
            )
            invalidated_receipts.append(invalidation)
            current = projection.consumers.get(consumer_id)
            if (
                current is not None
                and ConsumerDisposition(str(current["disposition"]))
                == ConsumerDisposition.VALIDATED
            ):
                self.store.change_consumer_disposition(
                    campaign_id,
                    consumer_id,
                    ConsumerDisposition.STALE,
                    occurred_at=str(invalidation["captured_at"]),
                    idempotency_key=(
                        "reconciliation-stale-"
                        f"{str(invalidation['invalidation_digest'])[-16:]}"
                    ),
                )
            envelope = _merge_unavailable_git_source(
                snapshot["evidence_envelope"],
                baseline_git,
                invalidation,
            )

        looker_observation: dict[str, Any] | None = None
        replacement_snapshot: dict[str, Any] | None = None
        baseline_looker_sources = [
            dict(source)
            for source in baseline_envelope["sources"]
            if str(source["id"]).startswith("looker:")
        ]
        if self.looker is None and baseline_looker_sources:
            raise Refusal(
                RefusalCode.SOURCE_LOOKER_UNAVAILABLE,
                "Reconciliation requires the configured Looker adapter for the "
                "recorded native source.",
            )
        if self.looker is not None:
            if len(baseline_looker_sources) != 1:
                raise Refusal(
                    RefusalCode.EVIDENCE_REQUIRED_SOURCE_INCOMPLETE,
                    "Reconciliation requires one recorded Looker source.",
                    {"source_count": len(baseline_looker_sources)},
                )
            replacement_snapshot = self.boundary.inventory(
                _replacement_field_specification(specification),
                artifact_root=(
                    self._reconciliation_root(campaign_id)
                    / "datahub"
                    / "replacement-field"
                ),
            )
            _require_refresh_visible(
                replacement_snapshot,
                refresh=refresh,
            )
            looker_plan = _load_looker_artifact(
                self._looker_root(campaign_id) / "plan.json"
            )
            looker_apply = _load_looker_artifact(
                self._looker_root(campaign_id) / "apply.json"
            )
            looker_receipt = _load_looker_artifact(
                self._looker_root(campaign_id) / "receipt.json"
            )
            looker_consumer_id = str(looker_plan["consumer_id"])
            baseline_looker = baseline_looker_sources[0]
            try:
                looker_observation = self.looker.reconcile_source(
                    looker_plan,
                    looker_apply,
                    looker_receipt,
                    legacy_snapshot=snapshot,
                    replacement_snapshot=replacement_snapshot,
                    require_live=True,
                )
                write_versioned_artifact(
                    self._reconciliation_root(campaign_id),
                    "looker-source-reconciliation",
                    looker_observation,
                )
                envelope = merge_looker_reconciliation_evidence(
                    envelope,
                    looker_observation,
                    baseline_source=baseline_looker,
                )
            except Refusal as exc:
                if exc.code not in _LOOKER_INVALIDATION_CODES:
                    raise
                invalidation = with_digest(
                    {
                        "schema_version": "1.0.0",
                        "captured_at": utc_now(),
                        "consumer_id": looker_consumer_id,
                        "receipt_digest": looker_receipt["receipt_digest"],
                        "refusal_code": str(exc.code),
                        "reason": exc.message,
                    },
                    "invalidation_digest",
                )
                write_versioned_artifact(
                    self._reconciliation_root(campaign_id),
                    "looker-receipt-invalidation",
                    invalidation,
                )
                invalidated_receipts.append(invalidation)
                current = self.store.projection(campaign_id).consumers.get(
                    looker_consumer_id
                )
                if (
                    current is not None
                    and ConsumerDisposition(str(current["disposition"]))
                    == ConsumerDisposition.VALIDATED
                ):
                    self.store.change_consumer_disposition(
                        campaign_id,
                        looker_consumer_id,
                        ConsumerDisposition.STALE,
                        occurred_at=str(invalidation["captured_at"]),
                        idempotency_key=(
                            "looker-reconciliation-stale-"
                            f"{str(invalidation['invalidation_digest'])[-16:]}"
                        ),
                    )
                envelope = _merge_unavailable_looker_source(
                    envelope,
                    baseline_looker,
                    invalidation,
                )

        baseline_scope = scope_signature(baseline_envelope)
        current_scope = scope_signature(envelope)
        if current_scope != baseline_scope:
            raise Refusal(
                RefusalCode.RECONCILIATION_SCOPE_MISMATCH,
                "Baseline and reconciliation evidence scopes are not equivalent.",
                {
                    "baseline_scope_digest": digest_json(baseline_scope),
                    "current_scope_digest": digest_json(current_scope),
                },
            )
        current_ids = sorted(str(consumer["id"]) for consumer in snapshot["consumers"])
        inventory_ids = sorted(projection.inventory_consumer_ids)
        added = sorted(set(current_ids) - set(inventory_ids))
        disappeared = sorted(set(inventory_ids) - set(current_ids))
        unchanged = sorted(set(inventory_ids) & set(current_ids))
        comparison = with_digest(
            {
                "schema_version": "1.0.0",
                "campaign_id": campaign_id,
                "mode": "live",
                "captured_at": envelope["captured_at"],
                "baseline": {
                    "snapshot_digest": projection.snapshot_digests[-1],
                    "envelope_digest": baseline_envelope["envelope_digest"],
                    "scope_digest": digest_json(baseline_scope),
                    "consumer_count": len(inventory_ids),
                },
                "current": {
                    "datahub_snapshot_digest": snapshot["snapshot_digest"],
                    "git_reconciliation_digest": (
                        git_observation["reconciliation_digest"]
                        if git_observation is not None
                        else None
                    ),
                    "looker_reconciliation_digest": (
                        looker_observation["reconciliation_digest"]
                        if looker_observation is not None
                        else None
                    ),
                    "replacement_datahub_snapshot_digest": (
                        replacement_snapshot["snapshot_digest"]
                        if replacement_snapshot is not None
                        else None
                    ),
                    "envelope_digest": envelope["envelope_digest"],
                    "scope_digest": digest_json(current_scope),
                    "consumer_count": len(current_ids),
                },
                "membership": {
                    "added": added,
                    "disappeared_without_closure": disappeared,
                    "unchanged": unchanged,
                },
                "invalidated_receipts": invalidated_receipts,
                "refresh": indexing,
                "limitations": [
                    (
                        "A disappeared graph edge is retained as unresolved "
                        "unless separate native closure already exists."
                    ),
                    (
                        "Equivalent scope proves comparison consistency, not "
                        "visibility outside the declared evidence envelope."
                    ),
                    (
                        "Looker graph closure is claimed only when native "
                        "validation and an exact replacement field edge agree."
                    ),
                ],
            },
            "comparison_digest",
        )
        write_versioned_artifact(
            self._reconciliation_root(campaign_id),
            "comparison",
            comparison,
        )
        occurred_at = str(comparison["captured_at"])
        manifest = self.store.record_reconciliation(
            campaign_id,
            evidence_envelope=envelope,
            consumers=[
                {
                    "id": consumer["id"],
                    "disposition": consumer["disposition"],
                    "receipt_digest": None,
                }
                for consumer in snapshot["consumers"]
            ],
            comparison={
                "comparison_digest": comparison["comparison_digest"],
                "added": added,
                "disappeared": disappeared,
                "invalidated_receipt_digests": [
                    item["invalidation_digest"] for item in invalidated_receipts
                ],
            },
            snapshot_digest=str(comparison["comparison_digest"]),
            occurred_at=occurred_at,
            idempotency_key=(
                f"reconciliation-{str(comparison['comparison_digest'])[-16:]}"
            ),
        )
        manifest = self.store.evaluate(
            campaign_id,
            occurred_at=occurred_at,
            idempotency_key=(
                f"reconciliation-evaluation-"
                f"{str(comparison['comparison_digest'])[-16:]}"
            ),
        )
        return {
            "result": "RECONCILED",
            "comparison": comparison,
            "manifest": manifest,
        }

    def _wait_for_indexing(
        self,
        specification: Mapping[str, Any],
        *,
        campaign_id: str,
        refresh: Mapping[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        expected_targets = set(
            str(item)
            for item in (refresh.get("target_urns") or [refresh.get("target_urn")])
            if item
        )
        started = time.monotonic()
        attempts = 0
        last_observed: str | None = None
        while time.monotonic() - started <= self.indexing_timeout_seconds:
            attempts += 1
            snapshot = self.boundary.inventory(
                specification,
                artifact_root=(
                    self._reconciliation_root(campaign_id)
                    / "datahub"
                    / f"attempt-{attempts:02d}"
                ),
            )
            source = _source(snapshot["evidence_envelope"], "datahub")
            last_observed = source["freshness"]["source_updated_at"]
            resolved = str(snapshot["resolution"]["dataset"]["urn"])
            if (
                resolved in expected_targets
                and isinstance(last_observed, str)
                and parse_timestamp(last_observed)
                >= parse_timestamp(str(refresh["source_updated_at"]))
            ):
                return snapshot, {
                    "status": "OBSERVED",
                    "refresh_run_id": refresh["ingestion_run_id"],
                    "refresh_source_updated_at": refresh["source_updated_at"],
                    "observed_source_updated_at": last_observed,
                    "attempts": attempts,
                    "timeout_seconds": self.indexing_timeout_seconds,
                    "duration_ms": round((time.monotonic() - started) * 1000),
                }
            if time.monotonic() - started < self.indexing_timeout_seconds:
                time.sleep(0.5)
        raise Refusal(
            RefusalCode.RECONCILIATION_REFRESH_TIMEOUT,
            "DataHub did not expose the requested refresh within the bound.",
            {
                "attempts": attempts,
                "last_observed_source_updated_at": last_observed,
                "timeout_seconds": self.indexing_timeout_seconds,
            },
        )

    def _git_root(self, campaign_id: str) -> Path:
        return self.artifact_directory / campaign_id / "git-dbt"

    def _looker_root(self, campaign_id: str) -> Path:
        return self.artifact_directory / campaign_id / "looker"

    def _reconciliation_root(self, campaign_id: str) -> Path:
        return self.artifact_directory / campaign_id / "reconciliation"


def scope_signature(envelope: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return only declared identity, permission, and traversal scope."""

    return sorted(
        [
            {
                "id": source["id"],
                "required": source["required"],
                "identity": source["identity"],
                "scope": {
                    "direction": source["scope"]["direction"],
                    "max_hops": source["scope"]["max_hops"],
                    "filters": list(source["scope"]["filters"]),
                },
                "permissions": dict(source["permissions"]),
            }
            for source in envelope["sources"]
        ],
        key=lambda source: str(source["id"]),
    )


def _source(envelope: Mapping[str, Any], source_id: str) -> dict[str, Any]:
    matches = [
        dict(source) for source in envelope["sources"] if source["id"] == source_id
    ]
    if len(matches) != 1:
        raise Refusal(
            RefusalCode.EVIDENCE_REQUIRED_SOURCE_INCOMPLETE,
            "The evidence envelope did not contain one required source identity.",
            {"source_id": source_id, "match_count": len(matches)},
        )
    return matches[0]


def _merge_unavailable_git_source(
    evidence_envelope: Mapping[str, Any],
    baseline_source: Mapping[str, Any],
    invalidation: Mapping[str, Any],
) -> dict[str, Any]:
    return _merge_unavailable_native_source(
        evidence_envelope,
        baseline_source,
        invalidation,
        limitation=(
            "The accepted Git/dbt receipt was invalidated during reconciliation"
        ),
    )


def _merge_unavailable_looker_source(
    evidence_envelope: Mapping[str, Any],
    baseline_source: Mapping[str, Any],
    invalidation: Mapping[str, Any],
) -> dict[str, Any]:
    return _merge_unavailable_native_source(
        evidence_envelope,
        baseline_source,
        invalidation,
        limitation=(
            "The accepted Looker receipt was invalidated during reconciliation"
        ),
    )


def _merge_unavailable_native_source(
    evidence_envelope: Mapping[str, Any],
    baseline_source: Mapping[str, Any],
    invalidation: Mapping[str, Any],
    *,
    limitation: str,
) -> dict[str, Any]:
    verify_digest(dict(evidence_envelope), "envelope_digest")
    sources = [
        dict(source)
        for source in evidence_envelope["sources"]
        if source["id"] != baseline_source["id"]
    ]
    sources.append(
        {
            **dict(baseline_source),
            "status": "STALE",
            "freshness": {
                **dict(baseline_source["freshness"]),
                "observed_at": invalidation["captured_at"],
            },
            "limitations": sorted(
                {
                    *baseline_source["limitations"],
                    limitation,
                }
            ),
            "artifact_ids": sorted(
                {
                    *baseline_source["artifact_ids"],
                    invalidation["invalidation_digest"],
                }
            ),
        }
    )
    return with_digest(
        {
            "schema_version": "1.0.0",
            "captured_at": invalidation["captured_at"],
            "mode": evidence_envelope["mode"],
            "sources": sorted(sources, key=lambda source: str(source["id"])),
        },
        "envelope_digest",
    )


def _replacement_field_specification(
    specification: Mapping[str, Any],
) -> dict[str, Any]:
    value = deepcopy(dict(specification))
    value["target"], value["replacement"] = (
        deepcopy(dict(specification["replacement"])),
        deepcopy(dict(specification["target"])),
    )
    unsigned = {
        key: item for key, item in value.items() if key != "specification_digest"
    }
    value["specification_digest"] = digest_json(unsigned)
    return value


def _load_looker_artifact(path: Path) -> dict[str, Any]:
    try:
        return load_object(path)
    except Refusal as exc:
        if exc.code != RefusalCode.SOURCE_DBT_UNAVAILABLE:
            raise
        raise Refusal(
            RefusalCode.SOURCE_LOOKER_UNAVAILABLE,
            "A required Looker reconciliation artifact could not be read.",
            {"artifact": path.name},
        ) from exc


def _require_refresh_visible(
    snapshot: Mapping[str, Any],
    *,
    refresh: Mapping[str, Any],
) -> None:
    snapshot_value = dict(snapshot)
    verify_digest(snapshot_value, "snapshot_digest")
    envelope = dict(snapshot_value["evidence_envelope"])
    verify_digest(envelope, "envelope_digest")
    source = _source(envelope, "datahub")
    source_updated_at = source["freshness"]["source_updated_at"]
    if not isinstance(source_updated_at, str) or parse_timestamp(
        source_updated_at
    ) < parse_timestamp(str(refresh["source_updated_at"])):
        raise Refusal(
            RefusalCode.RECONCILIATION_REFRESH_TIMEOUT,
            "The replacement-field snapshot did not expose the requested refresh.",
            {
                "observed_source_updated_at": source_updated_at,
                "refresh_source_updated_at": refresh["source_updated_at"],
            },
        )

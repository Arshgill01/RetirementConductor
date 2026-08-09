"""Deterministic one-shot reconciliation and Retirement Lease projection."""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

from retirement_conductor.canonical import (
    digest_json,
    verify_digest,
    with_digest,
    write_json,
)
from retirement_conductor.clock import parse_timestamp
from retirement_conductor.datahub import utc_now
from retirement_conductor.errors import Refusal
from retirement_conductor.events import manifest_from_projection, project_events
from retirement_conductor.schemas import validate_schema
from retirement_conductor.store import CampaignStore
from retirement_conductor.vocabulary import Decision, RefusalCode


class LeaseStatus(StrEnum):
    ISSUED = "ISSUED"
    EXPIRED = "EXPIRED"
    CONSUMED = "CONSUMED"
    INVALIDATED = "INVALIDATED"


class WatchResult(StrEnum):
    UNCHANGED = "UNCHANGED"
    REVERSED = "REVERSED"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"
    FAILED = "FAILED"


WATCH_EXIT_CODES = {
    WatchResult.UNCHANGED: 0,
    WatchResult.REVERSED: 3,
    WatchResult.PARTIAL: 4,
    WatchResult.UNAVAILABLE: 5,
    WatchResult.FAILED: 6,
}


class ReconciliationOperation(Protocol):
    def reconcile(self, campaign_id: str) -> dict[str, Any]: ...


class PublicationOperation(Protocol):
    def publish(self, campaign_id: str) -> dict[str, Any]: ...

    def verify(self, campaign_id: str) -> dict[str, Any]: ...


FaultInjector = Callable[[str], None]


def retirement_lease_status(
    store: CampaignStore,
    campaign_id: str,
    *,
    observed_at: str | None = None,
) -> dict[str, Any]:
    """Project one lease from the canonical manifest and producer gate ledger."""

    plans = store.gate_plans(campaign_id)
    if not plans:
        raise Refusal(
            RefusalCode.GATE_PLAN_MISSING,
            "The campaign has no issued Retirement Lease.",
        )
    plan = max(
        plans,
        key=lambda item: (
            parse_timestamp(str(item["prepared_at"])),
            str(item["plan_digest"]),
        ),
    )
    plan_digest = str(plan["plan_digest"])
    manifest = store.materialize(campaign_id)
    attempts = [
        entry
        for entry in store.gate_attempts(campaign_id)
        if entry["attempt"].get("plan_digest") == plan_digest
        and entry["status"] in {"INTENT_RECORDED", "EXECUTED", "OUTCOME_UNKNOWN"}
    ]
    now = observed_at or utc_now()
    parse_timestamp(now)
    if attempts:
        status = LeaseStatus.CONSUMED
    elif manifest["manifest_digest"] != plan["manifest"]["digest"]:
        status = LeaseStatus.INVALIDATED
    elif parse_timestamp(now) >= parse_timestamp(str(plan["expires_at"])):
        status = LeaseStatus.EXPIRED
    else:
        status = LeaseStatus.ISSUED
    return {
        "schema_version": "1.0.0",
        "campaign_id": campaign_id,
        "status": status,
        "observed_at": now,
        "plan_digest": plan_digest,
        "prepared_at": plan["prepared_at"],
        "expires_at": plan["expires_at"],
        "issued_manifest_digest": plan["manifest"]["digest"],
        "current_manifest_digest": manifest["manifest_digest"],
        "evidence_envelope_digest": plan["manifest"].get("evidence_envelope_digest"),
        "publication_content_digest": plan["manifest"].get(
            "publication_content_digest"
        ),
        "writer_id": plan["writer_id"],
        "trusted_run": dict(plan["trusted_run"]),
        "producer_source": dict(plan.get("producer_source") or {}),
        "action": dict(plan["action"]),
        "consuming_attempts": [entry["status"] for entry in attempts],
    }


class WatchWorkflow:
    """Observe one issued lease through canonical reconciliation and publication."""

    def __init__(
        self,
        *,
        store: CampaignStore,
        reconciliation: ReconciliationOperation,
        publication: PublicationOperation,
        artifact_directory: Path,
        publication_timeout_seconds: float = 30,
        publication_poll_seconds: float = 0.5,
        clock: Callable[[], str] = utc_now,
        fault_injector: FaultInjector | None = None,
    ) -> None:
        self.store = store
        self.reconciliation = reconciliation
        self.publication = publication
        self.artifact_directory = artifact_directory
        self.publication_timeout_seconds = publication_timeout_seconds
        self.publication_poll_seconds = publication_poll_seconds
        self.clock = clock
        self.fault_injector = fault_injector

    def run_once(self, campaign_id: str) -> dict[str, Any]:
        """Run one cron-safe observation and return a schema-validated receipt."""

        with self.store.operation_lock():
            plans = self.store.gate_plans(campaign_id)
            if not plans:
                raise Refusal(
                    RefusalCode.GATE_PLAN_MISSING,
                    "Continuous reconciliation requires an issued Retirement Lease.",
                )
            plan = max(
                plans,
                key=lambda item: (
                    parse_timestamp(str(item["prepared_at"])),
                    str(item["plan_digest"]),
                ),
            )
            operation_id = _operation_id(campaign_id, str(plan["plan_digest"]))
            prior_receipt = self._load_receipt(campaign_id, operation_id)
            if prior_receipt is not None and not _retryable_receipt(prior_receipt):
                return prior_receipt

            events = self.store.events(campaign_id)
            watch_index = _watch_event_index(events, operation_id)
            if watch_index is None:
                lease_before = retirement_lease_status(
                    self.store,
                    campaign_id,
                    observed_at=self.clock(),
                )
                if lease_before["status"] != LeaseStatus.ISSUED:
                    raise _lease_refusal(str(lease_before["status"]))
                before = self.store.materialize(campaign_id)
                observed_at = str(lease_before["observed_at"])
                self.store.record_watch_observation(
                    campaign_id,
                    {
                        "schema_version": "1.0.0",
                        "operation_id": operation_id,
                        "producer_plan_digest": plan["plan_digest"],
                        "before_manifest_digest": before["manifest_digest"],
                    },
                    occurred_at=observed_at,
                    idempotency_key=operation_id,
                )
                self._inject("after_observation")
                events = self.store.events(campaign_id)
                watch_index = _watch_event_index(events, operation_id)
                if watch_index is None:
                    raise Refusal(
                        RefusalCode.INTEGRITY_EVENT_SEQUENCE_INVALID,
                        "The durable watch observation could not be recovered.",
                    )
            else:
                observed_at = str(events[watch_index]["occurred_at"])
                before = manifest_from_projection(project_events(events[:watch_index]))
                lease_before = {
                    "status": LeaseStatus.ISSUED,
                    "plan_digest": plan["plan_digest"],
                }

            failure_phase = "RECONCILIATION"
            comparison_digest: str | None = None
            try:
                events = self.store.events(campaign_id)
                reconciliation_index = _event_index_after(
                    events, watch_index, "RECONCILIATION_RECORDED"
                )
                policy_index = _event_index_after(
                    events, watch_index, "POLICY_EVALUATED"
                )
                if reconciliation_index is None:
                    reconciled = self.reconciliation.reconcile(campaign_id)
                    comparison = reconciled.get("comparison")
                    if isinstance(comparison, Mapping):
                        comparison_digest = str(comparison.get("comparison_digest"))
                else:
                    projection = self.store.projection(campaign_id)
                    if projection.reconciliations:
                        comparison_digest = str(
                            projection.reconciliations[-1].get("comparison_digest")
                        )
                    if policy_index is None:
                        manifest = self.store.materialize(campaign_id)
                        self.store.evaluate(
                            campaign_id,
                            occurred_at=self.clock(),
                            idempotency_key=(
                                "reconciliation-evaluation-"
                                f"{str(manifest['manifest_digest'])[-16:]}"
                            ),
                        )
                failure_phase = "PUBLICATION"
                self._inject("after_reconciliation")
                events = self.store.events(campaign_id)
                policy_index = _event_index_after(
                    events, watch_index, "POLICY_EVALUATED"
                )
                if policy_index is None:
                    raise Refusal(
                        RefusalCode.INTEGRITY_EVENT_SEQUENCE_INVALID,
                        "The watch operation has no canonical policy evaluation.",
                    )
                publication_index = _event_index_after(
                    events, policy_index, "PUBLICATION_RECORDED"
                )
                if publication_index is None:
                    self.publication.publish(campaign_id)
                self._inject("after_publication")

                failure_phase = "VERIFICATION"
                events = self.store.events(campaign_id)
                publication_index = _event_index_after(
                    events, policy_index, "PUBLICATION_RECORDED"
                )
                verification_index = (
                    _event_index_after(
                        events, publication_index, "PUBLICATION_VERIFIED"
                    )
                    if publication_index is not None
                    else None
                )
                if verification_index is None:
                    self._verify_with_polling(campaign_id)
                self._inject("after_verification")
            except Refusal as exc:
                result = _result_for_refusal(exc)
                return self._failure_receipt(
                    campaign_id=campaign_id,
                    operation_id=operation_id,
                    observed_at=observed_at,
                    before=before,
                    lease_before=lease_before,
                    comparison_digest=comparison_digest,
                    phase=failure_phase,
                    refusal=exc,
                    result=result,
                )
            except Exception as exc:
                return self._failure_receipt(
                    campaign_id=campaign_id,
                    operation_id=operation_id,
                    observed_at=observed_at,
                    before=before,
                    lease_before=lease_before,
                    comparison_digest=comparison_digest,
                    phase=failure_phase,
                    refusal=None,
                    result=WatchResult.FAILED,
                    error_type=type(exc).__name__,
                )

            after = self.store.materialize(campaign_id)
            result = _successful_result(after)
            receipt = self._build_receipt(
                campaign_id=campaign_id,
                operation_id=operation_id,
                observed_at=observed_at,
                result=result,
                before=before,
                after=after,
                comparison_digest=comparison_digest,
                lease_before=str(lease_before["status"]),
                failure=None,
            )
            self._write_receipt(receipt)
            return receipt

    def _verify_with_polling(self, campaign_id: str) -> None:
        started = time.monotonic()
        while True:
            try:
                self.publication.verify(campaign_id)
                return
            except Refusal as exc:
                if exc.code not in {
                    RefusalCode.EVIDENCE_PUBLICATION_MISMATCH,
                    RefusalCode.SOURCE_DATAHUB_UNAVAILABLE,
                }:
                    raise
                if time.monotonic() - started >= self.publication_timeout_seconds:
                    raise
                time.sleep(self.publication_poll_seconds)

    def _failure_receipt(
        self,
        *,
        campaign_id: str,
        operation_id: str,
        observed_at: str,
        before: Mapping[str, Any],
        lease_before: Mapping[str, Any],
        comparison_digest: str | None,
        phase: str,
        refusal: Refusal | None,
        result: WatchResult,
        error_type: str | None = None,
    ) -> dict[str, Any]:
        after = self.store.materialize(campaign_id)
        failure = {
            "phase": phase,
            "refusal_code": str(refusal.code) if refusal is not None else None,
            "message": (
                refusal.message
                if refusal is not None
                else f"The watch operation failed with {error_type or 'an error'}."
            ),
        }
        receipt = self._build_receipt(
            campaign_id=campaign_id,
            operation_id=operation_id,
            observed_at=observed_at,
            result=result,
            before=before,
            after=after,
            comparison_digest=comparison_digest,
            lease_before=str(lease_before["status"]),
            failure=failure,
        )
        self._write_receipt(receipt)
        return receipt

    def _build_receipt(
        self,
        *,
        campaign_id: str,
        operation_id: str,
        observed_at: str,
        result: WatchResult,
        before: Mapping[str, Any],
        after: Mapping[str, Any],
        comparison_digest: str | None,
        lease_before: str,
        failure: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        lease_after = retirement_lease_status(
            self.store,
            campaign_id,
            observed_at=self.clock(),
        )
        publication = after.get("publication")
        receipt = with_digest(
            {
                "schema_version": "1.0.0",
                "campaign_id": campaign_id,
                "operation_id": operation_id,
                "observed_at": observed_at,
                "completed_at": self.clock(),
                "result": result,
                "before": _campaign_state(before),
                "after": _campaign_state(after),
                "comparison_digest": comparison_digest,
                "source_versions": _source_versions(after),
                "publication": {
                    "content_digest": (
                        publication.get("content_digest")
                        if isinstance(publication, Mapping)
                        else None
                    ),
                    "readback_verified": bool(
                        isinstance(publication, Mapping)
                        and publication.get("readback_verified") is True
                    ),
                },
                "lease": {
                    "plan_digest": lease_after["plan_digest"],
                    "status_before": lease_before,
                    "status_after": lease_after["status"],
                },
                "failure": dict(failure) if failure is not None else None,
                "limitations": _limitations(after, result),
            },
            "receipt_digest",
        )
        validate_schema(
            "watch-receipt",
            receipt,
            refusal_code=RefusalCode.INTEGRITY_DIGEST_MISMATCH,
        )
        return receipt

    def _receipt_root(self, campaign_id: str, operation_id: str) -> Path:
        return self.artifact_directory / campaign_id / "watch" / operation_id

    def _load_receipt(
        self, campaign_id: str, operation_id: str
    ) -> dict[str, Any] | None:
        path = self._receipt_root(campaign_id, operation_id) / "receipt.json"
        if not path.is_file():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise Refusal(
                RefusalCode.INTEGRITY_DIGEST_MISMATCH,
                "The retained watch receipt could not be read.",
            ) from exc
        if not isinstance(value, dict):
            raise Refusal(
                RefusalCode.INTEGRITY_DIGEST_MISMATCH,
                "The retained watch receipt is not an object.",
            )
        verify_digest(value, "receipt_digest")
        validate_schema(
            "watch-receipt",
            value,
            refusal_code=RefusalCode.INTEGRITY_DIGEST_MISMATCH,
        )
        return value

    def _write_receipt(self, receipt: Mapping[str, Any]) -> None:
        root = self._receipt_root(
            str(receipt["campaign_id"]), str(receipt["operation_id"])
        )
        write_json(root / "receipt.json", receipt)
        identity = str(receipt["receipt_digest"]).removeprefix("sha256:")[:16]
        write_json(root / f"receipt-{identity}.json", receipt)

    def _inject(self, boundary: str) -> None:
        if self.fault_injector is not None:
            self.fault_injector(boundary)


def _operation_id(campaign_id: str, plan_digest: str) -> str:
    identity = digest_json([campaign_id, plan_digest]).removeprefix("sha256:")[:24]
    return f"watch-{identity}"


def _watch_event_index(events: list[dict[str, Any]], operation_id: str) -> int | None:
    for index, event in enumerate(events):
        if (
            event["event_type"] == "WATCH_OBSERVATION_RECORDED"
            and event["payload"].get("operation_id") == operation_id
        ):
            return index
    return None


def _event_index_after(
    events: list[dict[str, Any]], start: int | None, event_type: str
) -> int | None:
    offset = 0 if start is None else start + 1
    for index in range(offset, len(events)):
        if events[index]["event_type"] == event_type:
            return index
    return None


def _campaign_state(manifest: Mapping[str, Any]) -> dict[str, Any]:
    envelope = manifest.get("evidence_envelope")
    return {
        "manifest_digest": manifest["manifest_digest"],
        "decision": manifest["decision"],
        "evidence_envelope_digest": (
            envelope.get("envelope_digest") if isinstance(envelope, Mapping) else None
        ),
    }


def _source_versions(manifest: Mapping[str, Any]) -> list[dict[str, str]]:
    envelope = manifest.get("evidence_envelope")
    sources = envelope.get("sources") if isinstance(envelope, Mapping) else []
    return sorted(
        [
            {
                "id": str(source.get("id") or "unknown"),
                "status": str(source.get("status") or "UNKNOWN"),
                "source_version": str(
                    source.get("source_version") or "source version not reported"
                ),
            }
            for source in sources or []
            if isinstance(source, Mapping)
        ],
        key=lambda source: source["id"],
    )


def _limitations(manifest: Mapping[str, Any], result: WatchResult) -> list[str]:
    envelope = manifest.get("evidence_envelope")
    sources = envelope.get("sources") if isinstance(envelope, Mapping) else []
    observed = {
        str(limitation)
        for source in sources or []
        if isinstance(source, Mapping)
        for limitation in source.get("limitations") or []
    }
    observed.add(
        "The result is bounded by the recorded evidence envelope and is not "
        "universal safety."
    )
    if result in {WatchResult.UNAVAILABLE, WatchResult.FAILED}:
        observed.add(
            "The observation did not establish fresh equivalent evidence; the "
            "prior lease remains invalidated."
        )
    return sorted(observed)


def _successful_result(manifest: Mapping[str, Any]) -> WatchResult:
    statuses = {source["status"] for source in _source_versions(manifest)}
    if "UNAVAILABLE" in statuses:
        return WatchResult.UNAVAILABLE
    if statuses & {"PARTIAL", "UNKNOWN", "STALE"}:
        return WatchResult.PARTIAL
    if manifest["decision"] != Decision.READY_TO_RETIRE:
        return WatchResult.REVERSED
    return WatchResult.UNCHANGED


def _result_for_refusal(refusal: Refusal) -> WatchResult:
    if refusal.code in {
        RefusalCode.SOURCE_DATAHUB_UNAVAILABLE,
        RefusalCode.SOURCE_DATAHUB_PERMISSION_DENIED,
        RefusalCode.RECONCILIATION_REFRESH_TIMEOUT,
    }:
        return WatchResult.UNAVAILABLE
    if refusal.code in {
        RefusalCode.EVIDENCE_PAGINATION_FAILED,
        RefusalCode.EVIDENCE_REQUIRED_SOURCE_INCOMPLETE,
    }:
        return WatchResult.PARTIAL
    return WatchResult.FAILED


def _retryable_receipt(receipt: Mapping[str, Any]) -> bool:
    failure = receipt.get("failure")
    return bool(
        receipt.get("result") == WatchResult.FAILED
        and isinstance(failure, Mapping)
        and failure.get("phase") in {"PUBLICATION", "VERIFICATION"}
    )


def _lease_refusal(status: str) -> Refusal:
    codes = {
        LeaseStatus.EXPIRED: RefusalCode.GATE_PLAN_EXPIRED,
        LeaseStatus.CONSUMED: RefusalCode.GATE_PLAN_REPLAYED,
        LeaseStatus.INVALIDATED: RefusalCode.GATE_STATE_DRIFT,
    }
    return Refusal(
        codes.get(LeaseStatus(status), RefusalCode.GATE_PLAN_INVALID),
        f"The Retirement Lease is {status.lower()} and cannot be observed again.",
        {"lease_status": status},
    )

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import pytest

from retirement_conductor.canonical import (
    digest_bytes,
    digest_json,
    with_digest,
    write_json,
)
from retirement_conductor.datahub import DataHubBoundary
from retirement_conductor.errors import Refusal
from retirement_conductor.publication import CampaignPublicationWorkflow
from retirement_conductor.store import CampaignStore
from retirement_conductor.watch import (
    LeaseStatus,
    WatchResult,
    WatchWorkflow,
    retirement_lease_status,
)
from tests.integration.test_gate import (
    CAMPAIGN_ID,
    CONSUMER_ID,
    _context,
    _plan,
    _ready_store,
    _workflow,
)


class ReconciliationStub:
    def __init__(
        self,
        store: CampaignStore,
        *,
        added_consumer: bool = False,
        source_status: str = "COMPLETE",
        refusal: Refusal | None = None,
    ) -> None:
        self.store = store
        self.added_consumer = added_consumer
        self.source_status = source_status
        self.refusal = refusal
        self.calls = 0

    def reconcile(self, campaign_id: str) -> dict[str, Any]:
        self.calls += 1
        if self.refusal is not None:
            raise self.refusal
        projection = self.store.projection(campaign_id)
        envelope = deepcopy(projection.evidence_envelope)
        assert envelope is not None
        envelope["captured_at"] = "2026-01-01T12:02:00Z"
        envelope["sources"][0]["status"] = self.source_status
        envelope = with_digest(envelope, "envelope_digest")
        consumers = [
            {
                "id": CONSUMER_ID,
                "disposition": "IDENTIFIED",
                "receipt_digest": None,
            }
        ]
        current_ids = [CONSUMER_ID]
        added: list[str] = []
        if self.added_consumer:
            consumers.append(
                {
                    "id": "late-datahub-consumer",
                    "disposition": "OPAQUE",
                    "receipt_digest": None,
                }
            )
            current_ids.append("late-datahub-consumer")
            added.append("late-datahub-consumer")
        comparison = with_digest(
            {
                "schema_version": "1.0.0",
                "campaign_id": campaign_id,
                "membership": {
                    "added": added,
                    "disappeared_without_closure": [],
                    "unchanged": [CONSUMER_ID],
                },
            },
            "comparison_digest",
        )
        self.store.record_reconciliation(
            campaign_id,
            evidence_envelope=envelope,
            consumers=consumers,
            comparison={
                "comparison_digest": comparison["comparison_digest"],
                "added": added,
                "disappeared": [],
                "invalidated_receipt_digests": [],
            },
            snapshot_digest=str(comparison["comparison_digest"]),
            occurred_at="2026-01-01T12:02:00Z",
            idempotency_key=f"watch-reconciliation-{comparison['comparison_digest']}",
        )
        manifest = self.store.evaluate(
            campaign_id,
            occurred_at="2026-01-01T12:03:00Z",
            idempotency_key=f"watch-evaluation-{comparison['comparison_digest']}",
        )
        return {
            "result": "RECONCILED",
            "comparison": comparison,
            "manifest": manifest,
        }


class PublicationStub:
    def __init__(self, store: CampaignStore) -> None:
        self.store = store
        self.publish_calls = 0
        self.verify_calls = 0

    def publish(self, campaign_id: str) -> dict[str, Any]:
        self.publish_calls += 1
        manifest = self.store.materialize(campaign_id)
        content_digest = digest_json(
            [campaign_id, manifest["manifest_digest"], "watch-publication"]
        )
        updated = self.store.record_publication(
            campaign_id,
            {
                "logical_key": f"campaign/{campaign_id}",
                "urn": "urn:li:document:gate-test",
                "content_digest": content_digest,
                "published_manifest_digest": manifest["manifest_digest"],
                "lifecycle_digest_before": f"sha256:{'4' * 64}",
                "readback_verified": False,
            },
            occurred_at="2026-01-01T12:04:00Z",
            idempotency_key=f"watch-publication-{content_digest}",
        )
        return {"result": "PUBLISHED", "manifest": updated}

    def verify(self, campaign_id: str) -> dict[str, Any]:
        self.verify_calls += 1
        manifest = self.store.materialize(campaign_id)
        publication = manifest["publication"]
        assert isinstance(publication, dict)
        updated = self.store.verify_publication(
            campaign_id,
            {
                "urn": publication["urn"],
                "content_digest": publication["content_digest"],
                "lifecycle_digest_after": publication["lifecycle_digest_before"],
                "readback_artifact_id": f"sha256:{'6' * 64}",
                "verified_at": "2026-01-01T12:05:00Z",
            },
            occurred_at="2026-01-01T12:05:00Z",
            idempotency_key=f"watch-verification-{publication['content_digest']}",
        )
        return {"result": "VERIFIED", "manifest": updated}


class AlreadyWrittenBoundaryStub:
    def __init__(self) -> None:
        self.save_calls = 0
        self.verify_calls = 0

    def resolve_field_pair(self, *_args: Any) -> dict[str, Any]:
        return {"dataset": {"urn": "urn:li:dataset:watch-test"}}

    def lifecycle(self, _target_urn: str) -> dict[str, Any]:
        return {"status": "ACTIVE"}

    def verify_summary(self, **arguments: Any) -> dict[str, Any]:
        self.verify_calls += 1
        return {
            "readback_artifact_id": f"sha256:{'7' * 64}",
            "search_artifact_id": f"sha256:{'8' * 64}",
            "lifecycle_artifact_id": f"sha256:{'9' * 64}",
            "lifecycle_digest_after": digest_json({"status": "ACTIVE"}),
            "content_digest": digest_bytes(str(arguments["expected_content"]).encode()),
        }

    def save_summary(self, **_arguments: Any) -> dict[str, Any]:
        self.save_calls += 1
        raise AssertionError("an already visible write must not be repeated")


def watcher(
    store: CampaignStore,
    tmp_path: Path,
    reconciliation: ReconciliationStub,
    publication: PublicationStub,
    *,
    fault: str | None = None,
) -> WatchWorkflow:
    def inject(boundary: str) -> None:
        if boundary == fault:
            raise RuntimeError("simulated interruption")

    return WatchWorkflow(
        store=store,
        reconciliation=reconciliation,
        publication=publication,
        artifact_directory=tmp_path / "artifacts",
        publication_timeout_seconds=0,
        publication_poll_seconds=0,
        clock=lambda: "2026-01-01T12:01:00Z",
        fault_injector=inject,
    )


def test_watch_reverses_ready_campaign_and_invalidates_preserved_lease(
    tmp_path: Path,
) -> None:
    with _ready_store(tmp_path) as store:
        plan = _plan(store, tmp_path)
        plan_path = tmp_path / "preserved-plan.json"
        write_json(plan_path, plan)
        original_bytes = plan_path.read_bytes()
        reconciliation = ReconciliationStub(store, added_consumer=True)
        publication = PublicationStub(store)

        receipt = watcher(store, tmp_path, reconciliation, publication).run_once(
            CAMPAIGN_ID
        )

        assert receipt["result"] == WatchResult.REVERSED
        assert receipt["before"]["decision"] == "READY_TO_RETIRE"
        assert receipt["after"]["decision"] == "UNSAFE"
        assert (
            receipt["before"]["manifest_digest"] != receipt["after"]["manifest_digest"]
        )
        assert receipt["lease"] == {
            "plan_digest": plan["plan_digest"],
            "status_before": "ISSUED",
            "status_after": "INVALIDATED",
        }
        assert receipt["publication"]["readback_verified"] is True
        assert plan_path.read_bytes() == original_bytes

        gate = _workflow(store, tmp_path)
        with pytest.raises(Refusal, match="GATE_DECISION_NOT_READY"):
            gate.execute(
                CAMPAIGN_ID,
                context=_context(),
                plan_path=plan_path,
                executed_at="2026-01-01T12:06:00Z",
            )
        assert not (tmp_path / "sentinels").exists()


def test_watch_unchanged_result_still_refreshes_and_invalidates_old_lease(
    tmp_path: Path,
) -> None:
    with _ready_store(tmp_path) as store:
        _plan(store, tmp_path)
        reconciliation = ReconciliationStub(store)
        publication = PublicationStub(store)

        receipt = watcher(store, tmp_path, reconciliation, publication).run_once(
            CAMPAIGN_ID
        )

        assert receipt["result"] == WatchResult.UNCHANGED
        assert receipt["after"]["decision"] == "READY_TO_RETIRE"
        assert receipt["lease"]["status_after"] == LeaseStatus.INVALIDATED
        assert reconciliation.calls == 1
        assert publication.publish_calls == 1
        assert publication.verify_calls == 1


def test_partial_and_unavailable_observations_have_distinct_results(
    tmp_path: Path,
) -> None:
    partial_root = tmp_path / "partial"
    with _ready_store(partial_root) as store:
        _plan(store, partial_root)
        receipt = watcher(
            store,
            partial_root,
            ReconciliationStub(store, source_status="PARTIAL"),
            PublicationStub(store),
        ).run_once(CAMPAIGN_ID)
        assert receipt["result"] == WatchResult.PARTIAL
        assert receipt["after"]["decision"] == "BLOCKED"

    unavailable_root = tmp_path / "unavailable"
    with _ready_store(unavailable_root) as store:
        _plan(store, unavailable_root)
        receipt = watcher(
            store,
            unavailable_root,
            ReconciliationStub(
                store,
                refusal=Refusal(
                    "SOURCE_DATAHUB_UNAVAILABLE",
                    "Disposable DataHub was unavailable.",
                ),
            ),
            PublicationStub(store),
        ).run_once(CAMPAIGN_ID)
        assert receipt["result"] == WatchResult.UNAVAILABLE
        assert receipt["failure"]["phase"] == "RECONCILIATION"
        assert receipt["lease"]["status_after"] == LeaseStatus.INVALIDATED


def test_watch_resumes_after_reconciliation_without_duplicate_events(
    tmp_path: Path,
) -> None:
    with _ready_store(tmp_path) as store:
        _plan(store, tmp_path)
        reconciliation = ReconciliationStub(store, added_consumer=True)
        publication = PublicationStub(store)
        interrupted = watcher(
            store,
            tmp_path,
            reconciliation,
            publication,
            fault="after_reconciliation",
        ).run_once(CAMPAIGN_ID)
        assert interrupted["result"] == WatchResult.FAILED
        assert interrupted["failure"]["phase"] == "PUBLICATION"

        completed = watcher(store, tmp_path, reconciliation, publication).run_once(
            CAMPAIGN_ID
        )
        event_types = [event["event_type"] for event in store.events(CAMPAIGN_ID)]
        assert completed["result"] == WatchResult.REVERSED
        assert event_types.count("WATCH_OBSERVATION_RECORDED") == 1
        assert event_types.count("RECONCILIATION_RECORDED") == 2
        assert event_types.count("PUBLICATION_RECORDED") == 2
        assert reconciliation.calls == 1
        assert publication.publish_calls == 1


def test_publication_resume_reads_before_repeating_an_interrupted_write(
    tmp_path: Path,
) -> None:
    with _ready_store(tmp_path) as store:
        _plan(store, tmp_path)
        plan = store.gate_plans(CAMPAIGN_ID)[-1]
        ready = store.materialize(CAMPAIGN_ID)
        store.record_watch_observation(
            CAMPAIGN_ID,
            {
                "schema_version": "1.0.0",
                "operation_id": "watch-222222222222222222222222",
                "producer_plan_digest": plan["plan_digest"],
                "before_manifest_digest": ready["manifest_digest"],
            },
            occurred_at="2026-01-01T12:01:00Z",
            idempotency_key="publication-resume-observation",
        )
        ReconciliationStub(store, added_consumer=True).reconcile(CAMPAIGN_ID)
        boundary = AlreadyWrittenBoundaryStub()
        publication = CampaignPublicationWorkflow(
            store=store,
            boundary=cast(DataHubBoundary, boundary),
            artifact_directory=tmp_path / "artifacts",
        )

        result = publication.publish(
            CAMPAIGN_ID,
            occurred_at="2026-01-01T12:04:00Z",
        )

        assert result["write_resumed_from_readback"] is True
        assert boundary.verify_calls == 1
        assert boundary.save_calls == 0


def test_lease_projection_covers_issued_expired_consumed_and_invalidated(
    tmp_path: Path,
) -> None:
    issued_root = tmp_path / "issued"
    with _ready_store(issued_root) as store:
        plan = _plan(store, issued_root)
        assert (
            retirement_lease_status(
                store, CAMPAIGN_ID, observed_at="2026-01-01T12:01:00Z"
            )["status"]
            == LeaseStatus.ISSUED
        )
        assert (
            retirement_lease_status(
                store, CAMPAIGN_ID, observed_at="2026-01-01T12:10:00Z"
            )["status"]
            == LeaseStatus.EXPIRED
        )
        store.record_watch_observation(
            CAMPAIGN_ID,
            {
                "schema_version": "1.0.0",
                "operation_id": "watch-111111111111111111111111",
                "producer_plan_digest": plan["plan_digest"],
                "before_manifest_digest": plan["manifest"]["digest"],
            },
            occurred_at="2026-01-01T12:02:00Z",
            idempotency_key="invalidate-plan",
        )
        assert (
            retirement_lease_status(
                store, CAMPAIGN_ID, observed_at="2026-01-01T12:03:00Z"
            )["status"]
            == LeaseStatus.INVALIDATED
        )

    consumed_root = tmp_path / "consumed"
    with _ready_store(consumed_root) as store:
        plan = _plan(store, consumed_root)
        intent = store.claim_gate_plan(
            CAMPAIGN_ID,
            manifest_digest=plan["manifest"]["digest"],
            decision="READY_TO_RETIRE",
            plan_digest=plan["plan_digest"],
            trusted_run_id="trusted-run-one",
            recorded_at="2026-01-01T12:02:00Z",
        )
        store.mark_gate_outcome_unknown(
            str(intent["attempt_id"]),
            error_type="OSError",
            observed_at="2026-01-01T12:02:01Z",
        )
        assert (
            retirement_lease_status(
                store, CAMPAIGN_ID, observed_at="2026-01-01T12:03:00Z"
            )["status"]
            == LeaseStatus.CONSUMED
        )


def test_concurrent_watch_refuses_at_existing_single_writer_lock(
    tmp_path: Path,
) -> None:
    store_path = tmp_path / "campaign.sqlite"
    with (
        CampaignStore(store_path, writer_id="writer-one") as first,
        CampaignStore(store_path, writer_id="writer-one") as second,
        first.operation_lock(),
        pytest.raises(Refusal, match="RUNTIME_STORE_LOCKED"),
        second.operation_lock(),
    ):
        pytest.fail("the second writer acquired the campaign lock")

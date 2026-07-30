from __future__ import annotations

import fcntl
import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from retirement_conductor.canonical import digest_json, with_digest
from retirement_conductor.errors import Refusal
from retirement_conductor.events import manifest_from_projection
from retirement_conductor.specification import load_specification
from retirement_conductor.store import CampaignStore

ROOT = Path(__file__).resolve().parents[2]
SPECIFICATION = ROOT / "fixtures/specs/valid.yaml"
CAMPAIGN_ID = "ret-orders-legacy-status"
CONSUMER_ID = "consumer-dbt-order-summary"
PLAN_DIGEST = f"sha256:{'a' * 64}"
SNAPSHOT_ONE = f"sha256:{'1' * 64}"
SNAPSHOT_TWO = f"sha256:{'2' * 64}"
TARGETS = ["models/order_summary.sql"]
NATIVE_IDENTITY = {
    "repository": "analytics",
    "commit": "commit-one",
    "path": TARGETS[0],
}
TRUSTED_NOW = datetime(2026, 1, 1, 11, 30, tzinfo=UTC)


class SimulatedCrash(RuntimeError):
    pass


def fault_at(selected: str) -> Any:
    def inject(boundary: str) -> None:
        if boundary == selected:
            raise SimulatedCrash(boundary)

    return inject


def live_envelope() -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "captured_at": "2026-01-01T11:00:00Z",
        "mode": "live",
        "sources": [
            {
                "id": "datahub",
                "required": True,
                "status": "COMPLETE",
                "source_version": "fixture-live/1",
            }
        ],
    }


def second_specification() -> dict[str, Any]:
    specification = deepcopy(load_specification(SPECIFICATION))
    specification["campaign"] = {
        "id": "ret-orders-second",
        "name": "Second overlapping campaign",
    }
    unsigned = dict(specification)
    unsigned.pop("specification_digest")
    specification["specification_digest"] = digest_json(unsigned)
    return specification


def approval_for(
    store: CampaignStore,
    campaign_id: str,
    *,
    expires_at: str = "2026-01-01T13:00:00Z",
) -> dict[str, Any]:
    projection = store.projection(campaign_id)
    return with_digest(
        {
            "schema_version": "1.0.0",
            "approval_id": f"approval-{campaign_id}",
            "campaign_id": campaign_id,
            "plan_digest": PLAN_DIGEST,
            "source_version": "commit-one",
            "targets": TARGETS,
            "principal": "fixture-operator",
            "scope": ["apply", "validate"],
            "authorization_digest": projection.input_digests["authorization"],
            "authorized_at": "2026-01-01T11:00:00Z",
            "expires_at": expires_at,
        },
        "approval_digest",
    )


def receipt_for(
    campaign_id: str = CAMPAIGN_ID,
    *,
    expires_at: str = "2026-01-01T13:00:00Z",
) -> dict[str, Any]:
    receipt = json.loads(
        (ROOT / "artifacts/public/phase00/receipt.json").read_text(encoding="utf-8")
    )
    receipt["campaign_id"] = campaign_id
    receipt["consumer_id"] = CONSUMER_ID
    receipt["adapter"]["mode"] = "live"
    receipt["apply"]["result"] = "APPLIED"
    receipt["apply"]["actual_targets"] = TARGETS
    receipt["plan"]["digest"] = PLAN_DIGEST
    receipt["source_before"]["version"] = "commit-one"
    receipt["captured_at"] = "2026-01-01T11:20:00Z"
    receipt["expires_at"] = expires_at
    return with_digest(receipt, "receipt_digest")


def create_and_inventory(
    store: CampaignStore,
    specification: dict[str, Any] | None = None,
) -> str:
    selected = specification or load_specification(SPECIFICATION)
    campaign_id = str(selected["campaign"]["id"])
    store.create_campaign(selected, occurred_at="2026-01-01T10:00:00Z")
    store.record_inventory(
        campaign_id,
        evidence_envelope=live_envelope(),
        consumers=[
            {
                "id": CONSUMER_ID,
                "disposition": "IDENTIFIED",
                "receipt_digest": None,
            }
        ],
        snapshot_digest=SNAPSHOT_ONE,
        occurred_at="2026-01-01T10:10:00Z",
    )
    return campaign_id


def propose_and_approve(store: CampaignStore, campaign_id: str) -> None:
    store.change_consumer_disposition(
        campaign_id,
        CONSUMER_ID,
        "CHANGE_PROPOSED",
        occurred_at="2026-01-01T10:20:00Z",
        idempotency_key="propose",
        plan_digest=PLAN_DIGEST,
        source_version="commit-one",
        approved_targets=TARGETS,
    )
    store.record_approval(
        campaign_id,
        approval_for(store, campaign_id),
        plan_digest=PLAN_DIGEST,
        source_version="commit-one",
        targets=TARGETS,
        required_scope=["apply"],
        trusted_now=TRUSTED_NOW,
        occurred_at="2026-01-01T11:00:00Z",
        idempotency_key="approval",
    )


def begin_and_apply(store: CampaignStore, campaign_id: str) -> None:
    store.begin_migration_with_claim(
        campaign_id,
        NATIVE_IDENTITY,
        plan_digest=PLAN_DIGEST,
        source_version="commit-one",
        targets=TARGETS,
        required_scope=["apply"],
        trusted_now=TRUSTED_NOW,
        occurred_at="2026-01-01T11:10:00Z",
    )
    store.change_consumer_disposition(
        campaign_id,
        CONSUMER_ID,
        "APPLIED",
        occurred_at="2026-01-01T11:15:00Z",
        idempotency_key="applied",
    )


def test_schema_migration_and_replay_match_materialized_manifest(
    tmp_path: Path,
) -> None:
    with CampaignStore(tmp_path / "campaign.sqlite", writer_id="writer-one") as store:
        assert store.schema_versions() == [1]
        create_and_inventory(store)

        materialized = store.materialize(CAMPAIGN_ID)
        replayed = manifest_from_projection(store.projection(CAMPAIGN_ID))

        assert materialized == replayed
        assert materialized["manifest_digest"] == replayed["manifest_digest"]


def test_complete_validated_flow_reaches_ready(tmp_path: Path) -> None:
    with CampaignStore(tmp_path / "campaign.sqlite", writer_id="writer-one") as store:
        create_and_inventory(store)
        propose_and_approve(store, CAMPAIGN_ID)
        begin_and_apply(store, CAMPAIGN_ID)
        store.accept_receipt(
            CAMPAIGN_ID,
            CONSUMER_ID,
            receipt_for(),
            trusted_now=TRUSTED_NOW,
            occurred_at="2026-01-01T11:30:00Z",
            idempotency_key="receipt",
        )
        store.record_reconciliation(
            CAMPAIGN_ID,
            evidence_envelope=live_envelope(),
            consumer_ids=[CONSUMER_ID],
            snapshot_digest=SNAPSHOT_TWO,
            occurred_at="2026-01-01T11:40:00Z",
        )
        manifest = store.evaluate(
            CAMPAIGN_ID,
            occurred_at="2026-01-01T11:45:00Z",
        )

        assert manifest["campaign"]["state"] == "READY"
        assert manifest["decision"] == "READY_TO_RETIRE"
        assert len(store.events(CAMPAIGN_ID)) == 10


def test_illegal_transition_and_malformed_receipt_do_not_promote(
    tmp_path: Path,
) -> None:
    with CampaignStore(tmp_path / "campaign.sqlite", writer_id="writer-one") as store:
        store.create_campaign(
            load_specification(SPECIFICATION),
            occurred_at="2026-01-01T10:00:00Z",
        )
        before = len(store.events(CAMPAIGN_ID))
        with pytest.raises(Refusal, match="POLICY_ILLEGAL_CAMPAIGN_TRANSITION"):
            store.append_event(
                CAMPAIGN_ID,
                "MIGRATION_STARTED",
                {},
                occurred_at="2026-01-01T10:01:00Z",
                idempotency_key="illegal",
            )
        assert len(store.events(CAMPAIGN_ID)) == before

        create_and_inventory(store)
        propose_and_approve(store, CAMPAIGN_ID)
        begin_and_apply(store, CAMPAIGN_ID)
        receipt = receipt_for()
        receipt["validation"]["validator"] = "tampered"
        before = len(store.events(CAMPAIGN_ID))
        with pytest.raises(Refusal, match="INTEGRITY_DIGEST_MISMATCH"):
            store.accept_receipt(
                CAMPAIGN_ID,
                CONSUMER_ID,
                receipt,
                trusted_now=TRUSTED_NOW,
                occurred_at="2026-01-01T11:30:00Z",
                idempotency_key="bad-receipt",
            )
        assert len(store.events(CAMPAIGN_ID)) == before
        assert (
            store.projection(CAMPAIGN_ID).consumers[CONSUMER_ID]["disposition"]
            == "APPLIED"
        )


@pytest.mark.parametrize(
    "boundary",
    ["before_event_insert", "after_event_insert", "after_event_commit"],
)
def test_create_resumes_at_every_event_boundary(
    tmp_path: Path,
    boundary: str,
) -> None:
    with CampaignStore(tmp_path / "campaign.sqlite", writer_id="writer-one") as store:
        specification = load_specification(SPECIFICATION)
        with pytest.raises(SimulatedCrash, match=boundary):
            store.create_campaign(
                specification,
                occurred_at="2026-01-01T10:00:00Z",
                fault_injector=fault_at(boundary),
            )
        manifest = store.create_campaign(
            specification,
            occurred_at="2026-01-01T10:00:00Z",
        )

        assert manifest["campaign"]["state"] == "PROPOSED"
        assert len(store.events(CAMPAIGN_ID)) == 1


@pytest.mark.parametrize(
    "boundary",
    ["before_event_insert", "after_event_insert", "after_event_commit"],
)
def test_append_resumes_without_duplicate_event(
    tmp_path: Path,
    boundary: str,
) -> None:
    with CampaignStore(tmp_path / "campaign.sqlite", writer_id="writer-one") as store:
        store.create_campaign(
            load_specification(SPECIFICATION),
            occurred_at="2026-01-01T10:00:00Z",
        )
        with pytest.raises(SimulatedCrash, match=boundary):
            store.record_inventory(
                CAMPAIGN_ID,
                evidence_envelope=live_envelope(),
                consumers=[
                    {
                        "id": CONSUMER_ID,
                        "disposition": "IDENTIFIED",
                        "receipt_digest": None,
                    }
                ],
                snapshot_digest=SNAPSHOT_ONE,
                occurred_at="2026-01-01T10:10:00Z",
                fault_injector=fault_at(boundary),
            )
        manifest = store.record_inventory(
            CAMPAIGN_ID,
            evidence_envelope=live_envelope(),
            consumers=[
                {
                    "id": CONSUMER_ID,
                    "disposition": "IDENTIFIED",
                    "receipt_digest": None,
                }
            ],
            snapshot_digest=SNAPSHOT_ONE,
            occurred_at="2026-01-01T10:10:00Z",
        )

        assert manifest["campaign"]["state"] == "INVENTORIED"
        assert len(store.events(CAMPAIGN_ID)) == 2


def test_idempotency_key_conflict_refuses(tmp_path: Path) -> None:
    with CampaignStore(tmp_path / "campaign.sqlite", writer_id="writer-one") as store:
        create_and_inventory(store)
        with pytest.raises(Refusal, match="INTEGRITY_IDEMPOTENCY_CONFLICT"):
            store.append_event(
                CAMPAIGN_ID,
                "CAMPAIGN_BLOCKED",
                {"reason": "different"},
                occurred_at="2026-01-01T10:11:00Z",
                idempotency_key="inventory",
            )


def test_two_campaigns_cannot_claim_same_native_identity(tmp_path: Path) -> None:
    with CampaignStore(tmp_path / "campaign.sqlite", writer_id="writer-one") as store:
        first = create_and_inventory(store)
        second = create_and_inventory(store, second_specification())
        propose_and_approve(store, first)
        propose_and_approve(store, second)
        store.begin_migration_with_claim(
            first,
            NATIVE_IDENTITY,
            plan_digest=PLAN_DIGEST,
            source_version="commit-one",
            targets=TARGETS,
            required_scope=["apply"],
            trusted_now=TRUSTED_NOW,
            occurred_at="2026-01-01T11:10:00Z",
        )

        with pytest.raises(Refusal, match="SOURCE_CONSUMER_OVERLAP"):
            store.begin_migration_with_claim(
                second,
                NATIVE_IDENTITY,
                plan_digest=PLAN_DIGEST,
                source_version="commit-one",
                targets=TARGETS,
                required_scope=["apply"],
                trusted_now=TRUSTED_NOW,
                occurred_at="2026-01-01T11:10:00Z",
            )


def test_event_and_materialized_corruption_refuse(tmp_path: Path) -> None:
    database = tmp_path / "campaign.sqlite"
    with CampaignStore(database, writer_id="writer-one") as store:
        create_and_inventory(store)
        event = store.events(CAMPAIGN_ID)[-1]
        event["payload"]["snapshot_digest"] = f"sha256:{'9' * 64}"
        with store.connection:
            store.connection.execute(
                "UPDATE campaign_events SET event_json = ? "
                "WHERE campaign_id = ? AND sequence = 2",
                (json.dumps(event), CAMPAIGN_ID),
            )
        with pytest.raises(Refusal, match="INTEGRITY_DIGEST_MISMATCH"):
            store.materialize(CAMPAIGN_ID)

    second_database = tmp_path / "materialized.sqlite"
    with CampaignStore(second_database, writer_id="writer-one") as store:
        create_and_inventory(store)
        row = store.connection.execute(
            "SELECT materialized_manifest_json FROM campaigns WHERE campaign_id = ?",
            (CAMPAIGN_ID,),
        ).fetchone()
        manifest = json.loads(row["materialized_manifest_json"])
        manifest["decision"] = "READY_TO_RETIRE"
        with store.connection:
            store.connection.execute(
                "UPDATE campaigns SET materialized_manifest_json = ? "
                "WHERE campaign_id = ?",
                (json.dumps(manifest), CAMPAIGN_ID),
            )
        with pytest.raises(Refusal, match="INTEGRITY_MATERIALIZED_STATE_MISMATCH"):
            store.materialize(CAMPAIGN_ID)


def test_writer_mismatch_and_policy_input_drift_refuse(tmp_path: Path) -> None:
    database = tmp_path / "campaign.sqlite"
    with CampaignStore(database, writer_id="writer-one") as store:
        create_and_inventory(store)
        before = len(store.events(CAMPAIGN_ID))
        changed = dict(store.projection(CAMPAIGN_ID).input_digests)
        changed["validator_configuration"] = f"sha256:{'f' * 64}"
        with pytest.raises(Refusal, match="POLICY_INPUT_DRIFT"):
            store.evaluate(
                CAMPAIGN_ID,
                occurred_at="2026-01-01T10:20:00Z",
                current_input_digests=changed,
            )
        assert len(store.events(CAMPAIGN_ID)) == before

    with pytest.raises(Refusal, match="RUNTIME_WRITER_MISMATCH"):
        CampaignStore(database, writer_id="writer-two")


def test_missing_campaign_conflicting_id_and_store_lock_refuse(
    tmp_path: Path,
) -> None:
    database = tmp_path / "campaign.sqlite"
    with CampaignStore(database, writer_id="writer-one") as store:
        with pytest.raises(Refusal, match="RUNTIME_CAMPAIGN_NOT_FOUND"):
            store.materialize("missing")

        store.create_campaign(
            load_specification(SPECIFICATION),
            occurred_at="2026-01-01T10:00:00Z",
        )
        conflict = deepcopy(load_specification(SPECIFICATION))
        conflict["campaign"]["name"] = "Conflicting campaign definition"
        unsigned = dict(conflict)
        unsigned.pop("specification_digest")
        conflict["specification_digest"] = digest_json(unsigned)
        with pytest.raises(Refusal, match="RUNTIME_CAMPAIGN_EXISTS"):
            store.create_campaign(
                conflict,
                occurred_at="2026-01-01T10:00:00Z",
            )

        with store.lock_path.open("a+", encoding="utf-8") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                with pytest.raises(Refusal, match="RUNTIME_STORE_LOCKED"):
                    store.append_event(
                        CAMPAIGN_ID,
                        "CAMPAIGN_BLOCKED",
                        {"reason": "locked"},
                        occurred_at="2026-01-01T10:01:00Z",
                        idempotency_key="locked",
                    )
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def test_missing_approval_refuses_before_identity_claim(tmp_path: Path) -> None:
    with CampaignStore(tmp_path / "campaign.sqlite", writer_id="writer-one") as store:
        create_and_inventory(store)
        store.change_consumer_disposition(
            CAMPAIGN_ID,
            CONSUMER_ID,
            "CHANGE_PROPOSED",
            occurred_at="2026-01-01T10:20:00Z",
            idempotency_key="propose",
            plan_digest=PLAN_DIGEST,
            source_version="commit-one",
            approved_targets=TARGETS,
        )

        with pytest.raises(Refusal, match="AUTH_APPROVAL_MISSING"):
            store.begin_migration_with_claim(
                CAMPAIGN_ID,
                NATIVE_IDENTITY,
                plan_digest=PLAN_DIGEST,
                source_version="commit-one",
                targets=TARGETS,
                required_scope=["apply"],
                trusted_now=TRUSTED_NOW,
                occurred_at="2026-01-01T11:10:00Z",
            )
        assert (
            store.connection.execute(
                "SELECT COUNT(*) FROM native_identity_claims"
            ).fetchone()[0]
            == 0
        )


def test_receipt_expiring_at_evaluation_boundary_refuses(tmp_path: Path) -> None:
    with CampaignStore(tmp_path / "campaign.sqlite", writer_id="writer-one") as store:
        create_and_inventory(store)
        propose_and_approve(store, CAMPAIGN_ID)
        begin_and_apply(store, CAMPAIGN_ID)
        store.accept_receipt(
            CAMPAIGN_ID,
            CONSUMER_ID,
            receipt_for(expires_at="2026-01-01T12:00:00Z"),
            trusted_now=TRUSTED_NOW,
            occurred_at="2026-01-01T11:30:00Z",
            idempotency_key="receipt",
        )
        store.record_reconciliation(
            CAMPAIGN_ID,
            evidence_envelope=live_envelope(),
            consumer_ids=[CONSUMER_ID],
            snapshot_digest=SNAPSHOT_TWO,
            occurred_at="2026-01-01T11:40:00Z",
        )

        with pytest.raises(Refusal, match="EVIDENCE_RECEIPT_EXPIRED"):
            store.evaluate(
                CAMPAIGN_ID,
                occurred_at="2026-01-01T12:00:00Z",
            )


def test_event_clock_rollback_refuses_without_write(tmp_path: Path) -> None:
    with CampaignStore(tmp_path / "campaign.sqlite", writer_id="writer-one") as store:
        create_and_inventory(store)
        before = len(store.events(CAMPAIGN_ID))

        with pytest.raises(Refusal, match="RUNTIME_CLOCK_ROLLBACK"):
            store.append_event(
                CAMPAIGN_ID,
                "CAMPAIGN_BLOCKED",
                {"reason": "clock rollback"},
                occurred_at="2026-01-01T09:00:00Z",
                idempotency_key="clock-rollback",
            )
        assert len(store.events(CAMPAIGN_ID)) == before

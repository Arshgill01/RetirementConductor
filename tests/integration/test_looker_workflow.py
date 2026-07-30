from __future__ import annotations

import json
from collections.abc import Mapping
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from retirement_conductor.canonical import digest_json, with_digest
from retirement_conductor.clock import parse_timestamp
from retirement_conductor.datahub import utc_now
from retirement_conductor.errors import Refusal
from retirement_conductor.looker import LookerAdapter
from retirement_conductor.looker_config import LookerSettings
from retirement_conductor.looker_workflow import LookerWorkflow
from retirement_conductor.specification import load_specification
from retirement_conductor.store import CampaignStore
from retirement_conductor.vocabulary import EvidenceMode
from tests.unit.test_looker import FakeLookerClient

ROOT = Path(__file__).resolve().parents[2]
CAMPAIGN_ID = "ret-orders-looker-workflow"
CONSUMER_ID = "dh-aaaaaaaaaaaaaaaaaaaa"
DATAHUB_URN = "urn:li:dashboard:(looker,retirement-disposable.look.41)"
GRAPH_DIGEST = f"sha256:{'7' * 64}"
CAPTURED_AT = "2026-07-30T12:00:00Z"


class FakeInventoryBoundary:
    def inventory(
        self,
        specification: Mapping[str, Any],
        *,
        artifact_root: Path,
    ) -> dict[str, Any]:
        del specification
        artifact_root.mkdir(parents=True, exist_ok=True)
        envelope = with_digest(
            {
                "schema_version": "1.0.0",
                "captured_at": CAPTURED_AT,
                "mode": "fixture",
                "sources": [
                    {
                        "id": "datahub",
                        "required": True,
                        "status": "COMPLETE",
                        "source_version": "fixture-datahub/1",
                        "identity": "fixture-datahub",
                        "scope": {
                            "direction": "downstream",
                            "max_hops": 3,
                            "filters": [],
                            "pages": 1,
                            "reported_total": 1,
                            "returned_total": 1,
                        },
                        "freshness": {
                            "observed_at": CAPTURED_AT,
                            "source_updated_at": CAPTURED_AT,
                            "maximum_age_seconds": 900,
                        },
                        "permissions": {
                            "principal": "fixture-reader",
                            "effective_scope": "read",
                        },
                        "limitations": ["Deterministic non-live workflow fixture"],
                        "artifact_ids": [f"sha256:{'6' * 64}"],
                    }
                ],
            },
            "envelope_digest",
        )
        return {
            "schema_version": "1.0.0",
            "captured_at": CAPTURED_AT,
            "snapshot_digest": GRAPH_DIGEST,
            "evidence_envelope": envelope,
            "consumers": [
                {
                    "id": CONSUMER_ID,
                    "datahub_urn": DATAHUB_URN,
                    "disposition": "OPAQUE",
                }
            ],
        }


class InterruptingLookerClient(FakeLookerClient):
    def __init__(self) -> None:
        super().__init__()
        self.interrupt_patch_response = True

    def request(
        self,
        method: str,
        path: str,
        *,
        query: Mapping[str, Any] | None = None,
        body: Mapping[str, Any] | None = None,
        form: Mapping[str, str] | None = None,
        authenticated: bool = True,
        mutation: bool = False,
    ) -> Any:
        result = super().request(
            method,
            path,
            query=query,
            body=body,
            form=form,
            authenticated=authenticated,
            mutation=mutation,
        )
        if method == "PATCH" and path == "/looks/41" and self.interrupt_patch_response:
            self.interrupt_patch_response = False
            raise KeyboardInterrupt
        return result


def _specification() -> dict[str, Any]:
    specification = deepcopy(load_specification(ROOT / "fixtures/specs/valid.yaml"))
    specification["campaign"] = {
        "id": CAMPAIGN_ID,
        "name": "Replace one saved Look field in a durable workflow fixture",
    }
    specification["authorization"]["mode"] = "apply"
    specification["authorization"]["allowed_native_objects"] = ["look:41"]
    specification["validation"]["required_receipt_types"] = ["dbt", "looker"]
    unsigned = {
        key: value
        for key, value in specification.items()
        if key != "specification_digest"
    }
    specification["specification_digest"] = digest_json(unsigned)
    return specification


def _settings() -> LookerSettings:
    return LookerSettings(
        base_url="http://127.0.0.1:19999",
        client_id="fixture-client",
        client_secret="fixture-secret",
        platform_instance="retirement-disposable",
        project_id="retirement_project",
        model_id="commerce",
        explore_id="orders",
        folder_id="9",
        content_target="look:41",
        legacy_reference="orders.legacy_status",
        replacement_reference="orders.order_status",
        datahub_urn=DATAHUB_URN,
        graph_snapshot_digest=GRAPH_DIGEST,
        mode=EvidenceMode.FIXTURE,
        allow_apply=True,
        page_size=1,
        max_pages=10,
        max_retries=0,
        timeout_seconds=1,
        query_limit=100,
    )


def _expires_after(value: str) -> str:
    return (
        (parse_timestamp(value) + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    )


def _workflow(
    tmp_path: Path,
    store: CampaignStore,
    client: FakeLookerClient,
) -> LookerWorkflow:
    return LookerWorkflow(
        store=store,
        adapter=LookerAdapter(_settings(), client=client),
        artifact_directory=tmp_path / "artifacts",
        boundary=FakeInventoryBoundary(),
    )


def test_workflow_persists_unknown_outcome_then_recovers_by_native_reread(
    tmp_path: Path,
) -> None:
    fake = FakeLookerClient()
    with CampaignStore(tmp_path / "campaign.sqlite", writer_id="test") as store:
        store.create_campaign(
            _specification(),
            occurred_at="2026-07-30T00:00:00Z",
        )
        workflow = _workflow(tmp_path, store, fake)
        preflight = workflow.preflight(CAMPAIGN_ID)
        plan = workflow.plan(CAMPAIGN_ID)["plan"]

        assert preflight["binding"]["selected_consumer_id"] == CONSUMER_ID
        assert preflight["manifest"]["campaign"]["state"] == "INVENTORIED"
        with pytest.raises(Refusal) as wrong_confirmation:
            workflow.apply(
                CAMPAIGN_ID,
                confirmed_plan_digest=f"sha256:{'0' * 64}",
            )
        assert wrong_confirmation.value.code == "AUTH_APPROVAL_WRONG_PLAN"

        authorized_at = utc_now()
        workflow.authorize(
            CAMPAIGN_ID,
            principal="fixture-operator",
            authorized_at=authorized_at,
            expires_at=_expires_after(authorized_at),
        )
        fake.drop_patch_response = True
        with pytest.raises(Refusal) as lost:
            workflow.apply(
                CAMPAIGN_ID,
                confirmed_plan_digest=str(plan["plan_digest"]),
                occurred_at=authorized_at,
            )
        assert lost.value.code == "APPLY_OUTCOME_UNKNOWN"
        intent_path = (
            tmp_path / "artifacts" / CAMPAIGN_ID / "looker" / "apply-intent.json"
        )
        unknown = json.loads(intent_path.read_text(encoding="utf-8"))
        assert unknown["status"] == "OUTCOME_UNKNOWN"
        assert (
            store.projection(CAMPAIGN_ID).consumers[CONSUMER_ID]["disposition"]
            == "CHANGE_PROPOSED"
        )

        recovered = workflow.apply(
            CAMPAIGN_ID,
            confirmed_plan_digest=str(plan["plan_digest"]),
            occurred_at=authorized_at,
        )
        resolved = json.loads(intent_path.read_text(encoding="utf-8"))

        assert recovered["apply"]["recovery"] == "native_reread"
        assert resolved["status"] == "RESOLVED"
        assert resolved["apply_digest"] == recovered["apply"]["apply_digest"]
        assert fake.patch_calls == 1
        assert (
            store.projection(CAMPAIGN_ID).consumers[CONSUMER_ID]["disposition"]
            == "APPLIED"
        )

        with pytest.raises(Refusal) as non_live:
            workflow.validate(CAMPAIGN_ID)
        assert non_live.value.code == "EVIDENCE_RECEIPT_MODE_NOT_LIVE"
        receipt = json.loads(
            (
                tmp_path / "artifacts" / CAMPAIGN_ID / "looker" / "receipt.json"
            ).read_text(encoding="utf-8")
        )
        assert receipt["adapter"]["mode"] == "fixture"
        assert (
            store.projection(CAMPAIGN_ID).consumers[CONSUMER_ID]["disposition"]
            == "APPLIED"
        )


def test_process_interruption_leaves_pending_intent_and_reread_recovers(
    tmp_path: Path,
) -> None:
    fake = InterruptingLookerClient()
    with CampaignStore(tmp_path / "campaign.sqlite", writer_id="test") as store:
        store.create_campaign(
            _specification(),
            occurred_at="2026-07-30T00:00:00Z",
        )
        workflow = _workflow(tmp_path, store, fake)
        workflow.preflight(CAMPAIGN_ID)
        plan = workflow.plan(CAMPAIGN_ID)["plan"]
        authorized_at = utc_now()
        workflow.authorize(
            CAMPAIGN_ID,
            principal="fixture-operator",
            authorized_at=authorized_at,
            expires_at=_expires_after(authorized_at),
        )

        with pytest.raises(KeyboardInterrupt):
            workflow.apply(
                CAMPAIGN_ID,
                confirmed_plan_digest=str(plan["plan_digest"]),
                occurred_at=authorized_at,
            )
        intent_path = (
            tmp_path / "artifacts" / CAMPAIGN_ID / "looker" / "apply-intent.json"
        )
        pending = json.loads(intent_path.read_text(encoding="utf-8"))
        assert pending["status"] == "PENDING"

        recovered = workflow.apply(
            CAMPAIGN_ID,
            confirmed_plan_digest=str(plan["plan_digest"]),
            occurred_at=authorized_at,
        )

        assert recovered["apply"]["recovery"] == "native_reread"
        assert fake.patch_calls == 1


def test_workflow_compensation_requires_replanning_before_reapply(
    tmp_path: Path,
) -> None:
    fake = FakeLookerClient()
    with CampaignStore(tmp_path / "campaign.sqlite", writer_id="test") as store:
        store.create_campaign(
            _specification(),
            occurred_at="2026-07-30T00:00:00Z",
        )
        workflow = _workflow(tmp_path, store, fake)
        workflow.preflight(CAMPAIGN_ID)
        first_plan = workflow.plan(CAMPAIGN_ID)["plan"]
        authorized_at = utc_now()
        workflow.authorize(
            CAMPAIGN_ID,
            principal="fixture-operator",
            authorized_at=authorized_at,
            expires_at=_expires_after(authorized_at),
        )
        workflow.apply(
            CAMPAIGN_ID,
            confirmed_plan_digest=str(first_plan["plan_digest"]),
            occurred_at=authorized_at,
        )

        restored = workflow.compensate(
            CAMPAIGN_ID,
            occurred_at=authorized_at,
        )
        assert restored["compensation"]["result"] == "RESTORED"
        assert (
            store.projection(CAMPAIGN_ID).consumers[CONSUMER_ID]["disposition"]
            == "STALE"
        )

        second_plan = workflow.plan(CAMPAIGN_ID)["plan"]
        assert second_plan["plan_digest"] != first_plan["plan_digest"]
        second_authorized_at = utc_now()
        workflow.authorize(
            CAMPAIGN_ID,
            principal="fixture-operator",
            authorized_at=second_authorized_at,
            expires_at=_expires_after(second_authorized_at),
        )
        reapplied = workflow.apply(
            CAMPAIGN_ID,
            confirmed_plan_digest=str(second_plan["plan_digest"]),
            occurred_at=second_authorized_at,
        )
        with pytest.raises(Refusal) as non_live:
            workflow.validate(CAMPAIGN_ID)
        receipt = json.loads(
            (
                tmp_path / "artifacts" / CAMPAIGN_ID / "looker" / "receipt.json"
            ).read_text(encoding="utf-8")
        )

        assert reapplied["apply"]["actual_targets"] == ["look:41"]
        assert non_live.value.code == "EVIDENCE_RECEIPT_MODE_NOT_LIVE"
        assert receipt["plan"]["digest"] == second_plan["plan_digest"]
        assert receipt["compensation"]["exercised"] is False
        assert fake.query_id == "q-after"

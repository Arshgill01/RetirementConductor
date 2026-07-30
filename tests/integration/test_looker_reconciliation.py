from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from retirement_conductor.canonical import with_digest, write_json
from retirement_conductor.errors import Refusal
from retirement_conductor.reconciliation import ReconciliationWorkflow
from retirement_conductor.specification import load_specification

ROOT = Path(__file__).resolve().parents[2]
CAMPAIGN_ID = "ret-orders-combined-reconciliation"
GIT_CONSUMER = "consumer-git"
LOOKER_CONSUMER = "consumer-looker"
LOOKER_URN = "urn:li:dashboard:(looker,retirement-disposable.look.41)"
DATASET_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:bigquery,"
    "retirement.analytics.commerce.orders,PROD)"
)
CAPTURED_AT = "2026-07-30T12:00:00Z"


def _source(
    source_id: str,
    *,
    identity: str,
    principal: str,
    effective_scope: str,
) -> dict[str, Any]:
    return {
        "id": source_id,
        "required": True,
        "status": "COMPLETE",
        "source_version": f"{source_id}/1",
        "identity": identity,
        "scope": {
            "direction": "downstream",
            "max_hops": 3 if source_id == "datahub" else 1,
            "filters": [],
            "pages": 1,
            "reported_total": 2,
            "returned_total": 2,
        },
        "freshness": {
            "observed_at": CAPTURED_AT,
            "source_updated_at": CAPTURED_AT,
            "maximum_age_seconds": 900,
        },
        "permissions": {
            "principal": principal,
            "effective_scope": effective_scope,
        },
        "limitations": [],
        "artifact_ids": [f"sha256:{'6' * 64}"],
    }


def _baseline_envelope() -> dict[str, Any]:
    return with_digest(
        {
            "schema_version": "1.0.0",
            "captured_at": CAPTURED_AT,
            "mode": "live",
            "sources": [
                _source(
                    "datahub",
                    identity="https://datahub.example.invalid",
                    principal="datahub-reader",
                    effective_scope="read",
                ),
                _source(
                    "git:analytics",
                    identity="git-identity",
                    principal="git-operator",
                    effective_scope="read,plan,apply,validate,compensate",
                ),
                _source(
                    "looker:retirement-disposable",
                    identity="looker-origin-digest",
                    principal="looker-principal-digest",
                    effective_scope="read,plan,apply,validate,compensate",
                ),
            ],
        },
        "envelope_digest",
    )


def _datahub_envelope() -> dict[str, Any]:
    return with_digest(
        {
            "schema_version": "1.0.0",
            "captured_at": CAPTURED_AT,
            "mode": "live",
            "sources": [
                _source(
                    "datahub",
                    identity="https://datahub.example.invalid",
                    principal="datahub-reader",
                    effective_scope="read",
                )
            ],
        },
        "envelope_digest",
    )


def _snapshot(field: str) -> dict[str, Any]:
    return with_digest(
        {
            "schema_version": "1.0.0",
            "campaign_id": CAMPAIGN_ID,
            "captured_at": CAPTURED_AT,
            "resolution": {
                "dataset": {"urn": DATASET_URN},
                "target_field": {"fieldPath": field},
            },
            "consumers": [
                {"id": GIT_CONSUMER, "disposition": "OPAQUE"},
                {
                    "id": LOOKER_CONSUMER,
                    "datahub_urn": LOOKER_URN,
                    "disposition": "OPAQUE",
                },
            ],
            "claims": [],
            "pagination": {"status": "COMPLETE"},
            "evidence_envelope": _datahub_envelope(),
        },
        "snapshot_digest",
    )


class FakeBoundary:
    def __init__(self) -> None:
        self.settings = SimpleNamespace(gms_url="https://datahub.example.invalid")

    def inventory(
        self,
        specification: dict[str, Any],
        *,
        artifact_root: Path,
    ) -> dict[str, Any]:
        artifact_root.mkdir(parents=True, exist_ok=True)
        return _snapshot(str(specification["target"]["field"]))


class FakeGitAdapter:
    def __init__(self) -> None:
        self.settings = SimpleNamespace(repository_id="analytics")

    def reconcile_source(self, *args: object, **kwargs: object) -> dict[str, Any]:
        return with_digest(
            {
                "schema_version": "1.0.0",
                "mode": "live",
                "captured_at": CAPTURED_AT,
                "repository": {
                    "id": "analytics",
                    "required": True,
                    "identity": "git-identity",
                    "source_branch": "main",
                    "source_version": "git-commit-after",
                    "source_committed_at": CAPTURED_AT,
                },
                "principal": "git-operator",
                "capabilities": {
                    "read": True,
                    "plan": True,
                    "apply": True,
                    "validate": True,
                    "compensate": True,
                },
                "limitations": [],
            },
            "reconciliation_digest",
        )


class FakeLookerAdapter:
    def __init__(self, *, refusal: Refusal | None = None) -> None:
        self.refusal = refusal

    def reconcile_source(self, *args: object, **kwargs: object) -> dict[str, Any]:
        if self.refusal is not None:
            raise self.refusal
        validation = with_digest(
            {
                "schema_version": "1.0.0",
                "result": "PASSED",
            },
            "validation_digest",
        )
        return with_digest(
            {
                "schema_version": "1.0.0",
                "result": "PASSED",
                "mode": "live",
                "captured_at": CAPTURED_AT,
                "source": {
                    "id": "looker:retirement-disposable",
                    "required": True,
                    "identity": "looker-origin-digest",
                    "source_version": "looker-after",
                    "source_updated_at": CAPTURED_AT,
                    "principal": "looker-principal-digest",
                    "effective_capabilities": [
                        "read",
                        "plan",
                        "apply",
                        "validate",
                        "compensate",
                    ],
                },
                "native_validation": validation,
                "limitations": [],
            },
            "reconciliation_digest",
        )


class FakeProjection:
    def __init__(self) -> None:
        self.evidence_envelope = _baseline_envelope()
        self.snapshot_digests = [f"sha256:{'1' * 64}"]
        self.inventory_consumer_ids = [GIT_CONSUMER, LOOKER_CONSUMER]
        self.consumers = {
            GIT_CONSUMER: {
                "id": GIT_CONSUMER,
                "disposition": "VALIDATED",
            },
            LOOKER_CONSUMER: {
                "id": LOOKER_CONSUMER,
                "disposition": "VALIDATED",
            },
        }


class FakeStore:
    def __init__(self) -> None:
        self.projection_value = FakeProjection()
        self.recorded: dict[str, Any] | None = None

    def specification(self, campaign_id: str) -> dict[str, Any]:
        specification = load_specification(ROOT / "fixtures/specs/valid.yaml")
        specification["campaign"] = {
            "id": campaign_id,
            "name": "Combined reconciliation fixture",
        }
        return specification

    def projection(self, campaign_id: str) -> FakeProjection:
        assert campaign_id == CAMPAIGN_ID
        return self.projection_value

    def change_consumer_disposition(
        self,
        campaign_id: str,
        consumer_id: str,
        disposition: str,
        **kwargs: object,
    ) -> dict[str, Any]:
        del campaign_id, kwargs
        self.projection_value.consumers[consumer_id]["disposition"] = disposition
        return {"result": "UPDATED"}

    def record_reconciliation(
        self,
        campaign_id: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        self.recorded = {"campaign_id": campaign_id, **kwargs}
        return {"campaign": {"id": campaign_id}}

    def evaluate(self, campaign_id: str, **kwargs: object) -> dict[str, Any]:
        del kwargs
        return {"campaign": {"id": campaign_id}, "decision": "UNSAFE"}


def _write_inputs(root: Path) -> Path:
    artifact_directory = root / "artifacts"
    git_root = artifact_directory / CAMPAIGN_ID / "git-dbt"
    looker_root = artifact_directory / CAMPAIGN_ID / "looker"
    write_json(git_root / "plan.json", {"consumer_id": GIT_CONSUMER})
    write_json(git_root / "apply.json", {"apply_digest": f"sha256:{'2' * 64}"})
    write_json(git_root / "receipt.json", {"receipt_digest": f"sha256:{'3' * 64}"})
    write_json(looker_root / "plan.json", {"consumer_id": LOOKER_CONSUMER})
    write_json(
        looker_root / "apply.json",
        {"apply_digest": f"sha256:{'4' * 64}"},
    )
    write_json(
        looker_root / "receipt.json",
        {"receipt_digest": f"sha256:{'5' * 64}"},
    )
    return artifact_directory


def _refresh(path: Path) -> Path:
    receipt = with_digest(
        {
            "mode": "live",
            "gms_url": "https://datahub.example.invalid",
            "target_urns": [DATASET_URN],
            "source_updated_at": CAPTURED_AT,
            "ingestion_run_id": "refresh-one",
        },
        "refresh_digest",
    )
    write_json(path, receipt)
    return path


def _workflow(
    tmp_path: Path,
    store: FakeStore,
    looker: FakeLookerAdapter,
) -> ReconciliationWorkflow:
    store_value: Any = store
    boundary_value: Any = FakeBoundary()
    git_value: Any = FakeGitAdapter()
    looker_value: Any = looker
    return ReconciliationWorkflow(
        store=store_value,
        boundary=boundary_value,
        git_dbt=git_value,
        looker=looker_value,
        artifact_directory=_write_inputs(tmp_path),
        refresh_receipt=_refresh(tmp_path / "refresh.json"),
        indexing_timeout_seconds=0.1,
    )


def test_combined_reconciliation_records_both_native_sources(
    tmp_path: Path,
) -> None:
    store = FakeStore()
    workflow = _workflow(tmp_path, store, FakeLookerAdapter())

    result = workflow.reconcile(CAMPAIGN_ID)

    assert result["result"] == "RECONCILED"
    assert result["comparison"]["current"]["git_reconciliation_digest"]
    assert result["comparison"]["current"]["looker_reconciliation_digest"]
    assert result["comparison"]["current"]["replacement_datahub_snapshot_digest"]
    assert result["comparison"]["invalidated_receipts"] == []
    assert store.recorded is not None
    source_ids = {
        source["id"] for source in store.recorded["evidence_envelope"]["sources"]
    }
    assert source_ids == {
        "datahub",
        "git:analytics",
        "looker:retirement-disposable",
    }


def test_recreated_looker_identity_stales_only_its_receipt(
    tmp_path: Path,
) -> None:
    store = FakeStore()
    workflow = _workflow(
        tmp_path,
        store,
        FakeLookerAdapter(
            refusal=Refusal(
                "IDENTITY_NATIVE_OBJECT_RECREATED",
                "fixture identity changed",
            )
        ),
    )

    result = workflow.reconcile(CAMPAIGN_ID)

    invalidations = result["comparison"]["invalidated_receipts"]
    assert [item["consumer_id"] for item in invalidations] == [LOOKER_CONSUMER]
    assert invalidations[0]["refusal_code"] == "IDENTITY_NATIVE_OBJECT_RECREATED"
    assert store.projection_value.consumers[LOOKER_CONSUMER]["disposition"] == "STALE"
    assert store.projection_value.consumers[GIT_CONSUMER]["disposition"] == "VALIDATED"

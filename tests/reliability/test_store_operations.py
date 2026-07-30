from __future__ import annotations

import json
import shutil
import sqlite3
import stat
from pathlib import Path
from typing import Any

import pytest

import retirement_conductor.store as store_module
from retirement_conductor.canonical import (
    canonical_json,
    digest_file,
    digest_json,
    verify_digest,
    with_digest,
)
from retirement_conductor.cli import main
from retirement_conductor.errors import Refusal
from retirement_conductor.specification import load_specification
from retirement_conductor.store import CampaignStore

ROOT = Path(__file__).resolve().parents[2]
SPECIFICATION = ROOT / "fixtures/specs/valid.yaml"
CAMPAIGN_ID = "ret-orders-legacy-status"


def evidence_envelope(status: str = "COMPLETE") -> dict[str, Any]:
    return with_digest(
        {
            "schema_version": "1.0.0",
            "captured_at": "2026-01-01T11:00:00Z",
            "mode": "fixture",
            "sources": [
                {
                    "id": "datahub",
                    "required": True,
                    "status": status,
                    "source_version": "fixture/1",
                    "identity": "fixture-datahub",
                    "scope": {
                        "direction": "downstream",
                        "max_hops": 5,
                        "filters": [],
                        "pages": 1,
                        "reported_total": 1,
                        "returned_total": 1,
                    },
                    "freshness": {
                        "observed_at": "2026-01-01T11:00:00Z",
                        "source_updated_at": "2026-01-01T10:59:00Z",
                        "maximum_age_seconds": 900,
                    },
                    "permissions": {
                        "principal": "fixture-reader",
                        "effective_scope": "read-only",
                    },
                    "limitations": [],
                    "artifact_ids": [f"sha256:{'1' * 64}"],
                },
            ],
        },
        "envelope_digest",
    )


def create_inventoried_campaign(
    store: CampaignStore,
    *,
    source_status: str = "COMPLETE",
) -> dict[str, Any]:
    store.create_campaign(
        load_specification(SPECIFICATION),
        occurred_at="2026-01-01T10:00:00Z",
    )
    return store.record_inventory(
        CAMPAIGN_ID,
        evidence_envelope=evidence_envelope(source_status),
        consumers=[
            {
                "id": "consumer-dbt-order-summary",
                "disposition": "IDENTIFIED",
                "receipt_digest": None,
            }
        ],
        snapshot_digest=f"sha256:{'2' * 64}",
        occurred_at="2026-01-01T10:10:00Z",
    )


def test_backup_restore_reproduces_manifest_and_evidence_references(
    tmp_path: Path,
) -> None:
    database = tmp_path / "campaign.sqlite"
    backup = tmp_path / "backups/campaign.sqlite"
    with CampaignStore(database, writer_id="writer-one") as store:
        expected_manifest = create_inventoried_campaign(store)
        receipt = store.backup_to(
            backup,
            captured_at="2026-01-01T12:00:00Z",
        )
        verification = store.verify_backup(backup)

    verify_digest(receipt, "backup_receipt_digest")
    verify_digest(verification, "verification_digest")
    assert receipt["result"] == "BACKUP_VERIFIED"
    assert receipt["logical_snapshot_digest"] == verification["logical_snapshot_digest"]
    assert stat.S_IMODE(backup.stat().st_mode) == 0o600
    assert stat.S_IMODE(database.stat().st_mode) == 0o600
    assert (
        stat.S_IMODE(database.with_name("campaign.sqlite.lock").stat().st_mode) == 0o600
    )

    archived = tmp_path / "campaign.before-restore.sqlite"
    database.replace(archived)
    shutil.copyfile(backup, database)
    with CampaignStore(database, writer_id="writer-one") as restored:
        assert restored.materialize(CAMPAIGN_ID) == expected_manifest
        assert restored.schema_versions() == [1, 2, 3]


def test_backup_refuses_overwrite_copy_writer_and_tampering(tmp_path: Path) -> None:
    database = tmp_path / "campaign.sqlite"
    backup = tmp_path / "campaign.backup.sqlite"
    with CampaignStore(database, writer_id="writer-one") as store:
        create_inventoried_campaign(store)
        store.backup_to(backup, captured_at="2026-01-01T12:00:00Z")

        with pytest.raises(Refusal, match="SCOPE_TARGET_NOT_ALLOWED"):
            store.backup_to(backup, captured_at="2026-01-01T12:01:00Z")

        copied = tmp_path / "copied.sqlite"
        shutil.copyfile(backup, copied)
        copied_digest = digest_file(copied)
        with pytest.raises(Refusal, match="RUNTIME_WRITER_MISMATCH"):
            CampaignStore(copied, writer_id="writer-one")
        assert digest_file(copied) == copied_digest

        tampered = tmp_path / "tampered.sqlite"
        shutil.copyfile(backup, tampered)
        connection = sqlite3.connect(tampered)
        try:
            connection.execute("PRAGMA journal_mode = DELETE")
            with connection:
                connection.execute(
                    "UPDATE campaign_events SET event_json = '{}' "
                    "WHERE campaign_id = ? AND sequence = 2",
                    (CAMPAIGN_ID,),
                )
        finally:
            connection.close()
        with pytest.raises(
            Refusal,
            match="INTEGRITY_MATERIALIZED_STATE_MISMATCH",
        ):
            store.verify_backup(tampered)

        forged_cache = tmp_path / "forged-cache.sqlite"
        shutil.copyfile(backup, forged_cache)
        connection = sqlite3.connect(forged_cache)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA journal_mode = DELETE")
            row = connection.execute(
                "SELECT materialized_manifest_json FROM campaigns "
                "WHERE campaign_id = ?",
                (CAMPAIGN_ID,),
            ).fetchone()
            manifest = json.loads(str(row["materialized_manifest_json"]))
            manifest["decision"] = "READY_TO_RETIRE"
            forged = with_digest(manifest, "manifest_digest")
            with connection:
                connection.execute(
                    """
                    UPDATE campaigns
                    SET materialized_manifest_json = ?,
                        materialized_manifest_digest = ?
                    WHERE campaign_id = ?
                    """,
                    (
                        canonical_json(forged),
                        forged["manifest_digest"],
                        CAMPAIGN_ID,
                    ),
                )
        finally:
            connection.close()
        with pytest.raises(
            Refusal,
            match="INTEGRITY_MATERIALIZED_STATE_MISMATCH",
        ):
            store.verify_backup(forged_cache)


def test_operational_metrics_surface_stuck_stale_and_repeated_refusals(
    tmp_path: Path,
) -> None:
    with CampaignStore(tmp_path / "campaign.sqlite", writer_id="writer-one") as store:
        manifest = create_inventoried_campaign(store, source_status="STALE")
        for offset in range(3):
            store.record_gate_refusal(
                CAMPAIGN_ID,
                manifest_digest=manifest["manifest_digest"],
                decision=manifest["decision"],
                refusal_code="GATE_PROVENANCE_UNTRUSTED",
                recorded_at=f"2026-01-01T11:00:0{offset}Z",
            )

        metrics = store.operational_metrics(
            observed_at="2026-01-02T11:00:00Z",
            stuck_after_seconds=3600,
        )

    verify_digest(metrics, "metrics_digest")
    assert metrics["healthy"] is False
    assert metrics["campaign_states"] == {"INVENTORIED": 1}
    assert metrics["gate_refusal_codes"] == {"GATE_PROVENANCE_UNTRUSTED": 3}
    assert metrics["alerts"]["stuck_campaigns"] == [
        {
            "campaign_id_digest": digest_json(CAMPAIGN_ID),
            "state": "INVENTORIED",
            "age_seconds": 89400,
        }
    ]
    assert metrics["alerts"]["stale_campaigns"] == [
        {
            "campaign_id_digest": digest_json(CAMPAIGN_ID),
            "source_count": 1,
            "source_ids": ["datahub"],
        }
    ]
    assert metrics["alerts"]["repeated_gate_refusals"] == [
        {"refusal_code": "GATE_PROVENANCE_UNTRUSTED", "count": 3}
    ]


def test_store_refuses_known_shared_filesystem(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(store_module, "_filesystem_type", lambda _path: "nfs")

    with pytest.raises(Refusal, match="RUNTIME_WRITER_MISMATCH") as refused:
        CampaignStore(tmp_path / "campaign.sqlite", writer_id="writer-one")

    assert refused.value.details == {"filesystem_type": "nfs"}
    assert not (tmp_path / "campaign.sqlite").exists()


def test_backup_verification_and_diagnostics_are_operator_commands(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database = tmp_path / "campaign.sqlite"
    backup = tmp_path / "campaign.backup.sqlite"
    with CampaignStore(database, writer_id="writer-one") as store:
        create_inventoried_campaign(store)

    common = ["--store", str(database), "--writer-id", "writer-one"]
    assert (
        main(
            [
                "campaign",
                "backup",
                "--output",
                str(backup),
                "--captured-at",
                "2026-01-01T12:00:00Z",
                *common,
            ]
        )
        == 0
    )
    backup_result = json.loads(capsys.readouterr().out)
    assert backup_result["result"] == "BACKUP_VERIFIED"

    assert main(["campaign", "verify-backup", str(backup), *common]) == 0
    verification = json.loads(capsys.readouterr().out)
    assert verification["result"] == "BACKUP_MATCHES_LIVE_STATE"

    assert (
        main(
            [
                "campaign",
                "diagnostics",
                "--observed-at",
                "2026-01-02T11:00:00Z",
                "--stuck-after-seconds",
                "3600",
                *common,
            ]
        )
        == 0
    )
    diagnostics = json.loads(capsys.readouterr().out)
    assert diagnostics["healthy"] is False
    assert len(diagnostics["alerts"]["stuck_campaigns"]) == 1

from __future__ import annotations

import json
from pathlib import Path

from retirement_conductor.cli import main
from retirement_conductor.specification import load_specification
from retirement_conductor.store import CampaignStore

ROOT = Path(__file__).resolve().parents[2]
SPECIFICATION = ROOT / "fixtures/specs/valid.yaml"
CAMPAIGN_ID = "ret-orders-legacy-status"


def read_output(capsys: object) -> dict[str, object]:
    return json.loads(capsys.readouterr().out)  # type: ignore[attr-defined,no-any-return]


def test_campaign_create_inspect_and_export_commands(
    tmp_path: Path,
    capsys: object,
) -> None:
    database = tmp_path / "campaign.sqlite"
    common = ["--store", str(database), "--writer-id", "writer-one"]

    assert (
        main(
            [
                "campaign",
                "create",
                str(SPECIFICATION),
                *common,
                "--occurred-at",
                "2026-01-01T10:00:00Z",
            ]
        )
        == 0
    )
    created = read_output(capsys)
    assert created["result"] == "OK"

    assert (
        main(
            [
                "campaign",
                "inspect",
                "--campaign",
                CAMPAIGN_ID,
                *common,
                "--format",
                "json",
            ]
        )
        == 0
    )
    inspected = read_output(capsys)
    created_manifest = created["manifest"]
    inspected_manifest = inspected["manifest"]
    assert isinstance(created_manifest, dict)
    assert isinstance(inspected_manifest, dict)
    assert created_manifest["manifest_digest"] == inspected_manifest["manifest_digest"]

    exported_path = tmp_path / "manifest.json"
    assert (
        main(
            [
                "campaign",
                "export",
                CAMPAIGN_ID,
                "--output",
                str(exported_path),
                *common,
            ]
        )
        == 0
    )
    exported = read_output(capsys)
    artifact = json.loads(exported_path.read_text(encoding="utf-8"))
    assert exported["result"] == "EXPORTED"
    assert artifact["manifest_digest"] == created_manifest["manifest_digest"]


def test_campaign_resume_command(tmp_path: Path, capsys: object) -> None:
    database = tmp_path / "campaign.sqlite"
    with CampaignStore(database, writer_id="writer-one") as store:
        store.create_campaign(
            load_specification(SPECIFICATION),
            occurred_at="2026-01-01T10:00:00Z",
        )
        store.record_inventory(
            CAMPAIGN_ID,
            evidence_envelope={
                "mode": "fixture",
                "sources": [{"id": "datahub", "required": True, "status": "COMPLETE"}],
            },
            consumers=[
                {
                    "id": "consumer-one",
                    "disposition": "UNRESOLVED",
                    "receipt_digest": None,
                }
            ],
            snapshot_digest=f"sha256:{'1' * 64}",
            occurred_at="2026-01-01T10:10:00Z",
        )
        store.evaluate(
            CAMPAIGN_ID,
            occurred_at="2026-01-01T10:20:00Z",
        )

    exit_code = main(
        [
            "campaign",
            "resume",
            "--campaign",
            CAMPAIGN_ID,
            "--state",
            "INVENTORIED",
            "--occurred-at",
            "2026-01-01T10:30:00Z",
            "--idempotency-key",
            "resume-one",
            "--store",
            str(database),
            "--writer-id",
            "writer-one",
            "--format",
            "json",
        ]
    )

    assert exit_code == 0
    output = read_output(capsys)
    manifest = output["manifest"]
    assert isinstance(manifest, dict)
    assert manifest["campaign"]["state"] == "INVENTORIED"


def test_gate_command_records_canonical_non_ready_refusal(
    tmp_path: Path,
    capsys: object,
) -> None:
    database = tmp_path / "campaign.sqlite"
    with CampaignStore(database, writer_id="writer-one") as store:
        store.create_campaign(
            load_specification(SPECIFICATION),
            occurred_at="2026-01-01T10:00:00Z",
        )

    exit_code = main(
        [
            "gate",
            "--campaign",
            CAMPAIGN_ID,
            "--store",
            str(database),
            "--writer-id",
            "writer-one",
            "--artifact-dir",
            str(tmp_path / "artifacts"),
        ]
    )

    assert exit_code == 2
    output = read_output(capsys)
    assert output["refusal_code"] == "GATE_DECISION_NOT_READY"
    with CampaignStore(database, writer_id="writer-one") as store:
        attempts = store.gate_attempts(CAMPAIGN_ID)
    assert attempts[0]["status"] == "REFUSED"
    assert attempts[0]["attempt"]["manifest_digest"] == store_manifest_digest(database)


def store_manifest_digest(database: Path) -> str:
    with CampaignStore(database, writer_id="writer-one") as store:
        return str(store.materialize(CAMPAIGN_ID)["manifest_digest"])

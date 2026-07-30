from __future__ import annotations

import json
from pathlib import Path

from retirement_conductor.cli import main
from retirement_conductor.store import CampaignStore

ROOT = Path(__file__).resolve().parents[2]
SPECIFICATION = ROOT / "fixtures/specs/valid.yaml"
CAMPAIGN_ID = "ret-orders-legacy-status"
READY_MANIFEST = ROOT / "artifacts/public/phase04/ready-manifest.json"


def create_campaign(database: Path, capsys: object) -> str:
    exit_code = main(
        [
            "campaign",
            "create",
            str(SPECIFICATION),
            "--store",
            str(database),
            "--writer-id",
            "operator-test",
            "--occurred-at",
            "2026-01-01T10:00:00Z",
        ]
    )
    assert exit_code == 0
    capsys.readouterr()  # type: ignore[attr-defined]
    with CampaignStore(database, writer_id="operator-test") as store:
        return str(store.materialize(CAMPAIGN_ID)["manifest_digest"])


def test_inspect_explain_and_report_share_one_manifest(
    tmp_path: Path,
    capsys: object,
) -> None:
    database = tmp_path / "campaign.sqlite"
    digest = create_campaign(database, capsys)
    common = [
        "--store",
        str(database),
        "--writer-id",
        "operator-test",
    ]

    assert main(["campaign", "inspect", "--campaign", CAMPAIGN_ID, *common]) == 0
    inspected = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "Decision: BLOCKED" in inspected
    assert "legacy_status" in inspected
    assert "order_status" in inspected
    assert "Evidence: Unknown" in inspected
    assert digest in inspected

    assert main(["campaign", "explain", "--campaign", CAMPAIGN_ID, *common]) == 0
    explained = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "Evidence sources" in explained
    assert "No consumers are recorded" not in explained
    assert "EVIDENCE_EMPTY_RESULT_UNPROVEN" in explained
    assert digest in explained

    first_report = tmp_path / "first.html"
    assert (
        main(
            [
                "report",
                "build",
                "--campaign",
                CAMPAIGN_ID,
                *common,
                "--output",
                str(first_report),
            ]
        )
        == 0
    )
    report_output = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "Report built:" in report_output
    assert "Decision: BLOCKED" in report_output
    assert digest in report_output
    assert digest in first_report.read_text(encoding="utf-8")

    second_report = tmp_path / "second.html"
    assert (
        main(
            [
                "report",
                "build",
                "--campaign",
                CAMPAIGN_ID,
                *common,
                "--output",
                str(second_report),
                "--format",
                "json",
            ]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert result["decision"] == "BLOCKED"
    assert result["manifest_digest"] == digest
    assert first_report.read_bytes() == second_report.read_bytes()


def test_public_cli_export_is_redacted_and_deterministic(
    tmp_path: Path,
    capsys: object,
) -> None:
    database = tmp_path / "campaign.sqlite"
    digest = create_campaign(database, capsys)
    output = tmp_path / "public.html"

    assert (
        main(
            [
                "report",
                "build",
                "--campaign",
                CAMPAIGN_ID,
                "--store",
                str(database),
                "--writer-id",
                "operator-test",
                "--output",
                str(output),
                "--public",
            ]
        )
        == 0
    )
    capsys.readouterr()  # type: ignore[attr-defined]

    content = output.read_text(encoding="utf-8")
    assert 'data-export="public"' in content
    assert "public-campaign" in content
    assert CAMPAIGN_ID not in content
    assert "fixture-principal" not in content
    assert digest in content


def test_campaign_selector_refuses_conflicting_identifiers(
    tmp_path: Path,
    capsys: object,
) -> None:
    database = tmp_path / "campaign.sqlite"
    create_campaign(database, capsys)

    exit_code = main(
        [
            "campaign",
            "inspect",
            CAMPAIGN_ID,
            "--campaign",
            "different-campaign",
            "--store",
            str(database),
            "--writer-id",
            "operator-test",
        ]
    )

    assert exit_code == 2
    refusal = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert refusal["refusal_code"] == "SPEC_SCHEMA_INVALID"


def test_exported_canonical_manifest_remains_inspectable_and_reportable(
    tmp_path: Path,
    capsys: object,
) -> None:
    manifest = json.loads(READY_MANIFEST.read_text(encoding="utf-8"))
    campaign_id = manifest["campaign"]["id"]

    assert (
        main(
            [
                "campaign",
                "inspect",
                "--campaign",
                campaign_id,
                "--manifest",
                str(READY_MANIFEST),
            ]
        )
        == 0
    )
    inspected = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "READY_TO_RETIRE" in inspected
    assert manifest["manifest_digest"] in inspected

    output = tmp_path / "portable.html"
    assert (
        main(
            [
                "report",
                "build",
                "--campaign",
                campaign_id,
                "--manifest",
                str(READY_MANIFEST),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    capsys.readouterr()  # type: ignore[attr-defined]
    assert manifest["manifest_digest"] in output.read_text(encoding="utf-8")

from __future__ import annotations

from pathlib import Path

from retirement_conductor.canonical import verify_digest
from retirement_conductor.cli import main
from retirement_conductor.reference import run_reference_fixture


def test_installed_reference_is_deterministic_and_explicitly_non_live(
    tmp_path: Path,
) -> None:
    first = run_reference_fixture(tmp_path / "first")
    second = run_reference_fixture(tmp_path / "second")

    assert first == second
    assert first["result"] == "FIXTURE_COMPLETE"
    assert first["mode"] == "fixture"
    assert first["decision"] == "BLOCKED"
    assert first["refusal_code"] == "EVIDENCE_MODE_NOT_LIVE"
    for filename in first["artifacts"]:
        assert (tmp_path / "first" / filename).read_bytes() == (
            tmp_path / "second" / filename
        ).read_bytes()

    manifest = __import__("json").loads(
        (tmp_path / "first" / "manifest.json").read_text(encoding="utf-8")
    )
    verify_digest(manifest, "manifest_digest")


def test_reference_cli_needs_no_input_file(capsys: object, tmp_path: Path) -> None:
    exit_code = main(
        [
            "reference",
            "run",
            "--output-dir",
            str(tmp_path / "reference"),
        ]
    )

    assert exit_code == 0
    output = __import__("json").loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert output["result"] == "FIXTURE_COMPLETE"
    assert output["decision"] == "BLOCKED"

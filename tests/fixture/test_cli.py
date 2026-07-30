from __future__ import annotations

import json
from pathlib import Path

from retirement_conductor.cli import build_parser, main

ROOT = Path(__file__).resolve().parents[2]


def test_validate_spec_command(capsys: object) -> None:
    exit_code = main(["validate-spec", str(ROOT / "fixtures/specs/valid.yaml")])

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert output["result"] == "VALID"


def test_fixture_refusal_command(capsys: object, tmp_path: Path) -> None:
    exit_code = main(
        [
            "fixture",
            "run",
            str(ROOT / "fixtures/specs/valid.yaml"),
            "--scenario",
            str(ROOT / "fixtures/scenarios/stale-source.json"),
            "--output-dir",
            str(tmp_path / "output"),
        ]
    )

    assert exit_code == 2
    output = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert output["refusal_code"] == "SOURCE_FINGERPRINT_MISMATCH"


def test_looker_cli_exposes_full_bounded_lifecycle() -> None:
    parser = build_parser()
    for operation in (
        "access-packet",
        "preflight",
        "plan",
        "authorize",
        "apply",
        "compensate",
        "validate",
    ):
        arguments = ["adapter", "looker", operation, "--campaign", "campaign-one"]
        if operation == "authorize":
            arguments.extend(
                [
                    "--principal",
                    "operator",
                    "--authorized-at",
                    "2026-07-30T12:00:00Z",
                    "--expires-at",
                    "2026-07-30T13:00:00Z",
                ]
            )
        parsed = parser.parse_args(arguments)
        assert parsed.adapter_name == "looker"
        assert parsed.adapter_command == operation

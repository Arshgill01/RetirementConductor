from __future__ import annotations

import json
from pathlib import Path

import pytest

from retirement_conductor.errors import Refusal
from retirement_conductor.fixtures import run_fixture

ROOT = Path(__file__).resolve().parents[2]
SPECIFICATION = ROOT / "fixtures/specs/valid.yaml"
SCENARIOS = ROOT / "fixtures/scenarios"


def test_fixture_run_is_deterministic_and_explicitly_non_live(tmp_path: Path) -> None:
    first_directory = tmp_path / "first"
    second_directory = tmp_path / "second"

    first = run_fixture(SPECIFICATION, output_directory=first_directory)
    second = run_fixture(SPECIFICATION, output_directory=second_directory)

    assert first == second
    assert first["mode"] == "fixture"
    assert first["decision"] == "BLOCKED"
    assert first["refusal_code"] == "EVIDENCE_MODE_NOT_LIVE"
    for filename in first["artifacts"]:
        assert (first_directory / filename).read_bytes() == (
            second_directory / filename
        ).read_bytes()

    manifest = json.loads((first_directory / "manifest.json").read_text())
    receipt = json.loads((first_directory / "receipt.json").read_text())
    assert manifest["decision"] == "BLOCKED"
    assert receipt["adapter"]["mode"] == "fixture"
    assert receipt["terminal_disposition"] == "VALIDATED"


@pytest.mark.parametrize(
    ("scenario", "code"),
    [
        ("stale-source.json", "SOURCE_FINGERPRINT_MISMATCH"),
        ("unauthorized-path.json", "SCOPE_PATH_OUTSIDE_ROOT"),
        ("incomplete-evidence.json", "EVIDENCE_REQUIRED_SOURCE_INCOMPLETE"),
        ("ambiguous-identity.json", "IDENTITY_AMBIGUOUS"),
        ("incompatible-replacement.json", "SPEC_REPLACEMENT_INCOMPATIBLE"),
    ],
)
def test_negative_fixture_refuses_without_mutation(
    scenario: str,
    code: str,
    tmp_path: Path,
) -> None:
    source = ROOT / "fixtures/repository/models/order_summary.sql"
    content_before = source.read_bytes()

    with pytest.raises(Refusal, match=code):
        run_fixture(
            SPECIFICATION,
            scenario_path=SCENARIOS / scenario,
            output_directory=tmp_path / "evidence",
        )

    assert source.read_bytes() == content_before

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from retirement_conductor.errors import Refusal
from retirement_conductor.schemas import validate_schema
from retirement_conductor.specification import load_specification

ROOT = Path(__file__).resolve().parents[2]
VALID_SPEC = ROOT / "fixtures/specs/valid.yaml"


def test_valid_specification_normalizes_with_digest() -> None:
    specification = load_specification(VALID_SPEC)

    assert specification["api_version"] == "retirement-conductor/v1alpha1"
    assert specification["target"]["field"] == "legacy_status"
    assert specification["replacement"]["field"] == "order_status"
    assert specification["specification_digest"].startswith("sha256:")


@pytest.mark.parametrize(
    ("filename", "code"),
    [
        ("identical-fields.yaml", "SPEC_IDENTICAL_FIELDS"),
        ("invalid-replacement.yaml", "SPEC_UNSUPPORTED_REPLACEMENT"),
        ("malformed.yaml", "SPEC_SCHEMA_INVALID"),
    ],
)
def test_invalid_specifications_refuse_with_stable_codes(
    filename: str,
    code: str,
) -> None:
    with pytest.raises(Refusal, match=code):
        load_specification(ROOT / "fixtures/specs" / filename)


def test_unknown_critical_field_is_rejected() -> None:
    value = yaml.safe_load(VALID_SPEC.read_text(encoding="utf-8"))
    value["authorization"]["bypass_gate"] = True

    with pytest.raises(Refusal, match="SPEC_SCHEMA_INVALID") as captured:
        validate_schema("retirement-spec", value)

    assert "Additional properties" in captured.value.details["error"]


def test_missing_required_field_is_rejected() -> None:
    value = yaml.safe_load(VALID_SPEC.read_text(encoding="utf-8"))
    invalid = deepcopy(value)
    del invalid["target"]["field"]

    with pytest.raises(Refusal, match="SPEC_SCHEMA_INVALID"):
        validate_schema("retirement-spec", invalid)

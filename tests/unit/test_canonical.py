from __future__ import annotations

import json

import pytest

from retirement_conductor.canonical import (
    canonical_json,
    digest_json,
    verify_digest,
    with_digest,
)
from retirement_conductor.errors import Refusal


def test_canonical_json_ignores_mapping_and_whitespace_order() -> None:
    first = {"z": [3, 2, 1], "a": {"enabled": True}}
    second = json.loads(' { "a": { "enabled": true }, "z": [3, 2, 1] } ')

    assert canonical_json(first) == canonical_json(second)
    assert digest_json(first) == digest_json(second)


def test_digest_verification_detects_change() -> None:
    artifact = with_digest({"campaign": "one", "decision": "BLOCKED"}, "digest")
    verify_digest(artifact, "digest")
    artifact["decision"] = "READY_TO_RETIRE"

    with pytest.raises(Refusal, match="INTEGRITY_DIGEST_MISMATCH"):
        verify_digest(artifact, "digest")


def test_non_json_numbers_are_rejected() -> None:
    with pytest.raises(ValueError):
        canonical_json({"invalid": float("nan")})

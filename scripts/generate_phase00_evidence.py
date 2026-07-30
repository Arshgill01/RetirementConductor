#!/usr/bin/env python3
"""Generate deterministic, public-safe phase 00 inspection artifacts."""

from __future__ import annotations

import platform
import sys
from importlib.metadata import metadata
from pathlib import Path
from typing import Any

from retirement_conductor.canonical import digest_file, write_json
from retirement_conductor.errors import Refusal
from retirement_conductor.fixtures import run_fixture
from retirement_conductor.specification import load_specification

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts/public/phase00"

SPEC_REFUSALS = {
    "identical-fields.yaml": "SPEC_IDENTICAL_FIELDS",
    "invalid-replacement.yaml": "SPEC_UNSUPPORTED_REPLACEMENT",
    "malformed.yaml": "SPEC_SCHEMA_INVALID",
}
SCENARIO_REFUSALS = {
    "ambiguous-identity.json": "IDENTITY_AMBIGUOUS",
    "incompatible-replacement.json": "SPEC_REPLACEMENT_INCOMPATIBLE",
    "incomplete-evidence.json": "EVIDENCE_REQUIRED_SOURCE_INCOMPLETE",
    "stale-source.json": "SOURCE_FINGERPRINT_MISMATCH",
    "unauthorized-path.json": "SCOPE_PATH_OUTSIDE_ROOT",
}
DEPENDENCY_LICENSES = {
    "PyYAML": "MIT",
    "jsonschema": "MIT",
    "mypy": "MIT",
    "pytest": "MIT",
    "ruff": "MIT",
    "types-PyYAML": "Apache-2.0",
    "types-jsonschema": "Apache-2.0",
}


def capture_refusal(action: Any, expected_code: str) -> dict[str, Any]:
    try:
        action()
    except Refusal as refusal:
        if refusal.code != expected_code:
            raise RuntimeError(
                f"expected {expected_code}, observed {refusal.code}"
            ) from refusal
        return {
            "expected_refusal_code": expected_code,
            "observed_refusal_code": refusal.code,
            "result": "REFUSED_WITHOUT_MUTATION",
        }
    raise RuntimeError(f"expected refusal was not raised: {expected_code}")


def dependency_report() -> dict[str, Any]:
    packages: list[dict[str, str]] = []
    for name, reviewed_license in sorted(DEPENDENCY_LICENSES.items()):
        package = metadata(name)
        observed_license = (
            package.get("License-Expression") or package.get("License") or "unreported"
        )
        if observed_license != reviewed_license:
            raise RuntimeError(
                f"license drift for {name}: {observed_license} != {reviewed_license}"
            )
        packages.append(
            {
                "name": package["Name"],
                "version": package["Version"],
                "observed_license": observed_license,
                "review": "compatible with Apache-2.0",
            }
        )
    return {
        "schema_version": "1.0.0",
        "python_version": platform.python_version(),
        "packages": packages,
        "limitations": [
            "Build-backend metadata is reviewed in docs/DEPENDENCIES.md and uv.lock."
        ],
    }


def run() -> int:
    specification = ROOT / "fixtures/specs/valid.yaml"
    source = ROOT / "fixtures/repository/models/order_summary.sql"
    source_before = source.read_bytes()
    run_fixture(specification, output_directory=OUTPUT)

    refusals: list[dict[str, Any]] = []
    for filename, code in sorted(SPEC_REFUSALS.items()):
        result = capture_refusal(
            lambda filename=filename: load_specification(
                ROOT / "fixtures/specs" / filename
            ),
            code,
        )
        refusals.append({"fixture": f"specs/{filename}", **result})
    for filename, code in sorted(SCENARIO_REFUSALS.items()):
        result = capture_refusal(
            lambda filename=filename: run_fixture(
                specification,
                scenario_path=ROOT / "fixtures/scenarios" / filename,
                output_directory=OUTPUT / "negative-output-must-not-exist",
            ),
            code,
        )
        refusals.append({"fixture": f"scenarios/{filename}", **result})

    if source.read_bytes() != source_before:
        raise RuntimeError("a refusal fixture mutated its source")
    write_json(
        OUTPUT / "refusal-matrix.json",
        {
            "schema_version": "1.0.0",
            "source_fingerprint": digest_file(source),
            "source_unchanged": True,
            "cases": refusals,
        },
    )
    write_json(OUTPUT / "dependencies.json", dependency_report())
    print(
        "Phase 00 artifacts generated: "
        f"{len(refusals)} refusal cases, source unchanged."
    )
    return 0


if __name__ == "__main__":
    sys.exit(run())

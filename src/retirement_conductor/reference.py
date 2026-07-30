"""Installed public-safe reference campaign."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from retirement_conductor.fixtures import run_fixture


def reference_specification_path() -> Path:
    """Locate the built-in reference specification in a wheel or checkout."""

    packaged = Path(__file__).resolve().parent / "reference_data" / "spec.yaml"
    if packaged.is_file():
        return packaged
    return Path(__file__).resolve().parents[2] / "fixtures" / "specs" / "valid.yaml"


def run_reference_fixture(output_directory: Path) -> dict[str, Any]:
    """Run the deterministic non-live reference without external input."""

    return run_fixture(
        reference_specification_path(),
        output_directory=output_directory,
    )

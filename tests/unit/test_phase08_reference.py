from __future__ import annotations

from pathlib import Path

import pytest

from scripts.run_phase04_end_to_end import (
    command_execution_mode,
    product_command,
)


def test_phase04_runner_can_bind_every_product_call_to_installed_cli(
    tmp_path: Path,
) -> None:
    executable = tmp_path / "retirement-conductor"
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    executable.chmod(0o700)
    original = [
        "uv",
        "run",
        "retirement-conductor",
        "campaign",
        "evaluate",
    ]

    assert product_command(
        original,
        {"RETIREMENT_CONDUCTOR_CLI": str(executable)},
    ) == [str(executable), "campaign", "evaluate"]
    assert (
        command_execution_mode(
            original,
            {"RETIREMENT_CONDUCTOR_CLI": str(executable)},
        )
        == "installed-product-cli"
    )
    assert product_command(original, {}) == original
    assert command_execution_mode(original, {}) == "source-product-cli"
    assert product_command(
        ["uv", "run", "python", "scripts/datahub_seed.py"],
        {"RETIREMENT_CONDUCTOR_CLI": str(executable)},
    ) == ["uv", "run", "python", "scripts/datahub_seed.py"]
    assert (
        command_execution_mode(
            ["uv", "run", "python", "scripts/datahub_seed.py"],
            {"RETIREMENT_CONDUCTOR_CLI": str(executable)},
        )
        == "orchestration"
    )


def test_phase04_runner_refuses_missing_installed_cli(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="installed product command"):
        product_command(
            ["uv", "run", "retirement-conductor", "campaign", "evaluate"],
            {"RETIREMENT_CONDUCTOR_CLI": str(tmp_path / "missing")},
        )

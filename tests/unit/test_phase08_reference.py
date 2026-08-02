from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts import reference_services
from scripts.run_phase04_end_to_end import (
    Runner,
    command_execution_mode,
    product_command,
    wait_for_publication,
)


def git(repository: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=repository,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()


def test_mcp_release_tag_must_resolve_to_the_pinned_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    git(tmp_path, "init")
    git(tmp_path, "config", "user.name", "Test")
    git(tmp_path, "config", "user.email", "test@example.invalid")
    source = tmp_path / "source.txt"
    source.write_text("pinned\n", encoding="utf-8")
    git(tmp_path, "add", source.name)
    git(tmp_path, "commit", "-m", "pinned source")
    commit = git(tmp_path, "rev-parse", "HEAD")
    git(tmp_path, "tag", "v-test")
    monkeypatch.setattr(reference_services, "MCP_COMMIT", commit)
    monkeypatch.setattr(reference_services, "MCP_TAG", "v-test")

    reference_services._ensure_mcp_release_tag(tmp_path)

    assert git(tmp_path, "rev-list", "-n", "1", "v-test") == commit


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


def test_publication_wait_records_pending_refusal_then_named_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = iter(
        [
            subprocess.CompletedProcess(
                args=["retirement-conductor"],
                returncode=2,
                stdout=json.dumps(
                    {
                        "result": "REFUSED",
                        "refusal_code": "EVIDENCE_PUBLICATION_MISMATCH",
                    }
                ),
                stderr="",
            ),
            subprocess.CompletedProcess(
                args=["retirement-conductor"],
                returncode=0,
                stdout=json.dumps(
                    {
                        "result": "VERIFIED",
                        "publication": {"readback_verified": True},
                    }
                ),
                stderr="",
            ),
        ]
    )

    def fake_run(
        *args: object,
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        del args, kwargs
        return next(responses)

    monkeypatch.setattr(
        "scripts.run_phase04_end_to_end.subprocess.run",
        fake_run,
    )
    monkeypatch.setattr(
        "scripts.run_phase04_end_to_end.time.sleep",
        lambda _: None,
    )
    runner = Runner(tmp_path, {})

    result, settle = wait_for_publication(
        runner=runner,
        name="campaign-verify-publication",
        arguments=["retirement-conductor"],
    )

    assert result["result"] == "VERIFIED"
    assert settle["attempts"] == 2
    assert [item.name for item in runner.observations] == [
        "campaign-verify-publication-pending-01",
        "campaign-verify-publication",
    ]
    assert (
        tmp_path / "commands/001-campaign-verify-publication-pending-01.json"
    ).is_file()
    assert (tmp_path / "commands/002-campaign-verify-publication.json").is_file()

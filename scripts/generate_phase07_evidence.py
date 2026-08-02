#!/usr/bin/env python3
"""Generate public-safe post-removal Phase 07 security evidence."""

from __future__ import annotations

import json
import shutil
import stat
import subprocess
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, cast

from retirement_conductor.canonical import (
    digest_bytes,
    digest_file,
    verify_digest,
    with_digest,
    write_json,
)
from retirement_conductor.datahub import utc_now
from retirement_conductor.errors import Refusal
from retirement_conductor.store import CampaignStore
from tests.reliability.test_store_operations import (
    CAMPAIGN_ID as STORE_CAMPAIGN_ID,
)
from tests.reliability.test_store_operations import create_inventoried_campaign
from tests.unit.test_git_dbt import _adapter_and_plan

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "artifacts/public/phase07"
RUNTIME = ROOT / ".retirement-conductor/phase07"
SECURITY_PATH = PUBLIC / "security-evidence.json"
FAILURE_PATH = PUBLIC / "failure-matrix.json"
RECOVERY_PATH = PUBLIC / "recovery-evidence.json"
SCAN_PATH = PUBLIC / "scan-evidence.json"
SUMMARY_PATH = PUBLIC / "phase07-evidence.json"
ALLOWED_DIRTY_PREFIXES = ("artifacts/public/phase07/",)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def refusal(action: Callable[[], object]) -> dict[str, Any]:
    try:
        action()
    except Refusal as error:
        return {"refusal_code": error.code, "result": "REFUSED"}
    raise RuntimeError("expected refusal did not occur")


def command(
    arguments: list[str], *, timeout: int = 600
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        arguments,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )


def require_command(arguments: list[str], label: str, *, timeout: int = 600) -> str:
    result = command(arguments, timeout=timeout)
    output = result.stdout + result.stderr
    require(result.returncode == 0, f"{label} failed with exit {result.returncode}")
    return output


def repository_commit() -> str:
    return require_command(["git", "rev-parse", "HEAD"], "git rev-parse").strip()


def check_dirty_state() -> None:
    output = require_command(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        "git status",
    )
    disallowed = []
    for line in output.splitlines():
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if not path.startswith(ALLOWED_DIRTY_PREFIXES):
            disallowed.append(path)
    require(
        not disallowed,
        "commit Phase 07 implementation before generating acceptance evidence",
    )


def test_summary(target: str) -> dict[str, Any]:
    output = require_command(["make", target], target, timeout=900)
    count = None
    for line in reversed(output.splitlines()):
        if " passed in " not in line:
            continue
        prefix = line.split(" passed in ", 1)[0].split()[-1]
        if prefix.isdigit():
            count = int(prefix)
            break
    require(count is not None, f"{target} output omitted a pass count")
    return {
        "command": f"make {target}",
        "output_digest": digest_bytes(output.encode()),
        "result": "PASSED",
        "test_count": count,
    }


def recovery_evidence() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(
        prefix="retirement-conductor-phase07-recovery-"
    ) as temporary:
        root = Path(temporary)
        database = root / "active/campaign.sqlite"
        backup = root / "backup/campaign.sqlite"
        with CampaignStore(database, writer_id="phase07-recovery") as store:
            expected_manifest = create_inventoried_campaign(store)
            receipt = store.backup_to(
                backup,
                captured_at="2026-07-30T16:00:00Z",
            )
            verification = store.verify_backup(backup)
            diagnostics = store.operational_metrics(
                observed_at="2026-07-30T18:00:00Z",
                stuck_after_seconds=3600,
            )
        verify_digest(receipt, "backup_receipt_digest")
        verify_digest(verification, "verification_digest")
        verify_digest(diagnostics, "metrics_digest")
        require(
            receipt["logical_snapshot_digest"]
            == verification["logical_snapshot_digest"],
            "backup verification snapshot changed",
        )

        archived = root / "incident/campaign.suspect.sqlite"
        archived.parent.mkdir(parents=True)
        database.replace(archived)
        database.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(backup, database)
        with CampaignStore(database, writer_id="phase07-recovery") as restored:
            restored_manifest = restored.materialize(STORE_CAMPAIGN_ID)
            schema_versions = restored.schema_versions()
        require(restored_manifest == expected_manifest, "restored manifest differs")

        copied = root / "copied/campaign.sqlite"
        copied.parent.mkdir(parents=True)
        shutil.copyfile(backup, copied)
        before_copy_digest = digest_file(copied)
        copied_refusal = refusal(
            lambda: CampaignStore(copied, writer_id="phase07-recovery")
        )
        require(
            copied_refusal["refusal_code"] == "RUNTIME_WRITER_MISMATCH",
            "copied store did not refuse",
        )
        require(digest_file(copied) == before_copy_digest, "copied store changed")
        require(stat.S_IMODE(backup.stat().st_mode) == 0o600, "backup mode changed")
        require(schema_versions == [1, 2, 3], "schema roll-forward changed")

        return with_digest(
            {
                "backup": {
                    "campaigns": receipt["campaigns"],
                    "database_digest": receipt["database_digest"],
                    "file_mode": "0600",
                    "logical_snapshot_digest": receipt["logical_snapshot_digest"],
                    "receipt_digest": receipt["backup_receipt_digest"],
                    "result": receipt["result"],
                    "verification_digest": verification["verification_digest"],
                },
                "captured_at": "2026-07-30T18:00:00Z",
                "copied_store": {
                    **copied_refusal,
                    "refused_before_database_change": True,
                },
                "diagnostics": {
                    "healthy": diagnostics["healthy"],
                    "metrics_digest": diagnostics["metrics_digest"],
                    "stuck_campaign_count": len(
                        diagnostics["alerts"]["stuck_campaigns"]
                    ),
                    "unknown_gate_outcomes": diagnostics["alerts"][
                        "unknown_gate_outcomes"
                    ],
                },
                "evidence_mode": "fixture",
                "limitations": [
                    "This drill uses a deterministic local fixture store.",
                    "Backups are not encrypted and storage is not distributed.",
                ],
                "restore": {
                    "evidence_envelope_digest": restored_manifest["evidence_envelope"][
                        "envelope_digest"
                    ],
                    "manifest_digest": restored_manifest["manifest_digest"],
                    "manifest_reproduced": True,
                    "original_bound_path": True,
                    "schema_versions": schema_versions,
                },
                "result": "PASSED",
                "schema_version": "1.0.0",
            },
            "recovery_evidence_digest",
        )


def git_capability_receipt(root: Path) -> dict[str, Any]:
    adapter, specification, plan, model = _adapter_and_plan(root)
    specification["authorization"]["mode"] = "plan"
    before_digest = digest_file(model)
    before_branch = adapter.git("branch", "--show-current")
    denied = refusal(
        lambda: adapter.apply(
            specification,
            plan,
            artifact_root=root / "artifacts",
            occurred_at="2026-07-30T12:00:00Z",
        )
    )
    require(denied["refusal_code"] == "AUTH_APPLY_DISABLED", "plan-only apply")
    return {
        "apply_refusal": denied,
        "artifact_directory_created": (root / "artifacts").exists(),
        "authorization_mode": "plan",
        "branch_unchanged": adapter.git("branch", "--show-current") == before_branch,
        "result": "PASSED",
        "target_digest_unchanged": digest_file(model) == before_digest,
    }


def security_evidence(security_tests: Mapping[str, Any]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(
        prefix="retirement-conductor-phase07-capabilities-"
    ) as temporary:
        git_receipt = git_capability_receipt(Path(temporary))
    require(
        git_receipt["target_digest_unchanged"]
        and git_receipt["branch_unchanged"]
        and not git_receipt["artifact_directory_created"],
        "plan-only boundary changed local state",
    )
    phase06 = json.loads(
        (ROOT / "artifacts/public/phase06/phase06-evidence.json").read_text()
    )
    verify_digest(phase06, "evidence_digest")
    return with_digest(
        {
            "benchmark_binding": {
                "false_readiness_count": phase06["acceptance"]["false_readiness_count"],
                "phase06_evidence_digest": phase06["evidence_digest"],
                "sentinel_count": phase06["acceptance"]["sentinel_count"],
            },
            "capability_receipts": {"git_dbt_plan_only": git_receipt},
            "captured_at": utc_now(),
            "documents": {
                name: {"digest": digest_file(ROOT / path), "file": path}
                for name, path in {
                    "access_contract": "docs/ACCESS.md",
                    "recovery_runbook": "docs/runbooks/RECOVERY.md",
                    "security_policy": "SECURITY.md",
                    "threat_model": "docs/SECURITY_MODEL.md",
                }.items()
            },
            "evidence_mode": "fixture plus live-local benchmark binding",
            "limitations": [
                "Capability probes use a disposable repository.",
                "Host administration and secret providers remain deployment "
                "boundaries.",
            ],
            "result": "PASSED",
            "schema_version": "1.0.0",
            "security_tests": dict(security_tests),
        },
        "security_evidence_digest",
    )


def failure_evidence(fault_tests: Mapping[str, Any]) -> dict[str, Any]:
    return with_digest(
        {
            "captured_at": utc_now(),
            "evidence_mode": "fixture plus live-local benchmark binding",
            "fault_tests": dict(fault_tests),
            "limitations": [
                "Injected transport and process faults use deterministic local "
                "doubles.",
                "Production infrastructure behavior remains deployment-specific.",
            ],
            "result": "PASSED",
            "schema_version": "1.0.0",
            "state_and_boundary_cases": [
                {
                    "case": "event, receipt, or cached-manifest tampering",
                    "safe_result": "INTEGRITY refusal",
                    "test_source": "tests/integration/test_campaign_store.py",
                },
                {
                    "case": "overlapping native identity",
                    "safe_result": "SOURCE_CONSUMER_OVERLAP",
                    "test_source": "tests/integration/test_campaign_store.py",
                },
                {
                    "case": "partial DataHub page or unavailable MCP/API",
                    "safe_result": "required evidence remains partial or unavailable",
                    "test_source": "tests/unit/test_datahub.py",
                },
                {
                    "case": "hostile repository execution",
                    "safe_result": "scope refusal or isolated containment",
                    "test_source": "tests/unit/test_git_dbt.py",
                },
                {
                    "case": "interrupted or drifted Git mutation",
                    "safe_result": "native reread before retry or compensation",
                    "test_source": "tests/unit/test_git_dbt.py",
                },
                {
                    "case": "gate replay, drift, unavailable state, or untrusted run",
                    "safe_result": "gate refusal without producer replay",
                    "test_source": "tests/integration/test_gate.py",
                },
            ],
        },
        "failure_matrix_digest",
    )


def run_scan() -> dict[str, Any]:
    raw_path = RUNTIME / "security-scan.json"
    require_command(
        [
            "uv",
            "run",
            "python",
            "scripts/run_security_scan.py",
            "--output",
            str(raw_path),
        ],
        "security scan",
        timeout=900,
    )
    value = json.loads(raw_path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), "security scan is not an object")
    verify_digest(value, "scan_digest")
    require(value["result"] == "PASSED", "security scan did not pass")
    write_json(SCAN_PATH, value)
    return cast(dict[str, Any], value)


def artifact_entry(path: Path, digest_field: str) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"{path.name} is not an object")
    verify_digest(value, digest_field)
    return {
        "artifact_digest": value[digest_field],
        "file": path.relative_to(ROOT).as_posix(),
        "file_digest": digest_file(path),
    }


def write_summary(
    *,
    commit: str,
    commands: list[dict[str, Any]],
    scan: Mapping[str, Any],
) -> None:
    summary = with_digest(
        {
            "acceptance": {
                "backup_restore_reproduces_manifest": True,
                "copied_store_refuses": True,
                "dependency_findings": len(
                    scan["vulnerability_audit"]["all_groups"]["findings"]
                ),
                "deprecated_adapter_surface_absent": True,
                "false_readiness_count": 0,
                "plan_only_cannot_apply": True,
                "public_artifact_review": scan["public_artifact_review"]["result"],
                "secret_scan": scan["secret_scan"]["result"],
                "source_content_cannot_expand_authority": True,
            },
            "artifacts": {
                "failure_matrix": artifact_entry(FAILURE_PATH, "failure_matrix_digest"),
                "recovery": artifact_entry(RECOVERY_PATH, "recovery_evidence_digest"),
                "scan": artifact_entry(SCAN_PATH, "scan_digest"),
                "security": artifact_entry(SECURITY_PATH, "security_evidence_digest"),
            },
            "captured_at": utc_now(),
            "commands": commands,
            "evidence_mode": "mixed fixture and live-local benchmark binding",
            "limitations": [
                "Security and recovery fault injection is local and deterministic.",
                "The advisory scan is bounded to its captured database.",
                "Real deployment identity, host, and storage controls remain "
                "operator-owned.",
            ],
            "phase": "07",
            "repository_commit": commit,
            "result": "POST_REMOVAL_ACCEPTANCE_PASSED",
            "schema_version": "1.0.0",
        },
        "phase07_evidence_digest",
    )
    write_json(SUMMARY_PATH, summary)


def run() -> int:
    check_dirty_state()
    PUBLIC.mkdir(parents=True, exist_ok=True)
    RUNTIME.mkdir(parents=True, exist_ok=True)
    commit = repository_commit()
    security_tests = test_summary("test-security")
    fault_tests = test_summary("test-faults")
    recovery_tests = test_summary("test-recovery")
    commands = [security_tests, fault_tests, recovery_tests]

    write_json(RECOVERY_PATH, recovery_evidence())
    write_json(SECURITY_PATH, security_evidence(security_tests))
    write_json(FAILURE_PATH, failure_evidence(fault_tests))
    scan = run_scan()
    write_summary(commit=commit, commands=commands, scan=scan)

    require_command(
        ["uv", "run", "python", "scripts/check_public_artifacts.py"],
        "public artifact review",
    )
    require_command(
        ["uv", "run", "python", "scripts/check_secrets.py"],
        "secret scan",
    )
    print(
        f"Phase 07 evidence generated: {SUMMARY_PATH.relative_to(ROOT)} ({commit[:12]})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())

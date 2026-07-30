#!/usr/bin/env python3
"""Exercise and publish public-safe phase 03 Git/dbt evidence."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from retirement_conductor.canonical import (
    digest_bytes,
    digest_file,
    digest_json,
    verify_digest,
    with_digest,
    write_json,
)
from retirement_conductor.datahub import utc_now
from retirement_conductor.errors import Refusal
from retirement_conductor.events import event_stream_digest
from retirement_conductor.git_dbt import (
    GitDbtAdapter,
    checked_target_path,
    reject_unsafe_tree,
    replace_identifier_once,
    resolve_replacement_evidence,
)
from retirement_conductor.git_dbt_config import GitDbtSettings
from retirement_conductor.schemas import validate_schema
from retirement_conductor.specification import load_specification
from retirement_conductor.store import CampaignStore

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".retirement-conductor"
CAMPAIGN_ID = "ret-orders-git-dbt"
GIT_ROOT = RUNTIME / "artifacts" / CAMPAIGN_ID / "git-dbt"
REPOSITORY = (RUNTIME / "workspaces" / "ret-orders-git-dbt" / "repository").resolve()
TEMPLATE = ROOT / "fixtures" / "git-dbt-project"
OUTPUT = ROOT / "artifacts" / "public" / "phase03"
CONSUMER_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:dbt,"
    "retirement_conductor.analytics.consumers.orders_model_00,PROD)"
)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected object artifact: {path.name}")
    return value


def git(repository: Path, *arguments: str) -> str:
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "LC_ALL": "C.UTF-8",
        "GIT_AUTHOR_NAME": "Retirement Conductor Probe",
        "GIT_AUTHOR_EMAIL": "probe@retirement-conductor.invalid",
        "GIT_COMMITTER_NAME": "Retirement Conductor Probe",
        "GIT_COMMITTER_EMAIL": "probe@retirement-conductor.invalid",
    }
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
        timeout=30,
    )
    return result.stdout.rstrip("\r\n")


def prepare_repository(parent: Path, name: str) -> Path:
    repository = parent / name / "repository"
    shutil.copytree(TEMPLATE, repository)
    git(repository, "init", "--initial-branch=main")
    git(repository, "add", "--all")
    git(repository, "commit", "-m", "probe: initialize dbt project")
    return repository


def settings(repository: Path, *, allow_apply: bool = True) -> GitDbtSettings:
    git_executable = shutil.which("git")
    bwrap_executable = shutil.which("bwrap")
    if git_executable is None or bwrap_executable is None:
        raise RuntimeError("Git and bubblewrap are required for phase 03 evidence")
    dbt = RUNTIME / "tools" / "dbt-duckdb-1.10.1" / "bin" / "dbt"
    if not dbt.is_file():
        raise RuntimeError("run `make git-dbt-tool` before phase 03 evidence")
    return GitDbtSettings(
        repository_root=repository.resolve(),
        repository_id="analytics",
        default_branch="main",
        dbt_executable=dbt.resolve(),
        principal="local-disposable-operator",
        allow_apply=allow_apply,
        validation_timeout_seconds=180,
        bwrap_executable=Path(bwrap_executable).resolve(),
        git_executable=Path(git_executable).resolve(),
    )


def specification(repository: Path, campaign_id: str) -> dict[str, Any]:
    value = load_specification(ROOT / "fixtures" / "specs" / "git-dbt-live.yaml")
    value["campaign"]["id"] = campaign_id
    value["evidence"]["repositories"][0]["path"] = str(repository.resolve())
    return value


def plan_for(
    repository: Path,
    campaign_id: str,
    *,
    target_branch: str,
) -> dict[str, Any]:
    model = repository / "models" / "orders_model_00.sql"
    before = model.read_text(encoding="utf-8")
    after = replace_identifier_once(before, "legacy_status", "order_status")
    source_version = git(repository, "rev-parse", "HEAD")
    return with_digest(
        {
            "schema_version": "1.0.0",
            "campaign_id": campaign_id,
            "consumer_id": "phase03-probe-consumer",
            "datahub_urn": CONSUMER_URN,
            "repository": {
                "id": "analytics",
                "identity": digest_json(str(repository.resolve())),
                "default_branch": "main",
                "source_branch": "main",
                "source_version": source_version,
                "target_branch": target_branch,
            },
            "native_identity": {
                "source_domain": "git-dbt",
                "repository_id": "analytics",
                "path": "models/orders_model_00.sql",
            },
            "target": {
                "path": "models/orders_model_00.sql",
                "before_token": "legacy_status",
                "after_token": "order_status",
                "before_fingerprint": digest_bytes(before.encode()),
                "after_fingerprint": digest_bytes(after.encode()),
            },
            "replacement": {
                "compatible": True,
                "target_type": "varchar",
                "replacement_type": "varchar",
            },
            "discovery": {"mapping_match_count": 1},
            "validators": ["dbt build", "dbt test"],
            "limitations": ["adversarial public fixture"],
        },
        "plan_digest",
    )


def refusal(operation: Callable[[], object]) -> dict[str, Any]:
    try:
        operation()
    except Refusal as exc:
        return {
            "result": "REFUSED",
            "refusal_code": str(exc.code),
            "message": exc.message,
        }
    raise RuntimeError("probe unexpectedly succeeded")


def native_validation_probe(
    parent: Path,
    name: str,
    content: str,
) -> tuple[dict[str, Any], Path]:
    repository = prepare_repository(parent, name)
    model = repository / "models" / "orders_model_00.sql"
    model.write_text(content, encoding="utf-8")
    git(repository, "add", "--all")
    git(repository, "commit", "-m", f"probe: {name}")
    artifact_root = parent / name / "artifacts"
    result = GitDbtAdapter(settings(repository)).validate_project(
        artifact_root=artifact_root
    )
    return result, artifact_root


def run_adversarial_probes(parent: Path) -> dict[str, Any]:
    occurred_at = utc_now()

    plan_only_repo = prepare_repository(parent, "plan-only")
    plan_only_plan = plan_for(
        plan_only_repo,
        "phase03-plan-only",
        target_branch="codex/phase03-plan-only",
    )
    plan_only_before = {
        "head": git(plan_only_repo, "rev-parse", "HEAD"),
        "branch": git(plan_only_repo, "branch", "--show-current"),
        "fingerprint": digest_file(plan_only_repo / "models" / "orders_model_00.sql"),
    }
    plan_only_result = refusal(
        lambda: GitDbtAdapter(settings(plan_only_repo, allow_apply=False)).apply(
            specification(plan_only_repo, "phase03-plan-only"),
            plan_only_plan,
            artifact_root=parent / "plan-only" / "artifacts",
            occurred_at=occurred_at,
        )
    )
    plan_only_after = {
        "head": git(plan_only_repo, "rev-parse", "HEAD"),
        "branch": git(plan_only_repo, "branch", "--show-current"),
        "fingerprint": digest_file(plan_only_repo / "models" / "orders_model_00.sql"),
    }
    plan_only_result["unchanged"] = plan_only_before == plan_only_after

    stale_repo = prepare_repository(parent, "stale-content")
    stale_plan = plan_for(
        stale_repo,
        "phase03-stale-content",
        target_branch="codex/phase03-stale-content",
    )
    stale_model = stale_repo / "models" / "orders_model_00.sql"
    intervening = stale_model.read_text(encoding="utf-8") + "-- owner edit\n"
    stale_model.write_text(intervening, encoding="utf-8")
    stale_result = refusal(
        lambda: GitDbtAdapter(settings(stale_repo)).apply(
            specification(stale_repo, "phase03-stale-content"),
            stale_plan,
            artifact_root=parent / "stale-content" / "artifacts",
            occurred_at=occurred_at,
        )
    )
    stale_result["intervening_edit_preserved"] = (
        stale_model.read_text(encoding="utf-8") == intervening
    )

    moved_repo = prepare_repository(parent, "branch-moved")
    moved_plan = plan_for(
        moved_repo,
        "phase03-branch-moved",
        target_branch="codex/phase03-branch-moved",
    )
    readme = moved_repo / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8") + "\nMoved after plan.\n",
        encoding="utf-8",
    )
    git(moved_repo, "add", "README.md")
    git(moved_repo, "commit", "-m", "probe: move source commit")
    moved_head = git(moved_repo, "rev-parse", "HEAD")
    moved_result = refusal(
        lambda: GitDbtAdapter(settings(moved_repo)).apply(
            specification(moved_repo, "phase03-branch-moved"),
            moved_plan,
            artifact_root=parent / "branch-moved" / "artifacts",
            occurred_at=occurred_at,
        )
    )
    moved_result["moved_head_preserved"] = (
        git(moved_repo, "rev-parse", "HEAD") == moved_head
    )

    expanded_repo = prepare_repository(parent, "expanded-target")
    expanded_plan = plan_for(
        expanded_repo,
        "phase03-expanded-target",
        target_branch="codex/phase03-expanded-target",
    )
    git(expanded_repo, "switch", "-c", "codex/phase03-expanded-target")
    expanded_model = expanded_repo / "models" / "orders_model_00.sql"
    expanded_model.write_text(
        replace_identifier_once(
            expanded_model.read_text(encoding="utf-8"),
            "legacy_status",
            "order_status",
        ),
        encoding="utf-8",
    )
    expanded_readme = expanded_repo / "README.md"
    expanded_readme.write_text(
        expanded_readme.read_text(encoding="utf-8") + "\nUnexpected edit.\n",
        encoding="utf-8",
    )
    expanded_result = refusal(
        lambda: GitDbtAdapter(settings(expanded_repo)).apply(
            specification(expanded_repo, "phase03-expanded-target"),
            expanded_plan,
            artifact_root=parent / "expanded-target" / "artifacts",
            occurred_at=occurred_at,
        )
    )
    expanded_result["actual_changed_paths"] = sorted(
        line[3:]
        for line in git(
            expanded_repo,
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        ).splitlines()
    )

    unauthorized_repo = prepare_repository(parent, "unauthorized-target")
    unauthorized_plan = plan_for(
        unauthorized_repo,
        "phase03-unauthorized-target",
        target_branch="codex/phase03-unauthorized-target",
    )
    unauthorized_plan["target"]["path"] = "README.md"
    unauthorized_plan = with_digest(unauthorized_plan, "plan_digest")
    unauthorized_result = refusal(
        lambda: GitDbtAdapter(settings(unauthorized_repo)).apply(
            specification(unauthorized_repo, "phase03-unauthorized-target"),
            unauthorized_plan,
            artifact_root=parent / "unauthorized-target" / "artifacts",
            occurred_at=occurred_at,
        )
    )
    unauthorized_result["branch_unchanged"] = (
        git(unauthorized_repo, "branch", "--show-current") == "main"
    )

    hook_repo = prepare_repository(parent, "malicious-hook")
    hook_plan = plan_for(
        hook_repo,
        "phase03-malicious-hook",
        target_branch="codex/phase03-malicious-hook",
    )
    hook_marker = parent / "malicious-hook" / "escaped-marker"
    hook = hook_repo / ".git" / "hooks" / "post-commit"
    hook.write_text(
        f"#!/bin/sh\n/usr/bin/touch '{hook_marker}'\nexit 99\n",
        encoding="utf-8",
    )
    hook.chmod(0o700)
    hook_adapter = GitDbtAdapter(settings(hook_repo))
    hook_apply = hook_adapter.apply(
        specification(hook_repo, "phase03-malicious-hook"),
        hook_plan,
        artifact_root=parent / "malicious-hook" / "artifacts",
        occurred_at=occurred_at,
    )
    hook_replay = hook_adapter.apply(
        specification(hook_repo, "phase03-malicious-hook"),
        hook_plan,
        artifact_root=parent / "malicious-hook" / "artifacts",
        occurred_at=occurred_at,
    )
    hook_result = {
        "result": "HOOK_SKIPPED",
        "marker_created": hook_marker.exists(),
        "apply_digest": hook_apply["apply_digest"],
        "replay_digest": hook_replay["apply_digest"],
        "idempotent": (
            hook_apply["apply_digest"] == hook_replay["apply_digest"]
            and len(
                git(
                    hook_repo,
                    "rev-list",
                    "--count",
                    f"{hook_plan['repository']['source_version']}..HEAD",
                )
            )
            > 0
            and git(
                hook_repo,
                "rev-list",
                "--count",
                f"{hook_plan['repository']['source_version']}..HEAD",
            )
            == "1"
        ),
    }

    conflict_repo = prepare_repository(parent, "compensation-conflict")
    conflict_plan = plan_for(
        conflict_repo,
        "phase03-compensation-conflict",
        target_branch="codex/phase03-compensation-conflict",
    )
    conflict_adapter = GitDbtAdapter(settings(conflict_repo))
    conflict_apply = conflict_adapter.apply(
        specification(conflict_repo, "phase03-compensation-conflict"),
        conflict_plan,
        artifact_root=parent / "compensation-conflict" / "artifacts",
        occurred_at=occurred_at,
    )
    conflict_model = conflict_repo / "models" / "orders_model_00.sql"
    conflict_content = (
        conflict_model.read_text(encoding="utf-8") + "-- intervening owner edit\n"
    )
    conflict_model.write_text(conflict_content, encoding="utf-8")
    conflict_result = refusal(
        lambda: conflict_adapter.compensate(
            specification(conflict_repo, "phase03-compensation-conflict"),
            conflict_plan,
            conflict_apply,
            artifact_root=parent / "compensation-conflict" / "artifacts",
            occurred_at=occurred_at,
        )
    )
    conflict_result["intervening_edit_preserved"] = (
        conflict_model.read_text(encoding="utf-8") == conflict_content
    )

    boundary_repo = prepare_repository(parent, "boundary-refusals")
    outside = parent / "outside-source.sql"
    outside.write_text("outside\n", encoding="utf-8")
    symlink = boundary_repo / "models" / "outside.sql"
    symlink.symlink_to(outside)
    symlink_result = refusal(lambda: reject_unsafe_tree(boundary_repo))
    symlink.unlink()
    (boundary_repo / "packages.yml").write_text(
        "packages:\n  - package: dbt-labs/dbt_utils\n    version: 1.3.0\n",
        encoding="utf-8",
    )
    dependency_result = refusal(lambda: reject_unsafe_tree(boundary_repo))
    traversal_result = refusal(
        lambda: checked_target_path(
            boundary_repo,
            "../../outside-source.sql",
            allowed_paths=["models/"],
        )
    )

    manifest = {
        "nodes": {
            "seed.project.orders": {
                "resource_type": "seed",
                "unique_id": "seed.project.orders",
                "columns": {
                    "legacy_status": {"data_type": "varchar"},
                    "order_status": {"data_type": "varchar"},
                },
            }
        }
    }
    incompatible_result = refusal(
        lambda: resolve_replacement_evidence(
            manifest,
            datahub_resolution={
                "target_field": {"nativeDataType": "VARCHAR"},
                "replacement_field": {"nativeDataType": "INTEGER"},
            },
            target_field="legacy_status",
            replacement_field="order_status",
        )
    )
    missing_result = refusal(
        lambda: resolve_replacement_evidence(
            manifest,
            datahub_resolution={
                "target_field": {"nativeDataType": "VARCHAR"},
                "replacement_field": {"nativeDataType": "VARCHAR"},
            },
            target_field="legacy_status",
            replacement_field="missing_replacement",
        )
    )

    base_model = (TEMPLATE / "models" / "orders_model_00.sql").read_text(
        encoding="utf-8"
    )
    wrong_validation, _ = native_validation_probe(
        parent,
        "semantic-wrong",
        replace_identifier_once(base_model, "legacy_status", "order_amount"),
    )

    secret_name = "RC_PHASE03_PROBE_SECRET"
    secret_value = "phase03-host-secret-must-not-cross"
    os.environ[secret_name] = secret_value
    try:
        secret_validation, secret_artifacts = native_validation_probe(
            parent,
            "secret-read",
            "{{ env_var('RC_PHASE03_PROBE_SECRET') }}\nselect 1 as value\n",
        )
    finally:
        os.environ.pop(secret_name, None)
    secret_observed = any(
        secret_value.encode() in path.read_bytes()
        for path in secret_artifacts.rglob("*")
        if path.is_file()
    )

    subprocess_marker = (
        Path("/tmp")
        / f"retirement-conductor-subprocess-{digest_json(str(parent))[-12:]}"
    )
    if subprocess_marker.exists():
        raise RuntimeError("unexpected pre-existing subprocess marker")
    subprocess_validation, _ = native_validation_probe(
        parent,
        "subprocess-attempt",
        (
            "{% set attempted = "
            "modules.subprocess.run(['/usr/bin/touch',"
            f"'{subprocess_marker}']) %}}\n"
            "select 1 as value\n"
        ),
    )

    network_validation, _ = native_validation_probe(
        parent,
        "network-attempt",
        ("select * from read_csv_auto('http://127.0.0.1:9/unreachable.csv')\n"),
    )

    return {
        "plan_only": plan_only_result,
        "stale_content": stale_result,
        "branch_moved": moved_result,
        "expanded_target": expanded_result,
        "unauthorized_target": unauthorized_result,
        "malicious_hook": hook_result,
        "compensation_conflict": conflict_result,
        "symlink_escape": symlink_result,
        "external_dependency": dependency_result,
        "path_traversal": traversal_result,
        "incompatible_replacement": incompatible_result,
        "missing_replacement": missing_result,
        "semantic_wrong": {
            "result": wrong_validation["result"],
            "failed_command": wrong_validation["failed_command"],
            "validation_digest": wrong_validation["validation_digest"],
        },
        "secret_read": {
            "result": secret_validation["result"],
            "failed_command": secret_validation["failed_command"],
            "host_secret_observed": secret_observed,
        },
        "subprocess_attempt": {
            "result": subprocess_validation["result"],
            "failed_command": subprocess_validation["failed_command"],
            "host_marker_created": subprocess_marker.exists(),
        },
        "network_attempt": {
            "result": network_validation["result"],
            "failed_command": network_validation["failed_command"],
            "sandbox_network": network_validation["sandbox"]["network"],
        },
    }


def unique_digest_artifacts(
    pattern: str,
    digest_field: str,
) -> list[dict[str, Any]]:
    values: dict[str, dict[str, Any]] = {}
    for path in GIT_ROOT.glob(pattern):
        value = load_json(path)
        digest = value.get(digest_field)
        if not isinstance(digest, str):
            continue
        verify_digest(value, digest_field)
        values[digest] = value
    return sorted(values.values(), key=lambda item: str(item[digest_field]))


def assert_refusals(probes: Mapping[str, Any]) -> None:
    expected = {
        "plan_only": "AUTH_APPLY_DISABLED",
        "stale_content": "SOURCE_GIT_DIRTY",
        "branch_moved": "SOURCE_GIT_BRANCH_MOVED",
        "expanded_target": "SCOPE_TARGET_NOT_ALLOWED",
        "unauthorized_target": "SCOPE_TARGET_NOT_ALLOWED",
        "compensation_conflict": "COMPENSATION_CONFLICT",
        "symlink_escape": "VALIDATION_SCOPE_VIOLATION",
        "external_dependency": "VALIDATION_SCOPE_VIOLATION",
        "path_traversal": "SCOPE_PATH_OUTSIDE_ROOT",
        "incompatible_replacement": "SPEC_REPLACEMENT_INCOMPATIBLE",
        "missing_replacement": "SPEC_REPLACEMENT_INCOMPATIBLE",
    }
    for name, code in expected.items():
        if probes[name]["refusal_code"] != code:
            raise RuntimeError(f"{name} returned an unexpected refusal")
    required_truths = [
        probes["plan_only"]["unchanged"],
        probes["stale_content"]["intervening_edit_preserved"],
        probes["branch_moved"]["moved_head_preserved"],
        probes["unauthorized_target"]["branch_unchanged"],
        probes["malicious_hook"]["marker_created"] is False,
        probes["malicious_hook"]["idempotent"],
        probes["compensation_conflict"]["intervening_edit_preserved"],
        probes["semantic_wrong"]["result"] == "FAILED",
        probes["secret_read"]["host_secret_observed"] is False,
        probes["subprocess_attempt"]["host_marker_created"] is False,
        probes["network_attempt"]["sandbox_network"] == "unshared",
    ]
    if not all(required_truths):
        raise RuntimeError("one or more phase 03 adversarial assertions failed")


def run() -> int:
    preflight = load_json(GIT_ROOT / "preflight.json")
    binding = load_json(GIT_ROOT / "inventory-binding.json")
    compensation = load_json(GIT_ROOT / "compensation.json")
    compensation_validation = load_json(
        GIT_ROOT / "compensation-validation" / "validation.json"
    )
    validation = load_json(GIT_ROOT / "native-validation" / "validation.json")
    receipt = load_json(GIT_ROOT / "receipt.json")
    for value, field in (
        (preflight, "preflight_digest"),
        (binding, "binding_digest"),
        (compensation, "compensation_digest"),
        (compensation_validation, "validation_digest"),
        (validation, "validation_digest"),
        (receipt, "receipt_digest"),
    ):
        verify_digest(value, field)
    validate_schema("consumer-receipt", receipt)
    plans = unique_digest_artifacts("plan-*.json", "plan_digest")
    applies = unique_digest_artifacts("apply-*.json", "apply_digest")
    if len(plans) != 2 or len(applies) != 2:
        raise RuntimeError("rollback and reapply artifacts were not both retained")
    current_plan = load_json(GIT_ROOT / "plan.json")
    current_apply = load_json(GIT_ROOT / "apply.json")
    if current_apply["plan_digest"] != current_plan["plan_digest"]:
        raise RuntimeError("current apply is not bound to the current plan")
    if compensation["plan_digest"] == current_plan["plan_digest"]:
        raise RuntimeError("compensation did not precede the reapply plan")
    if compensation_validation["result"] != "PASSED":
        raise RuntimeError("compensated source did not pass native validation")
    if validation["result"] != "PASSED":
        raise RuntimeError("current applied source did not pass native validation")
    if receipt["plan"]["digest"] != current_plan["plan_digest"]:
        raise RuntimeError("receipt is not bound to the current plan")
    if receipt["consumer_id"] != binding["selected_consumer_id"]:
        raise RuntimeError("receipt does not map to the selected campaign consumer")
    if receipt["datahub_urn"] != binding["selected_datahub_urn"]:
        raise RuntimeError("receipt does not map to the selected DataHub identity")
    if receipt["native_identity"]["replacement"]["compatible"] is not True:
        raise RuntimeError("receipt omitted replacement compatibility evidence")

    with CampaignStore(
        RUNTIME / "campaigns.sqlite",
        writer_id="local-operator",
    ) as store:
        events = store.events(CAMPAIGN_ID)
        manifest = store.materialize(CAMPAIGN_ID)
    selected = [
        consumer
        for consumer in manifest["consumers"]
        if consumer["id"] == receipt["consumer_id"]
    ]
    if len(selected) != 1 or selected[0]["disposition"] != "VALIDATED":
        raise RuntimeError("campaign did not retain one validated mapped consumer")
    if manifest["campaign"]["state"] != "BLOCKED":
        raise RuntimeError(
            "phase 03 campaign should remain blocked before reconciliation"
        )

    repository_head = git(REPOSITORY, "rev-parse", "HEAD")
    if repository_head not in current_apply["native_change_ids"] or git(
        REPOSITORY, "status", "--porcelain=v1", "--untracked-files=all"
    ):
        raise RuntimeError(
            "current review branch does not match the clean apply receipt"
        )
    changed_paths = git(
        REPOSITORY,
        "diff",
        "--name-only",
        f"{current_plan['repository']['source_version']}..{repository_head}",
    ).splitlines()
    if changed_paths != current_apply["actual_targets"]:
        raise RuntimeError("review branch diff differs from the approved target set")

    probe_root = RUNTIME / "phase03" / "probes"
    probe_root.mkdir(parents=True, exist_ok=True)
    probe_parent = Path(
        tempfile.mkdtemp(
            prefix="run-",
            dir=probe_root.resolve(),
        )
    )
    probes = run_adversarial_probes(probe_parent)
    assert_refusals(probes)

    missing_approval = load_json(RUNTIME / "phase03-missing-approval.json")
    if missing_approval.get("refusal_code") != "AUTH_APPROVAL_MISSING":
        raise RuntimeError("missing approval command evidence was absent")

    execution = with_digest(
        {
            "schema_version": "1.0.0",
            "mode": "live",
            "campaign_id": CAMPAIGN_ID,
            "captured_at": utc_now(),
            "repository": {
                "safe_identity": preflight["repository"]["identity"],
                "default_branch": preflight["repository"]["default_branch"],
                "source_version": preflight["repository"]["source_version"],
                "current_review_branch": current_plan["repository"]["target_branch"],
                "current_head": repository_head,
                "clean": True,
                "searched_branches": preflight["repository"]["searched_branches"],
                "non_default_branches_searched": preflight["repository"][
                    "non_default_branches_searched"
                ],
            },
            "discovery": {
                "layers": preflight["discovery"]["layers"],
                "mapping": preflight["mapping"],
                "limitations": preflight["limitations"],
            },
            "replacement": preflight["replacement"],
            "evidence_binding": binding,
            "plans": [
                {
                    "plan_digest": plan["plan_digest"],
                    "source_version": plan["repository"]["source_version"],
                    "target_branch": plan["repository"]["target_branch"],
                    "approved_target": plan["target"]["path"],
                    "before_fingerprint": plan["target"]["before_fingerprint"],
                    "after_fingerprint": plan["target"]["after_fingerprint"],
                }
                for plan in plans
            ],
            "applies": [
                {
                    "apply_digest": apply["apply_digest"],
                    "plan_digest": apply["plan_digest"],
                    "native_change_ids": apply["native_change_ids"],
                    "actual_targets": apply["actual_targets"],
                }
                for apply in applies
            ],
            "compensation": {
                "compensation_digest": compensation["compensation_digest"],
                "apply_commit": compensation["apply_commit"],
                "compensation_commit": compensation["compensation_commit"],
                "restored_fingerprint": compensation["restored_fingerprint"],
                "native_validation_result": compensation_validation["result"],
            },
            "validation": {
                "validation_digest": validation["validation_digest"],
                "result": validation["result"],
                "validator": validation["validator"],
                "validator_version": validation["validator_version"],
                "adapter_version": validation["adapter_version"],
                "commands": [
                    {
                        "arguments": command["arguments"],
                        "exit_code": command["exit_code"],
                        "timed_out": command["timed_out"],
                    }
                    for command in validation["commands"]
                ],
                "sandbox": validation["sandbox"],
            },
            "receipt": receipt,
            "campaign": {
                "state": manifest["campaign"]["state"],
                "decision": manifest["decision"],
                "selected_consumer": selected[0],
                "consumer_count": len(manifest["consumers"]),
                "opaque_consumer_count": sum(
                    consumer["disposition"] == "OPAQUE"
                    for consumer in manifest["consumers"]
                ),
                "blocker_codes": sorted(
                    {blocker["code"] for blocker in manifest["blockers"]}
                ),
                "event_count": len(events),
                "event_stream_digest": event_stream_digest(events),
            },
            "missing_approval": {
                "refusal_code": missing_approval["refusal_code"],
                "raw_artifact_digest": digest_file(
                    RUNTIME / "phase03-missing-approval.json"
                ),
            },
        },
        "evidence_digest",
    )
    write_json(OUTPUT / "execution-evidence.json", execution)

    adversarial = with_digest(
        {
            "schema_version": "1.0.0",
            "mode": "live",
            "input": "public adversarial dbt fixtures in disposable repositories",
            "captured_at": utc_now(),
            "tool_versions": preflight["tool_versions"],
            "probes": probes,
            "private_probe_root_digest": digest_json(str(probe_parent)),
            "limitations": [
                "Probes used local disposable Git repositories and DuckDB",
                "No production repository, warehouse, or credential was mounted",
                "A failed escape attempt proves this boundary, not every host kernel",
            ],
        },
        "evidence_digest",
    )
    write_json(OUTPUT / "adversarial-evidence.json", adversarial)

    summary = with_digest(
        {
            "schema_version": "1.0.0",
            "mode": "live",
            "campaign_id": CAMPAIGN_ID,
            "assertions": {
                "exact_datahub_consumer_mapped": True,
                "repository_evidence_joined": True,
                "approval_bound_before_mutation": True,
                "one_file_diff_exact": True,
                "native_dbt_validation_passed": True,
                "rollback_verified": True,
                "reapply_verified": True,
                "repeated_apply_idempotent": True,
                "live_receipt_accepted": True,
                "adversarial_boundaries_refused_or_contained": True,
                "campaign_not_ready_before_reconciliation": True,
            },
            "artifacts": {
                "execution": "artifacts/public/phase03/execution-evidence.json",
                "adversarial": "artifacts/public/phase03/adversarial-evidence.json",
            },
            "test_sources": [
                "tests/unit/test_git_dbt.py",
                "tests/unit/test_git_dbt_config.py",
                "tests/integration/test_git_dbt_workflow.py",
            ],
        },
        "evidence_digest",
    )
    write_json(OUTPUT / "phase03-evidence.json", summary)
    print(
        "Phase 03 live evidence generated: "
        "two applies, verified rollback, native receipt, adversarial containment."
    )
    return 0


if __name__ == "__main__":
    sys.exit(run())

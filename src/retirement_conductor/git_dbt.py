"""Bounded Git/dbt discovery, mutation, validation, and recovery."""

from __future__ import annotations

import json
import os
import re
import resource
import shutil
import subprocess
import tempfile
import time
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from retirement_conductor.canonical import (
    digest_bytes,
    digest_file,
    digest_json,
    verify_digest,
    with_digest,
    write_json,
)
from retirement_conductor.datahub import ArtifactWriter, redact_observation, utc_now
from retirement_conductor.errors import Refusal
from retirement_conductor.git_dbt_config import GitDbtSettings
from retirement_conductor.schemas import validate_schema
from retirement_conductor.vocabulary import RefusalCode

ADAPTER_VERSION = "0.1.0"
MODEL_SUFFIXES = {".py", ".sql", ".yaml", ".yml"}
IGNORED_DIRECTORIES = {
    ".git",
    ".runtime",
    ".venv",
    "dbt_packages",
    "logs",
    "target",
}


class GitDbtAdapter:
    """One exact local Git repository and one dbt model mutation."""

    def __init__(self, settings: GitDbtSettings) -> None:
        self.settings = settings
        self.sandbox = DbtSandbox(settings)

    def preflight(
        self,
        specification: Mapping[str, Any],
        *,
        datahub_resolution: Mapping[str, Any],
        known_consumer_urns: Sequence[str],
        artifact_root: Path,
    ) -> dict[str, Any]:
        captured_at = utc_now()
        repository = self._repository_contract(specification)
        root = self.settings.repository_root
        self._require_repository()
        source_version = self.git("rev-parse", "HEAD")
        source_branch = self.git("branch", "--show-current")
        if source_branch != str(repository["branch"]):
            raise Refusal(
                RefusalCode.SOURCE_GIT_BRANCH_MOVED,
                "The repository is not on the declared source branch.",
                {
                    "expected_branch": repository["branch"],
                    "actual_branch": source_branch,
                },
            )
        status = self.git("status", "--porcelain=v1", "--untracked-files=all")
        if status:
            raise Refusal(
                RefusalCode.SOURCE_GIT_DIRTY,
                "The disposable repository must be clean before discovery.",
            )
        reject_unsafe_tree(root)
        writer = ArtifactWriter(artifact_root)
        sandbox_result = self.sandbox.execute(
            root,
            [
                ["parse", "--no-partial-parse"],
                ["compile", "--no-partial-parse"],
            ],
            artifact_root=artifact_root,
            label="preflight",
        )
        if sandbox_result["result"] != "PASSED":
            raise Refusal(
                RefusalCode.SOURCE_DBT_UNAVAILABLE,
                "dbt parse or compile failed during preflight.",
                {"failed_command": sandbox_result.get("failed_command")},
            )
        staged_root = Path(str(sandbox_result["staged_root"]))
        manifest_path = staged_root / "target" / "manifest.json"
        manifest = load_object(manifest_path)
        discovery = discover_repository(
            root,
            manifest,
            target_field=str(specification["target"]["field"]),
        )
        mapping = resolve_manifest_mapping(manifest, known_consumer_urns)
        target_path = checked_target_path(
            root,
            str(mapping["original_file_path"]),
            allowed_paths=list(specification["authorization"]["allowed_paths"]),
        )
        self._reject_external_filter(target_path.relative_to(root).as_posix())
        replacement = resolve_replacement_evidence(
            manifest,
            datahub_resolution=datahub_resolution,
            target_field=str(specification["target"]["field"]),
            replacement_field=str(specification["replacement"]["field"]),
        )
        manifest_summary = {
            "metadata": manifest.get("metadata"),
            "mapping": mapping,
            "replacement": replacement,
            "node_count": len(manifest.get("nodes") or {}),
            "source_count": len(manifest.get("sources") or {}),
        }
        manifest_artifact = writer.write("dbt-manifest-summary", manifest_summary)
        discovery_artifact = writer.write("repository-discovery", discovery)
        tool_versions = {
            **self.sandbox.tool_versions(),
            "git": self.git("--version"),
            "adapter": ADAPTER_VERSION,
        }
        preflight = with_digest(
            {
                "schema_version": "1.0.0",
                "mode": "live",
                "captured_at": captured_at,
                "repository": {
                    "id": self.settings.repository_id,
                    "required": bool(repository["required"]),
                    "identity": digest_json(str(root)),
                    "default_branch": self.settings.default_branch,
                    "source_branch": source_branch,
                    "source_version": source_version,
                    "source_committed_at": self.git(
                        "show",
                        "-s",
                        "--format=%cI",
                        source_version,
                    ),
                    "working_tree_clean": True,
                    "non_default_branches_searched": False,
                    "searched_branches": [source_branch],
                },
                "principal": self.settings.principal,
                "capabilities": {
                    "read": True,
                    "plan": True,
                    "apply": self.settings.allow_apply,
                    "validate": True,
                    "compensate": self.settings.allow_apply,
                },
                "tool_versions": tool_versions,
                "sandbox": sandbox_result["sandbox"],
                "discovery": discovery,
                "mapping": {
                    **mapping,
                    "path": target_path.relative_to(root).as_posix(),
                },
                "replacement": replacement,
                "limitations": [
                    "Only the declared source branch was searched",
                    "Text discovery is high-recall evidence, not completeness proof",
                    "External dbt packages are refused in the initial adapter",
                ],
                "artifact_ids": sorted(
                    {
                        manifest_artifact,
                        discovery_artifact,
                        *sandbox_result["artifact_ids"],
                    }
                ),
            },
            "preflight_digest",
        )
        write_versioned_artifact(artifact_root, "preflight", preflight)
        return preflight

    def plan(
        self,
        specification: Mapping[str, Any],
        preflight: Mapping[str, Any],
        *,
        campaign_id: str,
        artifact_root: Path,
    ) -> dict[str, Any]:
        verify_digest(dict(preflight), "preflight_digest")
        root = self.settings.repository_root
        source_version = self.git("rev-parse", "HEAD")
        source_branch = self.git("branch", "--show-current")
        expected_version = str(preflight["repository"]["source_version"])
        if source_version != expected_version:
            raise Refusal(
                RefusalCode.SOURCE_GIT_BRANCH_MOVED,
                "The repository commit changed after preflight.",
                {
                    "expected_version": expected_version,
                    "actual_version": source_version,
                },
            )
        if source_branch != str(preflight["repository"]["source_branch"]):
            raise Refusal(
                RefusalCode.SOURCE_GIT_BRANCH_MOVED,
                "The repository branch changed after preflight.",
            )
        relative_path = str(preflight["mapping"]["path"])
        target_path = checked_target_path(
            root,
            relative_path,
            allowed_paths=list(specification["authorization"]["allowed_paths"]),
        )
        content = target_path.read_text(encoding="utf-8")
        before_token = str(specification["target"]["field"])
        after_token = str(specification["replacement"]["field"])
        occurrences = token_occurrences(content, before_token)
        if occurrences != 1:
            raise Refusal(
                RefusalCode.IDENTITY_AMBIGUOUS,
                "The authorized model did not contain exactly one legacy field token.",
                {"occurrences": occurrences, "path": relative_path},
            )
        patched = replace_identifier_once(content, before_token, after_token)
        branch_base = f"codex/{campaign_id}"
        branches = set(self.git("branch", "--format=%(refname:short)").splitlines())
        target_branch = branch_base
        if target_branch in branches:
            target_branch = f"{branch_base}-reapply-{source_version[:8]}"
        target_field = preflight["replacement"]["target"]
        replacement_field = preflight["replacement"]["replacement"]
        plan = with_digest(
            {
                "schema_version": "1.0.0",
                "campaign_id": campaign_id,
                "consumer_id": consumer_id_for_urn(
                    str(preflight["mapping"]["datahub_urn"])
                ),
                "datahub_urn": preflight["mapping"]["datahub_urn"],
                "repository": {
                    "id": self.settings.repository_id,
                    "identity": digest_json(str(root)),
                    "default_branch": self.settings.default_branch,
                    "source_branch": source_branch,
                    "source_version": source_version,
                    "target_branch": target_branch,
                    "searched_branches": list(
                        preflight["repository"]["searched_branches"]
                    ),
                    "non_default_branches_searched": bool(
                        preflight["repository"]["non_default_branches_searched"]
                    ),
                },
                "native_identity": {
                    "source_domain": "git-dbt",
                    "repository_id": self.settings.repository_id,
                    "repository_identity": digest_json(str(root)),
                    "path": relative_path,
                    "dbt_unique_id": preflight["mapping"]["unique_id"],
                    "datahub_urn": preflight["mapping"]["datahub_urn"],
                },
                "target": {
                    "path": relative_path,
                    "before_token": before_token,
                    "after_token": after_token,
                    "before_fingerprint": digest_file(target_path),
                    "after_fingerprint": digest_bytes(patched.encode()),
                },
                "replacement": {
                    "target": target_field,
                    "replacement": replacement_field,
                    "compatible": preflight["replacement"]["compatible"],
                    "evidence_digest": digest_json(preflight["replacement"]),
                },
                "discovery": {
                    "preflight_digest": preflight["preflight_digest"],
                    "layers": preflight["discovery"]["layers"],
                    "mapping_match_count": 1,
                },
                "validators": [
                    "dbt parse",
                    "dbt seed",
                    "dbt build",
                    "dbt test",
                    "orders_model_semantic_equivalence",
                ],
                "limitations": list(preflight["limitations"]),
            },
            "plan_digest",
        )
        validate_schema(
            "git-dbt-plan",
            plan,
            refusal_code=RefusalCode.INTEGRITY_DIGEST_MISMATCH,
        )
        return plan

    def apply(
        self,
        specification: Mapping[str, Any],
        plan: Mapping[str, Any],
        *,
        artifact_root: Path,
        occurred_at: str,
    ) -> dict[str, Any]:
        self._validate_plan(specification, plan)
        if not self.settings.allow_apply:
            raise Refusal(
                RefusalCode.AUTH_APPLY_DISABLED,
                "Git/dbt apply is disabled by configuration.",
                {"required_reference": "GIT_DBT_ALLOW_APPLY"},
            )
        root = self.settings.repository_root
        target = plan["target"]
        target_path = checked_target_path(
            root,
            str(target["path"]),
            allowed_paths=list(specification["authorization"]["allowed_paths"]),
        )
        self._reject_external_filter(str(target["path"]))
        existing = load_optional_object(artifact_root / "apply.json")
        if existing is not None and self._applied_state_matches(plan, existing):
            return existing

        source_version = str(plan["repository"]["source_version"])
        source_branch = str(plan["repository"]["source_branch"])
        target_branch = str(plan["repository"]["target_branch"])
        actual_branch = self.git("branch", "--show-current")
        actual_version = self.git("rev-parse", "HEAD")
        status = self.git("status", "--porcelain=v1", "--untracked-files=all")
        if actual_branch == source_branch and actual_version == source_version:
            if status:
                raise Refusal(
                    RefusalCode.SOURCE_GIT_DIRTY,
                    "Unexpected repository changes exist before apply.",
                )
            self.git("switch", "-c", target_branch)
        elif actual_branch == target_branch and actual_version == source_version:
            changed = changed_paths_from_status(status)
            if changed and changed != {str(target["path"])}:
                raise Refusal(
                    RefusalCode.SCOPE_TARGET_NOT_ALLOWED,
                    "A partial apply changed an unexpected target.",
                    {"actual_targets": sorted(changed)},
                )
        else:
            raise Refusal(
                RefusalCode.SOURCE_GIT_BRANCH_MOVED,
                "The source branch or commit moved before apply.",
                {
                    "expected_branch": source_branch,
                    "actual_branch": actual_branch,
                    "expected_version": source_version,
                    "actual_version": actual_version,
                },
            )

        actual_before = digest_file(target_path)
        if actual_before == target["after_fingerprint"]:
            changed = changed_paths_from_status(
                self.git("status", "--porcelain=v1", "--untracked-files=all")
            )
            if changed != {str(target["path"])}:
                raise Refusal(
                    RefusalCode.APPLY_OUTCOME_UNKNOWN,
                    "Post-apply content exists with an unexpected worktree scope.",
                )
        elif actual_before == target["before_fingerprint"]:
            content = target_path.read_text(encoding="utf-8")
            patched = replace_identifier_once(
                content,
                str(target["before_token"]),
                str(target["after_token"]),
            )
            if digest_bytes(patched.encode()) != target["after_fingerprint"]:
                raise Refusal(
                    RefusalCode.INTEGRITY_DIGEST_MISMATCH,
                    "The deterministic patch did not match the approved fingerprint.",
                )
            atomic_write_text(target_path, patched)
        else:
            raise Refusal(
                RefusalCode.SOURCE_GIT_FILE_CHANGED,
                "The approved file changed before apply.",
                {
                    "expected_fingerprint": target["before_fingerprint"],
                    "actual_fingerprint": actual_before,
                },
            )

        changed = changed_paths_from_status(
            self.git("status", "--porcelain=v1", "--untracked-files=all")
        )
        approved = {str(item) for item in [target["path"]]}
        if changed != approved:
            raise Refusal(
                RefusalCode.SCOPE_TARGET_NOT_ALLOWED,
                "The actual Git target set did not equal the approved plan.",
                {
                    "approved_targets": sorted(approved),
                    "actual_targets": sorted(changed),
                },
            )
        self.git("add", "--", str(target["path"]))
        self.git_with_identity(
            occurred_at,
            "commit",
            "--no-verify",
            "-m",
            f"migrate: replace {target['before_token']} with {target['after_token']}",
            "--",
            str(target["path"]),
        )
        apply_commit = self.git("rev-parse", "HEAD")
        actual_targets = set(
            self.git(
                "diff",
                "--name-only",
                f"{source_version}..{apply_commit}",
            ).splitlines()
        )
        if actual_targets != approved:
            raise Refusal(
                RefusalCode.SCOPE_TARGET_NOT_ALLOWED,
                "The committed diff expanded beyond the approved target.",
                {"actual_targets": sorted(actual_targets)},
            )
        if digest_file(target_path) != target["after_fingerprint"]:
            raise Refusal(
                RefusalCode.INTEGRITY_DIGEST_MISMATCH,
                "The committed file did not match the approved after fingerprint.",
            )
        diff_text = self.git(
            "diff",
            "--no-ext-diff",
            "--no-color",
            f"{source_version}..{apply_commit}",
            "--",
            str(target["path"]),
        )
        writer = ArtifactWriter(artifact_root)
        diff_artifact = writer.write("apply-diff", {"diff": diff_text})
        record = with_digest(
            {
                "schema_version": "1.0.0",
                "result": "APPLIED",
                "campaign_id": plan["campaign_id"],
                "consumer_id": plan["consumer_id"],
                "plan_digest": plan["plan_digest"],
                "source_version": source_version,
                "source_branch": source_branch,
                "target_branch": target_branch,
                "native_change_ids": [apply_commit],
                "actual_targets": sorted(actual_targets),
                "before_fingerprint": target["before_fingerprint"],
                "after_fingerprint": target["after_fingerprint"],
                "diff_artifact_id": diff_artifact,
                "occurred_at": occurred_at,
            },
            "apply_digest",
        )
        write_versioned_artifact(artifact_root, "apply", record)
        return record

    def compensate(
        self,
        specification: Mapping[str, Any],
        plan: Mapping[str, Any],
        apply_record: Mapping[str, Any],
        *,
        artifact_root: Path,
        occurred_at: str,
    ) -> dict[str, Any]:
        self._validate_plan(specification, plan)
        verify_digest(dict(apply_record), "apply_digest")
        if not self.settings.allow_apply:
            raise Refusal(
                RefusalCode.AUTH_APPLY_DISABLED,
                "Git/dbt compensation is disabled by configuration.",
            )
        target_path = checked_target_path(
            self.settings.repository_root,
            str(plan["target"]["path"]),
            allowed_paths=list(specification["authorization"]["allowed_paths"]),
        )
        apply_commit = str(apply_record["native_change_ids"][0])
        if (
            self.git("rev-parse", "HEAD") != apply_commit
            or self.git("branch", "--show-current")
            != str(apply_record["target_branch"])
            or self.git("status", "--porcelain=v1", "--untracked-files=all")
            or digest_file(target_path) != plan["target"]["after_fingerprint"]
        ):
            raise Refusal(
                RefusalCode.COMPENSATION_CONFLICT,
                (
                    "Compensation preconditions changed; the intervening edit "
                    "was preserved."
                ),
            )
        self.git("revert", "--no-commit", apply_commit)
        changed = changed_paths_from_status(
            self.git("status", "--porcelain=v1", "--untracked-files=all")
        )
        if changed != {str(plan["target"]["path"])}:
            raise Refusal(
                RefusalCode.COMPENSATION_CONFLICT,
                "Compensation produced an unexpected target set.",
                {"actual_targets": sorted(changed)},
            )
        self.git_with_identity(
            occurred_at,
            "commit",
            "--no-verify",
            "-m",
            f"revert: {apply_commit}",
            "--",
            str(plan["target"]["path"]),
        )
        compensation_commit = self.git("rev-parse", "HEAD")
        if digest_file(target_path) != plan["target"]["before_fingerprint"]:
            raise Refusal(
                RefusalCode.COMPENSATION_CONFLICT,
                "Compensation did not restore the approved before fingerprint.",
            )
        validation = self.validate_project(
            artifact_root=artifact_root / "compensation-validation",
        )
        if validation["result"] != "PASSED":
            raise Refusal(
                RefusalCode.VALIDATION_RECEIPT_FAILED,
                "The restored repository failed dbt verification.",
            )
        self.git("switch", self.settings.default_branch)
        record = with_digest(
            {
                "schema_version": "1.0.0",
                "result": "RESTORED",
                "campaign_id": plan["campaign_id"],
                "consumer_id": plan["consumer_id"],
                "plan_digest": plan["plan_digest"],
                "apply_commit": apply_commit,
                "compensation_commit": compensation_commit,
                "restored_fingerprint": plan["target"]["before_fingerprint"],
                "validation_artifact_ids": validation["artifact_ids"],
                "occurred_at": occurred_at,
            },
            "compensation_digest",
        )
        write_versioned_artifact(artifact_root, "compensation", record)
        return record

    def validate_project(self, *, artifact_root: Path) -> dict[str, Any]:
        self._require_repository()
        if self.git("status", "--porcelain=v1", "--untracked-files=all"):
            raise Refusal(
                RefusalCode.SOURCE_GIT_DIRTY,
                "Validation requires a clean committed worktree.",
            )
        result = self.sandbox.execute(
            self.settings.repository_root,
            [
                ["parse", "--no-partial-parse"],
                ["seed", "--full-refresh"],
                ["build"],
                ["test"],
            ],
            artifact_root=artifact_root,
            label="validation",
        )
        validation = with_digest(
            {
                "schema_version": "1.0.0",
                "result": result["result"],
                "validator": "dbt parse + seed + build + test on DuckDB",
                "validator_version": result["tool_versions"]["dbt_core"],
                "adapter_version": result["tool_versions"]["dbt_duckdb"],
                "commands": result["commands"],
                "artifact_ids": result["artifact_ids"],
                "sandbox": result["sandbox"],
                "failed_command": result.get("failed_command"),
            },
            "validation_digest",
        )
        write_versioned_artifact(artifact_root, "validation", validation)
        return validation

    def reconcile_source(
        self,
        specification: Mapping[str, Any],
        plan: Mapping[str, Any],
        apply_record: Mapping[str, Any],
        receipt: Mapping[str, Any],
        *,
        datahub_resolution: Mapping[str, Any],
        artifact_root: Path,
    ) -> dict[str, Any]:
        """Reread the exact applied Git source and replacement schema."""

        self._validate_plan(specification, plan)
        verify_digest(dict(apply_record), "apply_digest")
        verify_digest(dict(receipt), "receipt_digest")
        root = self.settings.repository_root
        target_path = checked_target_path(
            root,
            str(plan["target"]["path"]),
            allowed_paths=list(specification["authorization"]["allowed_paths"]),
        )
        self._reject_external_filter(str(plan["target"]["path"]))
        expected_commit = str(apply_record["native_change_ids"][0])
        actual_commit = self.git("rev-parse", "HEAD")
        actual_branch = self.git("branch", "--show-current")
        status = self.git("status", "--porcelain=v1", "--untracked-files=all")
        if (
            actual_commit != expected_commit
            or actual_branch != apply_record["target_branch"]
            or status
            or digest_file(target_path) != plan["target"]["after_fingerprint"]
        ):
            raise Refusal(
                RefusalCode.SOURCE_GIT_FILE_CHANGED,
                "The validated Git/dbt source changed before reconciliation.",
                {
                    "expected_branch": apply_record["target_branch"],
                    "actual_branch": actual_branch,
                    "expected_version": expected_commit,
                    "actual_version": actual_commit,
                },
            )
        actual_targets = sorted(
            self.git(
                "diff",
                "--name-only",
                f"{plan['repository']['source_version']}..{actual_commit}",
            ).splitlines()
        )
        if actual_targets != list(receipt["apply"]["actual_targets"]):
            raise Refusal(
                RefusalCode.SCOPE_RECEIPT_TARGET_MISMATCH,
                "The current Git diff no longer matches the accepted receipt.",
            )
        target_field = datahub_resolution["target_field"]
        replacement_field = datahub_resolution["replacement_field"]
        receipt_replacement = receipt["native_identity"]["replacement"]
        expected_types = {
            str(receipt_replacement["target"]["datahub_native_type"]).casefold(),
            str(receipt_replacement["replacement"]["datahub_native_type"]).casefold(),
        }
        actual_types = {
            str(target_field.get("nativeDataType", "")).casefold(),
            str(replacement_field.get("nativeDataType", "")).casefold(),
        }
        if (
            target_field.get("fieldPath") != receipt_replacement["target"]["field"]
            or replacement_field.get("fieldPath")
            != receipt_replacement["replacement"]["field"]
            or len(actual_types) != 1
            or "" in actual_types
            or actual_types != expected_types
        ):
            raise Refusal(
                RefusalCode.SPEC_REPLACEMENT_INCOMPATIBLE,
                "Replacement identity or type drifted after native validation.",
            )
        observation = with_digest(
            {
                "schema_version": "1.0.0",
                "mode": "live",
                "captured_at": utc_now(),
                "repository": {
                    "id": self.settings.repository_id,
                    "required": True,
                    "identity": plan["repository"]["identity"],
                    "declared_branch": plan["repository"]["source_branch"],
                    "observed_branch": actual_branch,
                    "source_version": actual_commit,
                    "source_committed_at": self.git(
                        "show",
                        "-s",
                        "--format=%cI",
                        actual_commit,
                    ),
                    "clean": True,
                },
                "principal": self.settings.principal,
                "capabilities": {
                    "read": True,
                    "plan": True,
                    "apply": self.settings.allow_apply,
                    "validate": True,
                    "compensate": self.settings.allow_apply,
                },
                "target": {
                    "path": plan["target"]["path"],
                    "fingerprint": digest_file(target_path),
                    "actual_targets": actual_targets,
                },
                "replacement": {
                    "target": dict(target_field),
                    "replacement": dict(replacement_field),
                    "compatible": True,
                },
                "plan_digest": plan["plan_digest"],
                "apply_digest": apply_record["apply_digest"],
                "receipt_digest": receipt["receipt_digest"],
                "limitations": list(plan["limitations"]),
            },
            "reconciliation_digest",
        )
        write_versioned_artifact(
            artifact_root,
            "source-reconciliation",
            observation,
        )
        return observation

    def emit_receipt(
        self,
        plan: Mapping[str, Any],
        apply_record: Mapping[str, Any],
        validation: Mapping[str, Any],
        *,
        compensation: Mapping[str, Any] | None,
        captured_at: str,
        expires_at: str | None,
        artifact_root: Path,
    ) -> dict[str, Any]:
        verify_digest(dict(plan), "plan_digest")
        verify_digest(dict(apply_record), "apply_digest")
        verify_digest(dict(validation), "validation_digest")
        if validation["result"] != "PASSED":
            raise Refusal(
                RefusalCode.VALIDATION_RECEIPT_FAILED,
                "A failed dbt validation cannot emit a validated receipt.",
            )
        limitations = list(plan["limitations"])
        if compensation is not None:
            verify_digest(dict(compensation), "compensation_digest")
            if compensation.get("plan_digest") != plan["plan_digest"]:
                limitations.append(
                    "The exercised compensation belongs to the immediately "
                    "preceding migration attempt for this same consumer."
                )
        compensation_value = {
            "available": True,
            "exercised": compensation is not None,
            "result": (
                "RESTORED"
                if compensation is not None and compensation.get("result") == "RESTORED"
                else "NOT_NEEDED"
            ),
        }
        receipt = with_digest(
            {
                "schema_version": "1.0.0",
                "receipt_id": (
                    f"git-dbt-{plan['consumer_id']}-"
                    f"{str(apply_record['native_change_ids'][0])[:12]}"
                ),
                "campaign_id": plan["campaign_id"],
                "consumer_id": plan["consumer_id"],
                "datahub_urn": plan["datahub_urn"],
                "native_identity": {
                    **plan["native_identity"],
                    "replacement": plan["replacement"],
                },
                "adapter": {
                    "name": "git-dbt",
                    "version": ADAPTER_VERSION,
                    "mode": "live",
                },
                "source_before": {
                    "version": plan["repository"]["source_version"],
                    "fingerprint": plan["target"]["before_fingerprint"],
                },
                "plan": {
                    "digest": plan["plan_digest"],
                    "proposed_targets": [plan["target"]["path"]],
                    "approved_targets": [plan["target"]["path"]],
                },
                "apply": {
                    "result": "APPLIED",
                    "actual_targets": apply_record["actual_targets"],
                    "before_fingerprint": apply_record["before_fingerprint"],
                    "after_fingerprint": apply_record["after_fingerprint"],
                    "native_change_ids": apply_record["native_change_ids"],
                },
                "validation": {
                    "result": "PASSED",
                    "validator": validation["validator"],
                    "validator_version": validation["validator_version"],
                    "artifact_ids": validation["artifact_ids"],
                },
                "compensation": compensation_value,
                "captured_at": captured_at,
                "expires_at": expires_at,
                "limitations": limitations,
                "terminal_disposition": "VALIDATED",
            },
            "receipt_digest",
        )
        validate_schema(
            "consumer-receipt",
            receipt,
            refusal_code=RefusalCode.INTEGRITY_DIGEST_MISMATCH,
        )
        write_versioned_artifact(artifact_root, "receipt", receipt)
        return receipt

    def git(self, *arguments: str) -> str:
        return run_git(self.settings, *arguments)

    def git_with_identity(self, occurred_at: str, *arguments: str) -> str:
        return run_git(
            self.settings,
            *arguments,
            identity_time=occurred_at,
        )

    def _require_repository(self) -> None:
        root = self.settings.repository_root
        if (
            not root.is_dir()
            or not (root / ".git").is_dir()
            or not self.settings.git_executable.is_file()
        ):
            raise Refusal(
                RefusalCode.SOURCE_GIT_UNAVAILABLE,
                "The disposable Git repository or Git executable is unavailable.",
            )
        top_level = self.git("rev-parse", "--show-toplevel")
        if Path(top_level).resolve() != root:
            raise Refusal(
                RefusalCode.SCOPE_PATH_OUTSIDE_ROOT,
                "Git resolved a different repository root.",
            )

    def _reject_external_filter(self, relative_path: str) -> None:
        attribute = self.git("check-attr", "filter", "--", relative_path)
        if not attribute.endswith(": unspecified"):
            raise Refusal(
                RefusalCode.VALIDATION_SCOPE_VIOLATION,
                "External Git content filters are refused for the mutation target.",
                {"path": relative_path},
            )

    def _repository_contract(
        self,
        specification: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        repositories = [
            repository
            for repository in specification["evidence"]["repositories"]
            if repository["id"] == self.settings.repository_id
        ]
        if len(repositories) != 1:
            raise Refusal(
                RefusalCode.IDENTITY_AMBIGUOUS,
                "The configured repository did not match one declared source.",
                {"match_count": len(repositories)},
            )
        repository = repositories[0]
        if Path(str(repository["path"])).resolve() != self.settings.repository_root:
            raise Refusal(
                RefusalCode.SCOPE_PATH_OUTSIDE_ROOT,
                "The runtime repository differs from the declared repository path.",
            )
        if (
            self.settings.repository_id
            not in specification["authorization"]["allowed_repositories"]
        ):
            raise Refusal(
                RefusalCode.SCOPE_TARGET_NOT_ALLOWED,
                "The repository is absent from the authorization allowlist.",
            )
        return dict(repository)

    def _validate_plan(
        self,
        specification: Mapping[str, Any],
        plan: Mapping[str, Any],
    ) -> None:
        validate_schema(
            "git-dbt-plan",
            plan,
            refusal_code=RefusalCode.INTEGRITY_DIGEST_MISMATCH,
        )
        verify_digest(dict(plan), "plan_digest")
        if plan["campaign_id"] != specification["campaign"]["id"]:
            raise Refusal(
                RefusalCode.AUTH_APPROVAL_WRONG_CAMPAIGN,
                "The Git/dbt plan belongs to another campaign.",
            )
        if specification["authorization"]["mode"] != "apply":
            raise Refusal(
                RefusalCode.AUTH_APPLY_DISABLED,
                "The specification grants planning but not apply.",
            )
        proposed = {str(plan["target"]["path"])}
        allowed = list(specification["authorization"]["allowed_paths"])
        if not all(path_is_allowed(path, allowed) for path in proposed):
            raise Refusal(
                RefusalCode.SCOPE_TARGET_NOT_ALLOWED,
                "The plan contains a path outside the authorization allowlist.",
            )

    def _applied_state_matches(
        self,
        plan: Mapping[str, Any],
        record: Mapping[str, Any],
    ) -> bool:
        try:
            verify_digest(dict(record), "apply_digest")
        except Refusal:
            return False
        target_path = checked_target_path(
            self.settings.repository_root,
            str(plan["target"]["path"]),
            allowed_paths=[str(plan["target"]["path"])],
        )
        return (
            record.get("plan_digest") == plan["plan_digest"]
            and self.git("rev-parse", "HEAD")
            in set(record.get("native_change_ids") or [])
            and digest_file(target_path) == plan["target"]["after_fingerprint"]
            and not self.git("status", "--porcelain=v1", "--untracked-files=all")
        )


class DbtSandbox:
    """Run dbt in a copied tree with no host home and an unshared network."""

    def __init__(self, settings: GitDbtSettings) -> None:
        self.settings = settings

    def tool_versions(self) -> dict[str, str]:
        python = self.settings.dbt_executable.parent / "python"
        script = (
            "import json; from importlib.metadata import version; "
            "print(json.dumps({'dbt_core':version('dbt-core'),"
            "'dbt_duckdb':version('dbt-duckdb'),"
            "'duckdb':version('duckdb')}))"
        )
        try:
            result = subprocess.run(
                [str(python), "-c", script],
                check=True,
                capture_output=True,
                text=True,
                env={"PATH": "/usr/bin:/bin", "LC_ALL": "C.UTF-8"},
                timeout=20,
            )
            value = json.loads(result.stdout)
        except (
            OSError,
            subprocess.SubprocessError,
            json.JSONDecodeError,
        ) as exc:
            raise Refusal(
                RefusalCode.SOURCE_DBT_UNAVAILABLE,
                "The pinned dbt tool environment could not report versions.",
            ) from exc
        if not isinstance(value, dict) or not all(
            isinstance(item, str) for item in value.values()
        ):
            raise Refusal(
                RefusalCode.SOURCE_DBT_UNAVAILABLE,
                "The dbt tool version response was malformed.",
            )
        return {str(key): str(item) for key, item in value.items()}

    def execute(
        self,
        repository: Path,
        commands: Sequence[Sequence[str]],
        *,
        artifact_root: Path,
        label: str,
    ) -> dict[str, Any]:
        self._require_boundary()
        reject_unsafe_tree(repository)
        stage_parent = artifact_root / "sandboxes"
        stage_parent.mkdir(parents=True, exist_ok=True)
        staged_root = Path(tempfile.mkdtemp(prefix=f"{label}-", dir=stage_parent))
        copy_repository(repository, staged_root)
        (staged_root / ".runtime").mkdir(mode=0o700)
        writer = ArtifactWriter(artifact_root)
        artifact_ids: list[str] = []
        command_results: list[dict[str, Any]] = []
        failed_command: list[str] | None = None
        for index, arguments in enumerate(commands):
            result = self._run_one(staged_root, list(arguments))
            command_results.append(result)
            artifact_ids.append(
                writer.write(
                    f"{label}-dbt-{index:02d}-{arguments[0]}",
                    result,
                )
            )
            if result["exit_code"] != 0:
                failed_command = list(arguments)
                break
        for name in ("manifest.json", "run_results.json"):
            candidate = staged_root / "target" / name
            if candidate.is_file():
                artifact_ids.append(digest_file(candidate))
        versions = self.tool_versions()
        return {
            "result": "PASSED" if failed_command is None else "FAILED",
            "commands": command_results,
            "failed_command": failed_command,
            "artifact_ids": sorted(set(artifact_ids)),
            "staged_root": str(staged_root),
            "tool_versions": versions,
            "sandbox": {
                "engine": "bubblewrap",
                "network": "unshared",
                "host_home_mounted": False,
                "source_repository_mounted": False,
                "workspace_copy_mounted": True,
                "environment": "allowlisted",
                "resource_limits": {
                    "timeout_seconds": self.settings.validation_timeout_seconds,
                    "address_space_bytes": 3 * 1024 * 1024 * 1024,
                    "file_size_bytes": 512 * 1024 * 1024,
                    "open_files": 256,
                    "processes": 128,
                },
            },
        }

    def _require_boundary(self) -> None:
        python = self.settings.dbt_executable.parent / "python"
        if (
            not self.settings.bwrap_executable.is_file()
            or not self.settings.dbt_executable.is_file()
            or not python.is_file()
        ):
            raise Refusal(
                RefusalCode.VALIDATION_SANDBOX_UNAVAILABLE,
                "Bubblewrap or the pinned dbt tool environment is unavailable.",
            )

    def _run_one(self, staged_root: Path, arguments: list[str]) -> dict[str, Any]:
        tool_root = self.settings.dbt_executable.parent.parent.resolve()
        python = (self.settings.dbt_executable.parent / "python").resolve()
        python_root = python.parents[1]
        command = [
            str(self.settings.bwrap_executable),
            "--unshare-net",
            "--unshare-pid",
            "--unshare-ipc",
            "--unshare-uts",
            "--die-with-parent",
            "--new-session",
        ]
        for system_path in (Path("/usr"), Path("/lib"), Path("/lib64")):
            if system_path.exists():
                command.extend(["--ro-bind", str(system_path), str(system_path)])
        command.extend(
            [
                "--ro-bind",
                str(tool_root),
                "/tool",
                "--ro-bind",
                str(python_root),
                "/runtime",
                "--bind",
                str(staged_root),
                "/workspace",
                "--dev",
                "/dev",
                "--proc",
                "/proc",
                "--tmpfs",
                "/tmp",
                "--dir",
                "/tmp/home",
                "--clearenv",
                "--setenv",
                "HOME",
                "/tmp/home",
                "--setenv",
                "PATH",
                "/tool/bin:/usr/bin:/bin",
                "--setenv",
                "PYTHONPATH",
                "/tool/lib/python3.11/site-packages",
                "--setenv",
                "DBT_PROFILES_DIR",
                "/workspace",
                "--setenv",
                "DBT_SEND_ANONYMOUS_USAGE_STATS",
                "false",
                "--setenv",
                "DO_NOT_TRACK",
                "1",
                "--setenv",
                "LC_ALL",
                "C.UTF-8",
                "--chdir",
                "/workspace",
                "/runtime/bin/python3.11",
                "-c",
                (
                    "import resource; "
                    "resource.setrlimit(resource.RLIMIT_NPROC,(128,128)); "
                    "from dbt.cli.main import cli; cli()"
                ),
                *arguments,
            ]
        )
        started = time.monotonic()
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                env={"PATH": "/usr/bin:/bin", "LC_ALL": "C.UTF-8"},
                timeout=self.settings.validation_timeout_seconds,
                preexec_fn=set_validation_limits,
            )
            exit_code = completed.returncode
            stdout = redact_log(completed.stdout)
            stderr = redact_log(completed.stderr)
            timed_out = False
        except subprocess.TimeoutExpired as exc:
            exit_code = 124
            stdout = redact_log(
                exc.stdout.decode(errors="replace")
                if isinstance(exc.stdout, bytes)
                else exc.stdout or ""
            )
            stderr = redact_log(
                exc.stderr.decode(errors="replace")
                if isinstance(exc.stderr, bytes)
                else exc.stderr or ""
            )
            timed_out = True
        return {
            "arguments": arguments,
            "exit_code": exit_code,
            "timed_out": timed_out,
            "duration_ms": round((time.monotonic() - started) * 1000),
            "stdout": stdout,
            "stderr": stderr,
        }


def merge_repository_evidence(
    evidence_envelope: Mapping[str, Any],
    preflight: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind a fresh repository observation into the campaign evidence envelope."""

    verify_digest(dict(evidence_envelope), "envelope_digest")
    verify_digest(dict(preflight), "preflight_digest")
    repository = preflight["repository"]
    source_id = f"git:{repository['id']}"
    sources = [
        dict(source)
        for source in evidence_envelope["sources"]
        if source["id"] != source_id
    ]
    capabilities = preflight["capabilities"]
    effective = [
        capability
        for capability in ("read", "plan", "apply", "validate", "compensate")
        if capabilities[capability]
    ]
    sources.append(
        {
            "id": source_id,
            "required": bool(repository["required"]),
            "status": "COMPLETE",
            "source_version": repository["source_version"],
            "identity": repository["identity"],
            "scope": {
                "direction": "downstream",
                "max_hops": 1,
                "filters": [
                    f"branch:{repository['source_branch']}",
                    f"path:{preflight['mapping']['path']}",
                ],
                "pages": 1,
                "reported_total": 1,
                "returned_total": 1,
            },
            "freshness": {
                "observed_at": preflight["captured_at"],
                "source_updated_at": repository["source_committed_at"],
                "maximum_age_seconds": 31_536_000,
            },
            "permissions": {
                "principal": preflight["principal"],
                "effective_scope": ",".join(effective),
            },
            "limitations": list(preflight["limitations"]),
            "artifact_ids": list(preflight["artifact_ids"]),
        }
    )
    merged = with_digest(
        {
            "schema_version": "1.0.0",
            "captured_at": preflight["captured_at"],
            "mode": evidence_envelope["mode"],
            "sources": sorted(sources, key=lambda source: str(source["id"])),
        },
        "envelope_digest",
    )
    validate_schema(
        "evidence-envelope",
        merged,
        refusal_code=RefusalCode.INTEGRITY_DIGEST_MISMATCH,
    )
    return merged


def merge_repository_reconciliation_evidence(
    evidence_envelope: Mapping[str, Any],
    observation: Mapping[str, Any],
    *,
    baseline_source: Mapping[str, Any],
) -> dict[str, Any]:
    """Join a verified applied Git source without changing declared scope."""

    verify_digest(dict(evidence_envelope), "envelope_digest")
    verify_digest(dict(observation), "reconciliation_digest")
    source_id = f"git:{observation['repository']['id']}"
    sources = [
        dict(source)
        for source in evidence_envelope["sources"]
        if source["id"] != source_id
    ]
    capabilities = observation["capabilities"]
    effective = [
        capability
        for capability in ("read", "plan", "apply", "validate", "compensate")
        if capabilities[capability]
    ]
    sources.append(
        {
            "id": source_id,
            "required": bool(baseline_source["required"]),
            "status": "COMPLETE",
            "source_version": observation["repository"]["source_version"],
            "identity": observation["repository"]["identity"],
            "scope": dict(baseline_source["scope"]),
            "freshness": {
                "observed_at": observation["captured_at"],
                "source_updated_at": observation["repository"]["source_committed_at"],
                "maximum_age_seconds": baseline_source["freshness"][
                    "maximum_age_seconds"
                ],
            },
            "permissions": {
                "principal": observation["principal"],
                "effective_scope": ",".join(effective),
            },
            "limitations": list(observation["limitations"]),
            "artifact_ids": [observation["reconciliation_digest"]],
        }
    )
    merged = with_digest(
        {
            "schema_version": "1.0.0",
            "captured_at": observation["captured_at"],
            "mode": evidence_envelope["mode"],
            "sources": sorted(sources, key=lambda source: str(source["id"])),
        },
        "envelope_digest",
    )
    validate_schema(
        "evidence-envelope",
        merged,
        refusal_code=RefusalCode.INTEGRITY_DIGEST_MISMATCH,
    )
    return merged


def discover_repository(
    root: Path,
    manifest: Mapping[str, Any],
    *,
    target_field: str,
) -> dict[str, Any]:
    token = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(target_field)}(?![A-Za-z0-9_])")
    text_matches: list[dict[str, Any]] = []
    select_star_paths: list[str] = []
    inspected = 0
    for path in safe_source_files(root):
        inspected += 1
        content = path.read_text(encoding="utf-8")
        relative = path.relative_to(root).as_posix()
        if re.search(r"(?is)\bselect\s+\*", content):
            select_star_paths.append(relative)
        if token.search(content):
            classification = "direct"
            if "{{" in content and path.parent.name == "macros":
                classification = "macro_or_generated"
            elif re.search(
                rf"(?i)\b{re.escape(target_field)}\s+as\s+\w+",
                content,
            ):
                classification = "aliased_direct"
            text_matches.append(
                {
                    "path": relative,
                    "classification": classification,
                    "fingerprint": digest_file(path),
                }
            )
    nodes = manifest.get("nodes")
    if not isinstance(nodes, dict):
        raise Refusal(
            RefusalCode.SOURCE_DBT_UNAVAILABLE,
            "The dbt manifest omitted nodes.",
        )
    structural = [
        {
            "unique_id": unique_id,
            "resource_type": node.get("resource_type"),
            "original_file_path": node.get("original_file_path"),
            "depends_on_nodes": sorted(
                (node.get("depends_on") or {}).get("nodes") or []
            ),
            "compiled_contains_target": bool(
                token.search(str(node.get("compiled_code") or ""))
            ),
        }
        for unique_id, node in sorted(nodes.items())
        if isinstance(node, dict)
        and node.get("resource_type") in {"model", "seed", "test"}
    ]
    return {
        "layers": [
            "bounded_text",
            "dbt_manifest",
            "dbt_compiled_sql",
        ],
        "inspected_file_count": inspected,
        "text_matches": text_matches,
        "select_star_paths": sorted(select_star_paths),
        "manifest_nodes": structural,
        "limitations": [
            "Jinja and macros can hide references from bounded text",
            "SELECT * is uncertain unless compiled structure proves the field",
            "Only the checked-out branch is covered",
        ],
    }


def resolve_manifest_mapping(
    manifest: Mapping[str, Any],
    known_consumer_urns: Sequence[str],
) -> dict[str, Any]:
    nodes = manifest.get("nodes")
    if not isinstance(nodes, dict):
        raise Refusal(
            RefusalCode.SOURCE_DBT_UNAVAILABLE,
            "The dbt manifest omitted nodes.",
        )
    known = set(known_consumer_urns)
    matches: list[dict[str, Any]] = []
    for unique_id, value in nodes.items():
        if not isinstance(value, dict) or value.get("resource_type") != "model":
            continue
        meta = (value.get("config") or {}).get("meta") or value.get("meta") or {}
        retirement = (
            meta.get("retirement_conductor") if isinstance(meta, dict) else None
        )
        observed = (
            retirement.get("datahub_urn") if isinstance(retirement, dict) else None
        )
        if isinstance(observed, str) and observed in known:
            matches.append(
                {
                    "unique_id": str(unique_id),
                    "original_file_path": str(value["original_file_path"]),
                    "datahub_urn": observed,
                    "mapping_basis": "exact_dbt_manifest_meta",
                }
            )
    if not matches:
        raise Refusal(
            RefusalCode.IDENTITY_NOT_FOUND,
            (
                "No dbt manifest node declared an exact URN from the fresh "
                "DataHub inventory."
            ),
        )
    if len(matches) != 1:
        raise Refusal(
            RefusalCode.IDENTITY_AMBIGUOUS,
            "Multiple dbt manifest nodes matched the fresh DataHub inventory.",
            {"match_count": len(matches)},
        )
    return matches[0]


def resolve_replacement_evidence(
    manifest: Mapping[str, Any],
    *,
    datahub_resolution: Mapping[str, Any],
    target_field: str,
    replacement_field: str,
) -> dict[str, Any]:
    nodes = manifest.get("nodes")
    if not isinstance(nodes, dict):
        raise Refusal(
            RefusalCode.SOURCE_DBT_UNAVAILABLE,
            "The dbt manifest omitted nodes.",
        )
    column_evidence: dict[str, dict[str, Any]] = {}
    for node in nodes.values():
        if not isinstance(node, dict) or node.get("resource_type") != "seed":
            continue
        columns = node.get("columns")
        if not isinstance(columns, dict):
            continue
        for name in (target_field, replacement_field):
            value = columns.get(name)
            if isinstance(value, dict):
                column_evidence[name] = {
                    "name": name,
                    "data_type": value.get("data_type"),
                    "resource_unique_id": node.get("unique_id"),
                }
    if target_field not in column_evidence or replacement_field not in column_evidence:
        raise Refusal(
            RefusalCode.SPEC_REPLACEMENT_INCOMPATIBLE,
            "dbt source metadata did not expose both field identities.",
        )
    target_datahub = datahub_resolution["target_field"]
    replacement_datahub = datahub_resolution["replacement_field"]
    datahub_types = {
        str(target_datahub.get("nativeDataType", "")).casefold(),
        str(replacement_datahub.get("nativeDataType", "")).casefold(),
    }
    dbt_types = {
        str(column_evidence[target_field].get("data_type", "")).casefold(),
        str(column_evidence[replacement_field].get("data_type", "")).casefold(),
    }
    compatible = (
        len(datahub_types) == 1
        and "" not in datahub_types
        and len(dbt_types) == 1
        and "" not in dbt_types
        and datahub_types == dbt_types
    )
    if not compatible:
        raise Refusal(
            RefusalCode.SPEC_REPLACEMENT_INCOMPATIBLE,
            "Live DataHub and dbt metadata did not prove compatible field types.",
            {
                "datahub_types": sorted(datahub_types),
                "dbt_types": sorted(dbt_types),
            },
        )
    return {
        "target": {
            "field": target_field,
            "datahub_native_type": target_datahub["nativeDataType"],
            "dbt_data_type": column_evidence[target_field]["data_type"],
        },
        "replacement": {
            "field": replacement_field,
            "datahub_native_type": replacement_datahub["nativeDataType"],
            "dbt_data_type": column_evidence[replacement_field]["data_type"],
        },
        "compatible": True,
        "basis": [
            "live_datahub_schema",
            "dbt_manifest_seed_columns",
            "declared_same_dataset_replacement",
        ],
    }


def run_git(
    settings: GitDbtSettings,
    *arguments: str,
    identity_time: str | None = None,
) -> str:
    environment = {
        "PATH": "/usr/bin:/bin",
        "HOME": "/tmp/retirement-conductor-git-home",
        "LC_ALL": "C.UTF-8",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_SYSTEM": "/dev/null",
    }
    if identity_time is not None:
        environment.update(
            {
                "GIT_AUTHOR_NAME": "Retirement Conductor",
                "GIT_AUTHOR_EMAIL": "adapter@retirement-conductor.invalid",
                "GIT_COMMITTER_NAME": "Retirement Conductor",
                "GIT_COMMITTER_EMAIL": "adapter@retirement-conductor.invalid",
                "GIT_AUTHOR_DATE": identity_time,
                "GIT_COMMITTER_DATE": identity_time,
            }
        )
    try:
        result = subprocess.run(
            [
                str(settings.git_executable),
                "-c",
                "commit.gpgsign=false",
                "-c",
                "core.fsmonitor=false",
                "-c",
                "core.hooksPath=/dev/null",
                "-C",
                str(settings.repository_root),
                *arguments,
            ],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise Refusal(
            RefusalCode.SOURCE_GIT_UNAVAILABLE,
            "The Git command could not run.",
            {"operation": arguments[0] if arguments else "unknown"},
        ) from exc
    if result.returncode != 0:
        raise Refusal(
            RefusalCode.SOURCE_GIT_UNAVAILABLE,
            "The Git command failed.",
            {
                "operation": arguments[0] if arguments else "unknown",
                "exit_code": result.returncode,
                "stderr": redact_log(result.stderr)[:400],
            },
        )
    return result.stdout.rstrip("\r\n")


def checked_target_path(
    root: Path,
    relative_text: str,
    *,
    allowed_paths: Sequence[str],
) -> Path:
    relative = PurePosixPath(relative_text)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise Refusal(
            RefusalCode.SCOPE_PATH_OUTSIDE_ROOT,
            "The repository target path is not a safe relative path.",
        )
    normalized = relative.as_posix()
    if not path_is_allowed(normalized, allowed_paths):
        raise Refusal(
            RefusalCode.SCOPE_TARGET_NOT_ALLOWED,
            "The repository target is outside the allowed path prefixes.",
            {"target": normalized},
        )
    path = root.joinpath(*relative.parts)
    if path.is_symlink():
        raise Refusal(
            RefusalCode.SCOPE_PATH_OUTSIDE_ROOT,
            "The repository target cannot be a symlink.",
        )
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(root.resolve(strict=True))
    except (OSError, ValueError) as exc:
        raise Refusal(
            RefusalCode.SCOPE_PATH_OUTSIDE_ROOT,
            "The repository target escaped or was absent from the root.",
        ) from exc
    if not resolved.is_file():
        raise Refusal(
            RefusalCode.SOURCE_NOT_FOUND,
            "The repository target is not a regular file.",
        )
    return resolved


def path_is_allowed(path: str, allowed_paths: Sequence[str]) -> bool:
    relative = PurePosixPath(path)
    if relative.is_absolute() or ".." in relative.parts:
        return False
    return any(
        path == prefix.rstrip("/") or path.startswith(f"{prefix.rstrip('/')}/")
        for prefix in allowed_paths
    )


def reject_unsafe_tree(root: Path) -> None:
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if relative.parts and relative.parts[0] == ".git":
            continue
        if path.is_symlink():
            raise Refusal(
                RefusalCode.VALIDATION_SCOPE_VIOLATION,
                "Repository symlinks are refused before validation.",
                {"path": relative.as_posix()},
            )
    for dependency_file in (".gitmodules", "dependencies.yml", "packages.yml"):
        path = root / dependency_file
        if path.is_file() and path.read_text(encoding="utf-8").strip():
            raise Refusal(
                RefusalCode.VALIDATION_SCOPE_VIOLATION,
                "External dbt dependencies are unsupported in the initial adapter.",
                {"path": dependency_file},
            )


def copy_repository(source: Path, destination: Path) -> None:
    for path in safe_source_files(source):
        relative = path.relative_to(source)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        target.chmod(path.stat().st_mode & 0o777)


def safe_source_files(root: Path) -> list[Path]:
    result: list[Path] = []
    for current, directory_names, file_names in os.walk(
        root,
        followlinks=False,
    ):
        current_path = Path(current)
        directory_names[:] = [
            name
            for name in sorted(directory_names)
            if name not in IGNORED_DIRECTORIES
            and not (current_path / name).is_symlink()
        ]
        for name in sorted(file_names):
            path = current_path / name
            if path.is_symlink():
                raise Refusal(
                    RefusalCode.VALIDATION_SCOPE_VIOLATION,
                    "Repository symlinks are refused before validation.",
                    {"path": path.relative_to(root).as_posix()},
                )
            if path.stat().st_size > 10 * 1024 * 1024:
                raise Refusal(
                    RefusalCode.VALIDATION_SCOPE_VIOLATION,
                    "A repository file exceeded the 10 MiB validation bound.",
                    {"path": path.relative_to(root).as_posix()},
                )
            result.append(path)
            if len(result) > 10_000:
                raise Refusal(
                    RefusalCode.VALIDATION_SCOPE_VIOLATION,
                    "The repository exceeded the 10,000-file validation bound.",
                )
    return result


def token_occurrences(content: str, identifier: str) -> int:
    pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(identifier)}(?![A-Za-z0-9_])")
    return len(pattern.findall(content))


def replace_identifier_once(content: str, before: str, after: str) -> str:
    pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(before)}(?![A-Za-z0-9_])")
    patched, count = pattern.subn(after, content, count=1)
    if count != 1 or token_occurrences(content, before) != 1:
        raise Refusal(
            RefusalCode.IDENTITY_AMBIGUOUS,
            "The approved patch token was missing or ambiguous.",
            {"occurrences": token_occurrences(content, before)},
        )
    return patched


def atomic_write_text(path: Path, content: str) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(path.stat().st_mode)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def changed_paths_from_status(status: str) -> set[str]:
    paths: set[str] = set()
    for line in status.splitlines():
        if len(line) < 4:
            continue
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        paths.add(path)
    return paths


def write_versioned_artifact(root: Path, name: str, value: Mapping[str, Any]) -> None:
    write_json(root / f"{name}.json", value)
    identity = digest_json(value).removeprefix("sha256:")[:16]
    write_json(root / f"{name}-{identity}.json", value)


def load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Refusal(
            RefusalCode.SOURCE_DBT_UNAVAILABLE,
            "A required Git/dbt artifact could not be read.",
            {"artifact": path.name},
        ) from exc
    if not isinstance(value, dict):
        raise Refusal(
            RefusalCode.INTEGRITY_DIGEST_MISMATCH,
            "A required Git/dbt artifact was not an object.",
            {"artifact": path.name},
        )
    return value


def load_optional_object(path: Path) -> dict[str, Any] | None:
    return load_object(path) if path.is_file() else None


def consumer_id_for_urn(urn: str) -> str:
    import hashlib

    return "dh-" + hashlib.sha256(urn.encode()).hexdigest()[:20]


def set_validation_limits() -> None:
    resource.setrlimit(
        resource.RLIMIT_AS,
        (3 * 1024 * 1024 * 1024, 3 * 1024 * 1024 * 1024),
    )
    resource.setrlimit(
        resource.RLIMIT_FSIZE,
        (512 * 1024 * 1024, 512 * 1024 * 1024),
    )
    resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))


def redact_log(value: str) -> str:
    without_ansi = re.sub(r"\x1b\[[0-9;]*m", "", value)
    redacted = redact_observation({"log": without_ansi})["log"]
    return str(redacted)[-20_000:]

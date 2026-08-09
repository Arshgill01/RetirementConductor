"""Bounded GitHub push, pull-request, and commit-bound CI evidence."""

from __future__ import annotations

import json
import os
import re
import subprocess
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from retirement_conductor.canonical import (
    digest_bytes,
    digest_json,
    verify_digest,
    with_digest,
)
from retirement_conductor.datahub import utc_now
from retirement_conductor.errors import Refusal
from retirement_conductor.github_pr_config import (
    GitHubPrSettings,
    canonical_github_repository,
)
from retirement_conductor.records import validate_approval
from retirement_conductor.schemas import validate_schema
from retirement_conductor.semantic_validation import approved_targets
from retirement_conductor.vocabulary import RefusalCode

SHA = re.compile(r"^[0-9a-f]{40}$")
WORKFLOW_RUN = re.compile(r"/actions/runs/([0-9]+)(?:/|$)")
VALIDATOR_MARKER = re.compile(
    r"retirement-conductor-validator-versions:\s*(\{[^\n]{1,1000}\})"
)
SAFE_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.+_-]{0,63}$")


class GitHubPrBoundary:
    """One explicit, non-merging GitHub boundary for an approved semantic plan."""

    def __init__(self, settings: GitHubPrSettings) -> None:
        self.settings = settings

    def preflight(self, plan: Mapping[str, Any]) -> dict[str, Any]:
        """Verify local source, exact remote identity, tools, and capabilities."""

        value = self._validate_plan(plan)
        root = self.settings.repository_root
        if (
            not root.is_dir()
            or not (root / ".git").exists()
            or not self.settings.git_executable.is_file()
            or not self.settings.gh_executable.is_file()
        ):
            raise Refusal(
                RefusalCode.SOURCE_GIT_UNAVAILABLE,
                "The GitHub PR repository or native tools are unavailable.",
            )
        top = Path(self._git("rev-parse", "--show-toplevel")).resolve()
        if top != root:
            raise Refusal(
                RefusalCode.SCOPE_PATH_OUTSIDE_ROOT,
                "Git resolved a different repository root.",
            )
        remote_url = self._git("remote", "get-url", self.settings.remote_name)
        if (
            remote_url != self.settings.allowed_remote_url
            or canonical_github_repository(remote_url)
            != self.settings.repository.casefold()
        ):
            raise Refusal(
                RefusalCode.IDENTITY_NOT_FOUND,
                (
                    "The configured Git remote does not equal the allowlisted "
                    "GitHub identity."
                ),
                {"remote_name": self.settings.remote_name},
            )
        repository = value["repository"]
        if repository["base_branch"] != self.settings.base_branch or not str(
            repository["target_branch"]
        ).startswith(self.settings.branch_prefix):
            raise Refusal(
                RefusalCode.SCOPE_TARGET_NOT_ALLOWED,
                "The semantic plan is outside the GitHub branch allowlist.",
            )
        self._git("cat-file", "-e", f"{repository['source_version']}^{{commit}}")
        return with_digest(
            {
                "schema_version": "1.0.0",
                "result": "PREFLIGHT_OK",
                "campaign_id": value["campaign_id"],
                "plan_digest": value["plan_digest"],
                "repository": self.settings.repository,
                "remote_name": self.settings.remote_name,
                "remote_url_identity": digest_json(remote_url),
                "base_branch": self.settings.base_branch,
                "target_branch": repository["target_branch"],
                "source_version": repository["source_version"],
                "required_check_name": self.settings.required_check_name,
                "capabilities": {
                    "push": self.settings.allow_push,
                    "create_pr": self.settings.allow_pr_creation,
                    "merge": False,
                    "approve": False,
                },
                "git_version": self._git("--version"),
                "gh_version": self._gh("--version").splitlines()[0],
            },
            "preflight_digest",
        )

    def commit_approved_changes(
        self,
        plan: Mapping[str, Any],
        approval: Mapping[str, Any] | None,
        *,
        authorization_digest: str,
        trusted_now: datetime,
        occurred_at: str,
    ) -> dict[str, Any]:
        """Commit the exact reviewed model and generated tests without hooks."""

        value = self._validate_plan(plan)
        self.preflight(value)
        self._validate_approval(
            value,
            approval,
            authorization_digest=authorization_digest,
            trusted_now=trusted_now,
            required_scope=["materialize"],
        )
        repository = value["repository"]
        branch = self._git("branch", "--show-current")
        if branch != repository["target_branch"]:
            raise Refusal(
                RefusalCode.SOURCE_GIT_BRANCH_MOVED,
                "The repository is not on the approved semantic-plan branch.",
                {
                    "expected_branch": repository["target_branch"],
                    "actual_branch": branch,
                },
            )
        expected_targets = approved_targets(value)
        actual_targets = self._working_and_committed_targets(
            str(repository["source_version"])
        )
        if actual_targets != expected_targets:
            raise Refusal(
                RefusalCode.SCOPE_TARGET_NOT_ALLOWED,
                "The local change set does not equal the approved semantic plan.",
                {
                    "approved_targets": expected_targets,
                    "actual_targets": actual_targets,
                },
            )
        self._git("add", "--", *expected_targets)
        if self._git("diff", "--cached", "--name-only"):
            self._git(
                "commit",
                "--no-verify",
                "-m",
                f"test: add semantic validation for {value['campaign_id']}",
                "--",
                *expected_targets,
                identity_time=occurred_at,
            )
        if self._git("status", "--porcelain=v1", "--untracked-files=all"):
            raise Refusal(
                RefusalCode.SOURCE_GIT_DIRTY,
                "The approved semantic commit left repository changes behind.",
            )
        head_sha = self._git("rev-parse", "HEAD")
        changed = self._committed_targets(str(repository["source_version"]), head_sha)
        if changed != expected_targets:
            raise Refusal(
                RefusalCode.SCOPE_TARGET_NOT_ALLOWED,
                "The committed Git diff differs from the approved target set.",
            )
        tree_listing = self._git("ls-tree", "-r", "--full-tree", head_sha)
        return with_digest(
            {
                "schema_version": "1.0.0",
                "campaign_id": value["campaign_id"],
                "plan_digest": value["plan_digest"],
                "base_sha": repository["source_version"],
                "head_sha": head_sha,
                "branch": repository["target_branch"],
                "changed_files": changed,
                "tree_digest": digest_bytes(tree_listing.encode("utf-8")),
                "committed_at": occurred_at,
            },
            "commit_digest",
        )

    def push(
        self,
        plan: Mapping[str, Any],
        approval: Mapping[str, Any] | None,
        commit: Mapping[str, Any],
        *,
        authorization_digest: str,
        trusted_now: datetime,
    ) -> dict[str, Any]:
        """Push without force and recover only by an exact native remote reread."""

        value = self._validate_plan(plan)
        commit_value = dict(commit)
        verify_digest(commit_value, "commit_digest")
        self.preflight(value)
        self._validate_approval(
            value,
            approval,
            authorization_digest=authorization_digest,
            trusted_now=trusted_now,
            required_scope=["push"],
        )
        if not self.settings.allow_push:
            raise Refusal(
                RefusalCode.AUTH_APPLY_DISABLED,
                "GitHub push is disabled by explicit configuration.",
            )
        head_sha = self._git("rev-parse", "HEAD")
        branch = str(value["repository"]["target_branch"])
        if (
            head_sha != commit_value.get("head_sha")
            or self._git("branch", "--show-current") != branch
        ):
            raise Refusal(
                RefusalCode.SOURCE_GIT_BRANCH_MOVED,
                "The approved local head changed before push.",
            )
        remote_before = self._remote_head(branch)
        result = "REUSED"
        if remote_before != head_sha:
            result = "PUSHED"
            try:
                self._git(
                    "push",
                    "--porcelain",
                    self.settings.remote_name,
                    f"HEAD:refs/heads/{branch}",
                )
            except (Refusal, subprocess.TimeoutExpired):
                remote_after_loss = self._remote_head(branch)
                if remote_after_loss != head_sha:
                    raise Refusal(
                        RefusalCode.APPLY_OUTCOME_UNKNOWN,
                        (
                            "Push outcome is unknown; native reread did not prove "
                            "the expected head."
                        ),
                        {"branch": branch},
                    ) from None
                result = "RECOVERED_AFTER_TRANSPORT_LOSS"
        remote_sha = self._remote_head(branch)
        if remote_sha != head_sha:
            raise Refusal(
                RefusalCode.SOURCE_GIT_BRANCH_MOVED,
                "The remote branch does not match the approved local commit.",
            )
        return with_digest(
            {
                "schema_version": "1.0.0",
                "result": result,
                "campaign_id": value["campaign_id"],
                "plan_digest": value["plan_digest"],
                "remote_name": self.settings.remote_name,
                "repository": self.settings.repository,
                "branch": branch,
                "head_sha": head_sha,
                "remote_url_identity": digest_json(self.settings.allowed_remote_url),
                "pushed_at": utc_now(),
            },
            "push_digest",
        )

    def create_or_reuse_pull_request(
        self,
        plan: Mapping[str, Any],
        approval: Mapping[str, Any] | None,
        commit: Mapping[str, Any],
        *,
        authorization_digest: str,
        trusted_now: datetime,
        title: str,
    ) -> dict[str, Any]:
        """Create exactly one campaign PR, or reread and reuse its exact identity."""

        value = self._validate_plan(plan)
        commit_value = dict(commit)
        verify_digest(commit_value, "commit_digest")
        self._validate_approval(
            value,
            approval,
            authorization_digest=authorization_digest,
            trusted_now=trusted_now,
            required_scope=["create-pr"],
        )
        if not self.settings.allow_pr_creation:
            raise Refusal(
                RefusalCode.AUTH_APPLY_DISABLED,
                "GitHub pull-request creation is disabled by explicit configuration.",
            )
        head_sha = str(commit_value["head_sha"])
        branch = str(value["repository"]["target_branch"])
        if self._remote_head(branch) != head_sha:
            raise Refusal(
                RefusalCode.SOURCE_GIT_BRANCH_MOVED,
                "The exact approved commit is not present on the allowlisted remote.",
            )
        marker = self._campaign_marker(value)
        matches = self._campaign_pull_requests(branch, marker)
        if len(matches) > 1:
            raise Refusal(
                RefusalCode.IDENTITY_AMBIGUOUS,
                "More than one GitHub pull request claims this campaign plan.",
            )
        result = "REUSED"
        if not matches:
            body = (
                f"Retirement Conductor campaign `{value['campaign_id']}`.\n\n"
                "The model proposed typed semantic checks; deterministic code "
                "froze the targets and a human approved the exact plan. This PR "
                "does not authorize merge or producer retirement.\n\n"
                f"{marker}\n"
            )
            try:
                self._gh(
                    "pr",
                    "create",
                    "--repo",
                    self.settings.repository,
                    "--base",
                    self.settings.base_branch,
                    "--head",
                    branch,
                    "--title",
                    title,
                    "--body",
                    body,
                )
            except (Refusal, subprocess.TimeoutExpired):
                matches = self._campaign_pull_requests(branch, marker)
                if len(matches) != 1:
                    raise Refusal(
                        RefusalCode.APPLY_OUTCOME_UNKNOWN,
                        "Pull-request outcome is unknown after transport loss.",
                        {"branch": branch},
                    ) from None
                result = "RECOVERED_AFTER_TRANSPORT_LOSS"
            else:
                result = "CREATED"
                matches = self._campaign_pull_requests(branch, marker)
        if len(matches) != 1:
            raise Refusal(
                RefusalCode.APPLY_OUTCOME_UNKNOWN,
                "GitHub did not expose exactly one campaign pull request.",
            )
        observed = self.reread_pull_request(int(matches[0]["number"]))
        self._verify_pull_request(value, commit_value, observed)
        return with_digest(
            {
                "schema_version": "1.0.0",
                "result": result,
                "campaign_id": value["campaign_id"],
                "plan_digest": value["plan_digest"],
                "pull_request": observed,
                "captured_at": utc_now(),
            },
            "pull_request_digest",
        )

    def reread_pull_request(self, number: int) -> dict[str, Any]:
        """Read exact PR identity, head, state, and changed-file set from GitHub."""

        value = self._gh_json(
            "pr",
            "view",
            str(number),
            "--repo",
            self.settings.repository,
            "--json",
            "number,url,baseRefName,headRefName,headRefOid,state,files",
        )
        if not isinstance(value, Mapping):
            raise Refusal(
                RefusalCode.SOURCE_GIT_UNAVAILABLE,
                "GitHub returned an invalid pull-request observation.",
            )
        files = value.get("files")
        if not isinstance(files, list) or not all(
            isinstance(item, Mapping) and isinstance(item.get("path"), str)
            for item in files
        ):
            raise Refusal(
                RefusalCode.EVIDENCE_REQUIRED_SOURCE_INCOMPLETE,
                "GitHub omitted the pull-request changed-file set.",
            )
        return {
            "number": int(value["number"]),
            "url": str(value["url"]),
            "base": str(value["baseRefName"]),
            "head": str(value["headRefName"]),
            "head_sha": str(value["headRefOid"]),
            "state": str(value["state"]),
            "changed_files": sorted(str(item["path"]) for item in files),
        }

    def capture_ci(
        self,
        plan: Mapping[str, Any],
        pull_request_record: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Accept only the named dbt check run for the exact current PR head SHA."""

        value = self._validate_plan(plan)
        pr_record = dict(pull_request_record)
        verify_digest(pr_record, "pull_request_digest")
        observed = self.reread_pull_request(int(pr_record["pull_request"]["number"]))
        self._verify_pull_request(value, None, observed)
        expected_sha = str(pr_record["pull_request"]["head_sha"])
        if observed["head_sha"] != expected_sha:
            raise Refusal(
                RefusalCode.SOURCE_GIT_BRANCH_MOVED,
                "The pull-request head changed after approval or validation.",
                {
                    "expected_head_sha": expected_sha,
                    "actual_head_sha": observed["head_sha"],
                },
            )
        response = self._gh_json(
            "api",
            "--method",
            "GET",
            f"repos/{self.settings.repository}/commits/{expected_sha}/check-runs?per_page=100",
            "-H",
            "Accept: application/vnd.github+json",
        )
        if not isinstance(response, Mapping) or not isinstance(
            response.get("check_runs"), list
        ):
            raise Refusal(
                RefusalCode.EVIDENCE_REQUIRED_SOURCE_INCOMPLETE,
                "GitHub check-run evidence is unavailable.",
            )
        runs = response["check_runs"]
        if int(response.get("total_count", len(runs))) != len(runs):
            raise Refusal(
                RefusalCode.EVIDENCE_PAGINATION_FAILED,
                "GitHub check-run evidence exceeded the bounded native page.",
            )
        candidates = [
            item
            for item in runs
            if isinstance(item, Mapping)
            and item.get("name") == self.settings.required_check_name
        ]
        if not candidates:
            raise Refusal(
                RefusalCode.VALIDATION_RECEIPT_INCONCLUSIVE,
                "The required dbt CI check is absent from the exact PR head.",
                {"required_check": self.settings.required_check_name},
            )
        selected = max(candidates, key=lambda item: int(item.get("id", 0)))
        if selected.get("head_sha") != expected_sha:
            raise Refusal(
                RefusalCode.SOURCE_RECEIPT_VERSION_MISMATCH,
                "The dbt CI check belongs to another commit.",
            )
        if (
            selected.get("status") != "completed"
            or selected.get("conclusion") != "success"
        ):
            raise Refusal(
                RefusalCode.VALIDATION_RECEIPT_FAILED,
                "The exact required dbt CI check did not pass.",
                {
                    "status": selected.get("status"),
                    "conclusion": selected.get("conclusion"),
                },
            )
        details_url = str(selected.get("details_url") or "")
        workflow_match = WORKFLOW_RUN.search(details_url)
        output = selected.get("output")
        summary = (
            str(output.get("summary") or "") if isinstance(output, Mapping) else ""
        )
        workflow_run_id = (
            int(workflow_match.group(1)) if workflow_match is not None else None
        )
        validator_versions = _validator_versions(summary)
        if not validator_versions and workflow_run_id is not None:
            log = self._gh(
                "run",
                "view",
                str(workflow_run_id),
                "--repo",
                self.settings.repository,
                "--log",
            )
            validator_versions = _validator_versions(log)
        receipt = with_digest(
            {
                "schema_version": "1.0.0",
                "campaign_id": value["campaign_id"],
                "plan_digest": value["plan_digest"],
                "pull_request_number": observed["number"],
                "head_sha": expected_sha,
                "check_name": self.settings.required_check_name,
                "check_run_id": int(selected["id"]),
                "workflow_run_id": workflow_run_id,
                "conclusion": "success",
                "completed_at": str(selected["completed_at"]),
                "validator_versions": validator_versions,
                "captured_at": utc_now(),
            },
            "ci_digest",
        )
        latest = self.reread_pull_request(observed["number"])
        if latest["head_sha"] != expected_sha:
            raise Refusal(
                RefusalCode.SOURCE_GIT_BRANCH_MOVED,
                "The pull-request head changed while CI evidence was captured.",
            )
        return receipt

    def emit_receipt(
        self,
        plan: Mapping[str, Any],
        commit: Mapping[str, Any],
        native_validation: Mapping[str, Any],
        pull_request_record: Mapping[str, Any],
        ci: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Emit a strict receipt only while the PR and CI still name one head."""

        value = self._validate_plan(plan)
        commit_value = dict(commit)
        validation_value = dict(native_validation)
        pr_record = dict(pull_request_record)
        ci_value = dict(ci)
        verify_digest(commit_value, "commit_digest")
        verify_digest(validation_value, "native_validation_digest")
        verify_digest(pr_record, "pull_request_digest")
        verify_digest(ci_value, "ci_digest")
        observed = self.reread_pull_request(int(pr_record["pull_request"]["number"]))
        self._verify_pull_request(value, commit_value, observed)
        expected_sha = str(commit_value["head_sha"])
        if (
            validation_value.get("head_sha") != expected_sha
            or validation_value.get("result") != "PASSED"
            or ci_value.get("head_sha") != expected_sha
        ):
            raise Refusal(
                RefusalCode.SOURCE_RECEIPT_VERSION_MISMATCH,
                "CI evidence is not bound to the exact pull-request head.",
            )
        receipt = with_digest(
            {
                "schema_version": "1.0.0",
                "campaign_id": value["campaign_id"],
                "plan_digest": value["plan_digest"],
                "remote": {
                    "name": self.settings.remote_name,
                    "repository": self.settings.repository,
                    "url_identity": digest_json(self.settings.allowed_remote_url),
                },
                "commit": {
                    "head_sha": expected_sha,
                    "tree_digest": commit_value["tree_digest"],
                    "changed_files": commit_value["changed_files"],
                },
                "native_validation": {
                    "head_sha": validation_value["head_sha"],
                    "result": validation_value["result"],
                    "validator": validation_value["validator"],
                    "validator_version": validation_value["validator_version"],
                    "validation_digest": validation_value["validation_digest"],
                    "artifact_ids": validation_value["artifact_ids"],
                },
                "pull_request": observed,
                "ci": {
                    "head_sha": ci_value["head_sha"],
                    "check_name": ci_value["check_name"],
                    "check_run_id": ci_value["check_run_id"],
                    "workflow_run_id": ci_value["workflow_run_id"],
                    "conclusion": ci_value["conclusion"],
                    "completed_at": ci_value["completed_at"],
                    "validator_versions": ci_value["validator_versions"],
                },
                "captured_at": utc_now(),
            },
            "receipt_digest",
        )
        validate_schema(
            "github-pr-receipt",
            receipt,
            refusal_code=RefusalCode.INTEGRITY_DIGEST_MISMATCH,
        )
        return receipt

    def bind_native_validation(
        self,
        plan: Mapping[str, Any],
        commit: Mapping[str, Any],
        validation: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Bind a passed dbt-native validation result to the exact local PR head."""

        value = self._validate_plan(plan)
        commit_value = dict(commit)
        validation_value = dict(validation)
        verify_digest(commit_value, "commit_digest")
        verify_digest(validation_value, "validation_digest")
        current_head = self._git("rev-parse", "HEAD")
        if current_head != commit_value.get("head_sha"):
            raise Refusal(
                RefusalCode.SOURCE_GIT_BRANCH_MOVED,
                "The repository head changed after the approved commit.",
            )
        if validation_value.get("result") != "PASSED":
            raise Refusal(
                RefusalCode.VALIDATION_RECEIPT_FAILED,
                "Only passed dbt-native validation can bind to a PR head.",
            )
        return with_digest(
            {
                "schema_version": "1.0.0",
                "campaign_id": value["campaign_id"],
                "plan_digest": value["plan_digest"],
                "head_sha": current_head,
                "result": "PASSED",
                "validator": validation_value["validator"],
                "validator_version": validation_value["validator_version"],
                "validation_digest": validation_value["validation_digest"],
                "artifact_ids": validation_value["artifact_ids"],
                "captured_at": utc_now(),
            },
            "native_validation_digest",
        )

    def require_current_head(self, receipt: Mapping[str, Any]) -> None:
        """Invalidate an accepted receipt after any later PR-head commit."""

        value = dict(receipt)
        validate_schema(
            "github-pr-receipt",
            value,
            refusal_code=RefusalCode.INTEGRITY_DIGEST_MISMATCH,
        )
        verify_digest(value, "receipt_digest")
        observed = self.reread_pull_request(int(value["pull_request"]["number"]))
        if observed["head_sha"] != value["commit"]["head_sha"]:
            raise Refusal(
                RefusalCode.SOURCE_GIT_BRANCH_MOVED,
                "The pull-request head changed; replan, reapprove, and revalidate.",
                {
                    "accepted_head_sha": value["commit"]["head_sha"],
                    "current_head_sha": observed["head_sha"],
                },
            )

    @staticmethod
    def require_supported_action(action: str) -> None:
        """Refuse merge, self-approval, deletion, force push, and protection changes."""

        if action not in {"push", "create-pr", "read-pr", "read-ci"}:
            raise Refusal(
                RefusalCode.AUTH_APPROVAL_WRONG_SCOPE,
                "The GitHub boundary does not authorize this action.",
                {"action": action},
            )

    def _validate_plan(self, plan: Mapping[str, Any]) -> dict[str, Any]:
        value = dict(plan)
        validate_schema(
            "semantic-validation-plan",
            value,
            refusal_code=RefusalCode.INTEGRITY_DIGEST_MISMATCH,
        )
        verify_digest(value, "plan_digest")
        return value

    def _validate_approval(
        self,
        plan: Mapping[str, Any],
        approval: Mapping[str, Any] | None,
        *,
        authorization_digest: str,
        trusted_now: datetime,
        required_scope: Sequence[str],
    ) -> None:
        validate_approval(
            approval,
            campaign_id=str(plan["campaign_id"]),
            plan_digest=str(plan["plan_digest"]),
            source_version=str(plan["repository"]["source_version"]),
            targets=approved_targets(plan),
            required_scope=required_scope,
            authorization_digest=authorization_digest,
            trusted_now=trusted_now,
        )

    def _verify_pull_request(
        self,
        plan: Mapping[str, Any],
        commit: Mapping[str, Any] | None,
        observed: Mapping[str, Any],
    ) -> None:
        expected_sha = (
            str(commit["head_sha"]) if commit is not None else str(observed["head_sha"])
        )
        if (
            observed["base"] != self.settings.base_branch
            or observed["head"] != plan["repository"]["target_branch"]
            or observed["head_sha"] != expected_sha
            or observed["state"] != "OPEN"
            or list(observed["changed_files"]) != approved_targets(plan)
        ):
            raise Refusal(
                RefusalCode.SCOPE_RECEIPT_TARGET_MISMATCH,
                "The native GitHub pull request differs from the approved plan.",
            )

    def _campaign_pull_requests(self, branch: str, marker: str) -> list[dict[str, Any]]:
        value = self._gh_json(
            "pr",
            "list",
            "--repo",
            self.settings.repository,
            "--state",
            "all",
            "--head",
            branch,
            "--limit",
            "100",
            "--json",
            "number,body",
        )
        if not isinstance(value, list):
            raise Refusal(
                RefusalCode.EVIDENCE_REQUIRED_SOURCE_INCOMPLETE,
                "GitHub pull-request listing was invalid.",
            )
        return [
            dict(item)
            for item in value
            if isinstance(item, Mapping) and marker in str(item.get("body") or "")
        ]

    @staticmethod
    def _campaign_marker(plan: Mapping[str, Any]) -> str:
        return (
            "<!-- retirement-conductor-campaign:"
            f"{plan['campaign_id']} plan:{plan['plan_digest']} -->"
        )

    def _working_and_committed_targets(self, base_sha: str) -> list[str]:
        committed = set(self._committed_targets(base_sha, "HEAD"))
        status = self._git("status", "--porcelain=v1", "--untracked-files=all")
        working: set[str] = set()
        for line in status.splitlines():
            if len(line) < 4:
                continue
            path = line[3:]
            if " -> " in path:
                path = path.split(" -> ", 1)[1]
            working.add(path)
        return sorted(committed | working)

    def _committed_targets(self, base_sha: str, head_sha: str) -> list[str]:
        return sorted(
            line
            for line in self._git(
                "diff", "--name-only", f"{base_sha}..{head_sha}"
            ).splitlines()
            if line
        )

    def _remote_head(self, branch: str) -> str | None:
        output = self._git(
            "ls-remote",
            "--heads",
            self.settings.remote_name,
            f"refs/heads/{branch}",
        )
        if not output:
            return None
        lines = output.splitlines()
        if len(lines) != 1:
            raise Refusal(
                RefusalCode.IDENTITY_AMBIGUOUS,
                "The remote branch identity is ambiguous.",
            )
        sha = lines[0].split("\t", 1)[0]
        if not SHA.fullmatch(sha):
            raise Refusal(
                RefusalCode.SOURCE_GIT_UNAVAILABLE,
                "The remote branch did not return a valid commit identity.",
            )
        return sha

    def _git(self, *arguments: str, identity_time: str | None = None) -> str:
        environment = {
            **os.environ,
            "LC_ALL": "C.UTF-8",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "Retirement Conductor",
            "GIT_AUTHOR_EMAIL": "retirement-conductor@example.invalid",
            "GIT_COMMITTER_NAME": "Retirement Conductor",
            "GIT_COMMITTER_EMAIL": "retirement-conductor@example.invalid",
        }
        if identity_time is not None:
            environment["GIT_AUTHOR_DATE"] = identity_time
            environment["GIT_COMMITTER_DATE"] = identity_time
        return self._run(
            [
                str(self.settings.git_executable),
                "-C",
                str(self.settings.repository_root),
                *arguments,
            ],
            environment=environment,
        )

    def _gh(self, *arguments: str) -> str:
        return self._run(
            [str(self.settings.gh_executable), *arguments],
            environment={**os.environ, "LC_ALL": "C.UTF-8", "GH_PROMPT_DISABLED": "1"},
        )

    def _gh_json(self, *arguments: str) -> Any:
        output = self._gh(*arguments)
        try:
            return json.loads(output)
        except json.JSONDecodeError as exc:
            raise Refusal(
                RefusalCode.SOURCE_GIT_UNAVAILABLE,
                "GitHub returned invalid JSON evidence.",
            ) from exc

    def _run(self, arguments: list[str], *, environment: Mapping[str, str]) -> str:
        try:
            result = subprocess.run(
                arguments,
                check=False,
                capture_output=True,
                text=True,
                cwd=self.settings.repository_root,
                env=dict(environment),
                timeout=self.settings.timeout_seconds,
            )
        except OSError as exc:
            raise Refusal(
                RefusalCode.SOURCE_GIT_UNAVAILABLE,
                "A required native Git or GitHub command is unavailable.",
            ) from exc
        if result.returncode != 0:
            raise Refusal(
                RefusalCode.SOURCE_GIT_UNAVAILABLE,
                "A native Git or GitHub operation failed.",
                {"exit_code": result.returncode},
            )
        return result.stdout.strip()


def _validator_versions(summary: str) -> dict[str, str]:
    match = VALIDATOR_MARKER.search(summary)
    if match is None:
        return {}
    try:
        value = json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}
    if not isinstance(value, Mapping):
        return {}
    result: dict[str, str] = {}
    for key, item in value.items():
        if (
            isinstance(key, str)
            and isinstance(item, str)
            and SAFE_VERSION.fullmatch(key)
            and SAFE_VERSION.fullmatch(item)
        ):
            result[key] = item
    return result

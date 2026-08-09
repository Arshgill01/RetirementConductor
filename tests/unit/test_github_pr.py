from __future__ import annotations

import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from retirement_conductor.canonical import digest_bytes, with_digest
from retirement_conductor.errors import Refusal
from retirement_conductor.github_pr import GitHubPrBoundary
from retirement_conductor.github_pr_config import GitHubPrSettings
from retirement_conductor.semantic_validation import create_semantic_approval

NOW = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)
AUTHORIZATION_DIGEST = f"sha256:{'a' * 64}"
REMOTE_URL = "https://github.com/example/disposable.git"


def _git(repository: Path, *arguments: str) -> str:
    environment = {
        **os.environ,
        "LC_ALL": "C.UTF-8",
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@example.invalid",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@example.invalid",
    }
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    return result.stdout.strip()


def _repository(tmp_path: Path) -> tuple[Path, str]:
    repository = tmp_path / "repository"
    model = repository / "models/orders.sql"
    model.parent.mkdir(parents=True)
    model.write_text("select legacy_status from orders\n", encoding="utf-8")
    _git(repository, "init", "--initial-branch=main")
    _git(repository, "remote", "add", "origin", REMOTE_URL)
    _git(repository, "add", "--all")
    _git(repository, "commit", "-m", "initial")
    source_version = _git(repository, "rev-parse", "HEAD")
    _git(repository, "switch", "-c", "codex/semantic-pr-campaign")
    model.write_text("select order_status from orders\n", encoding="utf-8")
    _git(repository, "add", "models/orders.sql")
    _git(repository, "commit", "-m", "migrate model")
    generated = repository / "tests/retirement_conductor/campaign/01_parity.sql"
    generated.parent.mkdir(parents=True)
    generated.write_text("select 1 where false\n", encoding="utf-8")
    return repository, source_version


def _settings(
    repository: Path, *, push: bool = True, create: bool = True
) -> GitHubPrSettings:
    git_path = shutil.which("git")
    true_path = shutil.which("true")
    assert git_path is not None and true_path is not None
    return GitHubPrSettings(
        repository_root=repository,
        repository="example/disposable",
        remote_name="origin",
        allowed_remote_url=REMOTE_URL,
        base_branch="main",
        branch_prefix="codex/semantic-pr-",
        required_check_name="semantic-dbt",
        principal="test-operator",
        allow_push=push,
        allow_pr_creation=create,
        git_executable=Path(git_path),
        gh_executable=Path(true_path),
        timeout_seconds=30,
    )


def _plan(source_version: str) -> dict[str, Any]:
    content = "select 1 where false\n"
    return with_digest(
        {
            "schema_version": "1.0.0",
            "campaign_id": "campaign",
            "git_plan_digest": f"sha256:{'1' * 64}",
            "repository": {
                "identity": f"sha256:{'2' * 64}",
                "base_branch": "main",
                "source_version": source_version,
                "target_branch": "codex/semantic-pr-campaign",
                "comparison_relation": "orders",
                "consumer_relation": "orders_model",
            },
            "target": {
                "datahub_urn": "urn:li:dataset:orders",
                "field": "legacy_status",
                "native_type": "VARCHAR",
            },
            "replacement": {
                "datahub_urn": "urn:li:dataset:orders",
                "field": "order_status",
                "native_type": "VARCHAR",
            },
            "consumer": {
                "id": "consumer-orders",
                "datahub_urn": "urn:li:dataset:orders-model",
                "repository_id": "analytics",
                "dbt_unique_id": "model.project.orders_model",
                "native_target": "models/orders.sql",
            },
            "evidence_snapshot": {
                "digest": f"sha256:{'3' * 64}",
                "captured_at": "2026-08-09T11:55:00Z",
                "expires_at": "2026-08-09T12:30:00Z",
                "references": [
                    {
                        "evidence_id": "schema",
                        "kind": "datahub_schema",
                        "subject": "urn:li:dataset:orders",
                        "source_version": "1.6.0",
                        "observed_at": "2026-08-09T11:55:00Z",
                        "artifact_id": f"sha256:{'4' * 64}",
                    }
                ],
            },
            "checks": [
                {
                    "check_id": "parity",
                    "primitive": "exact_model_output_parity",
                    "parameters": {},
                    "evidence_references": ["schema"],
                    "rationale": "Require exact field parity.",
                    "expected_validator": {
                        "name": "dbt-core",
                        "version_family": "1.x",
                    },
                    "limitations": [],
                }
            ],
            "materializations": [
                {
                    "check_id": "parity",
                    "path": "tests/retirement_conductor/campaign/01_parity.sql",
                    "content_digest": digest_bytes(content.encode()),
                    "template_version": "semantic-dbt-v1",
                }
            ],
            "generated_targets": ["tests/retirement_conductor/campaign/01_parity.sql"],
            "proposal_digest": f"sha256:{'5' * 64}",
        },
        "plan_digest",
    )


def _approval(plan: dict[str, Any]) -> dict[str, Any]:
    return create_semantic_approval(
        plan,
        principal="external-reviewer",
        authorization_digest=AUTHORIZATION_DIGEST,
        authorized_at="2026-08-09T11:59:00Z",
        expires_at="2026-08-09T13:00:00Z",
    )


def _commit(
    boundary: GitHubPrBoundary,
    plan: dict[str, Any],
) -> dict[str, Any]:
    return boundary.commit_approved_changes(
        plan,
        _approval(plan),
        authorization_digest=AUTHORIZATION_DIGEST,
        trusted_now=NOW,
        occurred_at="2026-08-09T12:00:00Z",
    )


def _observed_pr(plan: dict[str, Any], head_sha: str) -> dict[str, Any]:
    return {
        "number": 17,
        "url": "https://github.com/example/disposable/pull/17",
        "base": "main",
        "head": "codex/semantic-pr-campaign",
        "head_sha": head_sha,
        "state": "OPEN",
        "changed_files": [
            "models/orders.sql",
            "tests/retirement_conductor/campaign/01_parity.sql",
        ],
    }


def test_commit_requires_approval_and_exact_file_set(tmp_path: Path) -> None:
    repository, source_version = _repository(tmp_path)
    plan = _plan(source_version)
    boundary = GitHubPrBoundary(_settings(repository))

    with pytest.raises(Refusal, match="AUTH_APPROVAL_MISSING"):
        boundary.commit_approved_changes(
            plan,
            None,
            authorization_digest=AUTHORIZATION_DIGEST,
            trusted_now=NOW,
            occurred_at="2026-08-09T12:00:00Z",
        )
    commit = _commit(boundary, plan)

    assert commit["changed_files"] == [
        "models/orders.sql",
        "tests/retirement_conductor/campaign/01_parity.sql",
    ]
    assert _git(repository, "status", "--porcelain=v1") == ""
    assert commit["head_sha"] == _git(repository, "rev-parse", "HEAD")


def test_remote_mismatch_and_prepush_head_drift_refuse(tmp_path: Path) -> None:
    repository, source_version = _repository(tmp_path)
    plan = _plan(source_version)
    boundary = GitHubPrBoundary(_settings(repository))
    _git(repository, "remote", "set-url", "origin", "https://github.com/other/repo.git")
    with pytest.raises(Refusal, match="IDENTITY_NOT_FOUND"):
        boundary.preflight(plan)

    _git(repository, "remote", "set-url", "origin", REMOTE_URL)
    commit = _commit(boundary, plan)
    marker = repository / "owner-change.txt"
    marker.write_text("owner change\n", encoding="utf-8")
    _git(repository, "add", "owner-change.txt")
    _git(repository, "commit", "-m", "owner change")
    with pytest.raises(Refusal, match="SOURCE_GIT_BRANCH_MOVED"):
        boundary.push(
            plan,
            _approval(plan),
            commit,
            authorization_digest=AUTHORIZATION_DIGEST,
            trusted_now=NOW,
        )


def test_push_transport_loss_stays_outcome_unknown(tmp_path: Path) -> None:
    repository, source_version = _repository(tmp_path)
    plan = _plan(source_version)

    class LostPushBoundary(GitHubPrBoundary):
        def _remote_head(self, branch: str) -> str | None:
            return None

        def _git(self, *arguments: str, identity_time: str | None = None) -> str:
            if arguments and arguments[0] == "push":
                raise Refusal("SOURCE_GIT_UNAVAILABLE", "transport lost")
            return super()._git(*arguments, identity_time=identity_time)

    boundary = LostPushBoundary(_settings(repository))
    commit = _commit(boundary, plan)

    with pytest.raises(Refusal, match="APPLY_OUTCOME_UNKNOWN"):
        boundary.push(
            plan,
            _approval(plan),
            commit,
            authorization_digest=AUTHORIZATION_DIGEST,
            trusted_now=NOW,
        )


def test_duplicate_pr_retry_reuses_one_campaign_pr(tmp_path: Path) -> None:
    repository, source_version = _repository(tmp_path)
    plan = _plan(source_version)

    class ReuseBoundary(GitHubPrBoundary):
        head_sha = ""

        def _remote_head(self, branch: str) -> str | None:
            return self.head_sha

        def _campaign_pull_requests(
            self, branch: str, marker: str
        ) -> list[dict[str, Any]]:
            return [{"number": 17, "body": marker}]

        def reread_pull_request(self, number: int) -> dict[str, Any]:
            return _observed_pr(plan, self.head_sha)

    boundary = ReuseBoundary(_settings(repository))
    commit = _commit(boundary, plan)
    boundary.head_sha = str(commit["head_sha"])
    first = boundary.create_or_reuse_pull_request(
        plan,
        _approval(plan),
        commit,
        authorization_digest=AUTHORIZATION_DIGEST,
        trusted_now=NOW,
        title="Replace legacy status",
    )
    second = boundary.create_or_reuse_pull_request(
        plan,
        _approval(plan),
        commit,
        authorization_digest=AUTHORIZATION_DIGEST,
        trusted_now=NOW,
        title="Replace legacy status",
    )

    assert first["result"] == second["result"] == "REUSED"
    assert first["pull_request"]["number"] == second["pull_request"]["number"]


def test_ci_wrong_sha_and_later_head_drift_invalidate_receipt(tmp_path: Path) -> None:
    repository, source_version = _repository(tmp_path)
    plan = _plan(source_version)

    class CiBoundary(GitHubPrBoundary):
        current_sha = ""
        check_sha = ""

        def reread_pull_request(self, number: int) -> dict[str, Any]:
            return _observed_pr(plan, self.current_sha)

        def _gh_json(self, *arguments: str) -> Any:
            return {
                "total_count": 1,
                "check_runs": [
                    {
                        "id": 71,
                        "name": "semantic-dbt",
                        "head_sha": self.check_sha,
                        "status": "completed",
                        "conclusion": "success",
                        "completed_at": "2026-08-09T12:10:00Z",
                        "details_url": (
                            "https://github.com/example/disposable/actions/runs/99/job/1"
                        ),
                        "output": {
                            "summary": (
                                "retirement-conductor-validator-versions: "
                                '{"dbt-core":"1.10.13","dbt-duckdb":"1.10.0"}'
                            )
                        },
                    }
                ],
            }

    boundary = CiBoundary(_settings(repository))
    commit = _commit(boundary, plan)
    boundary.current_sha = str(commit["head_sha"])
    pr_record = with_digest(
        {
            "schema_version": "1.0.0",
            "result": "CREATED",
            "campaign_id": "campaign",
            "plan_digest": plan["plan_digest"],
            "pull_request": _observed_pr(plan, str(commit["head_sha"])),
            "captured_at": "2026-08-09T12:05:00Z",
        },
        "pull_request_digest",
    )
    boundary.check_sha = "9" * 40
    with pytest.raises(Refusal, match="SOURCE_RECEIPT_VERSION_MISMATCH"):
        boundary.capture_ci(plan, pr_record)

    boundary.check_sha = str(commit["head_sha"])
    ci = boundary.capture_ci(plan, pr_record)
    validation = with_digest(
        {
            "schema_version": "1.0.0",
            "result": "PASSED",
            "validator": "dbt parse + seed + build + test on DuckDB",
            "validator_version": "1.10.13",
            "adapter_version": "1.10.0",
            "commands": [],
            "artifact_ids": [f"sha256:{'7' * 64}"],
            "sandbox": {"engine": "test"},
            "failed_command": None,
        },
        "validation_digest",
    )
    native_validation = boundary.bind_native_validation(plan, commit, validation)
    receipt = boundary.emit_receipt(plan, commit, native_validation, pr_record, ci)
    assert receipt["ci"]["workflow_run_id"] == 99
    assert receipt["ci"]["validator_versions"]["dbt-core"] == "1.10.13"

    boundary.current_sha = "8" * 40
    with pytest.raises(Refusal, match="SOURCE_GIT_BRANCH_MOVED"):
        boundary.require_current_head(receipt)


@pytest.mark.parametrize("action", ["merge", "approve", "force-push", "delete"])
def test_agent_cannot_merge_approve_force_push_or_delete(action: str) -> None:
    with pytest.raises(Refusal, match="AUTH_APPROVAL_WRONG_SCOPE"):
        GitHubPrBoundary.require_supported_action(action)

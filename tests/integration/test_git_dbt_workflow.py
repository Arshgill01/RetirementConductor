from __future__ import annotations

import os
import shutil
import subprocess
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from retirement_conductor.canonical import (
    digest_file,
    digest_json,
    with_digest,
)
from retirement_conductor.clock import parse_timestamp
from retirement_conductor.datahub import utc_now
from retirement_conductor.errors import Refusal
from retirement_conductor.git_dbt import (
    GitDbtAdapter,
    consumer_id_for_urn,
    write_versioned_artifact,
)
from retirement_conductor.git_dbt_config import GitDbtSettings
from retirement_conductor.git_dbt_workflow import GitDbtWorkflow
from retirement_conductor.specification import load_specification
from retirement_conductor.store import CampaignStore

ROOT = Path(__file__).resolve().parents[2]
CONSUMER_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:dbt,"
    "retirement_conductor.analytics.consumers.orders_model_00,PROD)"
)


def _git(repository: Path, *arguments: str) -> str:
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "LC_ALL": "C.UTF-8",
        "GIT_AUTHOR_NAME": "Workflow Test",
        "GIT_AUTHOR_EMAIL": "workflow@example.invalid",
        "GIT_COMMITTER_NAME": "Workflow Test",
        "GIT_COMMITTER_EMAIL": "workflow@example.invalid",
    }
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    return result.stdout.strip()


def _rfc3339_after(value: str, *, hours: int) -> str:
    return (
        (parse_timestamp(value) + timedelta(hours=hours))
        .isoformat()
        .replace("+00:00", "Z")
    )


def _passing_validation(artifact_root: Path) -> dict[str, Any]:
    validation = with_digest(
        {
            "schema_version": "1.0.0",
            "result": "PASSED",
            "validator": "dbt test stub for campaign orchestration",
            "validator_version": "1.12.0",
            "adapter_version": "1.10.1",
            "commands": [{"arguments": ["test"], "exit_code": 0}],
            "artifact_ids": [f"sha256:{'9' * 64}"],
            "sandbox": {"engine": "test-double"},
            "failed_command": None,
        },
        "validation_digest",
    )
    write_versioned_artifact(artifact_root, "validation", validation)
    return validation


def test_workflow_requires_approval_then_rolls_back_reapplies_and_receipts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repository"
    model = repository / "models" / "orders_model_00.sql"
    model.parent.mkdir(parents=True)
    model.write_text(
        "select legacy_status as normalized_status from orders\n",
        encoding="utf-8",
    )
    _git(repository, "init", "--initial-branch=main")
    _git(repository, "add", "--all")
    _git(repository, "commit", "-m", "initial")
    source_version = _git(repository, "rev-parse", "HEAD")
    git_path = shutil.which("git")
    assert git_path is not None
    adapter = GitDbtAdapter(
        GitDbtSettings(
            repository_root=repository,
            repository_id="analytics",
            default_branch="main",
            dbt_executable=Path("/usr/bin/true"),
            principal="workflow-operator",
            allow_apply=True,
            validation_timeout_seconds=30,
            bwrap_executable=Path("/usr/bin/true"),
            git_executable=Path(git_path),
        )
    )
    monkeypatch.setattr(adapter, "validate_project", _passing_validation)
    specification = load_specification(ROOT / "fixtures/specs/git-dbt-live.yaml")
    specification["evidence"]["repositories"][0]["path"] = str(repository)
    unsigned_specification = {
        key: value
        for key, value in specification.items()
        if key != "specification_digest"
    }
    specification["specification_digest"] = digest_json(unsigned_specification)
    campaign_id = str(specification["campaign"]["id"])
    consumer_id = consumer_id_for_urn(CONSUMER_URN)
    artifact_directory = tmp_path / "artifacts"

    with CampaignStore(tmp_path / "campaign.sqlite", writer_id="test") as store:
        store.create_campaign(
            specification,
            occurred_at="2026-07-30T00:00:00Z",
        )
        envelope = with_digest(
            {
                "schema_version": "1.0.0",
                "captured_at": "2026-07-30T00:01:00Z",
                "mode": "live",
                "sources": [
                    {
                        "id": "datahub",
                        "required": True,
                        "status": "COMPLETE",
                        "source_version": "v1.6.0",
                        "identity": "disposable-datahub",
                        "scope": {
                            "direction": "downstream",
                            "max_hops": 3,
                            "filters": [],
                            "pages": 1,
                            "reported_total": 1,
                            "returned_total": 1,
                        },
                        "freshness": {
                            "observed_at": "2026-07-30T00:01:00Z",
                            "source_updated_at": "2026-07-30T00:01:00Z",
                            "maximum_age_seconds": 900,
                        },
                        "permissions": {
                            "principal": "test",
                            "effective_scope": "read",
                        },
                        "limitations": [],
                        "artifact_ids": [f"sha256:{'8' * 64}"],
                    }
                ],
            },
            "envelope_digest",
        )
        store.record_inventory(
            campaign_id,
            evidence_envelope=envelope,
            consumers=[
                {
                    "id": consumer_id,
                    "disposition": "OPAQUE",
                    "receipt_digest": None,
                }
            ],
            snapshot_digest=f"sha256:{'7' * 64}",
            occurred_at="2026-07-30T00:01:00Z",
        )
        preflight = with_digest(
            {
                "schema_version": "1.0.0",
                "mode": "live",
                "captured_at": "2026-07-30T00:01:00Z",
                "repository": {
                    "id": "analytics",
                    "source_branch": "main",
                    "source_version": source_version,
                    "searched_branches": ["main"],
                    "non_default_branches_searched": False,
                },
                "mapping": {
                    "path": "models/orders_model_00.sql",
                    "datahub_urn": CONSUMER_URN,
                    "unique_id": "model.project.orders_model_00",
                },
                "replacement": {
                    "target": {
                        "field": "legacy_status",
                        "datahub_native_type": "VARCHAR",
                        "dbt_data_type": "varchar",
                    },
                    "replacement": {
                        "field": "order_status",
                        "datahub_native_type": "VARCHAR",
                        "dbt_data_type": "varchar",
                    },
                    "compatible": True,
                },
                "discovery": {
                    "layers": [
                        "bounded_text",
                        "dbt_manifest",
                        "dbt_compiled_sql",
                    ]
                },
                "limitations": ["Only main was searched"],
            },
            "preflight_digest",
        )
        git_root = artifact_directory / campaign_id / "git-dbt"
        write_versioned_artifact(git_root, "preflight", preflight)
        workflow = GitDbtWorkflow(
            store=store,
            adapter=adapter,
            artifact_directory=artifact_directory,
        )

        first_plan = workflow.plan(campaign_id)["plan"]
        with pytest.raises(Refusal, match="AUTH_APPROVAL_WRONG_PLAN"):
            workflow.apply(
                campaign_id,
                confirmed_plan_digest=f"sha256:{'0' * 64}",
            )
        with pytest.raises(Refusal, match="AUTH_APPROVAL_MISSING"):
            workflow.apply(
                campaign_id,
                confirmed_plan_digest=str(first_plan["plan_digest"]),
            )
        assert _git(repository, "branch", "--show-current") == "main"
        assert (
            store.connection.execute(
                "SELECT COUNT(*) FROM native_identity_claims"
            ).fetchone()[0]
            == 0
        )

        authorized_at = utc_now()
        workflow.authorize(
            campaign_id,
            principal="workflow-operator",
            authorized_at=authorized_at,
            expires_at=_rfc3339_after(authorized_at, hours=1),
        )
        first_apply = workflow.apply(
            campaign_id,
            confirmed_plan_digest=str(first_plan["plan_digest"]),
        )["apply"]
        event_count = len(store.events(campaign_id))
        replay = workflow.apply(
            campaign_id,
            confirmed_plan_digest=str(first_plan["plan_digest"]),
        )["apply"]
        assert replay["apply_digest"] == first_apply["apply_digest"]
        assert len(store.events(campaign_id)) == event_count

        restored = workflow.compensate(campaign_id)["compensation"]
        assert (
            restored["restored_fingerprint"]
            == first_plan["target"]["before_fingerprint"]
        )
        assert _git(repository, "branch", "--show-current") == "main"
        assert digest_file(model) == first_plan["target"]["before_fingerprint"]

        second_plan = workflow.plan(campaign_id)["plan"]
        assert second_plan["plan_digest"] != first_plan["plan_digest"]
        authorized_at = utc_now()
        workflow.authorize(
            campaign_id,
            principal="workflow-operator",
            authorized_at=authorized_at,
            expires_at=_rfc3339_after(authorized_at, hours=1),
        )
        workflow.apply(
            campaign_id,
            confirmed_plan_digest=str(second_plan["plan_digest"]),
        )
        result = workflow.validate(campaign_id)

        assert result["receipt"]["consumer_id"] == consumer_id
        assert result["receipt"]["terminal_disposition"] == "VALIDATED"
        assert result["receipt"]["compensation"] == {
            "available": True,
            "exercised": True,
            "result": "RESTORED",
        }
        assert any(
            "preceding migration attempt" in limitation
            for limitation in result["receipt"]["limitations"]
        )
        assert (
            store.projection(campaign_id).consumers[consumer_id]["disposition"]
            == "VALIDATED"
        )

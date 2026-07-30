from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from retirement_conductor.canonical import (
    digest_bytes,
    digest_file,
    with_digest,
)
from retirement_conductor.errors import Refusal
from retirement_conductor.git_dbt import (
    GitDbtAdapter,
    checked_target_path,
    discover_repository,
    merge_repository_evidence,
    merge_repository_reconciliation_evidence,
    reject_unsafe_tree,
    replace_identifier_once,
    resolve_manifest_mapping,
    resolve_replacement_evidence,
)
from retirement_conductor.git_dbt_config import GitDbtSettings
from retirement_conductor.specification import load_specification

ROOT = Path(__file__).resolve().parents[2]
CONSUMER_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:dbt,"
    "retirement_conductor.analytics.consumers.orders_model_00,PROD)"
)


def test_discovery_reports_text_manifest_compiled_and_uncertain_layers(
    tmp_path: Path,
) -> None:
    models = tmp_path / "models"
    macros = tmp_path / "macros"
    models.mkdir()
    macros.mkdir()
    (models / "alias.sql").write_text(
        "select legacy_status as normalized_status from orders\n",
        encoding="utf-8",
    )
    (models / "select-star.sql").write_text(
        "select * from orders\n",
        encoding="utf-8",
    )
    (macros / "generated.sql").write_text(
        "select {{ choose('legacy_status') }} from orders\n",
        encoding="utf-8",
    )
    manifest = {
        "nodes": {
            "model.project.alias": {
                "resource_type": "model",
                "original_file_path": "models/alias.sql",
                "compiled_code": (
                    "select legacy_status as normalized_status from orders"
                ),
                "depends_on": {"nodes": ["seed.project.orders"]},
            }
        }
    }

    result = discover_repository(
        tmp_path,
        manifest,
        target_field="legacy_status",
    )

    assert result["layers"] == [
        "bounded_text",
        "dbt_manifest",
        "dbt_compiled_sql",
    ]
    assert result["select_star_paths"] == ["models/select-star.sql"]
    assert {item["classification"] for item in result["text_matches"]} == {
        "aliased_direct",
        "macro_or_generated",
    }
    assert result["manifest_nodes"][0]["compiled_contains_target"] is True


def test_manifest_mapping_requires_one_exact_fresh_datahub_identity() -> None:
    manifest = {
        "nodes": {
            "model.project.orders": {
                "resource_type": "model",
                "original_file_path": "models/orders.sql",
                "config": {
                    "meta": {"retirement_conductor": {"datahub_urn": CONSUMER_URN}}
                },
            }
        }
    }

    mapping = resolve_manifest_mapping(manifest, [CONSUMER_URN])

    assert mapping["datahub_urn"] == CONSUMER_URN
    assert mapping["mapping_basis"] == "exact_dbt_manifest_meta"
    with pytest.raises(Refusal, match="IDENTITY_NOT_FOUND"):
        resolve_manifest_mapping(manifest, ["urn:li:dataset:other"])


def test_replacement_requires_matching_live_and_dbt_types() -> None:
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
    resolution = {
        "target_field": {"nativeDataType": "VARCHAR"},
        "replacement_field": {"nativeDataType": "VARCHAR"},
    }

    evidence = resolve_replacement_evidence(
        manifest,
        datahub_resolution=resolution,
        target_field="legacy_status",
        replacement_field="order_status",
    )

    assert evidence["compatible"] is True
    incompatible = {
        **resolution,
        "replacement_field": {"nativeDataType": "INTEGER"},
    }
    with pytest.raises(Refusal, match="SPEC_REPLACEMENT_INCOMPATIBLE"):
        resolve_replacement_evidence(
            manifest,
            datahub_resolution=incompatible,
            target_field="legacy_status",
            replacement_field="order_status",
        )


def test_repository_evidence_is_digest_bound_and_names_its_scope() -> None:
    envelope = with_digest(
        {
            "schema_version": "1.0.0",
            "captured_at": "2026-07-30T10:00:00Z",
            "mode": "live",
            "sources": [
                {
                    "id": "datahub",
                    "required": True,
                    "status": "COMPLETE",
                    "source_version": "v1.6.0",
                    "identity": "http://127.0.0.1:18080",
                    "scope": {
                        "direction": "downstream",
                        "max_hops": 3,
                        "filters": [],
                        "pages": 1,
                        "reported_total": 1,
                        "returned_total": 1,
                    },
                    "freshness": {
                        "observed_at": "2026-07-30T10:00:00Z",
                        "source_updated_at": "2026-07-30T10:00:00Z",
                        "maximum_age_seconds": 900,
                    },
                    "permissions": {
                        "principal": "anonymous",
                        "effective_scope": "read",
                    },
                    "limitations": [],
                    "artifact_ids": [f"sha256:{'1' * 64}"],
                }
            ],
        },
        "envelope_digest",
    )
    preflight = with_digest(
        {
            "schema_version": "1.0.0",
            "mode": "live",
            "captured_at": "2026-07-30T10:01:00Z",
            "repository": {
                "id": "analytics",
                "required": True,
                "identity": f"sha256:{'2' * 64}",
                "source_branch": "main",
                "source_version": "abc123",
                "source_committed_at": "2026-07-30T10:00:30Z",
            },
            "principal": "disposable-operator",
            "capabilities": {
                "read": True,
                "plan": True,
                "apply": False,
                "validate": True,
                "compensate": False,
            },
            "mapping": {"path": "models/orders.sql"},
            "limitations": ["Only the declared source branch was searched"],
            "artifact_ids": [f"sha256:{'3' * 64}"],
        },
        "preflight_digest",
    )

    merged = merge_repository_evidence(envelope, preflight)

    assert [source["id"] for source in merged["sources"]] == [
        "datahub",
        "git:analytics",
    ]
    repository = merged["sources"][1]
    assert repository["scope"]["filters"] == [
        "branch:main",
        "path:models/orders.sql",
    ]
    assert repository["permissions"]["effective_scope"] == "read,plan,validate"


def test_path_and_token_guards_refuse_escape_symlink_and_ambiguity(
    tmp_path: Path,
) -> None:
    models = tmp_path / "models"
    models.mkdir()
    target = models / "orders.sql"
    target.write_text("select legacy_status from orders\n", encoding="utf-8")
    outside = tmp_path.parent / f"{tmp_path.name}-outside.sql"
    outside.write_text("secret\n", encoding="utf-8")
    link = models / "link.sql"
    link.symlink_to(outside)

    assert (
        checked_target_path(
            tmp_path,
            "models/orders.sql",
            allowed_paths=["models/"],
        )
        == target
    )
    with pytest.raises(Refusal, match="SCOPE_PATH_OUTSIDE_ROOT"):
        checked_target_path(
            tmp_path,
            "../outside.sql",
            allowed_paths=["models/"],
        )
    with pytest.raises(Refusal, match="SCOPE_PATH_OUTSIDE_ROOT"):
        checked_target_path(
            tmp_path,
            "models/link.sql",
            allowed_paths=["models/"],
        )
    with pytest.raises(Refusal, match="IDENTITY_AMBIGUOUS"):
        replace_identifier_once(
            "select legacy_status, legacy_status from orders",
            "legacy_status",
            "order_status",
        )
    with pytest.raises(Refusal, match="VALIDATION_SCOPE_VIOLATION"):
        reject_unsafe_tree(tmp_path)


def _git(repository: Path, *arguments: str) -> str:
    environment = {
        "PATH": os.environ.get("PATH", ""),
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


def _adapter_and_plan(
    tmp_path: Path,
) -> tuple[GitDbtAdapter, dict[str, Any], dict[str, Any], Path]:
    repository = tmp_path / "repository"
    model = repository / "models" / "orders.sql"
    model.parent.mkdir(parents=True)
    model.write_text("select legacy_status from orders\n", encoding="utf-8")
    _git(repository, "init", "--initial-branch=main")
    _git(repository, "add", "--all")
    _git(repository, "commit", "-m", "initial")
    source_version = _git(repository, "rev-parse", "HEAD")
    specification = load_specification(ROOT / "fixtures/specs/git-dbt-live.yaml")
    specification["evidence"]["repositories"][0]["path"] = str(repository)
    git_path = shutil.which("git")
    assert git_path is not None
    settings = GitDbtSettings(
        repository_root=repository,
        repository_id="analytics",
        default_branch="main",
        dbt_executable=Path("/usr/bin/true"),
        principal="test-operator",
        allow_apply=True,
        validation_timeout_seconds=30,
        bwrap_executable=Path("/usr/bin/true"),
        git_executable=Path(git_path),
    )
    adapter = GitDbtAdapter(settings)
    before = model.read_text(encoding="utf-8")
    after = before.replace("legacy_status", "order_status")
    plan = with_digest(
        {
            "schema_version": "1.0.0",
            "campaign_id": specification["campaign"]["id"],
            "consumer_id": "consumer-one",
            "datahub_urn": CONSUMER_URN,
            "repository": {
                "id": "analytics",
                "identity": "repository-one",
                "default_branch": "main",
                "source_branch": "main",
                "source_version": source_version,
                "target_branch": "codex/test-apply",
            },
            "native_identity": {
                "repository_id": "analytics",
                "path": "models/orders.sql",
            },
            "target": {
                "path": "models/orders.sql",
                "before_token": "legacy_status",
                "after_token": "order_status",
                "before_fingerprint": digest_bytes(before.encode()),
                "after_fingerprint": digest_bytes(after.encode()),
            },
            "replacement": {"compatible": True},
            "discovery": {"mapping_match_count": 1},
            "validators": ["dbt test"],
            "limitations": [],
        },
        "plan_digest",
    )
    return adapter, specification, plan, model


def test_apply_is_exact_idempotent_and_skips_repository_hooks(
    tmp_path: Path,
) -> None:
    adapter, specification, plan, model = _adapter_and_plan(tmp_path)
    hook = adapter.settings.repository_root / ".git" / "hooks" / "post-commit"
    hook.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
    hook.chmod(0o700)
    artifacts = tmp_path / "artifacts"

    first = adapter.apply(
        specification,
        plan,
        artifact_root=artifacts,
        occurred_at="2026-07-30T10:10:00Z",
    )
    second = adapter.apply(
        specification,
        plan,
        artifact_root=artifacts,
        occurred_at="2026-07-30T10:11:00Z",
    )

    assert first == second
    assert first["actual_targets"] == ["models/orders.sql"]
    assert digest_file(model) == plan["target"]["after_fingerprint"]
    assert _git(adapter.settings.repository_root, "status", "--porcelain") == ""


def test_reconciliation_rereads_exact_applied_source_and_replacement(
    tmp_path: Path,
) -> None:
    adapter, specification, plan, model = _adapter_and_plan(tmp_path)
    applied = adapter.apply(
        specification,
        plan,
        artifact_root=tmp_path / "apply-artifacts",
        occurred_at="2026-07-30T10:10:00Z",
    )
    receipt = with_digest(
        {
            "apply": {"actual_targets": ["models/orders.sql"]},
            "native_identity": {
                "replacement": {
                    "target": {
                        "field": "legacy_status",
                        "datahub_native_type": "VARCHAR",
                    },
                    "replacement": {
                        "field": "order_status",
                        "datahub_native_type": "VARCHAR",
                    },
                }
            },
        },
        "receipt_digest",
    )
    resolution = {
        "target_field": {
            "fieldPath": "legacy_status",
            "nativeDataType": "VARCHAR",
        },
        "replacement_field": {
            "fieldPath": "order_status",
            "nativeDataType": "VARCHAR",
        },
    }

    observation = adapter.reconcile_source(
        specification,
        plan,
        applied,
        receipt,
        datahub_resolution=resolution,
        artifact_root=tmp_path / "reconciliation-artifacts",
    )

    assert (
        observation["repository"]["source_version"] == applied["native_change_ids"][0]
    )
    assert observation["target"]["fingerprint"] == plan["target"]["after_fingerprint"]
    assert observation["receipt_digest"] == receipt["receipt_digest"]

    incompatible = {
        **resolution,
        "replacement_field": {
            "fieldPath": "order_status",
            "nativeDataType": "INTEGER",
        },
    }
    with pytest.raises(Refusal, match="SPEC_REPLACEMENT_INCOMPATIBLE"):
        adapter.reconcile_source(
            specification,
            plan,
            applied,
            receipt,
            datahub_resolution=incompatible,
            artifact_root=tmp_path / "replacement-drift-artifacts",
        )

    model.write_text(
        model.read_text(encoding="utf-8") + "-- source drift\n",
        encoding="utf-8",
    )
    with pytest.raises(Refusal, match="SOURCE_GIT_FILE_CHANGED"):
        adapter.reconcile_source(
            specification,
            plan,
            applied,
            receipt,
            datahub_resolution=resolution,
            artifact_root=tmp_path / "source-drift-artifacts",
        )


def test_reconciliation_evidence_preserves_declared_baseline_scope() -> None:
    baseline = with_digest(
        {
            "schema_version": "1.0.0",
            "captured_at": "2026-07-30T10:00:00Z",
            "mode": "live",
            "sources": [
                {
                    "id": "git:analytics",
                    "required": True,
                    "status": "COMPLETE",
                    "source_version": "source-commit",
                    "identity": "repository-one",
                    "scope": {
                        "direction": "downstream",
                        "max_hops": 1,
                        "filters": ["branch:main", "path:models/orders.sql"],
                        "pages": 1,
                        "reported_total": 1,
                        "returned_total": 1,
                    },
                    "freshness": {
                        "observed_at": "2026-07-30T10:00:00Z",
                        "source_updated_at": "2026-07-30T09:59:00Z",
                        "maximum_age_seconds": 900,
                    },
                    "permissions": {
                        "principal": "test-operator",
                        "effective_scope": "read,plan,apply,validate,compensate",
                    },
                    "limitations": [],
                    "artifact_ids": [f"sha256:{'1' * 64}"],
                }
            ],
        },
        "envelope_digest",
    )
    observation = with_digest(
        {
            "captured_at": "2026-07-30T10:20:00Z",
            "repository": {
                "id": "analytics",
                "identity": "repository-one",
                "source_version": "applied-commit",
                "source_committed_at": "2026-07-30T10:10:00Z",
            },
            "principal": "test-operator",
            "capabilities": {
                "read": True,
                "plan": True,
                "apply": True,
                "validate": True,
                "compensate": True,
            },
            "limitations": [],
        },
        "reconciliation_digest",
    )

    merged = merge_repository_reconciliation_evidence(
        baseline,
        observation,
        baseline_source=baseline["sources"][0],
    )

    source = merged["sources"][0]
    assert source["scope"] == baseline["sources"][0]["scope"]
    assert source["identity"] == "repository-one"
    assert source["source_version"] == "applied-commit"


def test_compensation_refuses_and_preserves_an_intervening_edit(
    tmp_path: Path,
) -> None:
    adapter, specification, plan, model = _adapter_and_plan(tmp_path)
    artifacts = tmp_path / "artifacts"
    applied = adapter.apply(
        specification,
        plan,
        artifact_root=artifacts,
        occurred_at="2026-07-30T10:10:00Z",
    )
    intervening = model.read_text(encoding="utf-8") + "-- owner edit\n"
    model.write_text(intervening, encoding="utf-8")

    with pytest.raises(Refusal, match="COMPENSATION_CONFLICT"):
        adapter.compensate(
            specification,
            plan,
            applied,
            artifact_root=artifacts,
            occurred_at="2026-07-30T10:20:00Z",
        )

    assert model.read_text(encoding="utf-8") == intervening

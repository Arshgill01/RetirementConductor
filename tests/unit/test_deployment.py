from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from retirement_conductor.canonical import digest_file, verify_digest
from retirement_conductor.deployment import (
    create_removal_plan,
    deployment_preflight,
    remove_deployment_state,
)
from retirement_conductor.errors import Refusal
from retirement_conductor.specification import load_specification
from retirement_conductor.store import CampaignStore

ROOT = Path(__file__).resolve().parents[2]
SPECIFICATION = ROOT / "fixtures/specs/valid.yaml"


def state_paths(tmp_path: Path) -> tuple[Path, Path]:
    state = tmp_path / ".retirement-conductor"
    return state / "campaigns.sqlite", state / "artifacts"


def create_state(store_path: Path, artifact_directory: Path) -> None:
    with CampaignStore(store_path, writer_id="writer-one") as store:
        store.create_campaign(
            load_specification(SPECIFICATION),
            occurred_at="2026-01-01T10:00:00Z",
        )
    artifact_directory.mkdir(parents=True)
    (artifact_directory / "receipt.json").write_text(
        '{"result":"fixture"}\n',
        encoding="utf-8",
    )


def looker_environment(secret: str) -> dict[str, str]:
    return {
        "DATAHUB_GMS_URL": "https://datahub.invalid",
        "DATAHUB_MCP_URL": "https://datahub.invalid/mcp",
        "LOOKER_BASE_URL": "https://looker.invalid",
        "LOOKER_CLIENT_ID": "client-reference",
        "LOOKER_CLIENT_SECRET": secret,
        "LOOKER_PLATFORM_INSTANCE": "sandbox",
        "LOOKER_PROJECT_ID": "retirement",
        "LOOKER_MODEL_ID": "retirement",
        "LOOKER_EXPLORE_ID": "orders",
        "LOOKER_FOLDER_ID": "17",
        "LOOKER_CONTENT_TARGET": "look:41",
        "LOOKER_LEGACY_REFERENCE": "orders.legacy_status",
        "LOOKER_REPLACEMENT_REFERENCE": "orders.order_status",
        "LOOKER_DATAHUB_URN": "urn:li:dataset:(fixture)",
        "LOOKER_GRAPH_SNAPSHOT_DIGEST": f"sha256:{'1' * 64}",
        "LOOKER_ALLOW_APPLY": "false",
    }


def test_local_preflight_is_non_mutating_and_digest_bound(tmp_path: Path) -> None:
    store_path, artifact_directory = state_paths(tmp_path)

    report = deployment_preflight(
        profile="local",
        store_path=store_path,
        writer_id="writer-one",
        artifact_directory=artifact_directory,
        environment={},
    )

    verify_digest(report, "preflight_digest")
    assert report["result"] == "READY"
    assert report["ready"] is True
    assert report["state"]["single_writer"] is True
    assert report["state"]["store_exists"] is False
    assert report["telemetry"] == {
        "mode": "local-only",
        "enabled": False,
        "remote_export": False,
        "activation": "explicit environment opt-in and command invocation",
    }
    assert not store_path.exists()
    assert not artifact_directory.exists()


def test_looker_preflight_reports_only_references_and_keeps_apply_disabled(
    tmp_path: Path,
) -> None:
    store_path, artifact_directory = state_paths(tmp_path)
    marker = "recognizable-phase08-secret"
    environment = looker_environment(marker)

    plan = deployment_preflight(
        profile="looker-plan",
        store_path=store_path,
        writer_id="writer-one",
        artifact_directory=artifact_directory,
        environment=environment,
    )
    apply = deployment_preflight(
        profile="looker-apply",
        store_path=store_path,
        writer_id="writer-one",
        artifact_directory=artifact_directory,
        environment=environment,
    )

    assert plan["ready"] is True
    assert apply["ready"] is False
    assert apply["missing"] == ["LOOKER_ALLOW_APPLY=true"]
    rendered = json.dumps({"plan": plan, "apply": apply}, sort_keys=True)
    assert marker not in rendered
    assert "client-reference" not in rendered
    assert "looker.invalid" not in rendered
    assert all(
        set(item) == {"present", "reference", "secret"}
        for item in plan["configuration"]
    )


def test_preflight_refuses_copied_store_before_modification(tmp_path: Path) -> None:
    store_path, artifact_directory = state_paths(tmp_path)
    create_state(store_path, artifact_directory)
    copied = tmp_path / "copy" / ".retirement-conductor" / "campaigns.sqlite"
    copied.parent.mkdir(parents=True)
    shutil.copyfile(store_path, copied)
    copied_digest = digest_file(copied)

    with pytest.raises(Refusal, match="RUNTIME_WRITER_MISMATCH"):
        deployment_preflight(
            profile="local",
            store_path=copied,
            writer_id="writer-one",
            artifact_directory=copied.parent / "artifacts",
            environment={},
        )

    assert digest_file(copied) == copied_digest
    assert not copied.with_name("campaigns.sqlite.lock").exists()


def test_removal_requires_exact_confirmation_and_unchanged_state(
    tmp_path: Path,
) -> None:
    store_path, artifact_directory = state_paths(tmp_path)
    create_state(store_path, artifact_directory)
    plan = create_removal_plan(
        store_path=store_path,
        writer_id="writer-one",
        artifact_directory=artifact_directory,
        generated_at="2026-01-01T12:00:00Z",
    )
    verify_digest(plan, "removal_plan_digest")
    original_store_digest = digest_file(store_path)

    with pytest.raises(Refusal, match="AUTH_APPROVAL_MISSING"):
        remove_deployment_state(
            plan,
            confirmed_plan_digest=None,
            store_path=store_path,
            writer_id="writer-one",
            artifact_directory=artifact_directory,
        )
    with pytest.raises(Refusal, match="AUTH_APPROVAL_WRONG_PLAN"):
        remove_deployment_state(
            plan,
            confirmed_plan_digest=f"sha256:{'0' * 64}",
            store_path=store_path,
            writer_id="writer-one",
            artifact_directory=artifact_directory,
        )
    assert digest_file(store_path) == original_store_digest

    drift = artifact_directory / "late.json"
    drift.write_text("{}\n", encoding="utf-8")
    with pytest.raises(Refusal, match="RUNTIME_STATE_DRIFT"):
        remove_deployment_state(
            plan,
            confirmed_plan_digest=str(plan["removal_plan_digest"]),
            store_path=store_path,
            writer_id="writer-one",
            artifact_directory=artifact_directory,
        )
    assert store_path.exists()
    assert drift.exists()

    plan = create_removal_plan(
        store_path=store_path,
        writer_id="writer-one",
        artifact_directory=artifact_directory,
        generated_at="2026-01-01T12:01:00Z",
    )
    receipt = remove_deployment_state(
        plan,
        confirmed_plan_digest=str(plan["removal_plan_digest"]),
        store_path=store_path,
        writer_id="writer-one",
        artifact_directory=artifact_directory,
    )

    verify_digest(receipt, "removal_receipt_digest")
    assert receipt["result"] == "STATE_REMOVED"
    assert receipt["removed_file_count"] >= 4
    assert not store_path.exists()
    assert not store_path.with_name("campaigns.sqlite.lock").exists()
    assert not artifact_directory.exists()


def test_deployment_targets_cannot_escape_product_state(tmp_path: Path) -> None:
    outside = tmp_path / "campaigns.sqlite"
    state = tmp_path / ".retirement-conductor"
    state.mkdir()
    link = state / "artifacts"
    link.symlink_to(tmp_path, target_is_directory=True)

    with pytest.raises(Refusal, match="SCOPE_TARGET_NOT_ALLOWED"):
        deployment_preflight(
            profile="local",
            store_path=outside,
            writer_id="writer-one",
            artifact_directory=state / "safe-artifacts",
            environment={},
        )
    with pytest.raises(Refusal, match="SCOPE_TARGET_NOT_ALLOWED"):
        deployment_preflight(
            profile="local",
            store_path=state / "campaigns.sqlite",
            writer_id="writer-one",
            artifact_directory=link,
            environment={},
        )

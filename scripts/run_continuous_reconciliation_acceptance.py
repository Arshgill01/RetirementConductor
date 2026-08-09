#!/usr/bin/env python3
"""Exercise live late-consumer lease invalidation through the one-shot watcher."""

from __future__ import annotations

import json
import os
import shutil
from contextlib import suppress
from typing import Any

from retirement_conductor.canonical import (
    digest_bytes,
    digest_file,
    verify_digest,
    with_digest,
    write_json,
)
from retirement_conductor.specification import load_specification
from scripts.run_phase04_end_to_end import (
    DBT_EXECUTABLE,
    ISOLATED_LATE_URN,
    ISOLATED_MODEL_URN,
    PRODUCER_MARKER,
    ROOT,
    SEED_RECEIPT,
    TEMPLATE,
    Runner,
    boundary,
    future,
    git,
    make_specification,
    require,
    runtime_arguments,
    seed,
    timestamp,
    wait_for_membership,
    wait_for_publication,
)

RUNTIME_ROOT = ROOT / ".retirement-conductor" / "e2e" / "continuous-reconciliation"


def run() -> dict[str, Any]:
    require(DBT_EXECUTABLE.is_file(), "run `make git-dbt-tool` before WS-03")
    require(
        not git(ROOT, "status", "--porcelain=v1", "--untracked-files=all"),
        "the producer repository must be clean before the WS-03 live run",
    )
    run_token = digest_bytes(timestamp().encode()).removeprefix("sha256:")[:12]
    runtime_run_id = f"run-{run_token}"
    run_root = RUNTIME_ROOT / runtime_run_id
    run_root.mkdir(parents=True, exist_ok=False)
    repository = run_root / "repository"
    store_path = run_root / "campaigns.sqlite"
    artifact_root = run_root / "artifacts"
    sentinel_root = run_root / "sentinels"
    writer_id = f"watch-writer-{run_token}"
    campaign_id = f"ret-orders-watch-{run_token}"
    trusted_run_id = f"watch-live-{run_token}"
    environment = dict(os.environ)
    environment.update(
        {
            "DATAHUB_GMS_URL": "http://127.0.0.1:18080",
            "DATAHUB_MCP_URL": "http://127.0.0.1:8000/mcp",
            "DATAHUB_PRINCIPAL": "anonymous-disposable-core",
            "GIT_DBT_REPOSITORY_ROOT": str(repository),
            "GIT_DBT_DBT_EXECUTABLE": str(DBT_EXECUTABLE),
            "GIT_DBT_PRINCIPAL": "local-disposable-operator",
            "GIT_DBT_ALLOW_APPLY": "true",
            "RETIREMENT_CONDUCTOR_TRUSTED_CONTEXT": "true",
            "RETIREMENT_CONDUCTOR_TRUSTED_RUN_ID": trusted_run_id,
            "RETIREMENT_CONDUCTOR_TRUST_PROVIDER": "disposable-local-ci",
        }
    )
    runner = Runner(run_root, environment)
    current_seed_mode = "unknown"
    try:
        runner.text(
            "prepare-isolated-repository",
            [
                "uv",
                "run",
                "python",
                "scripts/prepare_git_dbt_workspace.py",
                "--template",
                str(TEMPLATE),
                "--destination",
                str(repository),
            ],
        )
        specification_path = make_specification(run_root, repository, campaign_id)
        specification = load_specification(specification_path)
        datahub = boundary(environment)

        seed(runner, "base", environment)
        current_seed_mode = "base"
        baseline = wait_for_membership(
            source=datahub,
            specification=specification,
            expected_urns={ISOLATED_MODEL_URN},
            artifact_root=run_root / "independent-reread" / "baseline",
        )
        runner.json(
            "campaign-create",
            [
                "uv",
                "run",
                "retirement-conductor",
                "campaign",
                "create",
                str(specification_path),
                "--store",
                str(store_path),
                "--writer-id",
                writer_id,
                "--occurred-at",
                timestamp(),
            ],
        )
        common = runtime_arguments(
            campaign_id,
            store=store_path,
            artifacts=artifact_root,
            writer_id=writer_id,
        )
        runner.json(
            "git-dbt-preflight",
            [
                "uv",
                "run",
                "retirement-conductor",
                "adapter",
                "git-dbt",
                "preflight",
                *common,
            ],
            timeout=240,
        )
        planned = runner.json(
            "git-dbt-plan",
            [
                "uv",
                "run",
                "retirement-conductor",
                "adapter",
                "git-dbt",
                "plan",
                *common,
            ],
        )
        runner.json(
            "git-dbt-authorize",
            [
                "uv",
                "run",
                "retirement-conductor",
                "adapter",
                "git-dbt",
                "authorize",
                *common,
                "--principal",
                "local-disposable-operator",
                "--authorized-at",
                timestamp(),
                "--expires-at",
                future(30),
            ],
        )
        applied = runner.json(
            "git-dbt-apply",
            [
                "uv",
                "run",
                "retirement-conductor",
                "adapter",
                "git-dbt",
                "apply",
                *common,
                "--confirm-plan-digest",
                str(planned["plan"]["plan_digest"]),
            ],
        )
        validated = runner.json(
            "git-dbt-validate",
            [
                "uv",
                "run",
                "retirement-conductor",
                "adapter",
                "git-dbt",
                "validate",
                *common,
            ],
            timeout=300,
        )
        require(
            validated["validation"]["result"] == "PASSED",
            "the Git/dbt native validator did not pass",
        )

        seed(runner, "base", environment)
        wait_for_membership(
            source=datahub,
            specification=specification,
            expected_urns={ISOLATED_MODEL_URN},
            artifact_root=run_root / "independent-reread" / "ready",
        )
        ready_reconciliation = runner.json(
            "campaign-reconcile-ready",
            [
                "uv",
                "run",
                "retirement-conductor",
                "campaign",
                "reconcile",
                *common,
            ],
            timeout=240,
        )
        require(
            ready_reconciliation["manifest"]["decision"] == "READY_TO_RETIRE",
            "the isolated campaign did not become ready",
        )
        runner.json(
            "campaign-publish-ready",
            [
                "uv",
                "run",
                "retirement-conductor",
                "campaign",
                "publish",
                *common,
            ],
        )
        ready_verification, ready_publication_settle = wait_for_publication(
            runner=runner,
            name="campaign-verify-ready-publication",
            arguments=[
                "uv",
                "run",
                "retirement-conductor",
                "campaign",
                "verify-publication",
                *common,
            ],
        )
        ready_manifest = ready_verification["manifest"]
        producer_paths = [
            "--producer-repository",
            str(ROOT),
            "--producer-source-marker",
            str(PRODUCER_MARKER),
            "--sentinel-root",
            str(sentinel_root),
        ]
        producer_plan = runner.json(
            "producer-plan",
            [
                "uv",
                "run",
                "retirement-conductor",
                "producer",
                "plan",
                *common,
                *producer_paths,
                "--expires-at",
                future(14),
            ],
        )
        plan_path = artifact_root / campaign_id / "producer" / "plan.json"
        preserved_plan = run_root / "preserved-retirement-lease.json"
        shutil.copyfile(plan_path, preserved_plan)
        preserved_plan_bytes = preserved_plan.read_bytes()
        issued = runner.json(
            "lease-status-issued",
            [
                "uv",
                "run",
                "retirement-conductor",
                "campaign",
                "lease-status",
                *common,
            ],
        )
        require(issued["lease"]["status"] == "ISSUED", "the lease was not issued")

        seed(runner, "late-field", environment)
        current_seed_mode = "late-field"
        late_write_receipt = run_root / "late-datahub-write-receipt.json"
        shutil.copyfile(SEED_RECEIPT, late_write_receipt)
        late_write_value = json.loads(late_write_receipt.read_text(encoding="utf-8"))
        verify_digest(late_write_value, "refresh_digest")
        late_reread = wait_for_membership(
            source=datahub,
            specification=specification,
            expected_urns={ISOLATED_MODEL_URN, ISOLATED_LATE_URN},
            artifact_root=run_root / "independent-reread" / "late-consumer",
        )
        late_snapshot = late_reread["snapshot"]
        require(
            any(
                consumer.get("datahub_urn") == ISOLATED_LATE_URN
                for consumer in late_snapshot["consumers"]
            ),
            "the late DataHub field consumer was not independently readable",
        )
        late_claims = [
            claim
            for claim in late_snapshot["claims"]
            if claim.get("subject") == ISOLATED_LATE_URN
        ]
        require(
            len(late_claims) == 1
            and late_claims[0].get("confidence_basis") == "column_lineage_edge",
            "the late consumer was not independently proven by exact field lineage",
        )
        watch = runner.json(
            "watch-once-late-consumer",
            [
                "uv",
                "run",
                "retirement-conductor",
                "campaign",
                "watch",
                *common,
                "--once",
                "--publication-timeout-seconds",
                "60",
            ],
            expected_exit=3,
            timeout=300,
        )
        require(
            watch["result"] == "REVERSED"
            and watch["before"]["decision"] == "READY_TO_RETIRE"
            and watch["after"]["decision"] == "UNSAFE",
            "the watcher did not reverse the ready decision",
        )
        require(
            watch["publication"]["readback_verified"] is True,
            "the reversed summary was not read back from DataHub",
        )
        require(
            preserved_plan.read_bytes() == preserved_plan_bytes,
            "the preserved Retirement Lease bytes changed",
        )
        invalidated = runner.json(
            "lease-status-invalidated",
            [
                "uv",
                "run",
                "retirement-conductor",
                "campaign",
                "lease-status",
                *common,
            ],
        )
        require(
            invalidated["lease"]["status"] == "INVALIDATED",
            "the old Retirement Lease remained usable",
        )
        sentinel_before = len(list(sentinel_root.rglob("*.json")))
        gate_refusal = runner.json(
            "gate-preserved-invalidated-lease",
            [
                "uv",
                "run",
                "retirement-conductor",
                "gate",
                *common,
                *producer_paths,
                "--plan",
                str(preserved_plan),
            ],
            expected_exit=2,
            expected_refusal="GATE_DECISION_NOT_READY",
        )
        sentinel_after = len(list(sentinel_root.rglob("*.json")))
        require(
            sentinel_before == sentinel_after == 0,
            "the invalidated lease executed a producer sentinel",
        )

        seed(runner, "base", environment)
        current_seed_mode = "base"
        recovery_reread = wait_for_membership(
            source=datahub,
            specification=specification,
            expected_urns={ISOLATED_MODEL_URN},
            artifact_root=run_root / "independent-reread" / "recovery",
        )
        recovered = runner.json(
            "campaign-reconcile-after-edge-removal",
            [
                "uv",
                "run",
                "retirement-conductor",
                "campaign",
                "reconcile",
                *common,
            ],
            timeout=240,
        )
        require(
            recovered["manifest"]["decision"] == "UNSAFE",
            "edge disappearance incorrectly closed the late consumer",
        )
        runner.json(
            "campaign-publish-recovery",
            [
                "uv",
                "run",
                "retirement-conductor",
                "campaign",
                "publish",
                *common,
            ],
        )
        recovery_verification, recovery_publication_settle = wait_for_publication(
            runner=runner,
            name="campaign-verify-recovery-publication",
            arguments=[
                "uv",
                "run",
                "retirement-conductor",
                "campaign",
                "verify-publication",
                *common,
            ],
        )

        verify_digest(watch, "receipt_digest")
        summary = with_digest(
            {
                "schema_version": "1.0.0",
                "evidence_mode": "live local",
                "generated_at": timestamp(),
                "runtime_run_id": runtime_run_id,
                "repository_commit": git(ROOT, "rev-parse", "HEAD"),
                "campaign_id_digest": digest_bytes(campaign_id.encode()),
                "source_versions": watch["source_versions"],
                "baseline": {
                    "consumer_count": len(baseline["snapshot"]["consumers"]),
                    "ready_manifest_digest": ready_manifest["manifest_digest"],
                    "ready_publication_content_digest": ready_verification[
                        "publication"
                    ]["content_digest"],
                    "ready_publication_settle": ready_publication_settle,
                },
                "native_git_dbt": {
                    "actual_targets": applied["apply"]["actual_targets"],
                    "validation_result": validated["validation"]["result"],
                    "validator": validated["validation"]["validator"],
                    "validation_digest": validated["validation"]["validation_digest"],
                },
                "lease": {
                    "plan_digest": producer_plan["plan"]["plan_digest"],
                    "preserved_bytes_digest": digest_file(preserved_plan),
                    "issued_status": issued["lease"]["status"],
                    "after_watch_status": invalidated["lease"]["status"],
                },
                "late_consumer": {
                    "datahub_write_receipt_digest": digest_file(late_write_receipt),
                    "independent_snapshot_digest": late_snapshot["snapshot_digest"],
                    "independent_consumer_count": len(late_snapshot["consumers"]),
                    "exact_field_claim_id": late_claims[0]["claim_id"],
                    "confidence_basis": late_claims[0]["confidence_basis"],
                    "reread_attempts": late_reread["attempts"],
                },
                "watch": {
                    "result": watch["result"],
                    "receipt_digest": watch["receipt_digest"],
                    "before_manifest_digest": watch["before"]["manifest_digest"],
                    "after_manifest_digest": watch["after"]["manifest_digest"],
                    "before_decision": watch["before"]["decision"],
                    "after_decision": watch["after"]["decision"],
                    "comparison_digest": watch["comparison_digest"],
                    "publication_content_digest": watch["publication"][
                        "content_digest"
                    ],
                    "publication_verified": watch["publication"]["readback_verified"],
                },
                "gate": {
                    "refusal_code": gate_refusal["refusal_code"],
                    "sentinel_count_before": sentinel_before,
                    "sentinel_count_after": sentinel_after,
                },
                "recovery": {
                    "independent_snapshot_digest": recovery_reread["snapshot"][
                        "snapshot_digest"
                    ],
                    "consumer_count": len(recovery_reread["snapshot"]["consumers"]),
                    "decision_after_edge_removal": recovered["manifest"]["decision"],
                    "publication_content_digest": recovery_verification["publication"][
                        "content_digest"
                    ],
                    "publication_settle": recovery_publication_settle,
                },
                "commands": [
                    observation.as_dict() for observation in runner.observations
                ],
                "limitations": [
                    (
                        "Evidence is live-local against disposable DataHub Core "
                        "and Git/dbt."
                    ),
                    "Readiness remains bounded by the declared evidence envelope.",
                    (
                        "The producer action is a harmless local sentinel, not a "
                        "warehouse mutation."
                    ),
                    (
                        "Removing the late graph edge did not validate or close "
                        "that consumer."
                    ),
                ],
            },
            "evidence_digest",
        )
        write_json(run_root / "summary.json", summary)
        write_json(run_root / "watch-receipt.json", watch)
        write_json(RUNTIME_ROOT / "latest.json", summary)
        write_json(RUNTIME_ROOT / "latest-watch-receipt.json", watch)
        return summary
    except Exception:
        write_json(
            run_root / "failure.json",
            {
                "schema_version": "1.0.0",
                "result": "FAILED",
                "observed_at": timestamp(),
                "command_count": len(runner.observations),
            },
        )
        raise
    finally:
        if current_seed_mode not in {"unknown", "base"}:
            with suppress(Exception):
                seed(runner, "base", environment, record=False)


def main() -> int:
    summary = run()
    print(
        "Continuous reconciliation passed: "
        f"watch={summary['watch']['result']} "
        f"lease={summary['lease']['after_watch_status']} "
        f"gate={summary['gate']['refusal_code']} "
        f"digest={summary['evidence_digest']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

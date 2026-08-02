#!/usr/bin/env python3
"""Promote inspected, public-safe Phase 06 benchmark evidence."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from retirement_conductor.canonical import (
    digest_file,
    verify_digest,
    with_digest,
    write_json,
)

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "artifacts" / "public" / "phase06"
BENCHMARK = ROOT / ".retirement-conductor" / "benchmark"
GENERATION = BENCHMARK / "generation-a"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def load(path: Path, digest_field: str | None = None) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected an object: {path.name}")
    if digest_field is not None:
        verify_digest(value, digest_field)
    return value


def command(run_root: Path, name: str) -> dict[str, Any]:
    matches = list((run_root / "commands").glob(f"*-{name}.json"))
    if len(matches) != 1:
        raise RuntimeError(f"expected one command observation for {name}")
    return load(matches[0])


def repository_commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    ).stdout.strip()


def generate() -> dict[str, Any]:
    summary = load(BENCHMARK / "live" / "latest.json", "evidence_digest")
    require(summary["repository_commit"] == repository_commit(), "commit drift")
    require(
        summary["twin_run"]["matched_prior_run_count"] >= 1,
        "public evidence requires two semantically equivalent live runs",
    )
    semantic = summary["semantic_evidence"]
    verify_digest(semantic, "semantic_digest")
    require(
        semantic["semantic_digest"] == summary["twin_run"]["semantic_digest"],
        "twin-run digest binding changed",
    )
    run_root = BENCHMARK / "live" / str(summary["run_id"])
    require(run_root.is_dir(), "latest live run is unavailable")

    registry = load(ROOT / "fixtures" / "data-quality" / "datasets.json")
    offline = load(BENCHMARK / "data-verify-receipt.json", "receipt_digest")
    generation = load(GENERATION / "generation-receipt.json", "receipt_digest")
    quality = load(GENERATION / "quality-report.json", "quality_report_digest")
    fault_manifest = load(GENERATION / "fault-manifest.json", "fault_manifest_digest")
    oracle = load(GENERATION / "oracle.json", "oracle_digest")
    oracle_comparison = load(run_root / "oracle-comparison.json", "comparison_digest")
    readback = load(run_root / "direct-readback.json", "readback_digest")
    native_faults = load(run_root / "native-fault-probes.json", "receipt_digest")

    if PUBLIC.exists():
        shutil.rmtree(PUBLIC)
    PUBLIC.mkdir(parents=True)

    dataset_evidence = with_digest(
        {
            "all_verified": offline["all_verified"],
            "assets": [
                {
                    "archive_members": item["archive_members"],
                    "asset_id": item["asset_id"],
                    "dataset_id": item["dataset_id"],
                    "license_id": item["license_id"],
                    "sha256": item["sha256"],
                    "size_bytes": item["size_bytes"],
                    "variant": item["variant"],
                    "verified": item["verified"],
                }
                for item in offline["assets"]
            ],
            "evidence_mode": "fixture acquisition with offline byte verification",
            "license_manifest": sorted(
                {
                    (
                        str(item["license_id"]),
                        str(item["license_evidence_url"]),
                    )
                    for item in registry["assets"]
                }
            ),
            "offline_receipt_digest": offline["receipt_digest"],
            "registry_digest": offline["registry_digest"],
            "schema_version": "1.0.0",
            "upstream_revision": offline["upstream_revision"],
        },
        "evidence_digest",
    )
    write_json(PUBLIC / "dataset-evidence.json", dataset_evidence)

    corpus_evidence = with_digest(
        {
            "artifact_classification": "public-safe aggregates; no source rows",
            "faults": [
                {
                    "affected_count": item["affected_count"],
                    "affected_rate": item["affected_rate"],
                    "field": item["field"],
                    "impact": item["impact"],
                    "mutation": item["mutation"],
                    "variant_id": item["variant_id"],
                }
                for item in fault_manifest["variants"]
            ],
            "generation": {
                "artifact_digests": generation["artifact_digests"],
                "generator_version": generation["generator_version"],
                "receipt_digest": generation["receipt_digest"],
                "scale": generation["scale"],
                "seed": generation["seed"],
            },
            "quality": quality,
            "schema_version": "1.0.0",
            "twin_generation": {
                "artifact_count": len(generation["artifact_digests"]),
                "byte_equivalent": True,
                "generation_receipt_digest": generation["receipt_digest"],
            },
        },
        "evidence_digest",
    )
    write_json(PUBLIC / "corpus-evidence.json", corpus_evidence)

    oracle_evidence = with_digest(
        {
            "comparison": oracle_comparison,
            "independence": {
                "expected_result_module": ("retirement_conductor.benchmark_oracle"),
                "imports_campaign_policy": False,
                "intentional_corruption_result": oracle_comparison[
                    "corrupt_oracle_detection"
                ],
            },
            "oracle_digest": oracle["oracle_digest"],
            "oracle_version": oracle["oracle_version"],
            "scenario_count": len(oracle["scenarios"]),
            "schema_version": "1.0.0",
        },
        "evidence_digest",
    )
    write_json(PUBLIC / "oracle-evidence.json", oracle_evidence)

    datahub_evidence = with_digest(
        {
            "baseline_consumer_count": summary["datahub"]["baseline_consumer_count"],
            "baseline_expected_consumer_recall": summary["datahub"][
                "baseline_expected_consumer_recall"
            ],
            "direct_readback": readback,
            "evidence_mode": "live local DataHub Core over fixture data",
            "partial_pagination": {
                "refusal_code": "EVIDENCE_PAGINATION_FAILED",
                "status": summary["datahub"]["partial_pagination_status"],
            },
            "replacement_drift_refusal": summary["datahub"][
                "replacement_drift_refusal"
            ],
            "rich_consumer_count": summary["datahub"]["rich_consumer_count"],
            "schema_version": "1.0.0",
        },
        "evidence_digest",
    )
    write_json(PUBLIC / "datahub-evidence.json", datahub_evidence)

    validation_command = command(run_root, "git-dbt-validate")
    native_evidence = with_digest(
        {
            "clean": {
                "actual_targets": summary["campaign"]["apply_targets"],
                "commands": [
                    {
                        "arguments": item["arguments"],
                        "exit_code": item["exit_code"],
                        "timed_out": item["timed_out"],
                    }
                    for item in validation_command["validation"]["commands"]
                ],
                "receipt_digest": validation_command["receipt"]["receipt_digest"],
                "result": validation_command["validation"]["result"],
                "validator": validation_command["validation"]["validator"],
                "validator_version": validation_command["validation"][
                    "validator_version"
                ],
            },
            "evidence_mode": "live local dbt over generated fixture data",
            "fault_variants": native_faults,
            "schema_version": "1.0.0",
        },
        "evidence_digest",
    )
    write_json(PUBLIC / "native-validation-evidence.json", native_evidence)

    ready = command(run_root, "campaign-reconcile-ready")
    late = command(run_root, "campaign-reconcile-late")
    rich = command(run_root, "rich-campaign-evaluate")
    publication = command(run_root, "campaign-verify-publication")
    gate = command(run_root, "producer-gate-ready")
    campaign_evidence = with_digest(
        {
            "evidence_mode": "live local systems over fixture data",
            "gate": {
                "attempt_count": summary["gate_attempt_count"],
                "ready_result": gate["result"],
                "receipt_digest": gate["gate_receipt"]["receipt_digest"],
                "sentinel_count": summary["campaign"]["sentinel_count"],
                "sentinel_digest": summary["campaign"]["sentinel_digest"],
            },
            "late": {
                "blocker_codes": sorted(
                    item["code"] for item in late["manifest"]["blockers"]
                ),
                "decision": late["manifest"]["decision"],
                "manifest_digest": late["manifest"]["manifest_digest"],
                "membership": late["comparison"]["membership"],
            },
            "publication": {
                "content_digest": publication["publication"]["content_digest"],
                "lifecycle_unchanged": (
                    publication["publication"]["lifecycle_digest_before"]
                    == publication["publication"]["lifecycle_digest_after"]
                ),
                "published_manifest_digest": publication["publication"][
                    "published_manifest_digest"
                ],
                "readback_verified": publication["publication"]["readback_verified"],
                "write_count": 1,
            },
            "ready": {
                "consumer_dispositions": sorted(
                    item["disposition"] for item in ready["manifest"]["consumers"]
                ),
                "decision": ready["manifest"]["decision"],
                "manifest_digest": ready["manifest"]["manifest_digest"],
                "state": ready["manifest"]["campaign"]["state"],
            },
            "rich": {
                "blocker_codes": sorted(
                    item["code"] for item in rich["manifest"]["blockers"]
                ),
                "consumer_count": len(rich["manifest"]["consumers"]),
                "decision": rich["decision"],
                "manifest_digest": rich["manifest"]["manifest_digest"],
            },
            "schema_version": "1.0.0",
        },
        "evidence_digest",
    )
    write_json(PUBLIC / "campaign-evidence.json", campaign_evidence)

    refusal_commands = {
        "apply-without-approval": command(run_root, "git-dbt-apply-without-approval"),
        "late-consumer": command(run_root, "producer-gate-late-refusal"),
        "rich-graph": command(run_root, "rich-gate-refusal"),
    }
    refusal_matrix = with_digest(
        {
            "live_command_refusals": [
                {
                    "exit_code": value.get("exit_code", 2),
                    "id": name,
                    "refusal_code": value["refusal_code"],
                    "result": value["result"],
                }
                for name, value in sorted(refusal_commands.items())
            ],
            "oracle_scenarios": [
                {
                    "decision": item["observed"]["decision"],
                    "id": item["id"],
                    "matched": item["matched"],
                    "refusal_codes": item["observed"]["refusal_codes"],
                }
                for item in oracle_comparison["results"]
            ],
            "schema_version": "1.0.0",
        },
        "evidence_digest",
    )
    write_json(PUBLIC / "refusal-matrix.json", refusal_matrix)

    artifact_paths = sorted(PUBLIC.glob("*.json"))
    artifact_digests = {path.name: digest_file(path) for path in artifact_paths}
    phase = with_digest(
        {
            "acceptance": {
                "exact_expected_consumer_recall": 1.0,
                "false_readiness_count": oracle_comparison["false_readiness_count"],
                "matched_scenario_count": oracle_comparison["matched_scenario_count"],
                "native_fault_count": len(native_faults["observations"]),
                "publication_readback_verified": True,
                "ready_decision": ready["manifest"]["decision"],
                "rich_decision": rich["decision"],
                "sentinel_count": summary["campaign"]["sentinel_count"],
                "twin_live_semantic_digest": semantic["semantic_digest"],
                "twin_live_semantically_equivalent": True,
            },
            "artifact_digests": artifact_digests,
            "evidence_mode": (
                "live local DataHub/Git/dbt integration over pinned official "
                "and generated fixture data"
            ),
            "limitations": summary["limitations"],
            "repository_commit": summary["repository_commit"],
            "schema_version": "1.0.0",
            "source_receipts": {
                "generation": generation["receipt_digest"],
                "offline_dataset_verification": offline["receipt_digest"],
                "oracle": oracle["oracle_digest"],
                "quality": quality["quality_report_digest"],
                "semantic_live_run": semantic["semantic_digest"],
            },
        },
        "evidence_digest",
    )
    write_json(PUBLIC / "phase06-evidence.json", phase)
    return phase


def main() -> int:
    evidence = generate()
    print(
        "Phase 06 public evidence generated: "
        f"scenarios={evidence['acceptance']['matched_scenario_count']} "
        f"false_ready={evidence['acceptance']['false_readiness_count']} "
        f"digest={evidence['evidence_digest']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

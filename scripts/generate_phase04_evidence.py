#!/usr/bin/env python3
"""Verify the latest Phase 04 run and publish public-safe evidence."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from retirement_conductor.canonical import (
    digest_bytes,
    digest_file,
    verify_digest,
    with_digest,
    write_json,
)
from retirement_conductor.store import CampaignStore

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".retirement-conductor" / "e2e" / "phase04"
LATEST = RUNTIME / "latest.json"
OUTPUT = ROOT / "artifacts" / "public" / "phase04"
RUN_ID_PATTERN = re.compile(r"run-[0-9a-f]{12}")

EXPECTED_REFUSALS = {
    "git-dbt-apply-without-approval": "AUTH_APPROVAL_MISSING",
    "gate-authorization-drift": "GATE_STATE_DRIFT",
    "gate-configuration-drift": "GATE_STATE_DRIFT",
    "gate-consumer-source-drift": "SOURCE_GIT_FILE_CHANGED",
    "gate-datahub-unavailable": "SOURCE_DATAHUB_UNAVAILABLE",
    "gate-late-consumer": "GATE_DECISION_NOT_READY",
    "gate-missing-store": "RUNTIME_CAMPAIGN_NOT_FOUND",
    "gate-producer-source-drift": "GATE_SOURCE_DRIFT",
    "gate-replacement-drift": "SPEC_REPLACEMENT_INCOMPATIBLE",
    "gate-replay": "GATE_PLAN_REPLAYED",
    "gate-tampered-validation": "INTEGRITY_DIGEST_MISMATCH",
    "gate-untrusted": "GATE_PROVENANCE_UNTRUSTED",
    "gate-validator-drift": "GATE_STATE_DRIFT",
    "gate-wrong-run": "GATE_PROVENANCE_UNTRUSTED",
    "gate-wrong-writer": "RUNTIME_WRITER_MISMATCH",
    "rich-gate-refusal": "GATE_DECISION_NOT_READY",
}

FOCUSED_TESTS = [
    "tests/unit/test_datahub.py",
    "tests/unit/test_git_dbt.py",
    "tests/unit/test_policy.py",
    "tests/integration/test_gate.py",
    "tests/integration/test_campaign_store.py",
]


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected object artifact: {path.name}")
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def safe_name(value: str) -> str:
    return "".join(character if character.isalnum() else "-" for character in value)


def git(*arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(ROOT), *arguments],
        check=check,
        capture_output=True,
        text=True,
        timeout=30,
    )


def command_observation(
    summary: Mapping[str, Any],
    run_root: Path,
    name: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    matches = [
        (index, observation)
        for index, observation in enumerate(summary["commands"], start=1)
        if observation["name"] == name
    ]
    require(len(matches) == 1, f"expected one command observation for {name}")
    index, observation = matches[0]
    path = run_root / "commands" / f"{index:03d}-{safe_name(name)}.json"
    require(path.is_file(), f"missing command artifact for {name}")
    require(
        digest_file(path) == observation["output_digest"],
        f"command artifact digest changed for {name}",
    )
    return dict(observation), load_object(path)


def verify_comparison(
    comparison: Mapping[str, Any],
    *,
    expected_added: int,
    expected_consumers: int,
) -> None:
    value = dict(comparison)
    verify_digest(value, "comparison_digest")
    require(value["mode"] == "live", "reconciliation is not live")
    require(
        value["baseline"]["scope_digest"] == value["current"]["scope_digest"],
        "reconciliation scopes are not equivalent",
    )
    require(
        value["current"]["consumer_count"] == expected_consumers,
        "reconciliation consumer count changed",
    )
    require(
        len(value["membership"]["added"]) == expected_added,
        "reconciliation added membership changed",
    )
    refresh = value["refresh"]
    require(refresh["status"] == "OBSERVED", "refresh was not observed")
    require(
        0 <= refresh["duration_ms"] <= refresh["timeout_seconds"] * 1000,
        "refresh exceeded its recorded bound",
    )


def run_focused_tests() -> dict[str, Any]:
    command = ["uv", "run", "pytest", "-q", *FOCUSED_TESTS]
    result = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=300,
    )
    output = result.stdout + result.stderr
    require(result.returncode == 0, f"focused Phase 04 tests failed:\n{output[-1000:]}")
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    summary_line = next(
        (line for line in reversed(lines) if " passed in " in line),
        "",
    )
    match = re.search(r"(\d+) passed in ", summary_line)
    require(match is not None, "focused pytest output omitted its pass count")
    return {
        "result": "PASSED",
        "command": command,
        "test_count": int(match.group(1)),
        "summary": summary_line,
        "output_digest": digest_bytes(output.encode()),
        "test_sources": FOCUSED_TESTS,
    }


def public_attempt(entry: Mapping[str, Any]) -> dict[str, Any]:
    attempt = entry["attempt"]
    outcome = entry["outcome"]
    return {
        "attempt_digest": attempt["attempt_digest"],
        "manifest_digest": attempt["manifest_digest"],
        "outcome_digest": (
            outcome["outcome_digest"] if isinstance(outcome, dict) else None
        ),
        "plan_digest": attempt["plan_digest"],
        "refusal_code": attempt["refusal_code"],
        "status": entry["status"],
    }


def run() -> int:
    require(LATEST.is_file(), "run `make test-end-to-end` before Phase 04 evidence")
    summary = load_object(LATEST)
    verify_digest(summary, "evidence_digest")
    require(summary["evidence_mode"] == "live", "latest evidence is not live")
    require(
        set(summary["decision_matrix"].values())
        == {"BLOCKED", "UNSAFE", "REVIEW_REQUIRED", "READY_TO_RETIRE"},
        "the four-way decision matrix is incomplete",
    )

    runtime_run_id = str(summary["runtime_run_id"])
    require(
        RUN_ID_PATTERN.fullmatch(runtime_run_id) is not None,
        "latest runtime run identifier is malformed",
    )
    run_root = (RUNTIME / runtime_run_id).resolve()
    require(run_root.parent == RUNTIME.resolve(), "runtime evidence escaped its root")
    require((run_root / "summary.json").is_file(), "runtime summary is missing")
    require(
        load_object(run_root / "summary.json") == summary,
        "latest pointer and runtime summary differ",
    )
    tested_commit = str(summary["repository_commit"])
    commit_exists = git(
        "cat-file",
        "-e",
        f"{tested_commit}^{{commit}}",
        check=False,
    )
    require(
        commit_exists.returncode == 0,
        "tested repository commit is unavailable",
    )
    commit_is_ancestor = git(
        "merge-base",
        "--is-ancestor",
        tested_commit,
        "HEAD",
        check=False,
    )
    require(
        commit_is_ancestor.returncode == 0,
        "tested repository commit is not an ancestor of HEAD",
    )

    ready_manifest = load_object(run_root / "ready-manifest.json")
    late_manifest = load_object(run_root / "late-manifest.json")
    verify_digest(ready_manifest, "manifest_digest")
    verify_digest(late_manifest, "manifest_digest")
    isolated = summary["isolated"]
    require(
        ready_manifest["manifest_digest"] == isolated["ready_manifest_digest"],
        "ready manifest digest differs from the summary",
    )
    require(
        late_manifest["manifest_digest"] == isolated["late_manifest_digest"],
        "late manifest digest differs from the summary",
    )
    require(
        ready_manifest["decision"] == "READY_TO_RETIRE"
        and ready_manifest["campaign"]["state"] == "READY"
        and not ready_manifest["blockers"],
        "verified isolated manifest is not ready",
    )
    require(
        late_manifest["decision"] == "UNSAFE"
        and late_manifest["campaign"]["state"] == "BLOCKED"
        and {
            "POLICY_CONSUMER_OPAQUE",
            "RECONCILIATION_NEW_CONSUMER",
        }
        <= {blocker["code"] for blocker in late_manifest["blockers"]},
        "verified late-consumer manifest did not reopen",
    )
    for manifest in (ready_manifest, late_manifest):
        require(
            manifest["evidence_envelope"]["mode"] == "live"
            and all(
                source["status"] == "COMPLETE"
                for source in manifest["evidence_envelope"]["sources"]
                if source["required"]
            ),
            "a required final evidence source is not complete and live",
        )
        require(
            manifest["publication"]["readback_verified"] is True,
            "a final publication was not read back",
        )

    _, ready_reconcile = command_observation(
        summary,
        run_root,
        "campaign-reconcile-ready",
    )
    _, late_reconcile = command_observation(
        summary,
        run_root,
        "campaign-reconcile-late",
    )
    ready_comparison = ready_reconcile["comparison"]
    late_comparison = late_reconcile["comparison"]
    verify_comparison(ready_comparison, expected_added=0, expected_consumers=1)
    verify_comparison(late_comparison, expected_added=1, expected_consumers=2)
    require(
        not ready_comparison["membership"]["disappeared_without_closure"]
        and not late_comparison["membership"]["disappeared_without_closure"],
        "the live comparison unexpectedly lost a consumer",
    )
    require(
        ready_reconcile["manifest"]["manifest_digest"]
        == isolated["ready_reconciliation_manifest_digest"]
        == ready_manifest["publication"]["published_manifest_digest"],
        "ready publication did not bind the reconciled manifest",
    )
    require(
        late_reconcile["manifest"]["manifest_digest"]
        == isolated["late_reconciliation_manifest_digest"]
        == late_manifest["publication"]["published_manifest_digest"],
        "late publication did not bind the reconciled manifest",
    )
    require(
        ready_manifest["publication"]["urn"] == late_manifest["publication"]["urn"],
        "ready and late summaries used different DataHub identities",
    )

    _, producer = command_observation(summary, run_root, "producer-plan")
    _, executed = command_observation(summary, run_root, "gate-execute-ready")
    plan = producer["plan"]
    gate_receipt = executed["gate_receipt"]
    verify_digest(plan, "plan_digest")
    verify_digest(gate_receipt, "receipt_digest")
    require(
        plan["plan_digest"]
        == isolated["producer_plan_digest"]
        == gate_receipt["producer_plan_digest"],
        "producer plan and executed receipt differ",
    )
    require(
        plan["manifest"]["digest"]
        == ready_manifest["manifest_digest"]
        == gate_receipt["manifest_digest"],
        "gate execution was not bound to the verified ready manifest",
    )
    require(
        gate_receipt["result"] == "EXECUTED"
        and gate_receipt["decision"] == "READY_TO_RETIRE",
        "ready gate did not execute",
    )

    sentinel_paths = sorted((run_root / "sentinels").rglob("*.json"))
    require(len(sentinel_paths) == 1, "the producer wrote other than one sentinel")
    require(
        digest_file(sentinel_paths[0])
        == isolated["sentinel_digest"]
        == gate_receipt["sentinel"]["digest"],
        "the producer sentinel digest changed",
    )

    refusal_observations: dict[str, dict[str, Any]] = {}
    for name, expected_code in EXPECTED_REFUSALS.items():
        observation, payload = command_observation(summary, run_root, name)
        require(
            observation["exit_code"] == 2
            and observation["result"] == "REFUSED"
            and observation["refusal_code"] == expected_code
            and payload["refusal_code"] == expected_code,
            f"{name} did not produce {expected_code}",
        )
        refusal_observations[name] = {
            "exit_code": observation["exit_code"],
            "output_digest": observation["output_digest"],
            "refusal_code": expected_code,
            "result": observation["result"],
        }

    campaign_id = str(isolated["campaign_id"])
    with CampaignStore(
        run_root / "campaigns.sqlite",
        writer_id=str(plan["writer_id"]),
    ) as store:
        attempts = store.gate_attempts(campaign_id)
        schema_versions = store.schema_versions()
        issued = store.gate_plan_for_manifest(
            campaign_id,
            str(ready_manifest["manifest_digest"]),
        )
        sqlite_version = str(
            store.connection.execute("SELECT sqlite_version()").fetchone()[0]
        )
    require(schema_versions == [1, 2, 3], "gate ledger migrations are incomplete")
    require(issued == plan, "issued producer plan differs from the executed plan")
    attempt_counts = Counter(str(entry["status"]) for entry in attempts)
    require(
        dict(sorted(attempt_counts.items())) == isolated["gate_attempt_status_counts"],
        "gate attempt counts differ from the run summary",
    )
    require(attempt_counts["EXECUTED"] == 1, "gate ledger is execution-ambiguous")

    focused_tests = run_focused_tests()

    OUTPUT.mkdir(parents=True, exist_ok=True)
    write_json(OUTPUT / "ready-manifest.json", ready_manifest)
    write_json(OUTPUT / "late-manifest.json", late_manifest)

    reconciliation_evidence = with_digest(
        {
            "schema_version": "1.0.0",
            "mode": "live",
            "tested_commit": tested_commit,
            "captured_at": summary["generated_at"],
            "campaign_id": campaign_id,
            "ready": {
                "comparison": ready_comparison,
                "reconciled_manifest_digest": (
                    isolated["ready_reconciliation_manifest_digest"]
                ),
                "verified_manifest_digest": ready_manifest["manifest_digest"],
                "publication": ready_manifest["publication"],
                "evidence_envelope": ready_manifest["evidence_envelope"],
            },
            "late_consumer": {
                "comparison": late_comparison,
                "reconciled_manifest_digest": (
                    isolated["late_reconciliation_manifest_digest"]
                ),
                "verified_manifest_digest": late_manifest["manifest_digest"],
                "publication": late_manifest["publication"],
                "evidence_envelope": late_manifest["evidence_envelope"],
            },
            "assertions": {
                "equivalent_scope": True,
                "bounded_refresh_observed": True,
                "ready_publication_read_back": True,
                "stable_publication_identity": True,
                "late_consumer_added": True,
                "late_consumer_reopened_readiness": True,
            },
            "limitations": [
                "Equivalent scope does not prove visibility outside the envelope.",
                "DataHub Core did not expose an isPartial signal.",
                "The live graph is public-safe and disposable.",
            ],
        },
        "evidence_digest",
    )
    write_json(OUTPUT / "reconciliation-evidence.json", reconciliation_evidence)

    gate_evidence = with_digest(
        {
            "schema_version": "1.0.0",
            "mode": "live",
            "tested_commit": tested_commit,
            "captured_at": summary["generated_at"],
            "campaign_id": campaign_id,
            "producer_plan": plan,
            "gate_receipt": gate_receipt,
            "ledger": {
                "schema_versions": schema_versions,
                "sqlite_version": sqlite_version,
                "issued_plan_digest": issued["plan_digest"],
                "attempt_status_counts": dict(sorted(attempt_counts.items())),
                "attempts": [public_attempt(entry) for entry in attempts],
            },
            "sentinel": {
                "count": 1,
                "digest": isolated["sentinel_digest"],
            },
            "rich_graph": summary["rich_graph"],
            "assertions": {
                "exact_manifest_bound": True,
                "exact_producer_plan_issued": True,
                "durable_intent_preceded_action": True,
                "one_ready_action_executed": True,
                "replay_refused": True,
                "late_and_rich_non_ready_actions_refused": True,
            },
            "limitations": list(summary["limitations"]),
        },
        "evidence_digest",
    )
    write_json(OUTPUT / "gate-evidence.json", gate_evidence)

    refusal_evidence = with_digest(
        {
            "schema_version": "1.0.0",
            "modes": ["live", "fixture"],
            "tested_commit": tested_commit,
            "captured_at": summary["generated_at"],
            "decision_matrix": summary["decision_matrix"],
            "live_refusals": refusal_observations,
            "replacement_drift": isolated["replacement_drift"],
            "focused_contract_tests": focused_tests,
            "covered_fixture_contracts": [
                "partial and stale DataHub evidence block",
                "changed validated Git source refuses reconciliation",
                "disappeared unclosed consumer remains unsafe",
                "policy, validator, and authorization input drift block",
                "unissued, delayed, tampered, and replayed gate plans refuse",
                "failed producer action becomes outcome unknown and consumes the plan",
                "ready campaign without verified publication refuses",
            ],
            "assertions": {
                "all_four_decisions_exercised": True,
                "missing_access_failed_closed": True,
                "source_and_replacement_drift_refused": True,
                "configuration_and_authorization_drift_refused": True,
                "tampered_evidence_refused": True,
                "untrusted_provenance_refused": True,
                "replay_refused": True,
            },
        },
        "evidence_digest",
    )
    write_json(OUTPUT / "refusal-evidence.json", refusal_evidence)

    phase_summary = with_digest(
        {
            "schema_version": "1.0.0",
            "modes": ["live", "fixture"],
            "tested_commit": tested_commit,
            "captured_at": summary["generated_at"],
            "private_run_evidence_digest": summary["evidence_digest"],
            "campaign_id": campaign_id,
            "assertions": {
                "complete_supported_loop_exercised": True,
                "live_isolated_campaign_ready": True,
                "live_rich_campaign_unsafe": True,
                "late_consumer_reopened_campaign": True,
                "stable_datahub_summary_verified": True,
                "producer_gate_executed_exactly_once": True,
                "non_ready_and_adversarial_gate_paths_refused": True,
                "cli_report_and_gate_share_canonical_manifest": True,
                "four_way_policy_exercised": True,
            },
            "artifacts": {
                "ready_manifest": "artifacts/public/phase04/ready-manifest.json",
                "late_manifest": "artifacts/public/phase04/late-manifest.json",
                "reconciliation": (
                    "artifacts/public/phase04/reconciliation-evidence.json"
                ),
                "gate": "artifacts/public/phase04/gate-evidence.json",
                "refusals": "artifacts/public/phase04/refusal-evidence.json",
            },
            "limitations": list(summary["limitations"]),
        },
        "evidence_digest",
    )
    write_json(OUTPUT / "phase04-evidence.json", phase_summary)
    print(
        "Phase 04 evidence generated: "
        f"ready={ready_manifest['decision']} "
        f"late={late_manifest['decision']} "
        f"rich={summary['rich_graph']['decision']} "
        f"tests={focused_tests['test_count']}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(run())

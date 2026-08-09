#!/usr/bin/env python3
"""Promote a real full-agent run into a public-safe demo evidence bundle."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any, cast

from retirement_conductor.canonical import digest_bytes, with_digest, write_json

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LATEST = ROOT / ".retirement-conductor/agent-full-run/latest.json"
DEFAULT_OUTPUT = ROOT / "artifacts/public/agent/full-run.json"
DEFAULT_EXAMPLES = ROOT / "examples/agent-run"
FORBIDDEN_PUBLIC_TEXT = re.compile(r"(?:/home/|/Users/)[^/\s]+/")

STAGES = {
    "inspect_and_plan": "stage-1a",
    "authorization_pause": "stage-1b",
    "apply_and_validate": "stage-2a",
    "reconcile_and_execute": "stage-2b",
    "late_consumer_reversal": "stage-3",
}
EXPECTED_AGENT_TOOLS = {
    "inspect_and_plan": [
        "retirement_conductor.list_mcp_resources",
        "codex.list_mcp_resources",
        "datahub.search",
        "datahub.list_schema_fields",
        "datahub.get_lineage",
        "retirement_conductor.create_retirement_campaign",
        "retirement_conductor.inventory_retirement_consumers",
        "retirement_conductor.preflight_git_dbt_consumer",
        "retirement_conductor.plan_git_dbt_migration",
    ],
    "authorization_pause": [
        "retirement_conductor.get_human_authorization_instructions",
    ],
    "apply_and_validate": [
        "retirement_conductor.apply_git_dbt_migration",
        "retirement_conductor.validate_git_dbt_migration",
        "retirement_conductor.inspect_retirement_campaign",
    ],
    "reconcile_and_execute": [
        "retirement_conductor.reconcile_retirement_campaign",
        "retirement_conductor.publish_retirement_summary",
        "retirement_conductor.verify_retirement_summary",
        "retirement_conductor.inspect_retirement_campaign",
        "retirement_conductor.prepare_producer_retirement_plan",
        "retirement_conductor.execute_retirement_gate",
    ],
    "late_consumer_reversal": [
        "datahub.get_lineage",
        "retirement_conductor.reconcile_retirement_campaign",
        "retirement_conductor.publish_retirement_summary",
        "retirement_conductor.verify_retirement_summary",
        "retirement_conductor.inspect_retirement_campaign",
        "retirement_conductor.explain_retirement_campaign",
    ],
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def object_dict(value: object, message: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError(message)
    return cast(dict[str, Any], value)


def load_object(path: Path) -> dict[str, Any]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    return object_dict(value, f"expected a JSON object: {path}")


def parse_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        value: object = json.loads(line)
        events.append(object_dict(value, f"trace line {number} is not an object"))
    require(bool(events), f"empty trace: {path.name}")
    return events


def completed_mcp_calls(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for event in events:
        item = event.get("item")
        if (
            event.get("type") == "item.completed"
            and isinstance(item, dict)
            and item.get("type") == "mcp_tool_call"
        ):
            calls.append(cast(dict[str, Any], item))
    return calls


def structured_result(call: dict[str, Any]) -> dict[str, Any]:
    result = object_dict(call.get("result"), "completed MCP call has no result")
    return object_dict(
        result.get("structured_content"), "MCP result has no structured content"
    )


def result_for(
    stage_calls: dict[str, list[dict[str, Any]]], stage: str, tool: str
) -> dict[str, Any]:
    matches = [call for call in stage_calls[stage] if call.get("tool") == tool]
    require(len(matches) == 1, f"expected one {tool} call in {stage}")
    return structured_result(matches[0])


def git(repository: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def public_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8").strip()
    require(not FORBIDDEN_PUBLIC_TEXT.search(text), f"private path in {path.name}")
    return text


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def run(latest_path: Path, output_path: Path, examples_root: Path) -> dict[str, Any]:
    latest = load_object(latest_path)
    run_id = str(latest.get("run_id", ""))
    campaign_id = str(latest.get("campaign_id", ""))
    behavior_commit = str(latest.get("behavior_commit", ""))
    authorization_mode = str(latest.get("operator_authorization", ""))
    require(run_id.startswith("run-"), "invalid full-agent run id")
    require(bool(campaign_id), "full-agent campaign id is missing")
    require(len(behavior_commit) == 40, "full-agent behavior commit is invalid")
    require(
        authorization_mode == "explicit user-directed outer orchestration",
        "run does not record the expected external authorization boundary",
    )

    run_root = latest_path.parent / run_id
    repository = Path(str(latest.get("repository", "")))
    require(run_root.is_dir(), "retained full-agent run is unavailable")
    require(repository.is_dir(), "retained disposable repository is unavailable")
    git(ROOT, "cat-file", "-e", f"{behavior_commit}^{{commit}}")

    stage_calls: dict[str, list[dict[str, Any]]] = {}
    trace_evidence: dict[str, Any] = {}
    transcript_parts: list[str] = []
    for public_name, file_stem in STAGES.items():
        trace_path = run_root / f"{file_stem}-trace.jsonl"
        events = parse_events(trace_path)
        calls = completed_mcp_calls(events)
        observed_tools = [f"{call.get('server')}.{call.get('tool')}" for call in calls]
        require(
            observed_tools == EXPECTED_AGENT_TOOLS[public_name],
            f"unexpected tool order in {public_name}: {observed_tools}",
        )
        command_calls = [
            event
            for event in events
            if isinstance(event.get("item"), dict)
            and event["item"].get("type") == "command_execution"
        ]
        require(not command_calls, f"agent used the shell in {public_name}")
        require(
            all(call.get("status") in {None, "completed"} for call in calls),
            f"incomplete MCP call in {public_name}",
        )
        stage_calls[public_name] = calls
        trace_evidence[public_name] = {
            "tool_order": observed_tools,
            "shell_call_count": 0,
            "raw_trace_digest": digest_bytes(trace_path.read_bytes()),
            "raw_trace_retention": "ignored local evidence; not published",
        }
        message_path = run_root / f"{file_stem}-message.md"
        if public_name != "authorization_pause" and message_path.is_file():
            transcript_parts.extend(
                [
                    f"## {public_name.replace('_', ' ').title()}",
                    public_text(message_path),
                ]
            )

    plan_result = result_for(stage_calls, "inspect_and_plan", "plan_git_dbt_migration")
    authorization = result_for(
        stage_calls,
        "authorization_pause",
        "get_human_authorization_instructions",
    )
    apply_result = result_for(
        stage_calls, "apply_and_validate", "apply_git_dbt_migration"
    )
    validation = result_for(
        stage_calls, "apply_and_validate", "validate_git_dbt_migration"
    )
    ready_reconciliation = result_for(
        stage_calls, "reconcile_and_execute", "reconcile_retirement_campaign"
    )
    ready_publication = result_for(
        stage_calls, "reconcile_and_execute", "verify_retirement_summary"
    )
    lease_result = result_for(
        stage_calls, "reconcile_and_execute", "prepare_producer_retirement_plan"
    )
    gate_result = result_for(
        stage_calls, "reconcile_and_execute", "execute_retirement_gate"
    )
    late_reconciliation = result_for(
        stage_calls, "late_consumer_reversal", "reconcile_retirement_campaign"
    )
    late_publication = result_for(
        stage_calls, "late_consumer_reversal", "verify_retirement_summary"
    )
    late_inspection = result_for(
        stage_calls, "late_consumer_reversal", "inspect_retirement_campaign"
    )

    plan = object_dict(plan_result.get("plan"), "migration plan is missing")
    target = object_dict(plan.get("target"), "migration target is missing")
    plan_repository = object_dict(plan.get("repository"), "plan repository is missing")
    comparison = object_dict(
        late_reconciliation.get("comparison"), "late comparison is missing"
    )
    membership = object_dict(comparison.get("membership"), "membership is missing")
    late_view = object_dict(late_inspection.get("view"), "late view is missing")
    counts = object_dict(late_view.get("counts"), "late counts are missing")
    lease = object_dict(lease_result.get("plan"), "Retirement Lease is missing")
    gate_receipt = object_dict(
        gate_result.get("gate_receipt"), "gate receipt is missing"
    )
    ready_comparison = object_dict(
        ready_reconciliation.get("comparison"), "ready comparison is missing"
    )
    ready_membership = object_dict(
        ready_comparison.get("membership"), "ready membership is missing"
    )
    ready_publication_value = object_dict(
        ready_publication.get("publication"), "ready publication is missing"
    )
    late_publication_value = object_dict(
        late_publication.get("publication"), "late publication is missing"
    )

    blocker_codes = sorted(
        str(blocker.get("code"))
        for blocker in cast(list[object], late_view.get("blockers", []))
        if isinstance(blocker, dict)
    )
    added = cast(list[object], membership.get("added", []))
    require(plan_result.get("result") == "PLANNED", "agent did not produce a plan")
    require(
        authorization.get("result") == "HUMAN_AUTHORIZATION_REQUIRED",
        "agent did not pause",
    )
    require(apply_result.get("result") == "APPLIED", "migration was not applied")
    require(validation.get("validation_result") == "PASSED", "dbt validation failed")
    require(gate_result.get("result") == "EXECUTED", "producer gate did not execute")
    require(gate_result.get("decision") == "READY_TO_RETIRE", "ready gate changed")
    require(
        late_view.get("decision") == "UNSAFE", "late consumer did not reverse readiness"
    )
    require(
        counts.get("consumers") == 2 and counts.get("open") == 1, "late counts changed"
    )
    require(len(added) == 1, "expected exactly one late consumer")
    require(
        blocker_codes == ["POLICY_CONSUMER_OPAQUE", "RECONCILIATION_NEW_CONSUMER"],
        f"late blocker set changed: {blocker_codes}",
    )

    migration_commit = git(repository, "rev-parse", "HEAD")
    migration_patch = git(
        repository,
        "show",
        "--format=",
        "--no-ext-diff",
        "--unified=0",
        "HEAD",
        "--",
        str(target.get("path")),
    )
    require("-    legacy_status" in migration_patch, "patch omitted legacy field")
    require("+    order_status" in migration_patch, "patch omitted replacement field")

    evidence = with_digest(
        {
            "schema_version": "1.0.0",
            "artifact_classification": "public-safe full model execution evidence",
            "evidence_mode": "live-local DataHub and disposable Git/dbt",
            "observed_at": late_view.get("generated_at"),
            "behavior_commit": behavior_commit,
            "campaign_id": campaign_id,
            "actor_boundary": {
                "product_agent": (
                    "Codex using the Retirement Conductor skill and MCP tools"
                ),
                "authorization": "external operator command directed by the user",
                "authorization_mode": authorization_mode,
                "independent_operator_evidence": "NOT_RUN",
                "deterministic_authority": (
                    "campaign policy, preconditions, native validators, and "
                    "producer gate"
                ),
            },
            "trace": trace_evidence,
            "migration": {
                "source_version": plan_repository.get("source_version"),
                "migration_commit": migration_commit,
                "branch": plan_repository.get("target_branch"),
                "target": target.get("path"),
                "before_token": target.get("before_token"),
                "after_token": target.get("after_token"),
                "plan_digest": plan.get("plan_digest"),
                "apply_digest": apply_result.get("apply_digest"),
                "actual_targets": apply_result.get("actual_targets"),
            },
            "human_authorization_pause": {
                "result": authorization.get("result"),
                "plan_digest": authorization.get("plan_digest"),
                "authorized_targets": authorization.get("authorized_targets"),
                "required_environment_keys": sorted(
                    object_dict(
                        authorization.get("required_environment"),
                        "authorization environment is missing",
                    )
                ),
                "agent_authorization_tool_exposed": False,
            },
            "change_receipt": {
                "presentation_name": "Change Receipt",
                "contract_name": "consumer receipt",
                "result": validation.get("validation_result"),
                "validator": validation.get("validator"),
                "validation_digest": validation.get("validation_digest"),
                "receipt_id": validation.get("receipt_id"),
                "receipt_digest": validation.get("receipt_digest"),
                "terminal_disposition": validation.get("terminal_disposition"),
            },
            "ready_path": {
                "membership": ready_membership,
                "publication_readback_verified": ready_publication_value.get(
                    "readback_verified"
                ),
                "ready_manifest_digest": gate_result.get("manifest_digest"),
                "retirement_lease_digest": lease.get("plan_digest"),
                "gate_result": gate_result.get("result"),
                "gate_receipt_digest": gate_receipt.get("receipt_digest"),
                "outcome_digest": gate_receipt.get("outcome_digest"),
                "producer_action": "public-safe local sentinel only",
            },
            "late_consumer_reversal": {
                "decision_before": "READY_TO_RETIRE",
                "decision_after": late_view.get("decision"),
                "consumer_count_before": 1,
                "consumer_count_after": counts.get("consumers"),
                "added_consumer_ids": added,
                "blocker_codes": blocker_codes,
                "manifest_digest": late_view.get("manifest_digest"),
                "publication_readback_verified": late_publication_value.get(
                    "readback_verified"
                ),
                "next_action": late_view.get("next_action"),
                "new_retirement_lease_prepared": False,
                "second_gate_called": False,
            },
            "acceptance": {
                "model_inspected_datahub": True,
                "exact_migration_planned": True,
                "human_authorization_pause_observed": True,
                "authorized_target_set_preserved": True,
                "dbt_native_validation_passed": True,
                "fresh_reconciliation_completed": True,
                "datahub_summary_published_and_read_back": True,
                "bounded_ready_gate_executed": True,
                "late_consumer_reversed_readiness": True,
                "agent_shell_call_count": 0,
            },
            "limitations": [
                (
                    "This was a user-directed author/operator run, not independent "
                    "operator evidence."
                ),
                (
                    "All source systems were disposable local services; no production "
                    "data system was mutated."
                ),
                (
                    "The producer action was a harmless local sentinel, not warehouse "
                    "column deletion."
                ),
                (
                    "Readiness is valid only within the recorded DataHub and Git/dbt "
                    "evidence envelope."
                ),
                (
                    "Raw model traces remain ignored because they contain private "
                    "runtime details."
                ),
            ],
        },
        "agent_full_run_digest",
    )
    public_json = json.dumps(evidence, sort_keys=True)
    require(
        not FORBIDDEN_PUBLIC_TEXT.search(public_json),
        "public evidence contains a private path",
    )
    write_json(output_path, evidence)

    change_receipt = with_digest(
        {
            "schema_version": "1.0.0",
            "presentation_name": "Change Receipt",
            "campaign_id": campaign_id,
            "consumer_id": plan.get("consumer_id"),
            "target": target.get("path"),
            "source_version": plan_repository.get("source_version"),
            "migration_commit": migration_commit,
            "plan_digest": plan.get("plan_digest"),
            "apply_digest": apply_result.get("apply_digest"),
            "validation_result": validation.get("validation_result"),
            "validator": validation.get("validator"),
            "validation_digest": validation.get("validation_digest"),
            "receipt_id": validation.get("receipt_id"),
            "receipt_digest": validation.get("receipt_digest"),
        },
        "example_digest",
    )
    retirement_lease = with_digest(
        {
            "schema_version": "1.0.0",
            "presentation_name": "Retirement Lease",
            "campaign_id": campaign_id,
            "lease_digest": lease.get("plan_digest"),
            "prepared_at": lease.get("prepared_at"),
            "expires_at": lease.get("expires_at"),
            "manifest_digest": object_dict(
                lease.get("manifest"), "lease manifest is missing"
            ).get("digest"),
            "migration_plan_digest": object_dict(
                lease.get("git_dbt"), "lease Git/dbt binding is missing"
            ).get("migration_plan_digest"),
            "change_receipt_digest": object_dict(
                lease.get("git_dbt"), "lease Git/dbt binding is missing"
            ).get("receipt_digest"),
            "producer_action": "write_public_safe_sentinel",
            "gate_result": gate_result.get("result"),
            "gate_receipt_digest": gate_receipt.get("receipt_digest"),
            "outcome_digest": gate_receipt.get("outcome_digest"),
        },
        "example_digest",
    )
    reversal = with_digest(
        {
            "schema_version": "1.0.0",
            "campaign_id": campaign_id,
            "decision_before": "READY_TO_RETIRE",
            "decision_after": late_view.get("decision"),
            "added_consumer_ids": added,
            "blocker_codes": blocker_codes,
            "manifest_digest": late_view.get("manifest_digest"),
            "publication_readback_verified": late_publication_value.get(
                "readback_verified"
            ),
            "new_retirement_lease_prepared": False,
            "second_gate_called": False,
            "next_action": late_view.get("next_action"),
        },
        "example_digest",
    )
    write_json(examples_root / "change-receipt.json", change_receipt)
    write_json(examples_root / "retirement-lease.json", retirement_lease)
    write_json(examples_root / "readiness-reversal.json", reversal)
    write_text(examples_root / "migration.patch", migration_patch)
    write_text(
        examples_root / "agent-transcript.md",
        "# Full agent run transcript\n\n"
        "This is the public-safe final response from each model stage. Raw JSONL "
        "tool traces remain ignored and are digest-bound in the full-run evidence.\n\n"
        + "\n\n".join(transcript_parts),
    )
    write_text(
        examples_root / "README.md",
        f"""# Full agent run evidence

This bundle is the concrete artifact trail from one real Retirement Conductor
agent run over disposable local DataHub and Git/dbt systems.

The product agent inspected DataHub, created campaign `{campaign_id}`, planned
the exact one-file migration in `migration.patch`, and stopped at the human
authorization boundary. After the user directed the outer operator to record
that authorization, the product agent applied the change, ran dbt-native
validation, reconciled fresh evidence, published and read back the DataHub
summary, issued a short-lived Retirement Lease, and executed only a harmless
local sentinel.

A newly injected Spark consumer then caused the same campaign to reverse from
`READY_TO_RETIRE` to `UNSAFE`. No second lease was issued and the gate was not
called again.

## Inspect in order

1. `migration.patch` — the exact dbt change.
2. `change-receipt.json` — native validation and receipt binding.
3. `retirement-lease.json` — the short-lived manifest-bound producer lease.
4. `readiness-reversal.json` — the late consumer and stable refusal codes.
5. `agent-transcript.md` — public-safe stage-by-stage model conclusions.
6. `../../artifacts/public/agent/full-run.json` — the complete digest-bound
   orchestration summary.

## Evidence boundary

This is a user-directed author/operator run, not the independent operator
observation required by RC-018. It used disposable local systems and did not
mutate a production warehouse.
""",
    )
    print(
        "Full agent evidence promoted: "
        f"campaign={campaign_id} decision={late_view.get('decision')} "
        f"digest={evidence['agent_full_run_digest']}"
    )
    return evidence


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--latest", type=Path, default=DEFAULT_LATEST)
    value.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    value.add_argument("--examples", type=Path, default=DEFAULT_EXAMPLES)
    return value


def main() -> int:
    arguments = parser().parse_args()
    run(arguments.latest, arguments.output, arguments.examples)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

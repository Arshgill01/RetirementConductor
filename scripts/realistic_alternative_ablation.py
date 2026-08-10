"""Frozen executable comparison for CP-03 realistic alternative ablation v2."""

from __future__ import annotations

import copy
import json
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from retirement_conductor.canonical import digest_json, with_digest, write_json
from scripts.realistic_alternative_ablation_oracle import (
    OracleError,
    expected_properties,
    oracle_digest,
    scenario_input_digest,
    verify_frozen_protocol,
    verify_observation,
)

ARM_IDS = ("point-in-time", "fresh-ci", "retirement-conductor")
AUDIT_FIELDS = ("graph", "source", "approval", "validation", "action", "outcome")


class EvaluationError(ValueError):
    """Raised when evidence violates the frozen comparison contract."""


@dataclass
class NativeAction:
    """Task-local CP-01 adapter fake with native reread semantics."""

    fault: str
    reread_available: bool
    column_present: bool = True
    attempts: int = 0
    commits: int = 0
    crash_injected: bool = False

    def execute(self) -> str:
        if not self.column_present:
            return "ALREADY_APPLIED"
        if self.fault == "CRASH_BEFORE_ACTION" and not self.crash_injected:
            self.crash_injected = True
            return "CRASH_BEFORE_ACTION"
        self.attempts += 1
        self.commits += 1
        self.column_present = False
        if self.fault == "LOST_RESPONSE_AFTER_COMMIT":
            if not self.reread_available:
                return "OUTCOME_UNKNOWN"
            return "RESOLVED_COMMITTED_BY_NATIVE_REREAD"
        return "COMMITTED"


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise EvaluationError(f"expected a JSON object: {path}")
    return value


def _refusal_for_facts(facts: dict[str, Any], *, campaign: bool) -> str | None:
    prefix = "RECONCILIATION" if campaign else "CI"
    if facts["datahub_status"] == "UNAVAILABLE":
        return f"{prefix}_DATAHUB_UNAVAILABLE"
    if facts["datahub_status"] == "PARTIAL":
        return f"{prefix}_PAGINATION_INCOMPLETE"
    if facts["datahub_status"] == "AMBIGUOUS":
        return f"{prefix}_FIELD_LINEAGE_AMBIGUOUS"
    if facts["consumer_membership"] != facts["approved_membership"]:
        return f"{prefix}_CONSUMER_MEMBERSHIP_CHANGED"
    if not facts["producer_fingerprint_matches"]:
        return "SOURCE_PRODUCER_SCHEMA_CHANGED"
    if not facts["git_dbt_validation_matches"]:
        return "VALIDATION_GIT_DBT_DRIFT"
    if not facts["superset_validation_matches"]:
        return "VALIDATION_SUPERSET_DRIFT"
    if not facts["approval_valid_for_scope_and_time"]:
        return "AUTH_APPROVAL_STALE_OR_WRONG_SCOPE"
    if not facts["audit_sink_available"]:
        return "GATE_PUBLICATION_UNAVAILABLE" if campaign else "CI_REPORT_UNAVAILABLE"
    return None


def _audit_bindings(
    *, artifact_available: bool, static: bool = False
) -> dict[str, bool]:
    if artifact_available:
        return {field: True for field in AUDIT_FIELDS}
    if static:
        return {
            "graph": True,
            "source": True,
            "approval": True,
            "validation": True,
            "action": False,
            "outcome": False,
        }
    return {field: False for field in AUDIT_FIELDS}


def _complete_action(
    action: NativeAction,
    *,
    arm: str,
    replay: bool,
) -> tuple[str, bool, int, bool]:
    response = action.execute()
    green_reused = False
    recovered = False
    if response == "CRASH_BEFORE_ACTION":
        recovered = True
        green_reused = arm == "point-in-time"
        response = action.execute()
    outcome_unknown = response == "OUTCOME_UNKNOWN"
    if replay and arm == "point-in-time":
        green_reused = True
        action.execute()
        # The fresh CI rereads the now-missing producer field.  The Retirement
        # Conductor lease is already consumed.  Neither invokes native SQL again.
    return response, outcome_unknown, int(recovered), green_reused


def run_arm(
    arm: str,
    scenario: dict[str, Any],
    protocol: dict[str, Any],
) -> dict[str, Any]:
    facts = scenario["action_time_facts"]
    action = NativeAction(
        fault=facts["action_fault"],
        reread_available=facts["native_outcome_reread_available"],
    )
    refusal: str | None = None
    reread: list[str] = []
    green_reused = False
    recovered_steps = 0
    if arm == "point-in-time":
        reread = []
    elif arm == "fresh-ci":
        reread = [
            "datahub_complete_paged_inventory",
            "producer_schema_fingerprint",
            "git_dbt_source_and_validation",
            "superset_native_validation",
            "approval_scope_and_expiry",
        ]
        refusal = _refusal_for_facts(facts, campaign=False)
    elif arm == "retirement-conductor":
        reread = [
            "campaign_store",
            "datahub_complete_paged_inventory",
            "producer_schema_fingerprint",
            "git_dbt_source_and_validation",
            "superset_native_validation",
            "approval_scope_and_expiry",
            "publication_readback",
        ]
        refusal = _refusal_for_facts(facts, campaign=True)
    else:
        raise EvaluationError(f"unknown arm: {arm}")

    final_outcome = "REFUSED"
    response = "NOT_STARTED"
    outcome_unknown = False
    if refusal is None:
        response, outcome_unknown, recovered_steps, reused_during_action = (
            _complete_action(
                action,
                arm=arm,
                replay=facts["action_fault"] == "ACTION_REPLAY",
            )
        )
        green_reused = reused_during_action
        final_outcome = "OUTCOME_UNKNOWN" if outcome_unknown else "COMMITTED"
        reread.append("producer_schema_outcome")
    if arm == "point-in-time" and scenario["id"] != "no-drift-clean-control":
        green_reused = True

    artifact_available = facts["audit_sink_available"]
    modeled_ms = protocol["modeled_action_path_ms"][arm]
    if refusal is not None:
        modeled_ms -= protocol["modeled_action_path_ms"][arm] // 4
    return {
        "arm": arm,
        "scenario_id": scenario["id"],
        "scenario_input_digest": scenario_input_digest(scenario),
        "native_action_contract_digest": digest_json(
            protocol["native_action_contract"]
        ),
        "decision": "PERMIT" if refusal is None else "REFUSE",
        "reason_code": refusal or "ACTION_PRECONDITIONS_SATISFIED",
        "native_action_response": response,
        "destructive_statements_attempted": action.attempts,
        "committed_actions": action.commits,
        "column_present": action.column_present,
        "downstream_workload_healthy": action.column_present
        or facts["downstream_uses_replacement_only"],
        "final_outcome": final_outcome,
        "outcome_unknown": outcome_unknown,
        "green_artifact_reused": green_reused,
        "approval_artifact_reused": arm == "point-in-time" and green_reused,
        "replay_attempts": int(facts["action_fault"] == "ACTION_REPLAY"),
        "automatic_recovery_steps": recovered_steps,
        "manual_interventions_required": 0,
        "evidence_sources_reread": reread,
        "audit_bindings": _audit_bindings(
            artifact_available=artifact_available, static=arm == "point-in-time"
        ),
        "operator_reason": refusal
        or (
            "All arm-specific preconditions passed; the common action boundary "
            "committed once."
        ),
        "elapsed_action_path_ms": modeled_ms,
        "elapsed_measurement_mode": "frozen_modeled_fixture",
    }


def validate_baseline_capability(protocol: dict[str, Any]) -> None:
    required = set(protocol["required_fresh_ci_capabilities"])
    capability = protocol["fresh_ci_capability_statement"]
    enabled = {name for name, value in capability["capabilities"].items() if value}
    missing = sorted(required - enabled)
    if missing:
        raise EvaluationError(
            f"intentionally biased fresh-CI baseline: missing {missing}"
        )
    if capability["represents_named_vendor"] is not False:
        raise EvaluationError(
            "fresh-CI baseline must not be attributed to a named vendor"
        )


def _result_metrics(result: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    oracle_metrics = verify_observation(expected, result)
    stale_approval = bool(
        result["approval_artifact_reused"]
        and not expected["prior_approval_operationally_reusable"]
    )
    audit_present = sum(bool(value) for value in result["audit_bindings"].values())
    return {
        **oracle_metrics,
        "stale_approval_or_green_artifact_reuse": int(
            stale_approval or result["green_artifact_reused"]
        ),
        "destructive_statements_attempted": result["destructive_statements_attempted"],
        "destructive_statements_committed": result["committed_actions"],
        "replayed_action_attempts": result["replay_attempts"],
        "outcome_unknown_states_resolved_correctly": int(
            oracle_metrics["outcome_unknown_state_correct"]
        ),
        "manual_interventions_required": result["manual_interventions_required"],
        "evidence_sources_reread": result["evidence_sources_reread"],
        "operator_recovery_reason": result["operator_reason"],
        "audit_binding_presence": result["audit_bindings"],
        "audit_binding_count": audit_present,
        "elapsed_action_path_ms": result["elapsed_action_path_ms"],
    }


def classify(matrix: list[dict[str, Any]], protocol: dict[str, Any]) -> tuple[str, str]:
    by_arm: dict[str, list[dict[str, Any]]] = {arm: [] for arm in ARM_IDS}
    for row in matrix:
        by_arm[row["arm"]].append(row)
    fresh = by_arm["fresh-ci"]
    conductor = by_arm["retirement-conductor"]
    fresh_unsafe = sum(
        row["metrics"]["unsafe_committed_producer_actions"] for row in fresh
    )
    conductor_unsafe = sum(
        row["metrics"]["unsafe_committed_producer_actions"] for row in conductor
    )
    fresh_false = sum(row["metrics"]["false_refusal"] for row in fresh)
    conductor_false = sum(row["metrics"]["false_refusal"] for row in conductor)
    if conductor_unsafe > fresh_unsafe or conductor_false > fresh_false:
        return "WORSE", "REMOVE"
    no_clean_regression = conductor_false == 0
    fresh_stale = sum(
        row["metrics"]["stale_approval_or_green_artifact_reuse"] for row in fresh
    )
    conductor_stale = sum(
        row["metrics"]["stale_approval_or_green_artifact_reuse"] for row in conductor
    )
    if no_clean_regression and (
        conductor_unsafe < fresh_unsafe or conductor_stale < fresh_stale
    ):
        return "MATERIALLY_BETTER", "KEEP"
    fresh_manual = sum(row["metrics"]["manual_interventions_required"] for row in fresh)
    conductor_manual = sum(
        row["metrics"]["manual_interventions_required"] for row in conductor
    )
    fresh_unknown = sum(
        not row["metrics"]["outcome_unknown_state_correct"] for row in fresh
    )
    conductor_unknown = sum(
        not row["metrics"]["outcome_unknown_state_correct"] for row in conductor
    )
    fresh_audit = sum(row["metrics"]["audit_binding_count"] for row in fresh)
    conductor_audit = sum(row["metrics"]["audit_binding_count"] for row in conductor)
    if (
        conductor_unsafe == fresh_unsafe
        and conductor_false == fresh_false
        and (
            conductor_manual < fresh_manual
            or conductor_unknown < fresh_unknown
            or conductor_audit > fresh_audit
        )
    ):
        return "SAFETY_EQUIVALENT_PROTOCOL_ADVANTAGE", "KEEP"
    machinery = protocol["decision_rule"]["persistent_machinery_units"]
    if (
        conductor_unsafe == fresh_unsafe == 0
        and conductor_false == fresh_false == 0
        and conductor_stale == fresh_stale
        and conductor_manual == fresh_manual
        and conductor_unknown == fresh_unknown
        and conductor_audit == fresh_audit
        and machinery["fresh-ci"] < machinery["retirement-conductor"]
    ):
        return "NO_MATERIAL_ADVANTAGE", "SIMPLIFY"
    return "INCONCLUSIVE", "INCONCLUSIVE"


def evaluate_run(
    run_record: dict[str, Any], protocol: dict[str, Any]
) -> dict[str, Any]:
    verify_frozen_protocol(protocol)
    validate_baseline_capability(protocol)
    if run_record["frozen_digest"] != protocol["frozen_digest"]:
        raise EvaluationError("run inputs changed after freeze")
    results = run_record["results"]
    expected_rows = {
        (scenario["id"], arm) for scenario in protocol["scenarios"] for arm in ARM_IDS
    }
    actual_rows = {(row["scenario_id"], row["arm"]) for row in results}
    if actual_rows != expected_rows or len(results) != len(expected_rows):
        raise EvaluationError("missing arms or scenarios in run evidence")
    expected_action_digest = digest_json(protocol["native_action_contract"])
    oracle = expected_properties(protocol)
    matrix: list[dict[str, Any]] = []
    for result in results:
        scenario = next(
            item
            for item in protocol["scenarios"]
            if item["id"] == result["scenario_id"]
        )
        if result["scenario_input_digest"] != scenario_input_digest(scenario):
            raise EvaluationError("run scenario inputs do not match frozen inputs")
        if result["native_action_contract_digest"] != expected_action_digest:
            raise EvaluationError("unmatched native actions across comparison arms")
        matrix.append(
            {
                "scenario_id": result["scenario_id"],
                "arm": result["arm"],
                "observation": result,
                "metrics": _result_metrics(result, oracle[result["scenario_id"]]),
            }
        )
    classification, recommendation = classify(matrix, protocol)
    return {
        "matrix": matrix,
        "classification": classification,
        "recommendation": recommendation,
    }


def _failure_probes(
    run_record: dict[str, Any], protocol: dict[str, Any]
) -> list[dict[str, Any]]:
    probes: list[tuple[str, dict[str, Any], dict[str, Any], str]] = []
    missing_arm = copy.deepcopy(run_record)
    missing_arm["results"].pop()
    probes.append(("missing-arm", missing_arm, protocol, "missing arms"))
    changed_input = copy.deepcopy(run_record)
    changed_input["frozen_digest"] = "sha256:" + "0" * 64
    probes.append(("changed-inputs", changed_input, protocol, "inputs changed"))
    wrong_action = copy.deepcopy(run_record)
    wrong_action["results"][0]["native_action_contract_digest"] = "sha256:" + "1" * 64
    probes.append(
        ("unmatched-native-action", wrong_action, protocol, "unmatched native")
    )
    post_hoc = copy.deepcopy(protocol)
    post_hoc["scenarios"][0]["expected_properties"]["producer_action_safe"] = False
    probes.append(("post-hoc-oracle-edit", run_record, post_hoc, "post-hoc oracle"))
    biased = copy.deepcopy(protocol)
    biased["fresh_ci_capability_statement"]["capabilities"][
        "complete_paged_inventory"
    ] = False
    unsigned = dict(biased)
    unsigned.pop("frozen_digest", None)
    biased["frozen_digest"] = digest_json(unsigned)
    biased_run = copy.deepcopy(run_record)
    biased_run["frozen_digest"] = biased["frozen_digest"]
    probes.append(("biased-baseline", biased_run, biased, "biased fresh-CI"))
    observed: list[dict[str, Any]] = []
    for name, candidate_run, candidate_protocol, expected_message in probes:
        try:
            evaluate_run(candidate_run, candidate_protocol)
        except (EvaluationError, OracleError) as error:
            message = str(error)
            observed.append(
                {
                    "probe": name,
                    "expected_refusal_contains": expected_message,
                    "observed_refusal": message,
                    "passed": expected_message in message,
                }
            )
        else:
            observed.append(
                {
                    "probe": name,
                    "expected_refusal_contains": expected_message,
                    "observed_refusal": None,
                    "passed": False,
                }
            )
    if not all(item["passed"] for item in observed):
        raise EvaluationError("one or more adversarial evaluator probes failed")
    return observed


def run_foundation_matrix(
    protocol_path: Path,
    *,
    public_root: Path,
    raw_path: Path,
) -> dict[str, Any]:
    protocol = load_object(protocol_path)
    verify_frozen_protocol(protocol)
    validate_baseline_capability(protocol)
    results = [
        run_arm(arm, scenario, protocol)
        for scenario in protocol["scenarios"]
        for arm in ARM_IDS
    ]
    run_record = with_digest(
        {
            "schema_version": "1.0.0",
            "experiment_id": protocol["experiment_id"],
            "evidence_mode": "fixture executable local",
            "base_commit": protocol["base_commit"],
            "frozen_digest": protocol["frozen_digest"],
            "oracle_digest": oracle_digest(protocol),
            "runtime": {
                "python": platform.python_version(),
                "implementation": platform.python_implementation(),
                "retirement_conductor": "0.2.0",
                "native_action": protocol["native_action_contract"]["adapter_version"],
                "downstream_probe": protocol["downstream_outcome_adapter"][
                    "adapter_version"
                ],
            },
            "results": results,
        },
        "run_digest",
    )
    evaluated = evaluate_run(run_record, protocol)
    probes = _failure_probes(run_record, protocol)
    matrix = with_digest(
        {
            "schema_version": "1.0.0",
            "experiment_id": protocol["experiment_id"],
            "frozen_digest": protocol["frozen_digest"],
            "oracle_digest": run_record["oracle_digest"],
            "classification": evaluated["classification"],
            "recommendation": evaluated["recommendation"],
            "rows": evaluated["matrix"],
        },
        "matrix_digest",
    )
    failures = with_digest(
        {
            "schema_version": "1.0.0",
            "experiment_id": protocol["experiment_id"],
            "probes": probes,
        },
        "failures_digest",
    )
    baseline = with_digest(
        protocol["fresh_ci_capability_statement"], "capability_digest"
    )
    summary = _summarize(matrix["rows"])
    report = with_digest(
        {
            "schema_version": "1.0.0",
            "experiment_id": protocol["experiment_id"],
            "evidence_mode": "fixture executable local",
            "frozen_digest": protocol["frozen_digest"],
            "oracle_digest": run_record["oracle_digest"],
            "run_digest": run_record["run_digest"],
            "matrix_digest": matrix["matrix_digest"],
            "failures_digest": failures["failures_digest"],
            "baseline_capability_digest": baseline["capability_digest"],
            "classification": evaluated["classification"],
            "recommendation": evaluated["recommendation"],
            "per_arm_summary": summary,
            "decision_rule": protocol["decision_rule"],
            "limitations": protocol["limitations"],
            "integration_adapters": {
                "cp01": protocol["native_action_contract"],
                "cp02": protocol["superset_refresh_adapter"],
                "cp04": protocol["downstream_outcome_adapter"],
            },
        },
        "report_digest",
    )
    write_json(raw_path, run_record)
    write_json(public_root / "matrix.json", matrix)
    write_json(public_root / "failure-attempts.json", failures)
    write_json(public_root / "baseline-capability.json", baseline)
    write_json(public_root / "report.json", report)
    index = with_digest(
        {
            "schema_version": "1.0.0",
            "experiment_id": protocol["experiment_id"],
            "classification": evaluated["classification"],
            "recommendation": evaluated["recommendation"],
            "frozen_digest": protocol["frozen_digest"],
            "report_digest": report["report_digest"],
            "files": [
                "baseline-capability.json",
                "failure-attempts.json",
                "matrix.json",
                "report.json",
            ],
            "raw_evidence": {
                "path_class": "ignored task-local runtime state",
                "retention": "retain through CP-05 integration; do not publish",
                "digest": run_record["run_digest"],
            },
            "limitations": protocol["limitations"],
        },
        "index_digest",
    )
    write_json(public_root / "index.json", index)
    return index


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for arm in ARM_IDS:
        selected = [row for row in rows if row["arm"] == arm]
        result[arm] = {
            "unsafe_committed_producer_actions": sum(
                row["metrics"]["unsafe_committed_producer_actions"] for row in selected
            ),
            "false_refusals": sum(row["metrics"]["false_refusal"] for row in selected),
            "destructive_statements_attempted": sum(
                row["metrics"]["destructive_statements_attempted"] for row in selected
            ),
            "destructive_statements_committed": sum(
                row["metrics"]["destructive_statements_committed"] for row in selected
            ),
            "stale_approval_or_green_artifact_reuse": sum(
                row["metrics"]["stale_approval_or_green_artifact_reuse"]
                for row in selected
            ),
            "manual_interventions_required": sum(
                row["metrics"]["manual_interventions_required"] for row in selected
            ),
            "audit_binding_count": sum(
                row["metrics"]["audit_binding_count"] for row in selected
            ),
        }
    return result


def verify_public_evidence(protocol_path: Path, public_root: Path) -> dict[str, Any]:
    protocol = load_object(protocol_path)
    verify_frozen_protocol(protocol)
    index = load_object(public_root / "index.json")
    report = load_object(public_root / "report.json")
    matrix = load_object(public_root / "matrix.json")
    failures = load_object(public_root / "failure-attempts.json")
    baseline = load_object(public_root / "baseline-capability.json")
    from retirement_conductor.canonical import verify_digest

    for value, field in (
        (index, "index_digest"),
        (report, "report_digest"),
        (matrix, "matrix_digest"),
        (failures, "failures_digest"),
        (baseline, "capability_digest"),
    ):
        verify_digest(value, field)
    if index["frozen_digest"] != protocol["frozen_digest"]:
        raise EvaluationError("public evidence is bound to another frozen protocol")
    if report["matrix_digest"] != matrix["matrix_digest"]:
        raise EvaluationError("report does not bind the public matrix")
    if not all(item["passed"] for item in failures["probes"]):
        raise EvaluationError("public failure attempts contain a missed refusal")
    validate_baseline_capability(
        {
            **protocol,
            "fresh_ci_capability_statement": {
                key: value
                for key, value in baseline.items()
                if key != "capability_digest"
            },
        }
    )
    return index

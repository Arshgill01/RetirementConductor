#!/usr/bin/env python3
"""Verify inspected live artifacts and emit a public-safe Superset summary."""

from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from retirement_conductor.canonical import verify_digest, write_json
from retirement_conductor.superset import (
    SupersetClient,
    dataset_id_from_datahub,
    inspect_execution,
    snapshot_dataset,
)
from retirement_conductor.superset_config import SupersetSettings


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected JSON object: {path.name}")
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def binding_summary(
    plan: Mapping[str, Any],
    apply: Mapping[str, Any],
    validation: Mapping[str, Any],
    receipt: Mapping[str, Any],
    reconciliation: Mapping[str, Any],
    compensation: Mapping[str, Any],
) -> dict[str, Any]:
    require(apply["plan_digest"] == plan["plan_digest"], "apply/plan mismatch")
    require(receipt["plan"]["digest"] == plan["plan_digest"], "receipt/plan mismatch")
    require(
        receipt["apply"]["actual_targets"] == plan["proposed_targets"],
        "receipt target mismatch",
    )
    require(validation["result"] == "PASSED", "native validation did not pass")
    require(validation["semantic_parity"] is True, "semantic parity did not pass")
    require(
        reconciliation["receipt_digest"] == receipt["receipt_digest"],
        "reconciliation/receipt mismatch",
    )
    require(compensation["result"] == "RESTORED", "compensation was not restored")
    observation = reconciliation["datahub"]
    identity = plan["native_identity"]
    mapped = dataset_id_from_datahub(
        {
            "urn": observation["dataset_urn"],
            "external_url": observation["dataset_external_url"],
        }
    )
    require(mapped == identity["dataset_id"], "DataHub/native identity mismatch")
    return {
        "plan_digest": plan["plan_digest"],
        "apply_digest": apply["apply_digest"],
        "validation_digest": validation["validation_digest"],
        "receipt_digest": receipt["receipt_digest"],
        "reconciliation_digest": reconciliation["reconciliation_digest"],
        "compensation_digest": compensation["compensation_digest"],
        "actual_targets": list(apply["actual_targets"]),
    }


def focused_tests() -> dict[str, Any]:
    command = [
        "uv",
        "run",
        "pytest",
        "-q",
        "tests/unit/test_superset.py",
        "tests/unit/test_superset_config.py",
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError("focused Superset tests failed")
    last_line = completed.stdout.strip().splitlines()[-1]
    return {
        "command": " ".join(command),
        "result": "PASSED",
        "summary": last_line,
        "evidence_mode": "focused deterministic fault-injection tests",
    }


def generate(arguments: argparse.Namespace) -> None:
    root = arguments.artifact_root
    plan = load(arguments.plan)
    apply = load(root / "apply.json")
    validation = load(root / "native-validation" / "validation.json")
    receipt = load(root / "receipt.json")
    reconciliation = load(root / "reconciliation" / "source-reconciliation.json")
    compensation = load(root / "compensation.json")
    for value, field in (
        (plan, "plan_digest"),
        (apply, "apply_digest"),
        (validation, "validation_digest"),
        (receipt, "receipt_digest"),
        (reconciliation, "reconciliation_digest"),
        (compensation, "compensation_digest"),
    ):
        verify_digest(value, field)
    binding = binding_summary(
        plan, apply, validation, receipt, reconciliation, compensation
    )

    settings = SupersetSettings.from_environment()
    client = SupersetClient(settings)
    client.authenticate()
    identity = plan["native_identity"]
    current = snapshot_dataset(client.get_dataset(int(identity["dataset_id"])))
    require(
        current["fingerprint"] == plan["target"]["before_fingerprint"],
        "live object is not at the compensated before fingerprint",
    )
    chart = client.get_chart(int(identity["chart_id"]))
    require(chart["uuid"] == identity["chart_uuid"], "live chart UUID changed")
    restored_execution = inspect_execution(
        client.execute_chart(int(identity["chart_id"]))
    )
    require(restored_execution["result"] == "PASSED", "restored execution failed")
    require(
        restored_execution["safe_output_digest"]
        == plan["validation"]["baseline"]["safe_output_digest"],
        "restored semantic output changed",
    )

    observation = reconciliation["datahub"]
    replacement = str(plan["target"]["replacement_field"])
    legacy = str(plan["target"]["legacy_field"])
    fields = [str(value) for value in observation["upstream_field_urns"]]
    require(
        any(value.endswith(f",{replacement})") for value in fields),
        "replacement edge missing",
    )
    require(
        not any(value.endswith(f",{legacy})") for value in fields),
        "legacy edge remains",
    )

    refusal_evidence = load(arguments.refusal_evidence)
    require(
        refusal_evidence.get("approval_missing") == "AUTH_APPROVAL_MISSING",
        "live missing-approval refusal missing",
    )
    require(
        refusal_evidence.get("owner_change") == "COMPENSATION_CONFLICT",
        "live compensation-conflict refusal missing",
    )
    require(
        refusal_evidence.get("owner_change_preserved") is True,
        "owner drift overwritten",
    )

    evidence = {
        "schema_version": "1.0.0",
        "workstream": "WS-04 Superset native executor",
        "evidence_mode": "live-local disposable Superset and DataHub Core",
        "feasibility_gate": {
            "result": "PASSED",
            "superset_version": settings.version,
            "datahub_connector_version": observation["connector_version"],
            "authentication_mode": "database login to JWT bearer plus CSRF",
            "native_identity": dict(identity),
            "mapping_basis": "connector datasource_id URL plus native UUID reread",
            "field_authority": "direct native virtual-dataset SQL",
            "forced_native_execution": True,
            "semantic_output_parity": True,
            "single_allowlisted_object": True,
            "fresh_connector_reread": bool(observation["direct_reread"]),
            "safe_compensation": True,
        },
        "bindings": binding,
        "live_refusals": refusal_evidence,
        "fault_matrix": {
            "source_drift": "PASSED",
            "ambiguous_identity": "PASSED",
            "api_timeout_outcome_unknown": "PASSED",
            "execution_failure": "PASSED",
            "semantic_drift": "PASSED",
            "connector_failure": "PASSED",
            "table_only_evidence": "PASSED",
            "compensation_owner_conflict": "PASSED",
            "mode": (
                "live probes where named; otherwise focused deterministic "
                "fault injection"
            ),
        },
        "focused_tests": focused_tests(),
        "restored_native_state": {
            "fingerprint": current["fingerprint"],
            "execution": restored_execution,
        },
        "limitations": [
            *list(plan["limitations"]),
            "The connector contract documents table-level lineage.",
            (
                "The observed parser-derived field edge is retained only as "
                "corroboration for this SQL."
            ),
            (
                "This workstream does not register Superset with the campaign "
                "gate or alter the Git/dbt-only product claim."
            ),
        ],
        "credential_values_recorded": False,
    }
    write_json(arguments.output, evidence)
    print(json.dumps(evidence, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--refusal-evidence", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/public/superset/ws04-evidence.json"),
    )
    generate(parser.parse_args())


if __name__ == "__main__":
    main()

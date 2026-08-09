#!/usr/bin/env python3
"""Publish a redacted WS-02 evidence bundle from inspected live artifacts."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from retirement_conductor.canonical import verify_digest, with_digest, write_json
from retirement_conductor.schemas import validate_schema
from retirement_conductor.semantic_validation import approved_targets

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_PATH = re.compile(r"(?:/home/|/Users/)[^/\s]+/")
SECRET_ASSIGNMENT = re.compile(
    r"(?im)(?:bearer|client_secret|password|access_token)\s*[=:]\s*[\"']?\S+"
)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected a JSON object: {path.name}")
    return value


def checked_git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git evidence read failed with exit {result.returncode}")
    return result.stdout


def require_public_safe(label: str, text: str) -> None:
    if PRIVATE_PATH.search(text) or SECRET_ASSIGNMENT.search(text):
        raise RuntimeError(f"{label} contains private or credential-like material")


def publish(private: Path, repository: Path, output: Path) -> None:
    model = load(private / "model-acceptance.json")
    plan = load(private / "semantic-plan.json")
    receipt = load(private / "recovery-github-receipt.json")
    ci = load(private / "recovery-ci.json")
    preauthorization = load(private / "pre-authorization-refusal.json")
    drift = load(private / "head-drift-refusal.json")
    recovery = load(private / "owner-change-recovery.json")

    validate_schema("semantic-model-acceptance", model)
    validate_schema("semantic-validation-plan", plan)
    validate_schema("github-pr-receipt", receipt)
    verify_digest(model, "model_evidence_digest")
    verify_digest(plan, "plan_digest")
    verify_digest(receipt, "receipt_digest")
    verify_digest(preauthorization, "refusal_digest")
    verify_digest(drift, "refusal_digest")
    verify_digest(recovery, "history_digest")

    expected_files = approved_targets(plan)
    if receipt["commit"]["changed_files"] != expected_files:
        raise RuntimeError("the recovered receipt does not equal the approved files")
    diff_files = sorted(
        line
        for line in checked_git(
            repository,
            "diff",
            "--name-only",
            f"{plan['repository']['source_version']}..{receipt['commit']['head_sha']}",
        ).splitlines()
        if line
    )
    if diff_files != expected_files:
        raise RuntimeError("the native Git diff does not equal the approved files")
    diff = checked_git(
        repository,
        "diff",
        "--no-ext-diff",
        "--no-color",
        "--unified=0",
        f"{plan['repository']['source_version']}..{receipt['commit']['head_sha']}",
        "--",
        *expected_files,
    )

    ci_binding = with_digest(
        {
            "schema_version": "1.0.0",
            "campaign_id": plan["campaign_id"],
            "plan_digest": plan["plan_digest"],
            "pull_request_number": receipt["pull_request"]["number"],
            "head_sha": ci["head_sha"],
            "check_name": ci["check_name"],
            "check_run_id": ci["check_run_id"],
            "workflow_run_id": ci["workflow_run_id"],
            "conclusion": ci["conclusion"],
            "validator_versions": ci["validator_versions"],
            "captured_at": ci["captured_at"],
        },
        "ci_binding_digest",
    )
    summary = with_digest(
        {
            "schema_version": "1.0.0",
            "evidence_mode": "live",
            "campaign_id": plan["campaign_id"],
            "model": {
                "provider": model["provider"],
                "identifier": model["model_identifier"],
                "response_id": model["response_id"],
                "evidence_digest": model["model_evidence_digest"],
                "non_authority": model["non_authority"],
            },
            "semantic_plan_digest": plan["plan_digest"],
            "checks": [item["primitive"] for item in plan["checks"]],
            "approved_targets": expected_files,
            "pre_authorization_refusal": preauthorization["refusal_code"],
            "pull_request": receipt["pull_request"],
            "native_validation": receipt["native_validation"],
            "ci_binding_digest": ci_binding["ci_binding_digest"],
            "head_drift_refusal_digest": drift["refusal_digest"],
            "recovery_receipt_digest": receipt["receipt_digest"],
            "owner_change_preserved_in_history": recovery[
                "owner_change_preserved_in_history"
            ],
            "limitations": [
                "DataHub returned no glossary association or field-quality assertion.",
                "Empty query history is explicitly non-authoritative.",
                "The optional model did not authorize, validate, or decide readiness.",
                "The sample pull request remains open and unmerged.",
            ],
        },
        "acceptance_digest",
    )

    publications = {
        "model-acceptance.json": model,
        "semantic-plan.json": plan,
        "native-receipt.json": receipt,
        "ci-binding.json": ci_binding,
        "pre-authorization-refusal.json": preauthorization,
        "head-drift-refusal.json": drift,
        "owner-change-recovery.json": recovery,
        "acceptance-summary.json": summary,
    }
    for name, value in publications.items():
        rendered = json.dumps(value, sort_keys=True)
        require_public_safe(name, rendered)
    require_public_safe("exact-diff.patch", diff)

    output.mkdir(parents=True, exist_ok=True)
    for name, value in publications.items():
        write_json(output / name, value)
    (output / "exact-diff.patch").write_text(diff, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--private-root",
        type=Path,
        default=ROOT / ".retirement-conductor" / "semantic-pr",
    )
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "artifacts" / "public" / "semantic-pr",
    )
    arguments = parser.parse_args()
    publish(
        arguments.private_root.resolve(),
        arguments.repository.resolve(),
        arguments.output.resolve(),
    )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Promote inspected Phase 05 operator artifacts into public evidence."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from retirement_conductor.canonical import (
    digest_json,
    with_digest,
    write_json,
)
from retirement_conductor.events import (
    build_event,
    manifest_from_projection,
    project_events,
)
from retirement_conductor.operator import build_campaign_view
from retirement_conductor.policy import default_policy

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "artifacts/public/phase05"
RUNTIME = ROOT / ".retirement-conductor/phase05"
READY = ROOT / "artifacts/public/phase04/ready-manifest.json"
UNSAFE = ROOT / "artifacts/public/phase04/late-manifest.json"
BLOCKED = ROOT / "artifacts/public/phase01/blocked-manifest.json"
ALL_CLOSED_FIXTURE = ROOT / "artifacts/public/phase00/manifest.json"
BROWSER_RAW = RUNTIME / "browser-evidence.json"
ALLOWED_DIRTY_PREFIXES = (
    "artifacts/public/phase05/",
    "docs/assets/phase05/",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def run_command(arguments: list[str], *, timeout: int = 300) -> str:
    completed = subprocess.run(
        arguments,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    require(
        completed.returncode == 0,
        f"{arguments[0]} exited {completed.returncode}",
    )
    return completed.stdout


def git(*arguments: str) -> str:
    return run_command(["git", *arguments], timeout=60).strip()


def digest_bytes(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"{path.name} is not an object")
    return value


def load_manifest(path: Path) -> dict[str, Any]:
    value = load_object(path)
    build_campaign_view(value)
    return value


def review_manifest() -> dict[str, Any]:
    campaign_id = "phase05-review-required-fixture"
    policy = default_policy()
    policy["requires_live_evidence"] = False
    policy["allow_waivers"] = True
    input_digests = {
        "policy": digest_json(policy),
        "validator_configuration": digest_json({"mode": "fixture"}),
        "authorization": digest_json({"mode": "fixture"}),
    }
    target = {
        "platform": "snowflake",
        "instance": "public-fixture",
        "database": "analytics",
        "schema": "commerce",
        "table": "orders",
        "field": "legacy_status",
        "datahub_urn": None,
    }
    replacement = {**target, "field": "order_status"}
    envelope = with_digest(
        {
            "schema_version": "1.0.0",
            "captured_at": "2026-01-01T00:01:00Z",
            "mode": "fixture",
            "sources": [
                {
                    "id": "datahub",
                    "required": True,
                    "status": "COMPLETE",
                    "source_version": "public-fixture/1.0",
                    "identity": "public-fixture",
                    "scope": {
                        "direction": "downstream",
                        "max_hops": 1,
                        "filters": [],
                        "pages": 1,
                        "reported_total": 1,
                        "returned_total": 1,
                    },
                    "freshness": {
                        "observed_at": "2026-01-01T00:01:00Z",
                        "source_updated_at": "2026-01-01T00:01:00Z",
                        "maximum_age_seconds": 900,
                    },
                    "permissions": {
                        "principal": "public-fixture",
                        "effective_scope": "controlled fixture only",
                    },
                    "limitations": [
                        "Fixture review evidence does not establish a live outcome."
                    ],
                    "artifact_ids": [digest_json({"fixture": "review-evidence"})],
                }
            ],
        },
        "envelope_digest",
    )
    waiver = with_digest(
        {
            "schema_version": "1.0.0",
            "campaign_id": campaign_id,
            "consumer_id": "consumer-review",
            "authority": "fixture-authority",
            "scope": ["review"],
            "reason": "Exercise the visible review-required decision.",
            "residual_risk": "No live authority or consumer was exercised.",
            "authorized_at": "2026-01-01T00:02:00Z",
            "expires_at": "2026-01-02T00:02:00Z",
        },
        "waiver_digest",
    )
    events: list[dict[str, Any]] = []

    def append(
        event_type: str,
        occurred_at: str,
        idempotency_key: str,
        payload: dict[str, Any],
    ) -> None:
        events.append(
            build_event(
                campaign_id=campaign_id,
                sequence=len(events) + 1,
                event_type=event_type,
                occurred_at=occurred_at,
                idempotency_key=idempotency_key,
                previous_event_digest=(
                    str(events[-1]["event_digest"]) if events else None
                ),
                payload=payload,
            )
        )

    append(
        "CAMPAIGN_CREATED",
        "2026-01-01T00:00:00Z",
        "create-review-fixture",
        {
            "name": "Review one bounded fixture waiver",
            "specification_digest": digest_json(
                {"campaign_id": campaign_id, "mode": "fixture"}
            ),
            "target": target,
            "replacement": replacement,
            "policy": policy,
            "input_digests": input_digests,
        },
    )
    append(
        "INVENTORY_RECORDED",
        "2026-01-01T00:01:00Z",
        "inventory-review-fixture",
        {
            "evidence_envelope": envelope,
            "consumers": [
                {
                    "id": "consumer-review",
                    "disposition": "IDENTIFIED",
                    "receipt_digest": None,
                }
            ],
            "snapshot_digest": digest_json({"snapshot": "review-baseline"}),
        },
    )
    append(
        "WAIVER_RECORDED",
        "2026-01-01T00:02:00Z",
        "waive-review-fixture",
        {"waiver": waiver},
    )
    append(
        "RECONCILIATION_RECORDED",
        "2026-01-01T00:03:00Z",
        "reconcile-review-fixture",
        {
            "evidence_envelope": envelope,
            "consumer_ids": ["consumer-review"],
            "consumers": [],
            "snapshot_digest": digest_json({"snapshot": "review-reconciliation"}),
            "comparison": {
                "comparison_digest": digest_json({"comparison": "review-equivalent"}),
                "added": [],
            },
        },
    )
    append(
        "POLICY_EVALUATED",
        "2026-01-01T00:04:00Z",
        "evaluate-review-fixture",
        {
            "input_digests": input_digests,
            "decision": "REVIEW_REQUIRED",
            "blocker_codes": [],
        },
    )
    manifest = manifest_from_projection(project_events(events))
    require(
        manifest["decision"] == "REVIEW_REQUIRED",
        "review fixture did not produce REVIEW_REQUIRED",
    )
    require(
        len(manifest.get("review_requirements", [])) == 1,
        "review fixture omitted its canonical review reason",
    )
    return manifest


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8", newline="\n")


def inspect_cli(
    *,
    label: str,
    manifest_path: Path,
    expected_decision: str,
) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    campaign_id = str(manifest["campaign"]["id"])
    output = run_command(
        [
            "uv",
            "run",
            "retirement-conductor",
            "campaign",
            "inspect",
            "--campaign",
            campaign_id,
            "--manifest",
            manifest_path.relative_to(ROOT).as_posix(),
        ]
    )
    require(
        f"Decision: {expected_decision}" in output,
        f"{label} CLI output omitted its decision",
    )
    require(
        str(manifest["manifest_digest"]) in output,
        f"{label} CLI output omitted its manifest digest",
    )
    path = PUBLIC / f"cli-{label}.txt"
    write_text(path, output)
    return {
        "decision": expected_decision,
        "manifest_digest": manifest["manifest_digest"],
        "output": path.relative_to(ROOT).as_posix(),
        "output_digest": digest_bytes(path.read_bytes()),
    }


def build_report(
    *,
    label: str,
    manifest_path: Path,
    public: bool,
) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    campaign_id = str(manifest["campaign"]["id"])
    output = PUBLIC / f"{label}.html"
    twin = RUNTIME / f"{label}-determinism.html"
    command = [
        "uv",
        "run",
        "retirement-conductor",
        "report",
        "build",
        "--campaign",
        campaign_id,
        "--manifest",
        manifest_path.relative_to(ROOT).as_posix(),
    ]
    first = [*command, "--output", output.relative_to(ROOT).as_posix()]
    second = [*command, "--output", twin.relative_to(ROOT).as_posix()]
    if public:
        first.append("--public")
        second.append("--public")
    run_command(first)
    run_command(second)
    require(output.read_bytes() == twin.read_bytes(), f"{label} is not deterministic")
    content = output.read_text(encoding="utf-8")
    require(
        str(manifest["manifest_digest"]) in content,
        f"{label} omitted the canonical digest",
    )
    require(
        str(manifest["decision"]) in content,
        f"{label} omitted the canonical decision",
    )
    return {
        "decision": manifest["decision"],
        "manifest_digest": manifest["manifest_digest"],
        "output": output.relative_to(ROOT).as_posix(),
        "output_digest": digest_bytes(output.read_bytes()),
        "export_mode": "public" if public else "local",
        "deterministic": True,
    }


def focused_test_evidence(output: str) -> dict[str, Any]:
    matches = re.findall(r"(\d+) passed", output)
    require(matches, "make test-ui output omitted a passing test count")
    return {
        "command": "make test-ui",
        "result": "PASSED",
        "test_count": int(matches[-1]),
        "output_digest": digest_bytes(output.encode()),
    }


def check_allowed_dirty_state() -> None:
    lines = git("status", "--porcelain", "--untracked-files=all").splitlines()
    disallowed: list[str] = []
    for line in lines:
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if not path.startswith(ALLOWED_DIRTY_PREFIXES):
            disallowed.append(path)
    require(
        not disallowed,
        "Phase 05 evidence requires committed implementation; dirty paths: "
        + ", ".join(disallowed),
    )


def run() -> int:
    require(BROWSER_RAW.is_file(), "run `make phase05-browser` first")
    check_allowed_dirty_state()
    tested_commit = git("rev-parse", "HEAD")
    PUBLIC.mkdir(parents=True, exist_ok=True)
    RUNTIME.mkdir(parents=True, exist_ok=True)

    review_path = PUBLIC / "review-required-manifest.json"
    write_json(review_path, review_manifest())
    decisions = {
        "ready": inspect_cli(
            label="ready",
            manifest_path=READY,
            expected_decision="READY_TO_RETIRE",
        ),
        "review-required": inspect_cli(
            label="review-required",
            manifest_path=review_path,
            expected_decision="REVIEW_REQUIRED",
        ),
        "blocked": inspect_cli(
            label="blocked",
            manifest_path=BLOCKED,
            expected_decision="BLOCKED",
        ),
        "unsafe": inspect_cli(
            label="unsafe",
            manifest_path=UNSAFE,
            expected_decision="UNSAFE",
        ),
    }
    require(
        {item["decision"] for item in decisions.values()}
        == {"READY_TO_RETIRE", "REVIEW_REQUIRED", "BLOCKED", "UNSAFE"},
        "CLI evidence did not exercise all four decisions",
    )

    unsafe_manifest = load_manifest(UNSAFE)
    explain_output = run_command(
        [
            "uv",
            "run",
            "retirement-conductor",
            "campaign",
            "explain",
            "--campaign",
            str(unsafe_manifest["campaign"]["id"]),
            "--manifest",
            UNSAFE.relative_to(ROOT).as_posix(),
        ]
    )
    require(
        "Evidence source:" in explain_output and "Recovery:" in explain_output,
        "unsafe explanation omitted evidence source or recovery",
    )
    write_text(PUBLIC / "cli-unsafe-explain.txt", explain_output)

    reports = {
        "live_refusal": build_report(
            label="live-refusal-report",
            manifest_path=UNSAFE,
            public=False,
        ),
        "all_closed_fixture": build_report(
            label="all-closed-fixture-report",
            manifest_path=ALL_CLOSED_FIXTURE,
            public=False,
        ),
        "public_export": build_report(
            label="public-export",
            manifest_path=UNSAFE,
            public=True,
        ),
    }
    require(
        reports["live_refusal"]["manifest_digest"]
        == decisions["unsafe"]["manifest_digest"],
        "live refusal CLI/report digest parity failed",
    )
    require(
        reports["all_closed_fixture"]["decision"] == "BLOCKED",
        "all-closed fixture must remain visibly blocked by non-live evidence",
    )

    browser = load_object(BROWSER_RAW)
    require(browser.get("result") == "PASSED", "browser evidence did not pass")
    for report in browser.get("reports", {}).values():
        require(isinstance(report, dict), "browser report evidence is malformed")
        path = ROOT / str(report["file"])
        require(
            digest_bytes(path.read_bytes()) == report["digest"],
            f"browser report changed after acceptance: {path.name}",
        )
    for page in browser.get("pages", []):
        require(isinstance(page, dict), "browser page evidence is malformed")
        screenshot = page.get("screenshot")
        require(isinstance(screenshot, dict), "browser screenshot evidence is missing")
        path = ROOT / str(screenshot["file"])
        require(path.is_file(), f"browser screenshot is missing: {path.name}")
        require(
            digest_bytes(path.read_bytes()) == screenshot["digest"],
            f"browser screenshot digest changed: {path.name}",
        )
    require(
        all(
            item.get("violations") == 0 and item.get("incomplete") == 0
            for item in browser.get("axe", [])
            if isinstance(item, dict)
        ),
        "axe evidence is incomplete or contains violations",
    )
    write_json(PUBLIC / "browser-evidence.json", browser)

    accessibility_output = run_command(
        [
            "uv",
            "run",
            "python",
            "scripts/check_ui_artifacts.py",
            reports["live_refusal"]["output"],
            reports["all_closed_fixture"]["output"],
            reports["public_export"]["output"],
            "--output",
            "artifacts/public/phase05/accessibility-evidence.json",
        ]
    )
    accessibility = load_object(PUBLIC / "accessibility-evidence.json")
    require(
        accessibility.get("result") == "PASSED",
        "deterministic accessibility checks did not pass",
    )

    test_ui_output = run_command(["make", "test-ui"])
    validation = {
        "test_ui": focused_test_evidence(test_ui_output),
        "accessibility_output_digest": digest_bytes(accessibility_output.encode()),
        "git_diff_check": {
            "command": "git diff --check",
            "result": "PASSED",
            "output_digest": digest_bytes(
                run_command(["git", "diff", "--check"]).encode()
            ),
        },
    }

    write_json(PUBLIC / "phase05-evidence.json", {"result": "PENDING"})
    secret_output = run_command(["uv", "run", "python", "scripts/check_secrets.py"])
    public_output = run_command(
        ["uv", "run", "python", "scripts/check_public_artifacts.py"]
    )
    validation["secret_scan"] = {
        "command": "uv run python scripts/check_secrets.py",
        "result": "PASSED",
        "output_digest": digest_bytes(secret_output.encode()),
    }
    validation["public_artifact_scan"] = {
        "command": "uv run python scripts/check_public_artifacts.py",
        "result": "PASSED",
        "output_digest": digest_bytes(public_output.encode()),
    }

    evidence = with_digest(
        {
            "schema_version": "1.0.0",
            "result": "PASSED",
            "phase": "05",
            "repository_commit": tested_commit,
            "evidence_modes": ["live", "fixture"],
            "canonical_inputs": {
                "ready_live": {
                    "file": READY.relative_to(ROOT).as_posix(),
                    "manifest_digest": load_manifest(READY)["manifest_digest"],
                },
                "unsafe_live": {
                    "file": UNSAFE.relative_to(ROOT).as_posix(),
                    "manifest_digest": load_manifest(UNSAFE)["manifest_digest"],
                },
                "blocked_fixture": {
                    "file": BLOCKED.relative_to(ROOT).as_posix(),
                    "manifest_digest": load_manifest(BLOCKED)["manifest_digest"],
                },
                "review_fixture": {
                    "file": review_path.relative_to(ROOT).as_posix(),
                    "manifest_digest": load_manifest(review_path)["manifest_digest"],
                },
            },
            "cli_decisions": decisions,
            "reports": reports,
            "browser_evidence": {
                "file": "artifacts/public/phase05/browser-evidence.json",
                "digest": digest_json(browser),
                "playwright_cli_version": browser["playwright_cli_version"],
                "page_count": len(browser["pages"]),
                "keyboard_control_count": sum(
                    int(page["keyboard"]["control_count"]) for page in browser["pages"]
                ),
                "axe_violations": sum(
                    int(item["violations"]) for item in browser["axe"]
                ),
                "axe_incomplete": sum(
                    int(item["incomplete"]) for item in browser["axe"]
                ),
            },
            "accessibility_evidence": {
                "file": "artifacts/public/phase05/accessibility-evidence.json",
                "digest": digest_json(accessibility),
                "report_count": len(accessibility["reports"]),
            },
            "apply_confirmation": {
                "required_argument": "--confirm-plan-digest",
                "wrong_digest_refusal": "AUTH_APPROVAL_WRONG_PLAN",
                "missing_approval_refusal": "AUTH_APPROVAL_MISSING",
                "evidence": (
                    "tests/integration/test_git_dbt_workflow.py and "
                    "scripts/run_phase04_end_to_end.py"
                ),
            },
            "validation": validation,
            "limitations": [
                "The live report is derived from the disposable Phase 04 campaign.",
                "The all-closed report is fixture evidence and remains BLOCKED "
                "because fixture evidence cannot satisfy live policy.",
                "Automated browser and accessibility checks do not establish "
                "nontechnical human comprehension or independent operation.",
                "Public export redaction removes identities; the original canonical "
                "manifest remains the integrity authority.",
            ],
        },
        "evidence_digest",
    )
    write_json(PUBLIC / "phase05-evidence.json", evidence)
    run_command(["uv", "run", "python", "scripts/check_public_artifacts.py"])
    run_command(["uv", "run", "python", "scripts/check_secrets.py"])
    print(
        "Phase 05 evidence passed: 4 CLI decisions, 3 deterministic reports, "
        f"{evidence['browser_evidence']['keyboard_control_count']} keyboard "
        "controls, and 0 axe violations."
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(run())
    except (OSError, RuntimeError, subprocess.SubprocessError, ValueError) as exc:
        print(
            f"Phase 05 evidence failed: {type(exc).__name__}",
            file=sys.stderr,
        )
        sys.exit(1)

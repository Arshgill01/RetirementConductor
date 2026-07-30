#!/usr/bin/env python3
"""Run the full Core/Git/dbt reference through the installed release wheel."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from retirement_conductor import __version__
from retirement_conductor.canonical import (
    digest_bytes,
    digest_file,
    verify_digest,
    with_digest,
    write_json,
)
from retirement_conductor.datahub import utc_now
from scripts.phase08_support import (
    PHASE08_RUNTIME,
    ROOT,
    checked,
    create_clean_environment,
    installed_command,
    package_identity,
    runtime_environment,
)
from scripts.reference_services import (
    DATAHUB_GMS_URL,
    DATAHUB_MCP_URL,
    reference_services,
)

DBT_EXECUTABLE = ROOT / ".retirement-conductor/tools/dbt-duckdb-1.10.1/bin/dbt"
PHASE04_LATEST = ROOT / ".retirement-conductor/e2e/phase04/latest.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def payload_object(value: dict[str, Any] | None, label: str) -> dict[str, Any]:
    if value is None:
        raise RuntimeError(f"{label} did not return JSON")
    return value


def ensure_dbt() -> None:
    if DBT_EXECUTABLE.is_file():
        return
    checked(["make", "git-dbt-tool"], timeout=900)
    require(DBT_EXECUTABLE.is_file(), "the pinned dbt executable is unavailable")


def installed_fixture(
    environment_root: Path,
    *,
    base: Path,
    environment: dict[str, str],
) -> dict[str, Any]:
    work = base / "fixture-work"
    work.mkdir()
    summaries = []
    outputs = []
    for name in ("one", "two"):
        output = work / name
        _, value = installed_command(
            environment_root,
            ["reference", "run", "--output-dir", str(output)],
            cwd=work,
            environment=environment,
        )
        summary = payload_object(value, "installed reference")
        summaries.append(summary)
        outputs.append(output)
    require(summaries[0] == summaries[1], "reference summary did not reproduce")
    for filename in summaries[0]["artifacts"]:
        require(
            (outputs[0] / filename).read_bytes()
            == (outputs[1] / filename).read_bytes(),
            f"reference artifact did not reproduce: {filename}",
        )
    manifest = json.loads((outputs[0] / "manifest.json").read_text(encoding="utf-8"))
    verify_digest(manifest, "manifest_digest")
    require(manifest["decision"] == "BLOCKED", "fixture reference became ready")
    return {
        "mode": "fixture",
        "decision": manifest["decision"],
        "refusal_code": summaries[0]["refusal_code"],
        "manifest_digest": manifest["manifest_digest"],
        "summary_file_digest": digest_file(outputs[0] / "summary.json"),
        "byte_reproduced": True,
    }


def datahub_preflight(
    environment_root: Path,
    *,
    base: Path,
    environment: dict[str, str],
) -> dict[str, Any]:
    output = base / "datahub-capability.json"
    selected = {
        **environment,
        "DATAHUB_GMS_URL": DATAHUB_GMS_URL,
        "DATAHUB_MCP_URL": DATAHUB_MCP_URL,
        "DATAHUB_PRINCIPAL": "anonymous-disposable-core",
    }
    _, value = installed_command(
        environment_root,
        ["datahub", "preflight", "--output", str(output)],
        cwd=base,
        environment=selected,
        timeout=120,
    )
    result = payload_object(value, "DataHub preflight")
    capability = result["capability_fingerprint"]
    verify_digest(capability, "capability_digest")
    require(capability["edition"] == "core", "reference did not use Core")
    return {
        "edition": capability["edition"],
        "server_versions": capability["server_versions"],
        "mcp_tool_count": len(capability["mcp_tools"]),
        "fallbacks": capability["fallbacks"],
        "capability_digest": capability["capability_digest"],
    }


def live_reference(
    environment_root: Path,
    *,
    environment: dict[str, str],
) -> tuple[dict[str, Any], str]:
    selected = dict(os.environ)
    selected.update(environment)
    selected.pop("PYTHONPATH", None)
    selected.pop("VIRTUAL_ENV", None)
    selected["RETIREMENT_CONDUCTOR_CLI"] = str(
        environment_root / "bin/retirement-conductor"
    )
    selected["PYTHONNOUSERSITE"] = "1"
    result = checked(
        [sys.executable, "-m", "scripts.run_phase04_end_to_end"],
        environment=selected,
        timeout=1800,
    )
    summary = json.loads(PHASE04_LATEST.read_text(encoding="utf-8"))
    if not isinstance(summary, dict):
        raise RuntimeError("the live reference summary is not an object")
    verify_digest(summary, "evidence_digest")
    require(
        summary["isolated"]["ready_decision"] == "READY_TO_RETIRE",
        "installed live reference did not become ready",
    )
    require(
        summary["isolated"]["late_decision"] == "UNSAFE",
        "installed late-consumer reference did not reopen",
    )
    require(
        summary["rich_graph"]["decision"] == "UNSAFE",
        "installed rich reference did not refuse",
    )
    return summary, result.stdout.strip()


def run() -> dict[str, Any]:
    ensure_dbt()
    with tempfile.TemporaryDirectory(
        prefix="retirement-conductor-phase08-reference-"
    ) as temporary:
        base = Path(temporary)
        environment_root = create_clean_environment(
            base / "venv",
            python_version="3.11",
        )
        environment = runtime_environment(base / "home")
        version = checked(
            [
                str(environment_root / "bin/retirement-conductor"),
                "--version",
            ],
            cwd=base,
            environment=environment,
        ).stdout.strip()
        require(
            version == f"retirement-conductor {__version__}",
            "installed reference used the wrong package version",
        )
        fixture = installed_fixture(
            environment_root,
            base=base,
            environment=environment,
        )
        with reference_services() as services:
            capability = datahub_preflight(
                environment_root,
                base=base,
                environment=environment,
            )
            live, command_output = live_reference(
                environment_root,
                environment=environment,
            )
            service_evidence = services.evidence()

    product_operations = [
        command
        for command in live["commands"]
        if command["execution_mode"] in {"installed-product-cli", "source-product-cli"}
    ]
    require(
        bool(product_operations),
        "the live reference did not execute product commands",
    )
    require(
        all(
            command["execution_mode"] == "installed-product-cli"
            for command in product_operations
        ),
        "one or more live product operations bypassed the installed wheel",
    )
    repository_commit = checked(["git", "rev-parse", "HEAD"]).stdout.strip()
    require(
        live["repository_commit"] == repository_commit,
        "the live reference did not bind to the current repository commit",
    )
    evidence = with_digest(
        {
            "schema_version": "1.0.0",
            "captured_at": utc_now(),
            "result": "REFERENCE_CAMPAIGN_VERIFIED",
            "package": package_identity(),
            "installed_version": __version__,
            "fixture_reference": fixture,
            "core_capability": capability,
            "services": service_evidence,
            "live_reference": {
                "evidence_mode": live["evidence_mode"],
                "repository_commit": live["repository_commit"],
                "evidence_digest": live["evidence_digest"],
                "installed_cli_operation_count": len(product_operations),
                "source_cli_operation_count": 0,
                "isolated_consumer_count": live["isolated"]["baseline_consumer_count"],
                "apply_targets": live["isolated"]["apply_targets"],
                "validation_result": live["isolated"]["validation_result"],
                "ready_decision": live["isolated"]["ready_decision"],
                "ready_manifest_digest": live["isolated"]["ready_manifest_digest"],
                "producer_sentinel_count": live["isolated"]["sentinel_count"],
                "late_consumer_count": live["isolated"]["late_consumer_count"],
                "late_decision": live["isolated"]["late_decision"],
                "rich_consumer_count": live["rich_graph"]["consumer_count"],
                "rich_decision": live["rich_graph"]["decision"],
                "rich_gate_refusal": live["rich_graph"]["gate_refusal"],
                "command_output_digest": digest_bytes(command_output.encode()),
            },
            "limitations": [
                "The live reference uses disposable loopback DataHub Core, "
                "a local Git repository, DuckDB, and a harmless sentinel.",
                "The orchestration harness is source-controlled; every product "
                "CLI operation uses the clean installed wheel entry point.",
                "The deterministic fixture reference is not live evidence.",
            ],
        },
        "reference_evidence_digest",
    )
    PHASE08_RUNTIME.mkdir(parents=True, exist_ok=True)
    write_json(PHASE08_RUNTIME / "reference-evidence.json", evidence)
    print(
        "Installed reference campaign passed: fixture=BLOCKED "
        f"live={evidence['live_reference']['ready_decision']} "
        f"late={evidence['live_reference']['late_decision']} "
        f"rich={evidence['live_reference']['rich_decision']}."
    )
    return evidence


def main() -> int:
    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Validate raw Phase 08 receipts and publish only safe acceptance claims."""

from __future__ import annotations

import json
from collections.abc import Mapping
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
from scripts.phase08_support import PHASE08_RUNTIME, ROOT, checked

PUBLIC = ROOT / "artifacts/public/phase08"
RAW_PACKAGE = PHASE08_RUNTIME / "package-evidence.json"
RAW_INSTALL = PHASE08_RUNTIME / "install-evidence.json"
RAW_UPGRADE = PHASE08_RUNTIME / "upgrade-evidence.json"
RAW_REFERENCE = PHASE08_RUNTIME / "reference-evidence.json"

PACKAGE_PATH = PUBLIC / "package-evidence.json"
INSTALL_PATH = PUBLIC / "install-evidence.json"
UPGRADE_PATH = PUBLIC / "upgrade-evidence.json"
REFERENCE_PATH = PUBLIC / "reference-evidence.json"
COMPATIBILITY_PATH = PUBLIC / "compatibility-evidence.json"
OPERATOR_PATH = PUBLIC / "operator-boundary.json"
SUMMARY_PATH = PUBLIC / "phase08-preacceptance-evidence.json"

ALLOWED_DIRTY_PREFIXES = ("artifacts/public/phase08/",)
EXPECTED_MISSING_REFERENCES = {
    "DATAHUB_GMS_URL",
    "DATAHUB_MCP_URL",
    "GIT_DBT_DBT_EXECUTABLE",
    "GIT_DBT_PRINCIPAL",
    "GIT_DBT_REPOSITORY_ROOT",
}
EXPECTED_PYTHON_SERIES = {"3.11", "3.12", "3.13", "3.14"}
EXPECTED_PREVIOUS_COMMIT = "30173f160c3c87a8daf0a3c1988c7ccde10662ec"
EXPECTED_MCP_COMMIT = "9a6946daa7d30eb481c82dd8ee5e15ae6526a3c9"
MINIMUM_INSTALLED_REFERENCE_OPERATIONS = 34
FORBIDDEN_PUBLIC_FRAGMENTS = (
    "/home/",
    "/Users/",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def load_receipt(path: Path, digest_field: str) -> dict[str, Any]:
    require(path.is_file(), f"missing raw receipt: {path.name}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"{path.name} is not a JSON object")
    verify_digest(value, digest_field)
    return value


def repository_commit() -> str:
    return checked(["git", "rev-parse", "HEAD"]).stdout.strip()


def check_dirty_state() -> None:
    output = checked(["git", "status", "--porcelain", "--untracked-files=all"]).stdout
    disallowed = []
    for line in output.splitlines():
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if not path.startswith(ALLOWED_DIRTY_PREFIXES):
            disallowed.append(path)
    require(
        not disallowed,
        "commit Phase 08 implementation before generating acceptance evidence",
    )


def command_receipt(arguments: list[str], command_name: str) -> dict[str, Any]:
    result = checked(arguments, timeout=1200)
    output = result.stdout + result.stderr
    return {
        "command": command_name,
        "result": "PASSED",
        "exit_code": result.returncode,
        "output_digest": digest_bytes(output.encode()),
    }


def package_identity_from_raw(value: Mapping[str, Any]) -> dict[str, str]:
    wheel = value["wheel"]
    source = value["source_archive"]
    runtime_lock = value["runtime_lock"]
    require(isinstance(wheel, Mapping), "raw wheel evidence is invalid")
    require(isinstance(source, Mapping), "raw source archive evidence is invalid")
    require(isinstance(runtime_lock, Mapping), "raw runtime lock evidence is invalid")
    return {
        "wheel": str(wheel["filename"]),
        "wheel_digest": str(wheel["digest"]),
        "sdist": str(source["filename"]),
        "sdist_digest": str(source["digest"]),
        "requirements_digest": str(runtime_lock["digest"]),
    }


def require_package_identity(
    expected: Mapping[str, str],
    observed: object,
    label: str,
) -> None:
    require(isinstance(observed, Mapping), f"{label} package identity is invalid")
    normalized = {str(key): str(value) for key, value in observed.items()}
    require(normalized == dict(expected), f"{label} used a different release package")


def validate_package(
    raw: dict[str, Any],
    *,
    commit: str,
) -> tuple[dict[str, str], dict[str, Any]]:
    require(raw["result"] == "PACKAGE_VERIFIED", "package receipt did not pass")
    require(raw["version"] == __version__, "package version does not match runtime")
    require(
        raw["repository_commit"] == commit,
        "package receipt is not bound to the current commit",
    )
    reproducible = raw["reproducible_build"]
    require(
        reproducible
        == {
            "source_archive_byte_identical": True,
            "source_archive_rebuilt_wheel_identical": True,
            "wheel_byte_identical": True,
        },
        "release artifacts did not reproduce completely",
    )
    require(
        raw["source_archive"]["operational_state_excluded"] is True,
        "source archive retained operational state",
    )
    require(
        raw["runtime_lock"]["hash_bound"] is True,
        "runtime dependencies are not hash bound",
    )
    require(raw["signing"]["signed"] is False, "unexpected signing claim changed")
    identity = package_identity_from_raw(raw)
    public = with_digest(
        {
            "schema_version": "1.0.0",
            "phase": "08",
            "evidence_mode": "analysis",
            "captured_at": raw["captured_at"],
            "result": raw["result"],
            "command": "make package",
            "repository_commit": commit,
            "version": raw["version"],
            "package": identity,
            "wheel": raw["wheel"],
            "source_archive": raw["source_archive"],
            "runtime_lock": raw["runtime_lock"],
            "sbom": raw["sbom"],
            "checksums": raw["checksums"],
            "reproducible_build": reproducible,
            "signing": raw["signing"],
            "raw_receipt": {
                "file_digest": digest_file(RAW_PACKAGE),
                "artifact_digest": raw["package_evidence_digest"],
            },
            "limitations": [
                "The release is checksum-bound but has no signing identity.",
                "Reproducibility was observed on the recorded Linux build host.",
            ],
        },
        "phase08_package_evidence_digest",
    )
    return identity, public


def validate_install(
    raw: dict[str, Any],
    *,
    package: Mapping[str, str],
    commit: str,
) -> dict[str, Any]:
    require(raw["result"] == "CLEAN_INSTALL_VERIFIED", "install receipt failed")
    require_package_identity(package, raw["package"], "clean install")
    host = raw["host"]
    require(
        host["system"] == "Linux" and host["machine"] == "x86_64",
        "clean install ran outside the supported host boundary",
    )
    require(host["libc"][0] == "glibc", "clean install did not use glibc")

    runtimes = raw["runtimes"]
    require(len(runtimes) == 4, "clean install did not cover four Python series")
    observed_series = {
        ".".join(str(runtime["python_version"]).split(".")[:2]) for runtime in runtimes
    }
    require(
        observed_series == EXPECTED_PYTHON_SERIES,
        "clean install Python compatibility matrix changed",
    )
    reference_digests = set()
    for runtime in runtimes:
        require(runtime["package_version"] == __version__, "installed version drifted")
        require(
            runtime["import_isolated"] is True, "source checkout leaked into install"
        )
        require(
            runtime["configuration_refusal"] == "RUNTIME_CONFIGURATION_INCOMPLETE",
            "missing deployment configuration did not refuse",
        )
        require(
            set(runtime["missing_configuration_references"])
            == EXPECTED_MISSING_REFERENCES,
            "deployment refusal omitted an actionable reference",
        )
        require(
            runtime["reference_byte_reproduced"] is True,
            "built-in reference did not reproduce",
        )
        reference_digests.add(str(runtime["reference_manifest_digest"]))
    require(len(reference_digests) == 1, "reference digest changed by Python version")

    removal = raw["uninstall"]
    require(
        removal["copied_state_refusal"] == "RUNTIME_WRITER_MISMATCH"
        and removal["copied_state_unchanged"] is True,
        "copied deployment state did not refuse unchanged",
    )
    require(
        removal["unconfirmed_refusal"] == "AUTH_APPROVAL_MISSING",
        "state removal did not require exact confirmation",
    )
    require(
        removal["state_removed"] is True
        and removal["package_removed"] is True
        and removal["retained_plan"] is True,
        "confirmed state and package removal contract failed",
    )
    return with_digest(
        {
            "schema_version": "1.0.0",
            "phase": "08",
            "evidence_mode": "fixture",
            "captured_at": raw["captured_at"],
            "result": raw["result"],
            "command": "make test-install",
            "repository_commit": commit,
            "package": dict(package),
            "host": host,
            "runtimes": runtimes,
            "uninstall": removal,
            "raw_receipt": {
                "file_digest": digest_file(RAW_INSTALL),
                "artifact_digest": raw["install_evidence_digest"],
            },
            "limitations": raw["limitations"],
        },
        "phase08_install_evidence_digest",
    )


def validate_upgrade(
    raw: dict[str, Any],
    *,
    package: Mapping[str, str],
    commit: str,
) -> dict[str, Any]:
    require(
        raw["result"] == "UPGRADE_AND_ROLLBACK_VERIFIED",
        "upgrade receipt failed",
    )
    require_package_identity(package, raw["current"]["package"], "upgrade")
    require(
        raw["previous"]["version"] == "0.1.0"
        and raw["previous"]["commit"] == EXPECTED_PREVIOUS_COMMIT
        and raw["previous"]["schema_versions"] == [1],
        "upgrade baseline changed",
    )
    require(
        raw["current"]["version"] == __version__
        and raw["current"]["schema_versions"] == [1, 2, 3],
        "upgrade target or migrations changed",
    )
    campaign = raw["campaign"]
    digests = {
        campaign["manifest_digest_before"],
        campaign["manifest_digest_after"],
        campaign["manifest_digest_rollback"],
    }
    require(len(digests) == 1, "upgrade or rollback changed the campaign manifest")
    require(
        campaign["preserved_on_upgrade"] is True
        and campaign["restored_on_rollback"] is True,
        "upgrade or rollback preservation failed",
    )
    return with_digest(
        {
            "schema_version": "1.0.0",
            "phase": "08",
            "evidence_mode": "fixture",
            "captured_at": raw["captured_at"],
            "result": raw["result"],
            "command": "make test-upgrade",
            "repository_commit": commit,
            "previous": raw["previous"],
            "current": {
                "version": raw["current"]["version"],
                "package": dict(package),
                "schema_versions": raw["current"]["schema_versions"],
            },
            "campaign": campaign,
            "backup": raw["backup"],
            "raw_receipt": {
                "file_digest": digest_file(RAW_UPGRADE),
                "artifact_digest": raw["upgrade_evidence_digest"],
            },
            "limitations": raw["limitations"],
        },
        "phase08_upgrade_evidence_digest",
    )


def validate_reference(
    raw: dict[str, Any],
    *,
    package: Mapping[str, str],
    commit: str,
) -> dict[str, Any]:
    require(
        raw["result"] == "REFERENCE_CAMPAIGN_VERIFIED",
        "reference campaign receipt failed",
    )
    require_package_identity(package, raw["package"], "reference campaign")
    require(raw["installed_version"] == __version__, "reference version drifted")

    fixture = raw["fixture_reference"]
    require(
        fixture["mode"] == "fixture"
        and fixture["decision"] == "BLOCKED"
        and fixture["refusal_code"] == "EVIDENCE_MODE_NOT_LIVE"
        and fixture["byte_reproduced"] is True,
        "built-in reference weakened its evidence boundary",
    )

    deployment = raw["deployment_preflight"]
    require(
        deployment["profile"] == "core-git-dbt"
        and deployment["ready"] is True
        and deployment["single_writer"] is True,
        "installed deployment preflight did not pass its supported profile",
    )
    require(
        set(deployment["configuration_references"])
        == {
            "DATAHUB_GMS_URL",
            "DATAHUB_MCP_URL",
            "GIT_DBT_DBT_EXECUTABLE",
            "GIT_DBT_PRINCIPAL",
            "GIT_DBT_REPOSITORY_ROOT",
        },
        "reference preflight configuration boundary changed",
    )
    require(
        set(deployment["available_tools"]) == {"git", "bwrap", "docker", "dbt"},
        "reference preflight missed a required tool",
    )
    require(
        deployment["telemetry"]["enabled"] is True
        and deployment["telemetry"]["remote_export"] is False,
        "local metrics crossed the declared no-export boundary",
    )

    capability = raw["core_capability"]
    require(capability["edition"] == "core", "reference did not use DataHub Core")
    require(
        capability["server_versions"]["versions.acryldata/datahub.version"] == "v1.6.0",
        "DataHub Core version changed",
    )
    services = raw["services"]
    require(
        services["datahub_core"]["configured_image"] == "acryldata/datahub-gms:v1.6.0"
        and services["datahub_core"]["container_health"] == "healthy"
        and services["datahub_core"]["published_port"].startswith("127.0.0.1:"),
        "DataHub service identity or loopback boundary changed",
    )
    require(
        services["mcp_server"]["package_version"] == "0.6.0"
        and services["mcp_server"]["source_commit"] == EXPECTED_MCP_COMMIT
        and services["mcp_server"]["source_clean"] is True
        and services["mcp_server"]["listener"].startswith("127.0.0.1:"),
        "MCP service identity or loopback boundary changed",
    )

    live = raw["live_reference"]
    require(
        live["evidence_mode"] == "live" and live["repository_commit"] == commit,
        "live reference is not bound to the current commit",
    )
    require(
        live["installed_cli_operation_count"] >= MINIMUM_INSTALLED_REFERENCE_OPERATIONS
        and live["source_cli_operation_count"] == 0,
        "live reference bypassed or underused the installed product",
    )
    require(
        live["isolated_consumer_count"] == 1
        and live["validation_result"] == "PASSED"
        and live["ready_decision"] == "READY_TO_RETIRE"
        and live["producer_sentinel_count"] == 1,
        "isolated live reference did not close exactly once",
    )
    require(
        live["late_consumer_count"] >= 2 and live["late_decision"] == "UNSAFE",
        "late consumer did not reopen the live campaign",
    )
    require(
        live["rich_consumer_count"] >= 31
        and live["rich_decision"] == "UNSAFE"
        and live["rich_gate_refusal"] == "GATE_DECISION_NOT_READY",
        "rich graph did not retain its producer refusal",
    )
    require(
        live["ready_publication_settle"]["attempts"] >= 1
        and live["late_publication_settle"]["attempts"] >= 1,
        "publication read-back was not verified",
    )
    require(
        live["gate_attempt_status_counts"]["EXECUTED"] == 1
        and live["gate_attempt_status_counts"]["REFUSED"] >= 1,
        "gate execution/refusal evidence changed",
    )
    return with_digest(
        {
            "schema_version": "1.0.0",
            "phase": "08",
            "evidence_mode": "mixed fixture and live",
            "captured_at": raw["captured_at"],
            "result": raw["result"],
            "command": "make test-reference-campaign",
            "repository_commit": commit,
            "package": dict(package),
            "installed_version": raw["installed_version"],
            "fixture_reference": fixture,
            "deployment_preflight": deployment,
            "core_capability": capability,
            "services": services,
            "live_reference": live,
            "raw_receipt": {
                "file_digest": digest_file(RAW_REFERENCE),
                "artifact_digest": raw["reference_evidence_digest"],
            },
            "limitations": raw["limitations"],
        },
        "phase08_reference_evidence_digest",
    )


def safe_version(arguments: list[str], label: str) -> str:
    output = checked(arguments).stdout.strip()
    require(output and "\n" not in output, f"{label} version was not one line")
    require(len(output) <= 160, f"{label} version output was unexpectedly long")
    require(
        not any(fragment in output for fragment in FORBIDDEN_PUBLIC_FRAGMENTS),
        f"{label} version exposed a private path",
    )
    return output


def dbt_versions() -> dict[str, str]:
    python = ROOT / ".retirement-conductor/tools/dbt-duckdb-1.10.1/bin/python"
    require(python.is_file(), "the pinned dbt runtime is unavailable")
    code = (
        "import importlib.metadata as m, json; "
        "print(json.dumps({"
        "'dbt_core': m.version('dbt-core'), "
        "'dbt_duckdb': m.version('dbt-duckdb'), "
        "'duckdb': m.version('duckdb')"
        "}, sort_keys=True))"
    )
    value = json.loads(checked([str(python), "-I", "-c", code]).stdout)
    require(isinstance(value, dict), "dbt compatibility versions are invalid")
    return {str(key): str(item) for key, item in value.items()}


def compatibility_evidence(
    *,
    install: Mapping[str, Any],
    reference: Mapping[str, Any],
    package: Mapping[str, str],
    commit: str,
) -> dict[str, Any]:
    return with_digest(
        {
            "schema_version": "1.0.0",
            "phase": "08",
            "evidence_mode": "mixed live, fixture, and analysis",
            "captured_at": utc_now(),
            "result": "EXECUTED_BOUNDARIES_RECORDED",
            "repository_commit": commit,
            "package": dict(package),
            "host": install["host"],
            "python_versions": [
                runtime["python_version"] for runtime in install["runtimes"]
            ],
            "tools": {
                "uv": safe_version(["uv", "--version"], "uv"),
                "git": safe_version(["git", "--version"], "Git"),
                "bubblewrap": safe_version(["bwrap", "--version"], "bubblewrap"),
                "docker_client": safe_version(
                    ["docker", "--version"],
                    "Docker",
                ),
                **dbt_versions(),
            },
            "integrations": {
                "datahub_core": {
                    "configured_image": reference["services"]["datahub_core"][
                        "configured_image"
                    ],
                    "image_id": reference["services"]["datahub_core"]["image_id"],
                    "server_versions": reference["core_capability"]["server_versions"],
                    "evidence_mode": "live",
                },
                "datahub_mcp": {
                    "package_version": reference["services"]["mcp_server"][
                        "package_version"
                    ],
                    "source_commit": reference["services"]["mcp_server"][
                        "source_commit"
                    ],
                    "source_clean": reference["services"]["mcp_server"]["source_clean"],
                    "evidence_mode": "live",
                },
                "git_dbt_duckdb": {
                    "native_validation": reference["live_reference"]["validator"],
                    "reported_validator_version": reference["live_reference"][
                        "validator_version"
                    ],
                    "result": reference["live_reference"]["validation_result"],
                    "evidence_mode": "live disposable",
                },
            },
            "not_executed": [
                "macOS",
                "Windows",
                "musl Linux",
                "shared filesystem or multi-writer deployment",
                "Retirement Conductor product container",
                "DataHub Cloud",
                "live Looker saved-content workflow",
            ],
            "limitations": [
                "A package install result does not prove an unexecuted integration.",
                "The live integrations are disposable loopback services.",
                "A newer tool or source version requires new direct evidence.",
            ],
        },
        "compatibility_evidence_digest",
    )


def operator_boundary(*, commit: str, package: Mapping[str, str]) -> dict[str, Any]:
    return with_digest(
        {
            "schema_version": "1.0.0",
            "phase": "08",
            "evidence_mode": "analysis",
            "captured_at": utc_now(),
            "result": "NOT_RUN",
            "acceptance_status": "NOT_SATISFIED",
            "repository_commit": commit,
            "package": dict(package),
            "requirement": "RC-018",
            "evidence_packet": "EP-008",
            "reason": (
                "No independent prospective operator observation was provided "
                "during this autonomous repository run."
            ),
            "completed_preparation": [
                "clean installation and deployment runbook",
                "executed compatibility matrix",
                "independent evaluation protocol",
                "public-safe observation template",
                "maintenance and release policy",
            ],
            "smallest_remaining_boundary": {
                "human": "one real prospective operator independent of the author",
                "workflow": (
                    "one recent field replacement or retirement evaluated on "
                    "explicitly safe disposable resources"
                ),
                "observations": [
                    "frequency",
                    "baseline and observed time, steps, and handoffs",
                    "author interventions",
                    "friction and operational burden",
                    "decision-changing value",
                    "willingness to adopt or reject",
                    "buyer or approver role",
                ],
                "instructions": "docs/EVALUATION.md",
                "template": "docs/templates/OPERATOR_OBSERVATION.md",
                "secrets_requested": False,
            },
            "non_claims": [
                "Author-run reference evidence is not independent operation.",
                "A fixture or scripted run is not customer-value evidence.",
                "The Phase 08 acceptance contract remains access-dependent.",
            ],
        },
        "operator_boundary_digest",
    )


def assert_public_safe(value: object, label: str) -> None:
    content = json.dumps(value, ensure_ascii=False, sort_keys=True)
    for fragment in FORBIDDEN_PUBLIC_FRAGMENTS:
        require(fragment not in content, f"{label} contains forbidden material")


def artifact_entry(path: Path, digest_field: str) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"{path.name} is not an object")
    verify_digest(value, digest_field)
    return {
        "file": path.relative_to(ROOT).as_posix(),
        "file_digest": digest_file(path),
        "artifact_digest": value[digest_field],
    }


def write_artifact(path: Path, value: dict[str, Any]) -> None:
    assert_public_safe(value, path.name)
    write_json(path, value)


def write_summary(
    *,
    commit: str,
    package: Mapping[str, str],
    check_receipt: Mapping[str, Any],
    diff_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    value = with_digest(
        {
            "schema_version": "1.0.0",
            "phase": "08",
            "evidence_mode": "mixed live, fixture, and analysis",
            "captured_at": utc_now(),
            "result": "CREDENTIAL_INDEPENDENT_ACCEPTANCE_PASSED",
            "phase_status": "access-dependent",
            "repository_commit": commit,
            "package": dict(package),
            "commands": [
                dict(check_receipt),
                {
                    "command": "make package",
                    "result": "PASSED",
                    "artifact": artifact_entry(
                        PACKAGE_PATH,
                        "phase08_package_evidence_digest",
                    ),
                },
                {
                    "command": "make test-install",
                    "result": "PASSED",
                    "artifact": artifact_entry(
                        INSTALL_PATH,
                        "phase08_install_evidence_digest",
                    ),
                },
                {
                    "command": "make test-upgrade",
                    "result": "PASSED",
                    "artifact": artifact_entry(
                        UPGRADE_PATH,
                        "phase08_upgrade_evidence_digest",
                    ),
                },
                {
                    "command": "make test-reference-campaign",
                    "result": "PASSED",
                    "artifact": artifact_entry(
                        REFERENCE_PATH,
                        "phase08_reference_evidence_digest",
                    ),
                },
                dict(diff_receipt),
            ],
            "artifacts": {
                "package": artifact_entry(
                    PACKAGE_PATH,
                    "phase08_package_evidence_digest",
                ),
                "install": artifact_entry(
                    INSTALL_PATH,
                    "phase08_install_evidence_digest",
                ),
                "upgrade": artifact_entry(
                    UPGRADE_PATH,
                    "phase08_upgrade_evidence_digest",
                ),
                "reference": artifact_entry(
                    REFERENCE_PATH,
                    "phase08_reference_evidence_digest",
                ),
                "compatibility": artifact_entry(
                    COMPATIBILITY_PATH,
                    "compatibility_evidence_digest",
                ),
                "operator_boundary": artifact_entry(
                    OPERATOR_PATH,
                    "operator_boundary_digest",
                ),
            },
            "acceptance": {
                "clean_install": True,
                "actionable_configuration_refusal": True,
                "deterministic_fixture_remains_blocked": True,
                "installed_live_core_reference": True,
                "datahub_cloud_optional_and_not_claimed": True,
                "upgrade_preserves_campaign": True,
                "rollback_restores_prior_pair": True,
                "confirmed_state_removal": True,
                "package_uninstall": True,
                "single_writer_preflight": True,
                "copied_state_refusal": True,
                "local_metrics_opt_in_and_no_remote_export": True,
                "release_repository_documentation_agree": True,
                "independent_operator": False,
                "customer_value_observation": False,
            },
            "requirements": {
                "RC-017": "CREDENTIAL_INDEPENDENT_EVIDENCE_PRESENT",
                "RC-018": "NOT_SATISFIED",
            },
            "remaining_boundaries": [
                {
                    "phase": "06",
                    "evidence_packet": "EP-006",
                    "status": "access-dependent",
                    "boundary": "live disposable Looker saved-content workflow",
                    "provisioning_allowed": False,
                },
                {
                    "phase": "07",
                    "evidence_packet": "EP-007",
                    "status": "access-dependent",
                    "boundary": "live Looker-specific security and fault behavior",
                    "provisioning_allowed": False,
                },
                {
                    "phase": "08",
                    "evidence_packet": "EP-008",
                    "status": "not-run",
                    "boundary": "independent operator and real workflow value evidence",
                    "secrets_required": False,
                },
            ],
            "limitations": [
                "Credential-independent Phase 08 work cannot satisfy the "
                "independent operator acceptance row.",
                "The live Core reference uses disposable loopback services.",
                "Live Looker remains outside this evidence packet.",
                "No release signing identity or automated publication exists.",
            ],
        },
        "phase08_preacceptance_digest",
    )
    write_artifact(SUMMARY_PATH, value)
    return value


def run() -> int:
    check_dirty_state()
    commit = repository_commit()

    raw_package = load_receipt(RAW_PACKAGE, "package_evidence_digest")
    raw_install = load_receipt(RAW_INSTALL, "install_evidence_digest")
    raw_upgrade = load_receipt(RAW_UPGRADE, "upgrade_evidence_digest")
    raw_reference = load_receipt(RAW_REFERENCE, "reference_evidence_digest")

    package, package_public = validate_package(raw_package, commit=commit)
    install_public = validate_install(
        raw_install,
        package=package,
        commit=commit,
    )
    upgrade_public = validate_upgrade(
        raw_upgrade,
        package=package,
        commit=commit,
    )
    reference_public = validate_reference(
        raw_reference,
        package=package,
        commit=commit,
    )
    compatibility_public = compatibility_evidence(
        install=install_public,
        reference=reference_public,
        package=package,
        commit=commit,
    )
    operator_public = operator_boundary(commit=commit, package=package)
    check_receipt = command_receipt(["make", "check"], "make check")
    diff_receipt = command_receipt(["git", "diff", "--check"], "git diff --check")

    PUBLIC.mkdir(parents=True, exist_ok=True)
    write_artifact(PACKAGE_PATH, package_public)
    write_artifact(INSTALL_PATH, install_public)
    write_artifact(UPGRADE_PATH, upgrade_public)
    write_artifact(REFERENCE_PATH, reference_public)
    write_artifact(COMPATIBILITY_PATH, compatibility_public)
    write_artifact(OPERATOR_PATH, operator_public)
    summary = write_summary(
        commit=commit,
        package=package,
        check_receipt=check_receipt,
        diff_receipt=diff_receipt,
    )
    assert_public_safe(summary, SUMMARY_PATH.name)

    checked(["uv", "run", "python", "scripts/check_public_artifacts.py"])
    checked(["uv", "run", "python", "scripts/check_secrets.py"])
    print(
        "Phase 08 credential-independent evidence generated: "
        f"{SUMMARY_PATH.relative_to(ROOT)} ({commit[:12]}). "
        "Independent operator acceptance remains NOT_RUN."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())

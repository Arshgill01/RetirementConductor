#!/usr/bin/env python3
"""Run the pinned dependency, provenance, license, and secret review."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
import tomllib
from importlib.metadata import PackageNotFoundError, metadata, version
from pathlib import Path
from typing import Any, cast

from retirement_conductor.canonical import (
    digest_bytes,
    digest_file,
    with_digest,
    write_json,
)
from retirement_conductor.datahub import utc_now

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / ".retirement-conductor/phase07/security-scan.json"
PIP_AUDIT_VERSION = "2.9.0"
REGISTRY = "https://pypi.org/simple"
ACCEPTED_LICENSES = {
    "Apache-2.0",
    "Apache-2.0 OR BSD-2-Clause",
    "BSD-2-Clause",
    "MIT",
    "MPL-2.0",
    "PSF-2.0",
}
CLASSIFIER_LICENSES = {
    "License :: OSI Approved :: MIT License": "MIT",
    "License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)": "MPL-2.0",
}


def command(
    arguments: list[str], *, timeout: int = 300
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        arguments,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )


def require_success(result: subprocess.CompletedProcess[str], label: str) -> None:
    if result.returncode != 0:
        raise RuntimeError(
            f"{label} failed with exit code {result.returncode}; "
            "inspect the command locally"
        )


def export_requirements(path: Path, *, all_groups: bool) -> None:
    arguments = [
        "uv",
        "export",
        "--frozen",
        "--no-emit-project",
        "--format",
        "requirements-txt",
        "--output-file",
        str(path),
    ]
    if all_groups:
        arguments.insert(2, "--all-groups")
    else:
        arguments.insert(2, "--no-dev")
    require_success(command(arguments), "frozen dependency export")


def audit(path: Path) -> tuple[dict[str, Any], int]:
    result = command(
        [
            "uvx",
            "--from",
            f"pip-audit=={PIP_AUDIT_VERSION}",
            "pip-audit",
            "--requirement",
            str(path),
            "--progress-spinner",
            "off",
            "--format",
            "json",
        ],
        timeout=600,
    )
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("pip-audit did not return its documented JSON") from exc
    if not isinstance(value, dict) or not isinstance(value.get("dependencies"), list):
        raise RuntimeError("pip-audit returned an unexpected result shape")
    return value, result.returncode


def vulnerability_findings(audit_result: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for dependency in audit_result["dependencies"]:
        if not isinstance(dependency, dict):
            raise RuntimeError("pip-audit dependency entry is not an object")
        for vulnerability in dependency.get("vulns", []):
            if not isinstance(vulnerability, dict):
                raise RuntimeError("pip-audit vulnerability entry is not an object")
            findings.append(
                {
                    "package": str(dependency.get("name")),
                    "version": str(dependency.get("version")),
                    "id": str(vulnerability.get("id")),
                    "aliases": sorted(
                        str(item) for item in vulnerability.get("aliases", [])
                    ),
                    "fix_versions": sorted(
                        str(item) for item in vulnerability.get("fix_versions", [])
                    ),
                }
            )
    return sorted(findings, key=lambda item: (item["package"], item["id"]))


def locked_provenance() -> dict[str, Any]:
    value = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    packages = value.get("package")
    if not isinstance(packages, list):
        raise RuntimeError("uv.lock has no package inventory")
    third_party = [
        package
        for package in packages
        if isinstance(package, dict) and package.get("name") != "retirement-conductor"
    ]
    failures: list[str] = []
    for package in third_party:
        name = str(package.get("name"))
        if package.get("source") != {"registry": REGISTRY}:
            failures.append(f"{name}: unexpected source")
        source = package.get("sdist")
        if not isinstance(source, dict) or not str(source.get("hash", "")).startswith(
            "sha256:"
        ):
            failures.append(f"{name}: missing source hash")
        wheels = package.get("wheels")
        if not isinstance(wheels, list) or not wheels:
            failures.append(f"{name}: missing wheel inventory")
        elif any(
            not isinstance(wheel, dict)
            or not str(wheel.get("hash", "")).startswith("sha256:")
            for wheel in wheels
        ):
            failures.append(f"{name}: missing wheel hash")
    return {
        "result": "PASSED" if not failures else "FAILED",
        "lock_version": value.get("version"),
        "lock_revision": value.get("revision"),
        "lock_digest": digest_file(ROOT / "uv.lock"),
        "third_party_package_records": len(third_party),
        "registry": REGISTRY,
        "all_sources_and_wheels_sha256_bound": not failures,
        "findings": failures,
    }


def license_identifier(package_name: str) -> str:
    package_metadata = cast(Any, metadata(package_name))
    declared = package_metadata.get("License-Expression") or package_metadata.get(
        "License"
    )
    if declared:
        return str(declared).strip()
    for classifier in package_metadata.get_all("Classifier") or []:
        if classifier in CLASSIFIER_LICENSES:
            return CLASSIFIER_LICENSES[classifier]
    return "UNKNOWN"


def license_review(
    all_dependencies: list[dict[str, Any]],
    runtime_names: set[str],
) -> dict[str, Any]:
    packages: list[dict[str, Any]] = []
    failures: list[str] = []
    for dependency in sorted(
        all_dependencies,
        key=lambda item: str(item.get("name", "")).casefold(),
    ):
        name = str(dependency.get("name"))
        normalized_name = re.sub(r"[-_.]+", "-", name).casefold()
        try:
            installed_version = version(name)
            license_id = license_identifier(name)
        except PackageNotFoundError:
            failures.append(f"{name}: installed metadata unavailable")
            continue
        locked_version = str(dependency.get("version"))
        if installed_version != locked_version:
            failures.append(f"{name}: installed version differs from audit")
        if license_id not in ACCEPTED_LICENSES:
            failures.append(f"{name}: unreviewed license {license_id}")
        packages.append(
            {
                "name": name,
                "version": locked_version,
                "license": license_id,
                "scope": (
                    "runtime" if normalized_name in runtime_names else "development"
                ),
                "disposition": (
                    "compatible"
                    if license_id in ACCEPTED_LICENSES
                    else "review_required"
                ),
            }
        )
    return {
        "result": "PASSED" if not failures else "FAILED",
        "accepted_expressions": sorted(ACCEPTED_LICENSES),
        "packages": packages,
        "findings": failures,
    }


def local_scan(script: str, expected_pattern: str) -> dict[str, Any]:
    result = command(["uv", "run", "python", script])
    output = result.stdout + result.stderr
    match = re.search(expected_pattern, output)
    return {
        "result": (
            "PASSED" if result.returncode == 0 and match is not None else "FAILED"
        ),
        "checked_count": int(match.group(1)) if match is not None else None,
        "output_digest": digest_bytes(output.encode()),
    }


def run(output: Path) -> int:
    lock_check = command(["uv", "lock", "--check"])
    require_success(lock_check, "uv lock check")
    with tempfile.TemporaryDirectory(
        prefix="retirement-conductor-security-scan-"
    ) as temporary:
        root = Path(temporary)
        runtime_requirements = root / "runtime.txt"
        all_requirements = root / "all-groups.txt"
        export_requirements(runtime_requirements, all_groups=False)
        export_requirements(all_requirements, all_groups=True)
        runtime_audit, runtime_status = audit(runtime_requirements)
        all_audit, all_status = audit(all_requirements)

    runtime_findings = vulnerability_findings(runtime_audit)
    all_findings = vulnerability_findings(all_audit)
    runtime_names = {
        re.sub(r"[-_.]+", "-", str(item.get("name", ""))).casefold()
        for item in runtime_audit["dependencies"]
        if isinstance(item, dict)
    }
    licenses = license_review(all_audit["dependencies"], runtime_names)
    provenance = locked_provenance()
    secrets = local_scan(
        "scripts/check_secrets.py",
        r"Secret scan passed: (\d+) text files checked\.",
    )
    public_artifacts = local_scan(
        "scripts/check_public_artifacts.py",
        r"Public artifact review passed: (\d+) files checked\.",
    )
    passed = all(
        (
            runtime_status == 0,
            all_status == 0,
            not runtime_findings,
            not all_findings,
            provenance["result"] == "PASSED",
            licenses["result"] == "PASSED",
            secrets["result"] == "PASSED",
            public_artifacts["result"] == "PASSED",
        )
    )
    result = with_digest(
        {
            "schema_version": "1.0.0",
            "evidence_mode": "analysis",
            "captured_at": utc_now(),
            "result": "PASSED" if passed else "FAILED",
            "tools": {
                "pip_audit": PIP_AUDIT_VERSION,
                "uv": command(["uv", "--version"]).stdout.strip(),
            },
            "lock_provenance": provenance,
            "vulnerability_audit": {
                "runtime": {
                    "result": "PASSED" if not runtime_findings else "FAILED",
                    "package_count": len(runtime_audit["dependencies"]),
                    "findings": runtime_findings,
                },
                "all_groups": {
                    "result": "PASSED" if not all_findings else "FAILED",
                    "package_count": len(all_audit["dependencies"]),
                    "findings": all_findings,
                },
            },
            "license_review": licenses,
            "secret_scan": secrets,
            "public_artifact_review": public_artifacts,
            "limitations": [
                "The vulnerability result is bounded to the advisory database "
                "available to pip-audit at captured_at.",
                "Package license metadata is publisher-supplied and was reviewed "
                "for compatibility, not independently re-licensed.",
                "Static secret patterns cannot prove that every arbitrary value is "
                "non-sensitive.",
                "This scan does not establish binary reproducibility or signed "
                "package provenance.",
            ],
        },
        "scan_digest",
    )
    write_json(output, result)
    print(
        "Security scan "
        f"{result['result']}: {len(all_audit['dependencies'])} packages audited, "
        f"{len(all_findings)} vulnerabilities, "
        f"{secrets['checked_count']} text files checked."
    )
    evidence_path = (
        output.relative_to(ROOT) if output.is_relative_to(ROOT) else output.name
    )
    print(f"Evidence: {evidence_path}")
    return 0 if passed else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()
    return run(arguments.output.resolve())


if __name__ == "__main__":
    raise SystemExit(main())

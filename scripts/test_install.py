#!/usr/bin/env python3
"""Exercise the release from clean isolated Python environments."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from retirement_conductor import __version__
from retirement_conductor.canonical import (
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
    current_wheel,
    installed_command,
    package_identity,
    runtime_environment,
)

PYTHON_VERSIONS = ("3.11", "3.12", "3.13", "3.14")
REFERENCE_DIGEST = "manifest_digest"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def payload_object(value: dict[str, Any] | None, label: str) -> dict[str, Any]:
    if value is None:
        raise RuntimeError(f"{label} did not return JSON")
    return value


def exercise_runtime(
    root: Path,
    *,
    python_version: str,
) -> dict[str, Any]:
    environment_root = create_clean_environment(
        root / "venv",
        python_version=python_version,
    )
    home = root / "home"
    environment = runtime_environment(home)
    work = root / "work"
    work.mkdir()

    version = checked(
        [
            str(environment_root / "bin" / "retirement-conductor"),
            "--version",
        ],
        cwd=work,
        environment=environment,
    ).stdout.strip()
    require(version == f"retirement-conductor {__version__}", "version mismatch")

    origin = checked(
        [
            str(environment_root / "bin" / "python"),
            "-I",
            "-c",
            (
                "import json, retirement_conductor as r; "
                "print(json.dumps({'file': r.__file__, 'version': r.__version__}))"
            ),
        ],
        cwd=work,
        environment=environment,
    )
    origin_value = json.loads(origin.stdout)
    require(
        str(environment_root.resolve()) in str(origin_value["file"]),
        "clean environment imported the source checkout",
    )
    require(str(ROOT.resolve()) not in str(origin_value["file"]), "source leaked")

    state = home / ".retirement-conductor"
    _, preflight_value = installed_command(
        environment_root,
        [
            "deployment",
            "preflight",
            "--profile",
            "local",
            "--store",
            str(state / "campaigns.sqlite"),
            "--writer-id",
            "clean-install",
            "--artifact-dir",
            str(state / "artifacts"),
        ],
        cwd=work,
        environment=environment,
    )
    preflight = payload_object(preflight_value, "deployment preflight")
    verify_digest(preflight, "preflight_digest")
    require(preflight["ready"] is True, "clean local preflight did not pass")

    reference_summaries = []
    reference_directories = []
    for name in ("reference-one", "reference-two"):
        output = work / name
        _, reference_value = installed_command(
            environment_root,
            ["reference", "run", "--output-dir", str(output)],
            cwd=work,
            environment=environment,
        )
        reference = payload_object(reference_value, "reference run")
        require(reference["mode"] == "fixture", "reference mode was not fixture")
        require(reference["decision"] == "BLOCKED", "reference falsely became ready")
        require(
            reference["refusal_code"] == "EVIDENCE_MODE_NOT_LIVE",
            "reference used the wrong refusal",
        )
        reference_summaries.append(reference)
        reference_directories.append(output)
    require(
        reference_summaries[0] == reference_summaries[1],
        "installed reference summary was not deterministic",
    )
    for filename in reference_summaries[0]["artifacts"]:
        require(
            (reference_directories[0] / filename).read_bytes()
            == (reference_directories[1] / filename).read_bytes(),
            f"installed reference artifact drifted: {filename}",
        )

    manifest = json.loads(
        (reference_directories[0] / "manifest.json").read_text(encoding="utf-8")
    )
    verify_digest(manifest, REFERENCE_DIGEST)
    python_version = checked(
        [
            str(environment_root / "bin" / "python"),
            "-c",
            "import platform; print(platform.python_version())",
        ],
        cwd=work,
        environment=environment,
    ).stdout.strip()
    return {
        "python_version": python_version,
        "package_version": origin_value["version"],
        "import_isolated": True,
        "preflight_digest": preflight["preflight_digest"],
        "reference_manifest_digest": manifest["manifest_digest"],
        "reference_summary_digest": digest_file(
            reference_directories[0] / "summary.json"
        ),
        "reference_byte_reproduced": True,
    }


def exercise_uninstall(root: Path) -> dict[str, Any]:
    environment_root = create_clean_environment(
        root / "venv",
        python_version="3.11",
    )
    home = root / "home"
    environment = runtime_environment(home)
    work = root / "work"
    work.mkdir()
    state = home / ".retirement-conductor"
    store = state / "campaigns.sqlite"
    artifacts = state / "artifacts"
    artifacts.mkdir(parents=True)
    (artifacts / "operator-report.txt").write_text("fixture\n", encoding="utf-8")

    installed_command(
        environment_root,
        [
            "campaign",
            "create",
            str(ROOT / "fixtures/specs/valid.yaml"),
            "--store",
            str(store),
            "--writer-id",
            "uninstall-test",
            "--occurred-at",
            "2026-01-01T10:00:00Z",
        ],
        cwd=work,
        environment=environment,
    )
    plan_path = state / "removal-plan.json"
    _, planned_value = installed_command(
        environment_root,
        [
            "deployment",
            "removal-plan",
            "--output",
            str(plan_path),
            "--generated-at",
            "2026-01-01T11:00:00Z",
            "--store",
            str(store),
            "--writer-id",
            "uninstall-test",
            "--artifact-dir",
            str(artifacts),
        ],
        cwd=work,
        environment=environment,
    )
    planned = payload_object(planned_value, "removal plan")

    _, refused_value = installed_command(
        environment_root,
        [
            "deployment",
            "remove-state",
            "--plan",
            str(plan_path),
            "--store",
            str(store),
            "--writer-id",
            "uninstall-test",
            "--artifact-dir",
            str(artifacts),
        ],
        cwd=work,
        environment=environment,
        expected_exit=2,
    )
    refused = payload_object(refused_value, "unconfirmed removal")
    require(
        refused["refusal_code"] == "AUTH_APPROVAL_MISSING",
        "unconfirmed removal did not refuse",
    )
    require(store.exists() and artifacts.exists(), "refusal removed product state")

    _, receipt_value = installed_command(
        environment_root,
        [
            "deployment",
            "remove-state",
            "--plan",
            str(plan_path),
            "--confirm-plan-digest",
            str(planned["removal_plan_digest"]),
            "--store",
            str(store),
            "--writer-id",
            "uninstall-test",
            "--artifact-dir",
            str(artifacts),
        ],
        cwd=work,
        environment=environment,
    )
    receipt = payload_object(receipt_value, "confirmed removal")
    verify_digest(receipt, "removal_receipt_digest")
    require(not store.exists(), "confirmed removal retained the store")
    require(not artifacts.exists(), "confirmed removal retained artifacts")
    require(plan_path.exists(), "confirmed removal deleted its ignored plan")

    checked(
        [
            "uv",
            "pip",
            "uninstall",
            "--python",
            str(environment_root / "bin" / "python"),
            "retirement-conductor",
        ]
    )
    require(
        not (environment_root / "bin" / "retirement-conductor").exists(),
        "package manager retained the console entry point",
    )
    missing_import = subprocess.run(
        [
            str(environment_root / "bin" / "python"),
            "-I",
            "-c",
            "import retirement_conductor",
        ],
        cwd=work,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    require(missing_import.returncode != 0, "package import survived uninstall")
    return {
        "unconfirmed_refusal": refused["refusal_code"],
        "removal_plan_digest": planned["removal_plan_digest"],
        "removal_receipt_digest": receipt["removal_receipt_digest"],
        "state_removed": True,
        "package_removed": True,
        "retained_plan": True,
    }


def run() -> dict[str, Any]:
    require(current_wheel().is_file(), "run make package before test-install")
    observations = []
    with tempfile.TemporaryDirectory(
        prefix="retirement-conductor-phase08-install-"
    ) as temporary:
        base = Path(temporary)
        for version in PYTHON_VERSIONS:
            observations.append(
                exercise_runtime(base / f"python-{version}", python_version=version)
            )
        uninstall = exercise_uninstall(base / "uninstall")

    reference_digests = {
        str(item["reference_manifest_digest"]) for item in observations
    }
    require(
        len(reference_digests) == 1,
        "reference digest changed across supported Python runtimes",
    )
    evidence = with_digest(
        {
            "schema_version": "1.0.0",
            "captured_at": utc_now(),
            "result": "CLEAN_INSTALL_VERIFIED",
            "package": package_identity(),
            "runtimes": observations,
            "uninstall": uninstall,
            "limitations": [
                "Virtual environments isolate Python packages on one Linux host.",
                "The clean-install test does not exercise external integrations.",
            ],
        },
        "install_evidence_digest",
    )
    PHASE08_RUNTIME.mkdir(parents=True, exist_ok=True)
    write_json(PHASE08_RUNTIME / "install-evidence.json", evidence)
    print(
        f"Clean install passed on {len(observations)} Python runtimes; "
        "confirmed state and package removal passed."
    )
    return evidence


def main() -> int:
    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

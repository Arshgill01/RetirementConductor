#!/usr/bin/env python3
"""Build and inspect reproducible Phase 08 release artifacts."""

from __future__ import annotations

import email
import stat
import tarfile
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from retirement_conductor import __version__
from retirement_conductor.canonical import digest_file, with_digest, write_json
from retirement_conductor.datahub import utc_now
from scripts.phase08_support import (
    PHASE08_RUNTIME,
    RELEASE_DIST,
    RUNTIME_REQUIREMENTS,
    checked,
    current_sdist,
    current_wheel,
)

REQUIRED_WHEEL_MEMBERS = {
    "retirement_conductor/reference_data/spec.yaml",
    "retirement_conductor/fixture_data/repository/models/order_summary.sql",
    "retirement_conductor/fixture_data/scenarios/valid.json",
    "retirement_conductor/migrations/001_initial.sql",
    "retirement_conductor/migrations/002_initial.sql",
    "retirement_conductor/migrations/003_initial.sql",
    "retirement_conductor/schemas/retirement-spec-v1alpha1.schema.json",
    "retirement_conductor/schemas/campaign-manifest-v1.schema.json",
}

REQUIRED_SDIST_MEMBERS = {
    ".env.example",
    "CONTRIBUTING.md",
    "LICENSE",
    "README.md",
    "SECURITY.md",
    "pyproject.toml",
    "docs/COMPATIBILITY.md",
    "docs/EVALUATION.md",
    "docs/MAINTENANCE.md",
    "docs/runbooks/DEPLOYMENT.md",
    "docs/runbooks/RECOVERY.md",
    "docs/templates/OPERATOR_OBSERVATION.md",
    "fixtures/repository/models/order_summary.sql",
    "fixtures/scenarios/valid.json",
    "fixtures/specs/valid.yaml",
    "schemas/campaign-manifest-v1.schema.json",
    "src/retirement_conductor/__init__.py",
}

FORBIDDEN_SDIST_MEMBERS = {
    "AGENTS.md",
    "GOAL.md",
    "PLAN.md",
    "STATUS.md",
    "docs/EVIDENCE_LEDGER.md",
    "uv.lock",
}

FORBIDDEN_SDIST_PREFIXES = (
    ".git/",
    ".retirement-conductor/",
    "artifacts/",
    "scripts/",
    "tests/",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def safe_member(name: str) -> None:
    path = PurePosixPath(name)
    require(not path.is_absolute(), f"archive member is absolute: {name}")
    require(".." not in path.parts, f"archive member traverses: {name}")


def build(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    checked(["uv", "build", "--out-dir", str(output)], timeout=900)


def inspect_wheel(path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        names = {entry.filename for entry in entries}
        for entry in entries:
            safe_member(entry.filename)
            mode = (entry.external_attr >> 16) & 0xFFFF
            require(not stat.S_ISLNK(mode), "wheel contains a symbolic link")
        require(
            REQUIRED_WHEEL_MEMBERS.issubset(names),
            "wheel is missing required runtime data",
        )
        metadata_name = next(
            name for name in names if name.endswith(".dist-info/METADATA")
        )
        metadata = email.message_from_bytes(archive.read(metadata_name))
        entry_points_name = next(
            name for name in names if name.endswith(".dist-info/entry_points.txt")
        )
        entry_points = archive.read(entry_points_name).decode("utf-8")
    require(metadata["Name"] == "retirement-conductor", "wheel name drifted")
    require(metadata["Version"] == __version__, "wheel version drifted")
    require(metadata["Requires-Python"] == ">=3.11", "Python contract drifted")
    dependencies = sorted(metadata.get_all("Requires-Dist", []))
    require(len(dependencies) == 2, "runtime dependency count changed")
    require(
        "retirement-conductor = retirement_conductor.cli:main" in entry_points,
        "console entry point is missing",
    )
    return {
        "filename": path.name,
        "digest": digest_file(path),
        "size": path.stat().st_size,
        "member_count": len(names),
        "required_members_present": sorted(REQUIRED_WHEEL_MEMBERS),
        "runtime_dependencies": dependencies,
        "console_entry_point": "retirement-conductor",
    }


def inspect_sdist(path: Path) -> dict[str, Any]:
    with tarfile.open(path, "r:gz") as archive:
        members = archive.getmembers()
        roots = set()
        relative_names = set()
        for member in members:
            safe_member(member.name)
            member_path = PurePosixPath(member.name)
            roots.add(member_path.parts[0])
            if len(member_path.parts) > 1:
                relative_names.add(PurePosixPath(*member_path.parts[1:]).as_posix())
            require(
                not (
                    member.issym()
                    or member.islnk()
                    or member.isdev()
                    or member.isfifo()
                ),
                "source archive contains an unsafe member type",
            )
    require(len(roots) == 1, "source archive has multiple roots")
    require(
        REQUIRED_SDIST_MEMBERS.issubset(relative_names),
        "source archive is missing required build or operator content",
    )
    forbidden_members = sorted(FORBIDDEN_SDIST_MEMBERS & relative_names)
    forbidden_prefix_members = sorted(
        name for name in relative_names if name.startswith(FORBIDDEN_SDIST_PREFIXES)
    )
    require(
        not forbidden_members and not forbidden_prefix_members,
        "source archive contains operational state, evidence, or release tooling",
    )
    return {
        "filename": path.name,
        "digest": digest_file(path),
        "size": path.stat().st_size,
        "member_count": len(members),
        "single_root": True,
        "required_members_present": sorted(REQUIRED_SDIST_MEMBERS),
        "operational_state_excluded": True,
    }


def rebuild_wheel_from_sdist(source_archive: Path, destination: Path) -> Path:
    source = destination / "source"
    source.mkdir(parents=True)
    with tarfile.open(source_archive, "r:gz") as archive:
        archive.extractall(source, filter="data")
    roots = [path for path in source.iterdir() if path.is_dir()]
    require(len(roots) == 1, "extracted source archive has multiple roots")
    output = destination / "dist"
    checked(
        ["uv", "build", "--wheel", "--out-dir", str(output)],
        cwd=roots[0],
        timeout=900,
    )
    wheels = list(output.glob("*.whl"))
    require(len(wheels) == 1, "source archive did not build exactly one wheel")
    return wheels[0]


def export_runtime_lock() -> None:
    checked(
        [
            "uv",
            "export",
            "--frozen",
            "--no-dev",
            "--no-emit-project",
            "--no-header",
            "--no-annotate",
            "--output-file",
            str(RUNTIME_REQUIREMENTS),
        ]
    )
    requirements = RUNTIME_REQUIREMENTS.read_text(encoding="utf-8")
    require(" @ file:" not in requirements, "runtime lock contains a local path")
    require("-e " not in requirements, "runtime lock contains an editable source")
    require("--hash=sha256:" in requirements, "runtime lock is not hash bound")
    RUNTIME_REQUIREMENTS.chmod(0o644)


def export_sbom() -> Path:
    destination = RELEASE_DIST / "runtime-sbom.cdx.json"
    checked(
        [
            "uv",
            "export",
            "--format",
            "cyclonedx1.5",
            "--frozen",
            "--no-dev",
            "--no-emit-project",
            "--output-file",
            str(destination),
        ]
    )
    destination.chmod(0o644)
    return destination


def write_checksums(paths: list[Path]) -> Path:
    destination = RELEASE_DIST / "SHA256SUMS"
    content = "".join(
        f"{digest_file(path).removeprefix('sha256:')}  {path.name}\n"
        for path in sorted(paths, key=lambda item: item.name)
    )
    destination.write_text(content, encoding="utf-8")
    destination.chmod(0o644)
    return destination


def run() -> dict[str, Any]:
    checked(["uv", "lock", "--check"])
    RELEASE_DIST.mkdir(parents=True, exist_ok=True)
    build(RELEASE_DIST)
    export_runtime_lock()
    sbom = export_sbom()

    wheel = current_wheel()
    sdist = current_sdist()
    wheel_evidence = inspect_wheel(wheel)
    sdist_evidence = inspect_sdist(sdist)

    with tempfile.TemporaryDirectory(
        prefix="retirement-conductor-phase08-build-"
    ) as temporary:
        comparison = Path(temporary)
        build(comparison)
        comparison_wheel = next(comparison.glob("*.whl"))
        comparison_sdist = next(comparison.glob("*.tar.gz"))
        require(
            digest_file(comparison_wheel) == wheel_evidence["digest"],
            "wheel did not reproduce byte-for-byte",
        )
        require(
            digest_file(comparison_sdist) == sdist_evidence["digest"],
            "source archive did not reproduce byte-for-byte",
        )
        sdist_wheel = rebuild_wheel_from_sdist(sdist, comparison / "sdist-build")
        require(
            digest_file(sdist_wheel) == wheel_evidence["digest"],
            "source archive did not reproduce the release wheel",
        )

    checksum_file = write_checksums([wheel, sdist, RUNTIME_REQUIREMENTS, sbom])
    evidence = with_digest(
        {
            "schema_version": "1.0.0",
            "captured_at": utc_now(),
            "result": "PACKAGE_VERIFIED",
            "version": __version__,
            "wheel": wheel_evidence,
            "source_archive": sdist_evidence,
            "runtime_lock": {
                "filename": RUNTIME_REQUIREMENTS.name,
                "digest": digest_file(RUNTIME_REQUIREMENTS),
                "hash_bound": True,
            },
            "sbom": {
                "filename": sbom.name,
                "digest": digest_file(sbom),
                "format": "CycloneDX 1.5",
            },
            "checksums": {
                "filename": checksum_file.name,
                "digest": digest_file(checksum_file),
            },
            "reproducible_build": {
                "wheel_byte_identical": True,
                "source_archive_byte_identical": True,
                "source_archive_rebuilt_wheel_identical": True,
            },
            "signing": {
                "signed": False,
                "limitation": (
                    "No release signing identity or operational key model exists."
                ),
            },
        },
        "package_evidence_digest",
    )
    PHASE08_RUNTIME.mkdir(parents=True, exist_ok=True)
    write_json(PHASE08_RUNTIME / "package-evidence.json", evidence)
    print(
        f"Package {__version__} verified: wheel and source archive reproduce "
        "byte-for-byte."
    )
    return evidence


def main() -> int:
    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

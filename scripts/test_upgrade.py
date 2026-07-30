#!/usr/bin/env python3
"""Rehearse package upgrade, schema migration, and backup-based rollback."""

from __future__ import annotations

import shutil
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
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

PREVIOUS_COMMIT = "30173f1"
PREVIOUS_VERSION = "0.1.0"
CAMPAIGN_ID = "ret-orders-legacy-status"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def payload_object(value: dict[str, Any] | None, label: str) -> dict[str, Any]:
    if value is None:
        raise RuntimeError(f"{label} did not return JSON")
    return value


def extract_previous_source(destination: Path) -> str:
    commit = checked(["git", "rev-parse", PREVIOUS_COMMIT]).stdout.strip()
    archive_path = destination.parent / "previous.tar"
    checked(
        [
            "git",
            "archive",
            "--format=tar",
            f"--output={archive_path}",
            commit,
        ]
    )
    with tarfile.open(archive_path, "r:") as archive:
        for member in archive.getmembers():
            path = PurePosixPath(member.name)
            require(not path.is_absolute(), "previous source contains absolute path")
            require(".." not in path.parts, "previous source contains traversal")
            require(
                not (
                    member.issym()
                    or member.islnk()
                    or member.isdev()
                    or member.isfifo()
                ),
                "previous source contains unsafe archive member",
            )
        archive.extractall(destination, filter="data")
    return commit


def build_previous_release(base: Path) -> tuple[Path, str]:
    source = base / "previous-source"
    source.mkdir()
    commit = extract_previous_source(source)
    output = base / "previous-dist"
    checked(["uv", "build", "--out-dir", str(output)], cwd=source, timeout=900)
    wheels = list(output.glob("retirement_conductor-*.whl"))
    require(len(wheels) == 1, "previous build did not produce one wheel")
    require(
        f"-{PREVIOUS_VERSION}-" in wheels[0].name,
        "previous package version changed",
    )
    return wheels[0], commit


def installed_json(
    environment_root: Path,
    arguments: list[str],
    *,
    cwd: Path,
    environment: dict[str, str],
) -> dict[str, Any]:
    _, value = installed_command(
        environment_root,
        arguments,
        cwd=cwd,
        environment=environment,
    )
    return payload_object(value, arguments[0])


def install_wheel(environment_root: Path, wheel: Path) -> None:
    checked(
        [
            "uv",
            "pip",
            "install",
            "--python",
            str(environment_root / "bin" / "python"),
            "--force-reinstall",
            "--no-deps",
            "--no-config",
            "--no-progress",
            str(wheel),
        ]
    )


def package_version(
    environment_root: Path,
    *,
    cwd: Path,
    environment: dict[str, str],
) -> str:
    return checked(
        [
            str(environment_root / "bin" / "python"),
            "-I",
            "-c",
            (
                "from importlib.metadata import version; "
                "print(version('retirement-conductor'))"
            ),
        ],
        cwd=cwd,
        environment=environment,
    ).stdout.strip()


def run() -> dict[str, Any]:
    require(__version__ != PREVIOUS_VERSION, "upgrade needs distinct versions")
    with tempfile.TemporaryDirectory(
        prefix="retirement-conductor-phase08-upgrade-"
    ) as temporary:
        base = Path(temporary)
        previous_wheel, previous_commit = build_previous_release(base)
        environment_root = create_clean_environment(
            base / "venv",
            python_version="3.11",
            wheel=previous_wheel,
        )
        home = base / "home"
        environment = runtime_environment(home)
        work = base / "work"
        work.mkdir()
        state = home / ".retirement-conductor"
        store = state / "campaigns.sqlite"

        require(
            package_version(
                environment_root,
                cwd=work,
                environment=environment,
            )
            == PREVIOUS_VERSION,
            "previous console version mismatch",
        )
        installed_json(
            environment_root,
            [
                "campaign",
                "create",
                str(ROOT / "fixtures/specs/valid.yaml"),
                "--store",
                str(store),
                "--writer-id",
                "upgrade-test",
                "--occurred-at",
                "2026-01-01T10:00:00Z",
            ],
            cwd=work,
            environment=environment,
        )
        before_path = base / "before.json"
        before = installed_json(
            environment_root,
            [
                "campaign",
                "export",
                CAMPAIGN_ID,
                "--output",
                str(before_path),
                "--store",
                str(store),
                "--writer-id",
                "upgrade-test",
            ],
            cwd=work,
            environment=environment,
        )
        pre_upgrade_backup = base / "pre-upgrade.sqlite"
        shutil.copy2(store, pre_upgrade_backup)
        pre_upgrade_store_digest = digest_file(pre_upgrade_backup)

        install_wheel(environment_root, current_wheel())
        require(
            package_version(
                environment_root,
                cwd=work,
                environment=environment,
            )
            == __version__,
            "current console version mismatch",
        )
        after_path = base / "after.json"
        after = installed_json(
            environment_root,
            [
                "campaign",
                "export",
                CAMPAIGN_ID,
                "--output",
                str(after_path),
                "--store",
                str(store),
                "--writer-id",
                "upgrade-test",
            ],
            cwd=work,
            environment=environment,
        )
        require(
            before["manifest_digest"] == after["manifest_digest"],
            "upgrade changed the canonical campaign",
        )

        backup_path = base / "post-upgrade.sqlite"
        backup = installed_json(
            environment_root,
            [
                "campaign",
                "backup",
                "--output",
                str(backup_path),
                "--captured-at",
                "2026-01-01T11:00:00Z",
                "--store",
                str(store),
                "--writer-id",
                "upgrade-test",
            ],
            cwd=work,
            environment=environment,
        )
        require(
            backup["schema_versions"] == [1, 2, 3],
            "upgrade did not apply every database migration",
        )
        verify_digest(backup, "backup_receipt_digest")

        migrated_store = base / "migrated.sqlite"
        store.replace(migrated_store)
        shutil.copy2(pre_upgrade_backup, store)
        install_wheel(environment_root, previous_wheel)
        require(
            package_version(
                environment_root,
                cwd=work,
                environment=environment,
            )
            == PREVIOUS_VERSION,
            "rollback console version mismatch",
        )
        rollback_path = base / "rollback.json"
        rollback = installed_json(
            environment_root,
            [
                "campaign",
                "export",
                CAMPAIGN_ID,
                "--output",
                str(rollback_path),
                "--store",
                str(store),
                "--writer-id",
                "upgrade-test",
            ],
            cwd=work,
            environment=environment,
        )
        require(
            rollback["manifest_digest"] == before["manifest_digest"],
            "rollback did not restore the prior canonical campaign",
        )
        require(
            digest_file(store) == pre_upgrade_store_digest,
            "old runtime changed the restored pre-upgrade database",
        )

        evidence = with_digest(
            {
                "schema_version": "1.0.0",
                "captured_at": utc_now(),
                "result": "UPGRADE_AND_ROLLBACK_VERIFIED",
                "previous": {
                    "version": PREVIOUS_VERSION,
                    "commit": previous_commit,
                    "wheel_digest": digest_file(previous_wheel),
                    "schema_versions": [1],
                },
                "current": {
                    "version": __version__,
                    "package": package_identity(),
                    "schema_versions": backup["schema_versions"],
                },
                "campaign": {
                    "manifest_digest_before": before["manifest_digest"],
                    "manifest_digest_after": after["manifest_digest"],
                    "manifest_digest_rollback": rollback["manifest_digest"],
                    "preserved_on_upgrade": True,
                    "restored_on_rollback": True,
                },
                "backup": {
                    "pre_upgrade_database_digest": pre_upgrade_store_digest,
                    "post_upgrade_receipt_digest": backup["backup_receipt_digest"],
                    "post_upgrade_database_digest": digest_file(backup_path),
                },
                "limitations": [
                    "Rollback restores the verified pre-upgrade database before "
                    "reinstalling the prior package.",
                    "Downgrading a migrated database in place is unsupported.",
                ],
            },
            "upgrade_evidence_digest",
        )

    PHASE08_RUNTIME.mkdir(parents=True, exist_ok=True)
    write_json(PHASE08_RUNTIME / "upgrade-evidence.json", evidence)
    print(
        f"Upgrade {PREVIOUS_VERSION} -> {__version__} preserved the campaign; "
        "backup restore and package rollback passed."
    )
    return evidence


def main() -> int:
    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

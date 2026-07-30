"""Shared helpers for Phase 08 release acceptance."""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from retirement_conductor.canonical import digest_file

ROOT = Path(__file__).resolve().parents[1]
PHASE08_RUNTIME = ROOT / ".retirement-conductor" / "phase08"
RELEASE_ROOT = PHASE08_RUNTIME / "release"
RELEASE_DIST = RELEASE_ROOT / "dist"
RUNTIME_REQUIREMENTS = RELEASE_DIST / "runtime-requirements.txt"


def checked(
    arguments: Sequence[str],
    *,
    cwd: Path = ROOT,
    environment: Mapping[str, str] | None = None,
    timeout: int = 600,
) -> subprocess.CompletedProcess[str]:
    """Run one command or raise with a bounded, non-sensitive diagnostic."""

    result = subprocess.run(
        list(arguments),
        cwd=cwd,
        env=dict(environment) if environment is not None else None,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )
    if result.returncode != 0:
        output = (result.stdout + result.stderr)[-1000:]
        raise RuntimeError(f"{arguments[0]} exited {result.returncode}: {output}")
    return result


def current_wheel() -> Path:
    wheels = sorted(RELEASE_DIST.glob("retirement_conductor-*-py3-none-any.whl"))
    if len(wheels) != 1:
        raise RuntimeError(f"expected one release wheel, found {len(wheels)}")
    return wheels[0]


def current_sdist() -> Path:
    archives = sorted(RELEASE_DIST.glob("retirement_conductor-*.tar.gz"))
    if len(archives) != 1:
        raise RuntimeError(f"expected one source archive, found {len(archives)}")
    return archives[0]


def create_clean_environment(
    destination: Path,
    *,
    python_version: str,
    wheel: Path | None = None,
) -> Path:
    """Create a fresh virtual environment and install the hash-locked release."""

    selected_wheel = wheel or current_wheel()
    checked(
        [
            "uv",
            "venv",
            "--python",
            python_version,
            str(destination),
        ]
    )
    python = destination / "bin" / "python"
    checked(
        [
            "uv",
            "pip",
            "install",
            "--python",
            str(python),
            "--require-hashes",
            "--no-config",
            "--no-progress",
            "-r",
            str(RUNTIME_REQUIREMENTS),
        ],
        timeout=900,
    )
    checked(
        [
            "uv",
            "pip",
            "install",
            "--python",
            str(python),
            "--no-deps",
            "--no-config",
            "--no-progress",
            str(selected_wheel),
        ],
        timeout=300,
    )
    return destination


def runtime_environment(home: Path) -> dict[str, str]:
    """Return a minimal environment for installed CLI execution."""

    home.mkdir(parents=True, exist_ok=True)
    return {
        "HOME": str(home),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": os.environ.get("PATH", ""),
        "PYTHONNOUSERSITE": "1",
        "NO_COLOR": "1",
    }


def installed_command(
    environment_root: Path,
    arguments: Sequence[str],
    *,
    cwd: Path,
    environment: Mapping[str, str],
    expected_exit: int = 0,
    timeout: int = 300,
) -> tuple[subprocess.CompletedProcess[str], dict[str, Any] | None]:
    """Run the installed console entry point and parse JSON when possible."""

    executable = environment_root / "bin" / "retirement-conductor"
    result = subprocess.run(
        [str(executable), *arguments],
        cwd=cwd,
        env=dict(environment),
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )
    if result.returncode != expected_exit:
        raise RuntimeError(
            f"installed command exited {result.returncode}, expected "
            f"{expected_exit}: {(result.stdout + result.stderr)[-1000:]}"
        )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = None
    if payload is not None and not isinstance(payload, dict):
        raise RuntimeError("installed command returned non-object JSON")
    return result, payload


def package_identity() -> dict[str, str]:
    wheel = current_wheel()
    sdist = current_sdist()
    return {
        "wheel": wheel.name,
        "wheel_digest": digest_file(wheel),
        "sdist": sdist.name,
        "sdist_digest": digest_file(sdist),
        "requirements_digest": digest_file(RUNTIME_REQUIREMENTS),
    }

#!/usr/bin/env python3
"""Create the ignored disposable Git repository from the public dbt template."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from retirement_conductor.canonical import digest_json, write_json

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE = ROOT / "fixtures" / "git-dbt-project"
DEFAULT_DESTINATION = (
    ROOT / ".retirement-conductor" / "workspaces" / "ret-orders-git-dbt" / "repository"
)


def git(repository: Path, *arguments: str) -> str:
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "GIT_AUTHOR_NAME": "Retirement Conductor Fixture",
        "GIT_AUTHOR_EMAIL": "fixture@retirement-conductor.invalid",
        "GIT_COMMITTER_NAME": "Retirement Conductor Fixture",
        "GIT_COMMITTER_EMAIL": "fixture@retirement-conductor.invalid",
        "GIT_AUTHOR_DATE": "2026-07-30T00:00:00Z",
        "GIT_COMMITTER_DATE": "2026-07-30T00:00:00Z",
        "LC_ALL": "C.UTF-8",
    }
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
        timeout=30,
    )
    return result.stdout.strip()


def prepare(template: Path, destination: Path) -> dict[str, Any]:
    template = template.resolve(strict=True)
    destination = destination.resolve()
    if destination.exists():
        if not (destination / ".git").is_dir():
            raise RuntimeError("existing workspace is not a Git repository")
        if git(destination, "status", "--porcelain"):
            raise RuntimeError("existing disposable repository is not clean")
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(template, destination)
        git(destination, "init", "--initial-branch=main")
        git(destination, "add", "--all")
        git(destination, "commit", "-m", "fixture: initialize dbt consumer")
    commit = git(destination, "rev-parse", "HEAD")
    result = {
        "schema_version": "1.0.0",
        "mode": "live",
        "repository_identity": digest_json(str(destination)),
        "default_branch": git(destination, "branch", "--show-current"),
        "commit": commit,
        "template_digest": digest_json(
            sorted(
                path.relative_to(template).as_posix()
                for path in template.rglob("*")
                if path.is_file()
            )
        ),
    }
    write_json(
        ROOT / ".retirement-conductor" / "git-dbt" / "workspace-receipt.json",
        result,
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--destination", type=Path, default=DEFAULT_DESTINATION)
    args = parser.parse_args()
    result = prepare(args.template, args.destination)
    print(
        "Prepared disposable Git/dbt repository: "
        f"branch={result['default_branch']} commit={result['commit']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

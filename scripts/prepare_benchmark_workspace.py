#!/usr/bin/env python3
"""Prepare the ignored Git/dbt workspace from one verified generation."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from retirement_conductor.benchmark_data import verify_generation_output
from retirement_conductor.canonical import (
    digest_file,
    digest_json,
    with_digest,
    write_json,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE = ROOT / "fixtures" / "benchmark-dbt-project"
DEFAULT_GENERATION = ROOT / ".retirement-conductor/benchmark/generation-a"
DEFAULT_DESTINATION = ROOT / ".retirement-conductor/benchmark/workspace/repository"
DEFAULT_RECEIPT = ROOT / ".retirement-conductor/benchmark/workspace-receipt.json"


def git(repository: Path, *arguments: str) -> str:
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "GIT_AUTHOR_NAME": "Retirement Conductor Benchmark",
        "GIT_AUTHOR_EMAIL": "benchmark@retirement-conductor.invalid",
        "GIT_COMMITTER_NAME": "Retirement Conductor Benchmark",
        "GIT_COMMITTER_EMAIL": "benchmark@retirement-conductor.invalid",
        "GIT_AUTHOR_DATE": "2026-08-02T00:00:00Z",
        "GIT_COMMITTER_DATE": "2026-08-02T00:00:00Z",
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


def prepare(
    template: Path,
    generation: Path,
    destination: Path,
    receipt_path: Path,
) -> dict[str, Any]:
    template = template.resolve(strict=True)
    generation = generation.resolve(strict=True)
    source_receipt = verify_generation_output(generation)
    source_seed = generation / "data/clean/orders.csv"
    expected_seed_digest = source_receipt["artifact_digests"]["data/clean/orders.csv"]
    destination = destination.resolve()
    seed_path = destination / "seeds/orders.csv"
    if destination.exists():
        if not (destination / ".git").is_dir():
            raise RuntimeError("existing benchmark workspace is not a Git repository")
        if git(destination, "status", "--porcelain=v1", "--untracked-files=all"):
            raise RuntimeError("existing benchmark workspace is not clean")
        if not seed_path.is_file() or digest_file(seed_path) != expected_seed_digest:
            raise RuntimeError("existing benchmark workspace uses another generation")
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(template, destination)
        seed_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_seed, seed_path)
        git(destination, "init", "--initial-branch=main")
        git(destination, "add", "--all")
        git(destination, "commit", "-m", "benchmark: initialize generated consumer")

    receipt = with_digest(
        {
            "branch": git(destination, "branch", "--show-current"),
            "commit": git(destination, "rev-parse", "HEAD"),
            "generation_receipt_digest": source_receipt["receipt_digest"],
            "mode": "live-local",
            "repository_identity": digest_json(str(destination)),
            "schema_version": "1.0.0",
            "seed_digest": digest_file(seed_path),
            "template_digest": digest_json(
                {
                    path.relative_to(template).as_posix(): digest_file(path)
                    for path in sorted(template.rglob("*"))
                    if path.is_file()
                }
            ),
        },
        "workspace_digest",
    )
    write_json(receipt_path, receipt)
    return receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--generation", type=Path, default=DEFAULT_GENERATION)
    parser.add_argument("--destination", type=Path, default=DEFAULT_DESTINATION)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    result = prepare(
        arguments.template,
        arguments.generation,
        arguments.destination,
        arguments.receipt,
    )
    print(
        "Prepared benchmark Git/dbt repository: "
        f"branch={result['branch']} commit={result['commit']}"
    )

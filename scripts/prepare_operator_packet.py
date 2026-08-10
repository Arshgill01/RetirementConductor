#!/usr/bin/env python3
"""Build an ignored, checksum-bound packet for a real independent operator."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from retirement_conductor.canonical import digest_file, with_digest, write_json

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = ROOT / ".retirement-conductor/operator-evaluation"


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def build_release() -> list[Path]:
    subprocess.run(["uv", "build"], cwd=ROOT, check=True)
    packages = sorted((ROOT / "dist").glob("retirement_conductor-*"))
    if len(packages) != 2:
        raise RuntimeError("expected exactly one wheel and one source distribution")
    return packages


def prepare(
    output_root: Path,
    *,
    packages: list[Path],
    created_at: str,
) -> dict[str, Any]:
    session_id = created_at.replace(":", "").replace("-", "").replace(".", "")
    session_root = output_root / session_id
    if session_root.exists():
        raise RuntimeError(f"operator packet already exists: {session_root}")
    session_root.mkdir(parents=True)
    release_root = session_root / "release"
    release_root.mkdir()

    copies = {
        "INDEPENDENT_OPERATOR.md": ROOT / "docs/runbooks/INDEPENDENT_OPERATOR.md",
        "EVALUATION.md": ROOT / "docs/EVALUATION.md",
        "DEPLOYMENT.md": ROOT / "docs/runbooks/DEPLOYMENT.md",
        "OPERATOR_OBSERVATION.md": ROOT / "docs/templates/OPERATOR_OBSERVATION.md",
    }
    for name, source in copies.items():
        shutil.copyfile(source, session_root / name)
    for package in packages:
        shutil.copyfile(package, release_root / package.name)

    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    tracked = sorted(
        [session_root / name for name in copies] + list(release_root.iterdir()),
        key=lambda path: str(path.relative_to(session_root)),
    )
    manifest = with_digest(
        {
            "schema_version": "1.0.0",
            "evidence_status": "PREPARED_NOT_RUN",
            "created_at": created_at,
            "repository_commit": commit,
            "files": [
                {
                    "path": str(path.relative_to(session_root)),
                    "digest": digest_file(path),
                }
                for path in tracked
            ],
            "independence_rules": {
                "implementation_author_is_operator": False,
                "author_interventions_must_be_recorded": True,
                "raw_notes_committed": False,
                "production_mutation_allowed": False,
            },
            "claims": [
                "Packet preparation is not operator evidence.",
                (
                    "RC-018 remains NOT_RUN until a real participant completes "
                    "and reviews an observation."
                ),
            ],
        },
        "packet_digest",
    )
    write_json(session_root / "MANIFEST.json", manifest)
    (session_root / "START_HERE.md").write_text(
        "# Retirement Conductor independent evaluation\n\n"
        f"Packet: `{manifest['packet_digest']}`  \n"
        f"Repository commit: `{commit}`\n\n"
        "You are evaluating the product, not trying to make the demo pass. "
        "Begin with `INDEPENDENT_OPERATOR.md`. Use the packaged release and "
        "published documentation. Record all outcomes in "
        "`OPERATOR_OBSERVATION.md`. If the author gives you a command, hint, "
        "interpretation, or repair, record it as an intervention. Do not place "
        "credentials, names, employer details, private SQL, data, or paths in "
        "the observation.\n",
        encoding="utf-8",
    )
    return {"session_root": str(session_root), "manifest": manifest}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--created-at", default=None)
    parser.add_argument(
        "--packages",
        type=Path,
        nargs="*",
        help="Use existing package files instead of building (primarily for tests).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    packages = list(args.packages) if args.packages else build_release()
    result = prepare(
        args.output_root,
        packages=packages,
        created_at=args.created_at or utc_now(),
    )
    print(
        f"Operator packet prepared (NOT_RUN): {result['session_root']} "
        f"digest={result['manifest']['packet_digest']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

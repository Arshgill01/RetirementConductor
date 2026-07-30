#!/usr/bin/env python3
"""Conservative repository secret scan without printing matched values."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".retirement-conductor",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "private",
    "raw",
}
PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "GitHub token": re.compile(r"\bgh[opsu]_[A-Za-z0-9]{30,}\b"),
    "Slack token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    "credential assignment": re.compile(
        r"(?im)^(?:DATAHUB_GMS_TOKEN|LOOKER_CLIENT_SECRET|"
        r"LOOKERSDK_CLIENT_SECRET)[ \t]*=[ \t]*"
        r"(?!$|example$|synthetic$)[^\r\n]+$"
    ),
}


def candidates() -> list[Path]:
    return sorted(
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and not any(part in EXCLUDED_PARTS for part in path.relative_to(ROOT).parts)
        and path.stat().st_size <= 2_000_000
    )


def run() -> int:
    findings: list[str] = []
    scanned = 0
    for path in candidates():
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        scanned += 1
        for label, pattern in PATTERNS.items():
            if pattern.search(content):
                findings.append(f"{path.relative_to(ROOT)}: possible {label}")
    if findings:
        print("Secret scan failed:")
        for finding in findings:
            print(f"- {finding}")
        return 1
    print(f"Secret scan passed: {scanned} text files checked.")
    return 0


if __name__ == "__main__":
    sys.exit(run())

#!/usr/bin/env python3
"""Reject private paths and sensitive material in tracked public artifacts."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "artifacts/public"
FORBIDDEN = {
    "home path": re.compile(r"(?:/home/|/Users/)[^/\s]+/"),
    "private key": re.compile(r"-----BEGIN .*PRIVATE KEY-----"),
    "credential value": re.compile(
        r"(?im)(?:token|client_secret|password)\s*[=:]\s*[\"']?[A-Za-z0-9+/=_-]{12,}"
    ),
}


def run() -> int:
    findings: list[str] = []
    checked = 0
    if PUBLIC.exists():
        for path in sorted(PUBLIC.rglob("*")):
            if not path.is_file():
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                findings.append(f"{path.relative_to(ROOT)}: binary public artifact")
                continue
            checked += 1
            for label, pattern in FORBIDDEN.items():
                if pattern.search(content):
                    findings.append(f"{path.relative_to(ROOT)}: contains {label}")
    if findings:
        print("Public artifact review failed:")
        for finding in findings:
            print(f"- {finding}")
        return 1
    print(f"Public artifact review passed: {checked} files checked.")
    return 0


if __name__ == "__main__":
    sys.exit(run())

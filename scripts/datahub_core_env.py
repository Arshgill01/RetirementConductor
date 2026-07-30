#!/usr/bin/env python3
"""Create ignored, least-lived token-service material for disposable Core."""

from __future__ import annotations

import argparse
import os
import secrets
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".retirement-conductor/datahub/core.env"),
    )
    args = parser.parse_args()
    output: Path = args.output
    if output.exists():
        print(f"Disposable DataHub environment already exists: {output}")
        return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    content = (
        "# Generated local runtime material; ignored by git.\n"
        f"DATAHUB_TOKEN_SERVICE_SIGNING_KEY={secrets.token_urlsafe(32)}\n"
        f"DATAHUB_TOKEN_SERVICE_SALT={secrets.token_urlsafe(32)}\n"
    )
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    print(f"Created ignored disposable DataHub environment: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

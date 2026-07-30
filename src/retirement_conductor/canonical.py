"""Canonical JSON and content-integrity utilities."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from retirement_conductor.errors import Refusal
from retirement_conductor.vocabulary import RefusalCode


def canonical_json(value: Any) -> str:
    """Serialize JSON deterministically without insignificant whitespace."""

    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def digest_bytes(content: bytes) -> str:
    """Return a namespaced SHA-256 content digest."""

    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def digest_json(value: Any) -> str:
    """Return the digest of a value's canonical JSON representation."""

    return digest_bytes(canonical_json(value).encode("utf-8"))


def digest_file(path: Path) -> str:
    """Return the digest of the exact file bytes."""

    return digest_bytes(path.read_bytes())


def with_digest(value: dict[str, Any], digest_field: str) -> dict[str, Any]:
    """Copy a mapping and bind the named field to all other content."""

    result = dict(value)
    result.pop(digest_field, None)
    result[digest_field] = digest_json(result)
    return result


def verify_digest(value: dict[str, Any], digest_field: str) -> None:
    """Refuse when a digest no longer matches its canonical content."""

    expected = value.get(digest_field)
    unsigned = dict(value)
    unsigned.pop(digest_field, None)
    actual = digest_json(unsigned)
    if expected != actual:
        raise Refusal(
            RefusalCode.INTEGRITY_DIGEST_MISMATCH,
            "The artifact content does not match its recorded digest.",
            {"digest_field": digest_field, "expected": expected, "actual": actual},
        )


def write_json(path: Path, value: Any) -> None:
    """Atomically write stable, human-inspectable JSON."""

    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        delete=False,
    ) as temporary:
        temporary.write(rendered)
        temporary.flush()
        os.fsync(temporary.fileno())
        temporary_path = Path(temporary.name)
    os.replace(temporary_path, path)

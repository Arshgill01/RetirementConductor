"""Filesystem scope and source-precondition checks."""

from __future__ import annotations

from pathlib import Path

from retirement_conductor.canonical import digest_file
from retirement_conductor.errors import Refusal
from retirement_conductor.vocabulary import RefusalCode


def resolve_scoped_path(candidate: str, allowed_root: Path) -> Path:
    """Resolve a path without allowing traversal or symlink escape."""

    root = allowed_root.resolve(strict=True)
    requested = Path(candidate)
    path = requested if requested.is_absolute() else root / requested
    resolved = path.resolve(strict=False)
    if resolved != root and root not in resolved.parents:
        raise Refusal(
            RefusalCode.SCOPE_PATH_OUTSIDE_ROOT,
            "The requested path resolves outside the authorized root.",
            {"candidate": candidate},
        )
    if not resolved.is_file():
        raise Refusal(
            RefusalCode.SOURCE_NOT_FOUND,
            "The authorized source file does not exist.",
            {"candidate": candidate},
        )
    return resolved


def verify_source_fingerprint(path: Path, expected: str) -> str:
    """Require an exact content fingerprint immediately before use."""

    actual = digest_file(path)
    if actual != expected:
        raise Refusal(
            RefusalCode.SOURCE_FINGERPRINT_MISMATCH,
            "The source changed after the plan was created.",
            {"expected": expected, "actual": actual},
        )
    return actual


def require_allowed_target(relative_path: str, allowed_paths: list[str]) -> None:
    """Require the exact target to fall under one declared path prefix."""

    normalized = Path(relative_path).as_posix()
    allowed = False
    for entry in allowed_paths:
        prefix = Path(entry).as_posix().rstrip("/")
        if normalized == prefix or normalized.startswith(f"{prefix}/"):
            allowed = True
            break
    if not allowed:
        raise Refusal(
            RefusalCode.SCOPE_TARGET_NOT_ALLOWED,
            "The proposed target is outside the specification allowlist.",
            {"target": normalized, "allowed_paths": sorted(allowed_paths)},
        )

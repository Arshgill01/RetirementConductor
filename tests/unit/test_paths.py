from __future__ import annotations

from pathlib import Path

import pytest

from retirement_conductor.canonical import digest_file
from retirement_conductor.errors import Refusal
from retirement_conductor.paths import (
    require_allowed_target,
    resolve_scoped_path,
    verify_source_fingerprint,
)


def test_scoped_path_and_fingerprint_accept_exact_source(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    source = root / "models" / "consumer.sql"
    source.parent.mkdir(parents=True)
    source.write_text("select legacy_status\n", encoding="utf-8")

    resolved = resolve_scoped_path("models/consumer.sql", root)

    assert resolved == source
    expected = digest_file(source)
    assert verify_source_fingerprint(resolved, expected) == expected
    require_allowed_target("models/consumer.sql", ["models/"])


def test_path_traversal_refuses_before_file_access(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    outside = tmp_path / "outside.sql"
    outside.write_text("private\n", encoding="utf-8")

    with pytest.raises(Refusal, match="SCOPE_PATH_OUTSIDE_ROOT"):
        resolve_scoped_path("../outside.sql", root)


def test_symlink_escape_refuses(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    outside = tmp_path / "outside.sql"
    outside.write_text("private\n", encoding="utf-8")
    (root / "linked.sql").symlink_to(outside)

    with pytest.raises(Refusal, match="SCOPE_PATH_OUTSIDE_ROOT"):
        resolve_scoped_path("linked.sql", root)


def test_stale_fingerprint_refuses(tmp_path: Path) -> None:
    source = tmp_path / "consumer.sql"
    source.write_text("changed\n", encoding="utf-8")

    with pytest.raises(Refusal, match="SOURCE_FINGERPRINT_MISMATCH"):
        verify_source_fingerprint(source, f"sha256:{'0' * 64}")


def test_target_outside_allowlist_refuses() -> None:
    with pytest.raises(Refusal, match="SCOPE_TARGET_NOT_ALLOWED"):
        require_allowed_target("seeds/private.csv", ["models/"])

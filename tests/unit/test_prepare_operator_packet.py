from __future__ import annotations

import json
from pathlib import Path

from retirement_conductor.canonical import verify_digest
from scripts.prepare_operator_packet import prepare


def test_operator_packet_is_bound_and_does_not_claim_a_run(tmp_path: Path) -> None:
    wheel = tmp_path / "retirement_conductor-0.2.0-py3-none-any.whl"
    source = tmp_path / "retirement_conductor-0.2.0.tar.gz"
    wheel.write_bytes(b"test-wheel")
    source.write_bytes(b"test-source")

    result = prepare(
        tmp_path / "packets",
        packages=[wheel, source],
        created_at="2026-08-10T06:00:00Z",
    )
    session_root = Path(result["session_root"])
    manifest = json.loads((session_root / "MANIFEST.json").read_text(encoding="utf-8"))

    verify_digest(manifest, "packet_digest")
    assert manifest["evidence_status"] == "PREPARED_NOT_RUN"
    assert manifest["independence_rules"]["implementation_author_is_operator"] is False
    assert (session_root / "START_HERE.md").is_file()
    assert len(manifest["files"]) == 6

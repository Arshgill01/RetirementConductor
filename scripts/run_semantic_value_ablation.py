#!/usr/bin/env python3
"""Verify the frozen TE-01 corpus and retained public evidence offline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from retirement_conductor.semantic_ablation import (
    verify_frozen_corpus,
    verify_public_evidence,
)

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "fixtures/semantic-ablation-v2/corpus.json"
FREEZE = ROOT / "fixtures/semantic-ablation-v2/FROZEN.json"
PUBLIC = ROOT / "artifacts/public/semantic-ablation-v2"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("verify-freeze", "verify"))
    args = parser.parse_args()
    if args.action == "verify-freeze":
        value = verify_frozen_corpus(CORPUS, FREEZE)
        digest = json.loads(FREEZE.read_text(encoding="utf-8"))["freeze_record_digest"]
        print(f"Frozen corpus verified: {len(value['scenarios'])} scenarios; {digest}")
        return 0
    summary = verify_public_evidence(PUBLIC)
    print(
        "Public semantic ablation verified offline: "
        f"{summary['summary_digest']} "
        f"recommendation={summary['nested_gemini_recommendation']['recommendation']} "
        "datahub_context="
        f"{summary['datahub_context_recommendation']['recommendation']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

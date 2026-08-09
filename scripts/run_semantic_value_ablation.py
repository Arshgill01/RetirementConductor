#!/usr/bin/env python3
"""Freeze, run, publish, and verify TE-01 semantic ablation evidence."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from retirement_conductor.canonical import write_json
from retirement_conductor.semantic_ablation import (
    freeze_corpus,
    publish_evidence,
    run_experiment,
    verify_frozen_corpus,
    verify_public_evidence,
)
from retirement_conductor.semantic_model_planner import VertexPlannerSettings

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "fixtures/semantic-ablation-v2/corpus.json"
FREEZE = ROOT / "fixtures/semantic-ablation-v2/FROZEN.json"
RAW = ROOT / ".retirement-conductor/semantic-ablation-v2/raw"
PUBLIC = ROOT / "artifacts/public/semantic-ablation-v2"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("freeze", "verify-freeze", "run", "publish", "verify")
    )
    args = parser.parse_args()
    if args.action == "freeze":
        if RAW.exists() and any(RAW.rglob("*.json")):
            raise SystemExit("refusing to freeze after raw model evidence exists")
        value = freeze_corpus(CORPUS, FREEZE)
        print(json.dumps(value, indent=2, sort_keys=True))
        return 0
    if args.action == "verify-freeze":
        value = verify_frozen_corpus(CORPUS, FREEZE)
        print(
            f"Frozen corpus verified: {len(value['scenarios'])} scenarios; "
            f"{json.loads(FREEZE.read_text(encoding='utf-8'))['freeze_record_digest']}"
        )
        return 0
    settings = _live_settings()
    if args.action == "run":
        results = run_experiment(
            corpus_path=CORPUS,
            freeze_path=FREEZE,
            raw_directory=RAW,
            settings=settings,
        )
        print(f"Semantic ablation matrix complete: {len(results)} attempts")
        return 0
    if args.action == "publish":
        summary = publish_evidence(
            corpus_path=CORPUS,
            freeze_path=FREEZE,
            raw_directory=RAW,
            public_directory=PUBLIC,
            settings=settings,
        )
        _write_run_receipt(summary, settings)
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    summary = verify_public_evidence(PUBLIC)
    print(
        "Public semantic ablation verified: "
        f"{summary['summary_digest']} "
        f"recommendation={summary['nested_gemini_recommendation']['recommendation']}"
    )
    return 0


def _live_settings() -> VertexPlannerSettings:
    values = dict(os.environ)
    if not values.get("SEMANTIC_MODEL_PROJECT") and not values.get(
        "GOOGLE_CLOUD_PROJECT"
    ):
        project = subprocess.run(
            ["gcloud", "config", "get-value", "project"],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        ).stdout.strip()
        if project and project != "(unset)":
            values["SEMANTIC_MODEL_PROJECT"] = project
    if values.get("SEMANTIC_MODEL_ALLOW_LIVE", "").casefold() != "true":
        raise SystemExit(
            "SEMANTIC_MODEL_ALLOW_LIVE=true is required for run, publish, and verify"
        )
    return VertexPlannerSettings.from_environment(values)


def _write_run_receipt(
    summary: dict[str, Any], settings: VertexPlannerSettings
) -> None:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    ).stdout.strip()
    write_json(
        RAW.parent / "run-receipt.json",
        {
            "schema_version": "1.0.0",
            "source_commit_at_run": commit,
            "branch": "codex/semantic-value-ablation",
            "provider": "google-vertex-ai",
            "model": settings.model,
            "summary_digest": summary["summary_digest"],
            "raw_classification": "ignored-private-raw-model-trace",
        },
    )


if __name__ == "__main__":
    raise SystemExit(main())

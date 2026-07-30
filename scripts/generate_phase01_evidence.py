#!/usr/bin/env python3
"""Generate public-safe phase 01 event, manifest, and coverage artifacts."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from retirement_conductor.canonical import digest_file, digest_json, write_json
from retirement_conductor.events import (
    build_event,
    event_stream_digest,
    manifest_from_projection,
    project_events,
)
from retirement_conductor.policy import default_policy, evaluate_policy
from retirement_conductor.refusals import (
    REFUSAL_REGISTRY,
    validate_refusal_registry,
)
from retirement_conductor.specification import load_specification

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIRECTORY = ROOT / "fixtures/campaigns/blocked"
OUTPUT_DIRECTORY = ROOT / "artifacts/public/phase01"
TIMESTAMP = "2026-01-02T00:00:00Z"


def create_events() -> list[dict[str, Any]]:
    specification = load_specification(ROOT / "fixtures/specs/valid.yaml")
    policy = default_policy()
    inputs = {
        "policy": digest_json(policy),
        "validator_configuration": digest_json(specification["validation"]),
        "authorization": digest_json(specification["authorization"]),
    }
    created = build_event(
        campaign_id=specification["campaign"]["id"],
        sequence=1,
        event_type="CAMPAIGN_CREATED",
        occurred_at=TIMESTAMP,
        idempotency_key="fixture-create",
        previous_event_digest=None,
        payload={
            "name": specification["campaign"]["name"],
            "specification_digest": specification["specification_digest"],
            "target": specification["target"],
            "replacement": specification["replacement"],
            "policy": policy,
            "input_digests": inputs,
        },
    )
    envelope = {
        "schema_version": "1.0.0",
        "captured_at": TIMESTAMP,
        "mode": "fixture",
        "sources": [
            {
                "id": "datahub",
                "required": True,
                "status": "COMPLETE",
                "source_version": "fixture-datahub/1.0",
            }
        ],
    }
    inventory = build_event(
        campaign_id=specification["campaign"]["id"],
        sequence=2,
        event_type="INVENTORY_RECORDED",
        occurred_at=TIMESTAMP,
        idempotency_key="fixture-inventory",
        previous_event_digest=created["event_digest"],
        payload={
            "evidence_envelope": envelope,
            "consumers": [
                {
                    "id": "consumer-unresolved",
                    "disposition": "UNRESOLVED",
                    "receipt_digest": None,
                }
            ],
            "snapshot_digest": digest_json(envelope),
        },
    )
    projection = project_events([created, inventory])
    result = evaluate_policy(
        evidence_envelope=projection.evidence_envelope,
        consumers=list(projection.consumers.values()),
        inventory_consumer_ids=projection.inventory_consumer_ids,
        current_consumer_ids=projection.current_consumer_ids,
        reconciled=projection.reconciled,
        policy=projection.policy,
    )
    evaluated = build_event(
        campaign_id=specification["campaign"]["id"],
        sequence=3,
        event_type="POLICY_EVALUATED",
        occurred_at=TIMESTAMP,
        idempotency_key="fixture-evaluation",
        previous_event_digest=inventory["event_digest"],
        payload={
            "input_digests": inputs,
            "decision": result.decision,
            "blocker_codes": sorted(item["code"] for item in result.blockers),
        },
    )
    return [created, inventory, evaluated]


def refusal_coverage() -> dict[str, Any]:
    validate_refusal_registry()
    test_sources = [
        "tests/unit/test_clock.py",
        "tests/unit/test_paths.py",
        "tests/unit/test_policy.py",
        "tests/unit/test_state.py",
        "tests/contracts/test_records.py",
        "tests/contracts/test_specification.py",
        "tests/fixture/test_fixture_run.py",
        "tests/integration/test_campaign_store.py",
    ]
    return {
        "schema_version": "1.0.0",
        "registered_code_count": len(REFUSAL_REGISTRY),
        "families": sorted(set(REFUSAL_REGISTRY.values())),
        "codes": [
            {
                "code": code,
                "family": family,
                "coverage": "direct refusal or deterministic policy-result assertion",
            }
            for code, family in sorted(REFUSAL_REGISTRY.items())
        ],
        "test_sources": test_sources,
        "limitation": (
            "This report maps registered phase 00/01 codes to the focused suite; "
            "later adapters add source-specific refusal codes and evidence."
        ),
    }


def run() -> int:
    events = create_events()
    stream_digest = event_stream_digest(events)
    fixture = {
        "schema_version": "1.0.0",
        "mode": "fixture",
        "events": events,
        "event_stream_digest": stream_digest,
    }
    write_json(FIXTURE_DIRECTORY / "events.json", fixture)

    first_manifest = manifest_from_projection(project_events(events))
    second_manifest = manifest_from_projection(project_events(events))
    if first_manifest != second_manifest:
        raise RuntimeError("phase 01 manifest replay was not deterministic")
    write_json(OUTPUT_DIRECTORY / "blocked-manifest.json", first_manifest)
    write_json(OUTPUT_DIRECTORY / "refusal-coverage.json", refusal_coverage())

    migration = ROOT / "src/retirement_conductor/migrations/001_initial.sql"
    write_json(
        OUTPUT_DIRECTORY / "kernel-evidence.json",
        {
            "schema_version": "1.0.0",
            "mode": "fixture",
            "database_migration": {
                "path": "src/retirement_conductor/migrations/001_initial.sql",
                "digest": digest_file(migration),
            },
            "event_fixture": {
                "path": "fixtures/campaigns/blocked/events.json",
                "event_count": len(events),
                "event_stream_digest": stream_digest,
            },
            "manifest": {
                "path": "artifacts/public/phase01/blocked-manifest.json",
                "digest": first_manifest["manifest_digest"],
                "replay_digest_parity": True,
                "decision": first_manifest["decision"],
                "blocker_codes": [
                    blocker["code"] for blocker in first_manifest["blockers"]
                ],
            },
        },
    )
    print(
        "Phase 01 artifacts generated: "
        f"{len(events)} events, {len(REFUSAL_REGISTRY)} refusal codes."
    )
    return 0


if __name__ == "__main__":
    sys.exit(run())

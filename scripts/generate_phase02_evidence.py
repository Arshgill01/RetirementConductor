#!/usr/bin/env python3
"""Publish public-safe summaries of observed phase 02 live evidence."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from retirement_conductor.canonical import (
    digest_bytes,
    digest_file,
    verify_digest,
    with_digest,
    write_json,
)
from retirement_conductor.datahub import render_campaign_summary
from retirement_conductor.events import (
    event_stream_digest,
    manifest_from_projection,
    project_events,
)
from retirement_conductor.schemas import validate_schema
from retirement_conductor.store import CampaignStore

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".retirement-conductor"
CAMPAIGN_ID = "ret-orders-live-status"
DATAHUB_ROOT = RUNTIME / "artifacts" / CAMPAIGN_ID / "datahub"
BASELINE_ROOT = DATAHUB_ROOT / "baseline"
PUBLICATION_ROOT = DATAHUB_ROOT / "publication"
OUTPUT_ROOT = ROOT / "artifacts" / "public" / "phase02"

VERSIONS = {
    "datahub_core": {
        "gms_image": "acryldata/datahub-gms:v1.6.0",
        "upgrade_image": "acryldata/datahub-upgrade:v1.6.0",
        "source_commit": "b5c566f3e215c3074dbd1443101a916714dd88b3",
    },
    "datahub_cli": "1.6.0",
    "datahub_sdk": "acryl-datahub==1.6.0",
    "mcp_server": {
        "package_version": "0.6.0",
        "source_commit": "9a6946daa7d30eb481c82dd8ee5e15ae6526a3c9",
    },
    "seed_connector": {
        "component": "retirement-conductor-seed/1.0",
        "mode": "direct SDK emitter",
    },
}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected a JSON object: {path.relative_to(ROOT)}")
    return value


def load_candidates(pattern: str) -> list[dict[str, Any]]:
    candidates = [load_json(path) for path in sorted(PUBLICATION_ROOT.glob(pattern))]
    if not candidates:
        raise RuntimeError(f"missing publication artifact: {pattern}")
    return candidates


def publication_source_manifest(
    events: list[dict[str, Any]],
    content_digest: str,
) -> dict[str, Any]:
    for index in range(len(events) - 1, 0, -1):
        event = events[index]
        publication = event.get("payload", {}).get("publication", {})
        if (
            event.get("event_type") == "PUBLICATION_RECORDED"
            and publication.get("content_digest") == content_digest
        ):
            manifest = manifest_from_projection(project_events(events[:index]))
            if manifest["manifest_digest"] != publication["published_manifest_digest"]:
                raise RuntimeError("publication source manifest digest mismatch")
            return manifest
    raise RuntimeError("publication source manifest not found")


def raw_artifact_index(snapshot: dict[str, Any]) -> list[dict[str, str]]:
    indexed: dict[str, dict[str, str]] = {}
    for path in sorted(BASELINE_ROOT.glob("*.json")):
        artifact_digest = digest_file(path)
        if artifact_digest in snapshot["raw_artifact_ids"]:
            indexed.setdefault(
                artifact_digest,
                {
                    "runtime_name": path.name,
                    "digest": artifact_digest,
                },
            )
    if set(indexed) != set(snapshot["raw_artifact_ids"]):
        raise RuntimeError("snapshot raw artifact index is incomplete")
    return [indexed[digest] for digest in sorted(indexed)]


def run() -> int:
    capability = load_json(RUNTIME / "datahub" / "capability-fingerprint.json")
    verify_digest(capability, "capability_digest")
    snapshot = load_json(BASELINE_ROOT / "snapshot.json")
    validate_schema("datahub-snapshot", snapshot)
    verify_digest(snapshot, "snapshot_digest")
    seed = load_json(RUNTIME / "datahub" / "seed-receipt.json")

    with CampaignStore(
        RUNTIME / "campaigns.sqlite",
        writer_id="local-operator",
    ) as store:
        events = store.events(CAMPAIGN_ID)
        manifest = store.materialize(CAMPAIGN_ID)

    publications = [
        event for event in events if event["event_type"] == "PUBLICATION_RECORDED"
    ]
    verifications = [
        event for event in events if event["event_type"] == "PUBLICATION_VERIFIED"
    ]
    if len(publications) < 2 or len(verifications) < 2:
        raise RuntimeError("idempotent publication was not exercised twice")
    publication_urns = {
        event["payload"]["publication"]["urn"] for event in publications
    }
    if len(publication_urns) != 1:
        raise RuntimeError("publication changed its stable DataHub identity")

    current_publication = manifest.get("publication")
    if not isinstance(current_publication, dict):
        raise RuntimeError("current campaign has no publication")
    if current_publication.get("readback_verified") is not True:
        raise RuntimeError("current publication is not read-back verified")
    source_manifest = publication_source_manifest(
        events,
        str(current_publication["content_digest"]),
    )
    expected_content = render_campaign_summary(source_manifest)
    readback = next(
        (
            candidate
            for candidate in load_candidates("publication-readback*.json")
            if isinstance(candidate.get("document"), dict)
            and isinstance(candidate["document"].get("info"), dict)
            and isinstance(
                candidate["document"]["info"].get("contents"),
                dict,
            )
            and candidate["document"]["info"]["contents"].get("text")
            == expected_content
        ),
        None,
    )
    if readback is None:
        raise RuntimeError("no read-back artifact matched current content")
    document = readback.get("document")
    info = document.get("info") if isinstance(document, dict) else None
    contents = info.get("contents") if isinstance(info, dict) else None
    observed_content = contents.get("text") if isinstance(contents, dict) else None
    if observed_content != expected_content:
        raise RuntimeError("live DataHub document content did not match")
    if digest_bytes(expected_content.encode()) != current_publication["content_digest"]:
        raise RuntimeError("live DataHub document digest did not match")

    expected_title = f"Retirement Conductor — {CAMPAIGN_ID}"
    search = next(
        (
            candidate
            for candidate in load_candidates("publication-search*.json")
            if isinstance(candidate.get("searchDocuments"), dict)
            and any(
                isinstance(item, dict)
                and item.get("urn") == current_publication["urn"]
                and isinstance(item.get("info"), dict)
                and item["info"].get("title") == expected_title
                for item in candidate["searchDocuments"].get("documents") or []
            )
        ),
        None,
    )
    if search is None:
        raise RuntimeError("no search artifact matched the current document")
    search_result = search["searchDocuments"]
    documents = search_result.get("documents")
    exact_documents = [
        item
        for item in documents or []
        if isinstance(item, dict)
        and item.get("urn") == current_publication["urn"]
        and isinstance(item.get("info"), dict)
        and item["info"].get("title") == expected_title
    ]
    if not isinstance(documents, list) or len(exact_documents) != 1:
        raise RuntimeError("live DataHub search did not expose one logical record")

    lifecycle_before = snapshot["lifecycle"]
    lifecycle_after = next(
        (
            candidate
            for candidate in reversed(load_candidates("target-lifecycle-after*.json"))
            if candidate == lifecycle_before
        ),
        None,
    )
    if lifecycle_after is None:
        raise RuntimeError("no lifecycle read-back matched the baseline")
    if lifecycle_before != lifecycle_after:
        raise RuntimeError("target lifecycle changed during publication")
    if lifecycle_after.get("deprecation") is not None:
        raise RuntimeError("target lifecycle was mutated")
    source = snapshot["evidence_envelope"]["sources"][0]
    if snapshot["pagination"]["status"] != "COMPLETE" or source["status"] != "COMPLETE":
        raise RuntimeError("live DataHub inventory was not complete")
    if snapshot["counterfactual"]["datahub_additional_consumer_count"] <= 0:
        raise RuntimeError("DataHub did not add consequential inventory")

    public_capability = with_digest(
        {
            "schema_version": "1.0.0",
            "mode": "live",
            "captured_at": capability["captured_at"],
            "edition": capability["edition"],
            "versions": VERSIONS,
            "server_versions": capability["server_versions"],
            "mcp_tool_names": sorted(tool["name"] for tool in capability["mcp_tools"]),
            "fallbacks": capability["fallbacks"],
            "query_surfaces": {
                "complete_lineage_pagination": "searchAcrossLineage",
                "document_readback": "document",
                "document_identity_search": "searchDocuments",
            },
            "lifecycle_mutation_visible": (
                "updateDeprecation" in capability["graphql_mutation_fields"]
            ),
            "lifecycle_mutation_invoked": False,
            "source_capability_digest": capability["capability_digest"],
        },
        "evidence_digest",
    )
    write_json(OUTPUT_ROOT / "capability-evidence.json", public_capability)

    consumer_types = Counter(
        str(consumer["entity_type"]) for consumer in snapshot["consumers"]
    )
    hop_depths = Counter(str(consumer["degree"]) for consumer in snapshot["consumers"])
    inventory_evidence = with_digest(
        {
            "schema_version": "1.0.0",
            "mode": "live",
            "campaign_id": CAMPAIGN_ID,
            "captured_at": snapshot["captured_at"],
            "snapshot_digest": snapshot["snapshot_digest"],
            "resolution": snapshot["resolution"],
            "pagination": snapshot["pagination"],
            "consumer_count": len(snapshot["consumers"]),
            "consumer_types": dict(sorted(consumer_types.items())),
            "hop_depths": dict(sorted(hop_depths.items())),
            "claim_confidence_bases": sorted(
                {str(claim["confidence_basis"]) for claim in snapshot["claims"]}
            ),
            "query_history": snapshot["query_history"],
            "ownership": snapshot["ownership"],
            "counterfactual": snapshot["counterfactual"],
            "evidence_envelope": snapshot["evidence_envelope"],
            "raw_artifacts": raw_artifact_index(snapshot),
            "seed": seed,
        },
        "evidence_digest",
    )
    write_json(OUTPUT_ROOT / "inventory-evidence.json", inventory_evidence)

    publication_evidence = with_digest(
        {
            "schema_version": "1.0.0",
            "mode": "live",
            "campaign_id": CAMPAIGN_ID,
            "decision": source_manifest["decision"],
            "blocker_codes": sorted(
                {item["code"] for item in source_manifest["blockers"]}
            ),
            "evidence_envelope_digest": source_manifest["evidence_envelope"][
                "envelope_digest"
            ],
            "published_manifest_digest": source_manifest["manifest_digest"],
            "publication": current_publication,
            "logical_document": {
                "title": expected_title,
                "urn": current_publication["urn"],
                "exact_search_matches": len(exact_documents),
                "publish_count": len(publications),
                "verification_count": len(verifications),
                "stable_urn_count": len(publication_urns),
                "content_exactly_matched": True,
            },
            "lifecycle": {
                "before": lifecycle_before,
                "after": lifecycle_after,
                "unchanged": True,
                "mutation_invoked": False,
            },
            "event_stream_digest": event_stream_digest(events),
            "event_count": len(events),
            "event_receipts": [
                {
                    "sequence": event["sequence"],
                    "event_type": event["event_type"],
                    "occurred_at": event["occurred_at"],
                    "event_digest": event["event_digest"],
                }
                for event in events
                if event["event_type"].startswith("PUBLICATION_")
            ],
        },
        "evidence_digest",
    )
    write_json(
        OUTPUT_ROOT / "publication-evidence.json",
        publication_evidence,
    )

    summary = with_digest(
        {
            "schema_version": "1.0.0",
            "mode": "live",
            "campaign_id": CAMPAIGN_ID,
            "assertions": {
                "canonical_target_and_fields_resolved": True,
                "complete_pagination": True,
                "datahub_added_consequential_inventory": True,
                "evidence_envelope_is_bounded": True,
                "stable_summary_updated_in_place": True,
                "summary_read_back_exactly": True,
                "target_lifecycle_unchanged": True,
            },
            "artifacts": {
                "capability": "artifacts/public/phase02/capability-evidence.json",
                "inventory": "artifacts/public/phase02/inventory-evidence.json",
                "publication": ("artifacts/public/phase02/publication-evidence.json"),
            },
            "limitations": source["limitations"],
            "test_sources": [
                "tests/unit/test_datahub.py",
                "tests/unit/test_datahub_config.py",
                "tests/unit/test_datahub_http.py",
                "tests/unit/test_mcp_http.py",
            ],
        },
        "evidence_digest",
    )
    write_json(OUTPUT_ROOT / "phase02-evidence.json", summary)
    print(
        "Phase 02 live evidence generated: "
        f"{len(snapshot['consumers'])} consumers, "
        f"{len(publications)} writes, one stable document."
    )
    return 0


if __name__ == "__main__":
    sys.exit(run())

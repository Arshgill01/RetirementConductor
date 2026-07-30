"""Reconstruct the exact canonical manifest written to DataHub."""

from __future__ import annotations

from typing import Any

from retirement_conductor.errors import Refusal
from retirement_conductor.events import manifest_from_projection, project_events
from retirement_conductor.store import CampaignStore
from retirement_conductor.vocabulary import RefusalCode


def publication_source_manifest(
    store: CampaignStore,
    campaign_id: str,
    content_digest: str,
) -> dict[str, Any]:
    """Rebuild the manifest immediately preceding its publication event."""

    events = store.events(campaign_id)
    for index in range(len(events) - 1, 0, -1):
        event = events[index]
        if (
            event["event_type"] == "PUBLICATION_RECORDED"
            and event["payload"]["publication"]["content_digest"] == content_digest
        ):
            manifest = manifest_from_projection(project_events(events[:index]))
            recorded = event["payload"]["publication"]["published_manifest_digest"]
            if manifest["manifest_digest"] != recorded:
                raise Refusal(
                    RefusalCode.INTEGRITY_MATERIALIZED_STATE_MISMATCH,
                    "The publication source manifest could not be reconstructed.",
                )
            return manifest
    raise Refusal(
        RefusalCode.EVIDENCE_PUBLICATION_MISMATCH,
        "The publication write receipt was not found in campaign history.",
    )

"""Reconstruct the exact canonical manifest written to DataHub."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from retirement_conductor.canonical import digest_json
from retirement_conductor.datahub import (
    DataHubBoundary,
    render_campaign_summary,
    utc_now,
)
from retirement_conductor.errors import Refusal
from retirement_conductor.events import manifest_from_projection, project_events
from retirement_conductor.store import CampaignStore
from retirement_conductor.vocabulary import RefusalCode


class CampaignPublicationWorkflow:
    """Write once and independently verify one canonical campaign summary."""

    def __init__(
        self,
        *,
        store: CampaignStore,
        boundary: DataHubBoundary,
        artifact_directory: Path,
    ) -> None:
        self.store = store
        self.boundary = boundary
        self.artifact_directory = artifact_directory

    def publish(
        self,
        campaign_id: str,
        *,
        occurred_at: str | None = None,
    ) -> dict[str, Any]:
        specification = self.store.specification(campaign_id)
        resolved = self.boundary.resolve_field_pair(
            specification["target"], specification["replacement"]
        )
        target_urn = str(resolved["dataset"]["urn"])
        manifest = self.store.materialize(campaign_id)
        content = render_campaign_summary(manifest)
        existing = manifest.get("publication")
        existing_urn = (
            str(existing["urn"])
            if isinstance(existing, Mapping) and isinstance(existing.get("urn"), str)
            else None
        )
        lifecycle_digest = digest_json(self.boundary.lifecycle(target_urn))
        receipt: dict[str, Any] | None = None
        resumed_artifacts: list[str] = []
        if existing_urn is not None:
            try:
                resumed = self.boundary.verify_summary(
                    campaign_id=campaign_id,
                    urn=existing_urn,
                    expected_content=content,
                    target_urn=target_urn,
                    expected_lifecycle_digest=lifecycle_digest,
                    artifact_root=self._artifact_root(campaign_id),
                )
            except Refusal as exc:
                if exc.code != RefusalCode.EVIDENCE_PUBLICATION_MISMATCH:
                    raise
            else:
                receipt = {
                    "urn": existing_urn,
                    "content_digest": resumed["content_digest"],
                    "artifact_ids": [
                        resumed["readback_artifact_id"],
                        resumed["search_artifact_id"],
                        resumed["lifecycle_artifact_id"],
                    ],
                }
                resumed_artifacts = list(receipt["artifact_ids"])
        if receipt is None:
            receipt = self.boundary.save_summary(
                campaign_id=campaign_id,
                target_urn=target_urn,
                content=content,
                existing_urn=existing_urn,
                artifact_root=self._artifact_root(campaign_id),
            )
        publication_record = {
            "logical_key": f"campaign/{campaign_id}",
            "urn": receipt["urn"],
            "content_digest": receipt["content_digest"],
            "published_manifest_digest": manifest["manifest_digest"],
            "lifecycle_digest_before": lifecycle_digest,
            "readback_verified": False,
        }
        updated = self.store.record_publication(
            campaign_id,
            publication_record,
            occurred_at=occurred_at or utc_now(),
            idempotency_key=f"publication-{str(receipt['content_digest'])[-16:]}",
        )
        return {
            "result": "PUBLISHED",
            "publication": updated["publication"],
            "write_artifact_ids": receipt["artifact_ids"],
            "write_resumed_from_readback": bool(resumed_artifacts),
            "manifest": updated,
        }

    def verify(
        self,
        campaign_id: str,
        *,
        occurred_at: str | None = None,
    ) -> dict[str, Any]:
        specification = self.store.specification(campaign_id)
        resolved = self.boundary.resolve_field_pair(
            specification["target"], specification["replacement"]
        )
        target_urn = str(resolved["dataset"]["urn"])
        manifest = self.store.materialize(campaign_id)
        publication_value = manifest.get("publication")
        if not isinstance(publication_value, Mapping):
            raise Refusal(
                RefusalCode.EVIDENCE_PUBLICATION_MISMATCH,
                "The campaign has no DataHub publication to verify.",
            )
        source_manifest = publication_source_manifest(
            self.store,
            campaign_id,
            str(publication_value["content_digest"]),
        )
        verification = self.boundary.verify_summary(
            campaign_id=campaign_id,
            urn=str(publication_value["urn"]),
            expected_content=render_campaign_summary(source_manifest),
            target_urn=target_urn,
            expected_lifecycle_digest=str(publication_value["lifecycle_digest_before"]),
            artifact_root=self._artifact_root(campaign_id),
        )
        if publication_value.get("readback_verified") is True:
            return {
                "result": "VERIFIED",
                "publication": dict(publication_value),
                "manifest": manifest,
            }
        verified_at = occurred_at or utc_now()
        updated = self.store.verify_publication(
            campaign_id,
            {
                "urn": publication_value["urn"],
                "content_digest": publication_value["content_digest"],
                "lifecycle_digest_after": verification["lifecycle_digest_after"],
                "readback_artifact_id": verification["readback_artifact_id"],
                "verified_at": verified_at,
            },
            occurred_at=verified_at,
            idempotency_key=(
                f"publication-verify-{str(publication_value['content_digest'])[-16:]}"
            ),
        )
        return {
            "result": "VERIFIED",
            "publication": updated["publication"],
            "manifest": updated,
        }

    def _artifact_root(self, campaign_id: str) -> Path:
        return self.artifact_directory / campaign_id / "datahub" / "publication"


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

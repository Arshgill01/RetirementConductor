from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from retirement_conductor.canonical import with_digest
from retirement_conductor.events import CampaignProjection, manifest_from_projection
from retirement_conductor.operator import (
    build_campaign_view,
    render_campaign_explain,
    render_campaign_html,
    render_campaign_inspect,
    safe_report_filename,
    write_campaign_report,
)
from retirement_conductor.policy import default_policy
from retirement_conductor.vocabulary import CampaignState

ROOT = Path(__file__).resolve().parents[2]
READY = ROOT / "artifacts/public/phase04/ready-manifest.json"
LATE = ROOT / "artifacts/public/phase04/late-manifest.json"


def load_manifest(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def redigest(manifest: dict[str, Any]) -> dict[str, Any]:
    return with_digest(
        {key: value for key, value in manifest.items() if key != "manifest_digest"},
        "manifest_digest",
    )


def review_manifest() -> dict[str, Any]:
    policy = default_policy()
    policy["allow_waivers"] = True
    return manifest_from_projection(
        CampaignProjection(
            campaign_id="review-campaign",
            name="Review one bounded waiver",
            state=CampaignState.RECONCILING,
            specification_digest=f"sha256:{'1' * 64}",
            target={"field": "legacy_status"},
            replacement={"field": "order_status"},
            policy=policy,
            input_digests={},
            evidence_envelope={
                "mode": "live",
                "sources": [
                    {
                        "id": "datahub",
                        "required": True,
                        "status": "COMPLETE",
                    }
                ],
            },
            inventory_consumer_ids=["consumer-one"],
            current_consumer_ids=["consumer-one"],
            consumers={
                "consumer-one": {
                    "id": "consumer-one",
                    "disposition": "WAIVED",
                    "receipt_digest": None,
                }
            },
            reconciled=True,
            generated_at="2026-01-01T00:00:00Z",
        )
    )


def test_terminal_and_html_share_canonical_ready_decision_and_digest() -> None:
    manifest = load_manifest(READY)
    view = build_campaign_view(manifest)

    inspect = render_campaign_inspect(view)
    explain = render_campaign_explain(view)
    report = render_campaign_html(view)

    assert "READY_TO_RETIRE" in inspect
    assert "analytics.commerce.orders_isolated.legacy_status" in inspect
    assert "1 total, 1 closed, 0 open" in inspect
    assert "Complete within declared scope" in inspect
    assert manifest["manifest_digest"] in inspect
    assert manifest["manifest_digest"] in explain
    assert manifest["manifest_digest"] in report
    assert 'data-export="local"' in report
    assert "This report never claims visibility beyond" in report


def test_live_refusal_explains_each_blocker_and_recovery() -> None:
    manifest = load_manifest(LATE)
    view = build_campaign_view(manifest)
    explain = render_campaign_explain(view)

    assert view["decision"] == "UNSAFE"
    assert view["counts"] == {
        "consumers": 2,
        "closed": 1,
        "open": 1,
        "blockers": 2,
        "reviews": 0,
        "conditions": 2,
        "receipts": 1,
    }
    assert "POLICY_CONSUMER_OPAQUE" in explain
    assert "RECONCILIATION_NEW_CONSUMER" in explain
    assert "Evidence source:" in explain
    assert "Recovery:" in explain
    assert "Migrate or resolve every unsafe consumer" in explain


def test_review_required_names_the_canonical_review_reason() -> None:
    manifest = review_manifest()
    view = build_campaign_view(manifest)
    inspect = render_campaign_inspect(view)
    explain = render_campaign_explain(view)
    report = render_campaign_html(view)

    assert "REVIEW_REQUIRED" in inspect
    assert "0 blockers, 1 reviews" in inspect
    assert "Review requirement · POLICY_WAIVER_REVIEW" in explain
    assert "An allowed waiver remains visibly reviewable." in report
    assert manifest["manifest_digest"] in report


def test_unknown_coverage_never_looks_complete() -> None:
    manifest = deepcopy(load_manifest(LATE))
    manifest["evidence_envelope"] = {
        "schema_version": "1.0.0",
        "mode": "live",
        "sources": [],
    }
    manifest = redigest(manifest)

    view = build_campaign_view(manifest)
    report = render_campaign_html(view)

    assert view["evidence"]["coverage"]["state"] == "UNKNOWN"
    assert "Unknown — no required source is recorded" in report
    assert "Complete within declared scope" not in report
    assert "empty inventory is not proof of absence" not in report.lower()


def test_stale_receipt_is_unmistakable_from_validated_receipt() -> None:
    manifest = deepcopy(load_manifest(READY))
    manifest["consumers"][0]["disposition"] = "STALE"
    manifest["decision"] = "UNSAFE"
    manifest["blockers"] = [
        {
            "code": "POLICY_CONSUMER_STALE",
            "message": "Consumer remains stale.",
        }
    ]
    manifest = redigest(manifest)

    view = build_campaign_view(manifest)
    report = render_campaign_html(view)

    consumer = view["consumers"][0]
    assert consumer["receipt_digest"] is not None
    assert consumer["receipt_state"].startswith("STALE —")
    assert "STALE — recorded receipt is not acceptable now" in report
    assert "VALIDATED — native receipt accepted" not in report


def test_report_escapes_untrusted_manifest_text() -> None:
    manifest = deepcopy(load_manifest(LATE))
    manifest["campaign"]["name"] = '<script>alert("campaign")</script>'
    manifest["target"]["field"] = "<img src=x onerror=alert(1)>"
    manifest = redigest(manifest)

    report = render_campaign_html(build_campaign_view(manifest))

    assert '<script>alert("campaign")</script>' not in report
    assert "&lt;script&gt;alert" in report
    assert "&lt;img src=x onerror=alert(1)&gt;" in report


def test_public_report_structurally_redacts_sensitive_source_material(
    tmp_path: Path,
) -> None:
    manifest = deepcopy(load_manifest(LATE))
    manifest["campaign"]["id"] = "private-campaign"
    manifest["campaign"]["name"] = "Private customer migration"
    manifest["target"]["field"] = "customer_secret_field"
    manifest["replacement"]["field"] = "new_customer_secret_field"
    manifest["evidence_envelope"]["sources"][0]["identity"] = (
        "https://private.example.internal"
    )
    manifest["evidence_envelope"]["sources"][0]["source_version"] = "private-v9"
    manifest["evidence_envelope"]["sources"][0]["permissions"]["principal"] = (
        "owner@example.internal"
    )
    manifest["evidence_envelope"]["sources"][0]["limitations"].append(
        "token=never-publish-this-value"
    )
    manifest["consumers"][0]["id"] = "owner@example.internal"
    manifest = redigest(manifest)
    output = tmp_path / "public.html"

    first = write_campaign_report(manifest, output, public=True)
    first_bytes = output.read_bytes()
    second = write_campaign_report(manifest, output, public=True)

    content = output.read_text(encoding="utf-8")
    assert first == second
    assert output.read_bytes() == first_bytes
    assert 'data-export="public"' in content
    assert "public-campaign" in content
    assert "legacy field → replacement field" in content
    for sensitive in (
        "private-campaign",
        "Private customer migration",
        "customer_secret_field",
        "new_customer_secret_field",
        "private.example.internal",
        "private-v9",
        "owner@example.internal",
        "never-publish-this-value",
    ):
        assert sensitive not in content


def test_report_filename_cannot_escape_output_directory() -> None:
    assert safe_report_filename("../../private campaign") == "private-campaign.html"

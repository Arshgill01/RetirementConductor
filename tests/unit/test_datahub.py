from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

from retirement_conductor.canonical import digest_json
from retirement_conductor.datahub import (
    ArtifactWriter,
    DataHubBoundary,
    build_envelope,
    normalize_consumers,
    parse_dataset_urn,
    redact_observation,
    render_campaign_summary,
    resolve_dataset_identity,
    resolve_schema_field,
)
from retirement_conductor.datahub_config import DataHubSettings
from retirement_conductor.errors import Refusal
from retirement_conductor.specification import load_specification
from retirement_conductor.store import CampaignStore
from retirement_conductor.vocabulary import EvidenceStatus

ROOT = Path(__file__).resolve().parents[2]
DATASET_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:snowflake,"
    "retirement_conductor.analytics.commerce.orders,PROD)"
)
CONSUMER_URNS = [
    "urn:li:dataset:(urn:li:dataPlatform:dbt,"
    "retirement_conductor.analytics.commerce.order_model,PROD)",
    "urn:li:chart:(looker,retirement-conductor-orders)",
    "urn:li:dashboard:(powerbi,retirement-conductor-executive)",
]
CAPTURED_AT = "2026-07-30T10:00:00Z"


class FakeMCP:
    def __init__(self, *, source_updated_at: str = CAPTURED_AT) -> None:
        self.source_updated_at = source_updated_at
        self.document_content = ""

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": name,
                "annotations": {"readOnlyHint": name != "save_document"},
                "inputSchema": {"type": "object"},
            }
            for name in [
                "search",
                "get_entities",
                "list_schema_fields",
                "get_lineage",
                "get_lineage_paths_between",
                "get_dataset_queries",
                "save_document",
            ]
        ]

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        if name == "search":
            return {
                "total": 1,
                "count": 1,
                "searchResults": [{"entity": {"urn": DATASET_URN}}],
            }
        if name == "list_schema_fields":
            return {
                "fields": [
                    {
                        "fieldPath": "legacy_status",
                        "nativeDataType": "VARCHAR",
                    },
                    {"fieldPath": "order_status", "nativeDataType": "VARCHAR"},
                ]
            }
        if name == "get_entities":
            urns = arguments["urns"]
            if urns == [DATASET_URN]:
                return [
                    {
                        "urn": DATASET_URN,
                        "properties": {
                            "customProperties": [
                                {
                                    "key": ("retirement_conductor.source_updated_at"),
                                    "value": self.source_updated_at,
                                }
                            ]
                        },
                        "ownership": {
                            "owners": [
                                {"owner": {"urn": "urn:li:corpuser:fixture-owner"}}
                            ]
                        },
                    }
                ]
            return [{"urn": urns[0], "info": {"text": self.document_content}}]
        if name == "get_lineage":
            return {"downstreams": [{"entity": {"urn": CONSUMER_URNS[0]}}]}
        if name == "get_lineage_paths_between":
            return {"paths": [[DATASET_URN, arguments["target_urn"]]]}
        if name == "get_dataset_queries":
            return {"start": 0, "count": 0, "total": 0, "queries": []}
        if name == "save_document":
            self.document_content = str(arguments["content"])
            return {
                "success": True,
                "urn": arguments.get(
                    "urn",
                    "urn:li:document:retirement-conductor-fixture",
                ),
            }
        raise AssertionError(name)


class FakeGraph:
    def __init__(self, *, mcp: FakeMCP | None = None) -> None:
        self.mcp = mcp

    def health(self) -> Any:
        return {"status": "ok"}

    def server_config(self) -> Any:
        return {"versions": {"acryldata/datahub-gms": {"version": "v1.6.0"}}}

    def graphql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        if "QueryCapabilities" in query:
            return {"__type": {"fields": [{"name": "searchAcrossLineage"}]}}
        if "MutationCapabilities" in query:
            return {"__type": {"fields": [{"name": "updateDeprecation"}]}}
        if "RetirementConductorLifecycle" in query:
            return {"dataset": {"urn": DATASET_URN, "deprecation": None}}
        if "RetirementConductorDocumentSearch" in query:
            campaign_id = "ret-orders-live-status"
            return {
                "searchDocuments": {
                    "start": 0,
                    "count": 10,
                    "total": 1,
                    "documents": [
                        {
                            "urn": ("urn:li:document:retirement-conductor-fixture"),
                            "info": {
                                "title": (f"Retirement Conductor — {campaign_id}")
                            },
                        }
                    ],
                }
            }
        if "RetirementConductorDocument" in query:
            content = "" if self.mcp is None else self.mcp.document_content
            return {
                "document": {
                    "urn": variables["urn"],
                    "info": {"contents": {"text": content}},
                }
            }
        if "RetirementConductorLineage" in query:
            offset = variables["input"]["start"]
            count = variables["input"]["count"]
            selected = CONSUMER_URNS[offset : offset + count]
            return {
                "searchAcrossLineage": {
                    "start": offset,
                    "count": len(selected),
                    "total": len(CONSUMER_URNS),
                    "isPartial": False,
                    "searchResults": [
                        {
                            "degree": 1 if offset == 0 else 2,
                            "entity": {
                                "urn": urn,
                                "type": (
                                    "DATASET"
                                    if "dataset:" in urn
                                    else "DASHBOARD"
                                    if "dashboard:" in urn
                                    else "CHART"
                                ),
                            },
                        }
                        for urn in selected
                    ],
                }
            }
        raise AssertionError(query)


def settings() -> DataHubSettings:
    return DataHubSettings(
        gms_url="http://127.0.0.1:18080",
        mcp_url="http://127.0.0.1:8000/mcp",
        token=None,
        token_reference="DATAHUB_GMS_TOKEN",
        principal="anonymous-disposable-core",
        environment="PROD",
        page_size=2,
        timeout_seconds=1,
    )


def live_specification() -> dict[str, Any]:
    specification = copy.deepcopy(
        load_specification(ROOT / "fixtures/specs/valid.yaml")
    )
    for key in ("target", "replacement"):
        specification[key].update(
            {
                "platform": "snowflake",
                "instance": "retirement_conductor",
                "database": "analytics",
                "schema": "commerce",
                "table": "orders",
            }
        )
    specification["evidence"]["datahub"]["max_hops"] = 3
    return specification


def test_preflight_records_versions_tools_and_fallbacks() -> None:
    boundary = DataHubBoundary(settings(), mcp=FakeMCP(), graph=FakeGraph())

    result = boundary.preflight(captured_at=CAPTURED_AT)

    assert result["edition"] == "core"
    assert result["server_versions"]["versions.acryldata/datahub-gms.version"] == (
        "v1.6.0"
    )
    assert result["fallbacks"]["complete_lineage_pagination"] == "gms_graphql"
    assert result["configuration"]["token_present"] is False


def test_live_inventory_pages_to_total_and_keeps_weak_edges_qualified(
    tmp_path: Path,
) -> None:
    boundary = DataHubBoundary(settings(), mcp=FakeMCP(), graph=FakeGraph())

    snapshot = boundary.inventory(
        live_specification(),
        artifact_root=tmp_path,
        captured_at=CAPTURED_AT,
    )

    assert snapshot["pagination"] == {
        "status": "COMPLETE",
        "reported_total": 3,
        "returned_total": 3,
        "pages": 2,
        "errors": [],
    }
    assert len(snapshot["consumers"]) == 3
    assert snapshot["query_history"]["total"] == 0
    assert snapshot["query_history"]["closure_authority"] is False
    assert snapshot["ownership"]["routing_only"] is True
    assert any(
        claim["confidence_basis"] == "canonical_lineage_edge" and claim["limitations"]
        for claim in snapshot["claims"]
    )
    assert snapshot["counterfactual"]["datahub_additional_consumer_count"] == 3


def test_forced_page_failure_and_stale_source_fail_closed(tmp_path: Path) -> None:
    boundary = DataHubBoundary(settings(), mcp=FakeMCP(), graph=FakeGraph())
    partial = boundary.inventory(
        live_specification(),
        artifact_root=tmp_path / "partial",
        captured_at=CAPTURED_AT,
        forced_failure_offset=2,
    )
    assert partial["pagination"]["status"] == "PARTIAL"
    assert partial["evidence_envelope"]["sources"][0]["status"] == "PARTIAL"

    stale_boundary = DataHubBoundary(
        settings(),
        mcp=FakeMCP(source_updated_at="2026-07-29T10:00:00Z"),
        graph=FakeGraph(),
    )
    stale = stale_boundary.inventory(
        live_specification(),
        artifact_root=tmp_path / "stale",
        captured_at=CAPTURED_AT,
    )
    assert stale["pagination"]["status"] == "STALE"
    assert stale["evidence_envelope"]["sources"][0]["status"] == "STALE"


@pytest.mark.parametrize(
    ("changed", "value"),
    [
        ("table", "ORDERS"),
        ("table", '"orders"'),
        ("instance", "another_instance"),
        ("database", "Analytics"),
    ],
)
def test_identity_variants_cannot_authorize_a_guess(
    changed: str,
    value: str,
) -> None:
    declared = {
        "platform": "snowflake",
        "instance": "retirement_conductor",
        "database": "analytics",
        "schema": "commerce",
        "table": "orders",
    }
    declared[changed] = value

    with pytest.raises(Refusal, match="IDENTITY_NOT_FOUND"):
        resolve_dataset_identity([DATASET_URN], declared, environment="PROD")


def test_duplicate_display_names_do_not_create_identity_matches() -> None:
    parsed = parse_dataset_urn(DATASET_URN)
    assert parsed is not None
    declared = {
        "platform": parsed.platform,
        "instance": parsed.instance,
        "database": parsed.database,
        "schema": parsed.schema,
        "table": parsed.table,
    }
    unrelated_same_display_name = (
        "urn:li:dataset:(urn:li:dataPlatform:looker,"
        "retirement_conductor.analytics.commerce.orders,PROD)"
    )

    resolved = resolve_dataset_identity(
        [unrelated_same_display_name, DATASET_URN],
        declared,
        environment="PROD",
    )

    assert resolved.urn == DATASET_URN


def test_missing_and_duplicate_schema_fields_refuse() -> None:
    with pytest.raises(Refusal, match="IDENTITY_FIELD_NOT_FOUND"):
        resolve_schema_field([], "legacy_status")
    duplicate = [
        {"fieldPath": "legacy_status"},
        {"fieldPath": "legacy_status"},
    ]
    with pytest.raises(Refusal, match="IDENTITY_FIELD_AMBIGUOUS"):
        resolve_schema_field(duplicate, "legacy_status")


def test_publication_event_is_stable_and_requires_unchanged_lifecycle(
    tmp_path: Path,
) -> None:
    specification = live_specification()
    database = tmp_path / "campaign.sqlite"
    with CampaignStore(database, writer_id="writer-one") as store:
        manifest = store.create_campaign(
            specification,
            occurred_at="2026-07-30T09:00:00Z",
        )
        content = render_campaign_summary(manifest)
        lifecycle_digest = digest_json({"urn": DATASET_URN, "deprecation": None})
        publication = {
            "logical_key": f"campaign/{specification['campaign']['id']}",
            "urn": "urn:li:document:retirement-conductor-fixture",
            "content_digest": digest_json(content),
            "published_manifest_digest": manifest["manifest_digest"],
            "lifecycle_digest_before": lifecycle_digest,
            "readback_verified": False,
        }
        published = store.record_publication(
            specification["campaign"]["id"],
            publication,
            occurred_at="2026-07-30T09:01:00Z",
            idempotency_key="publication",
        )
        assert published["publication"]["urn"] == publication["urn"]
        verified = store.verify_publication(
            specification["campaign"]["id"],
            {
                "urn": publication["urn"],
                "content_digest": publication["content_digest"],
                "lifecycle_digest_after": lifecycle_digest,
                "readback_artifact_id": f"sha256:{'1' * 64}",
                "verified_at": "2026-07-30T09:02:00Z",
            },
            occurred_at="2026-07-30T09:02:00Z",
            idempotency_key="verify-publication",
        )
        assert verified["publication"]["readback_verified"] is True


def test_summary_write_updates_one_urn_and_reads_back_exact_content(
    tmp_path: Path,
) -> None:
    mcp = FakeMCP()
    boundary = DataHubBoundary(settings(), mcp=mcp, graph=FakeGraph(mcp=mcp))
    first = boundary.save_summary(
        campaign_id="ret-orders-live-status",
        target_urn=DATASET_URN,
        content="first summary",
        existing_urn=None,
        artifact_root=tmp_path,
    )
    second = boundary.save_summary(
        campaign_id="ret-orders-live-status",
        target_urn=DATASET_URN,
        content="updated summary",
        existing_urn=first["urn"],
        artifact_root=tmp_path,
    )

    assert second["urn"] == first["urn"]
    verified = boundary.verify_summary(
        campaign_id="ret-orders-live-status",
        urn=second["urn"],
        expected_content="updated summary",
        target_urn=DATASET_URN,
        expected_lifecycle_digest=digest_json(
            {"urn": DATASET_URN, "deprecation": None}
        ),
        artifact_root=tmp_path,
    )
    assert verified["content_digest"] == second["content_digest"]


def test_envelope_schema_rejects_no_artifact_fabrication() -> None:
    envelope = build_envelope(
        captured_at=CAPTURED_AT,
        status=EvidenceStatus.COMPLETE,
        required=True,
        source_version="v1.6.0",
        identity="disposable-core",
        max_hops=3,
        filters=[],
        page_count=0,
        reported_total=0,
        returned_total=0,
        source_updated_at=None,
        maximum_age_seconds=900,
        principal="anonymous",
        limitations=["empty results do not prove absence"],
        artifact_ids=[],
    )
    assert envelope["sources"][0]["limitations"]


def test_normalized_owner_or_table_claim_never_closes_consumer() -> None:
    consumers, claims = normalize_consumers(
        [
            {
                "urn": CONSUMER_URNS[1],
                "entity_type": "CHART",
                "degree": 2,
                "raw_artifact_id": f"sha256:{'1' * 64}",
            }
        ],
        target_urn=DATASET_URN,
        target_field="legacy_status",
        field_lineage_urns=set(),
        observed_at=CAPTURED_AT,
        source_version="v1.6.0",
    )
    assert consumers[0]["disposition"] == "OPAQUE"
    assert claims[0]["confidence_basis"] == "canonical_lineage_edge"
    assert claims[0]["limitations"]


def test_raw_artifacts_are_content_addressed_and_query_text_is_redacted(
    tmp_path: Path,
) -> None:
    writer = ArtifactWriter(tmp_path)
    first = writer.write("query-observation", {"query": "select private_value"})
    second = writer.write("query-observation", {"query": "select another_value"})

    assert first != second
    assert len(list(tmp_path.glob("query-observation-*.json"))) == 2
    rendered = "\n".join(
        path.read_text(encoding="utf-8")
        for path in tmp_path.glob("query-observation-*.json")
    )
    assert "private_value" not in rendered
    assert "another_value" not in rendered
    assert redact_observation({"query": "select secret"})["query"]["redacted"] is True

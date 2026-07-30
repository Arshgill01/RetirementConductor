"""DataHub identity, inventory, evidence-envelope, and publication boundary."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar, Protocol

from retirement_conductor.canonical import (
    canonical_json,
    digest_bytes,
    digest_file,
    digest_json,
    with_digest,
    write_json,
)
from retirement_conductor.datahub_config import DataHubSettings
from retirement_conductor.errors import Refusal
from retirement_conductor.schemas import validate_schema
from retirement_conductor.vocabulary import EvidenceStatus, RefusalCode

LINEAGE_QUERY = """
query RetirementConductorLineage($input: SearchAcrossLineageInput!) {
  searchAcrossLineage(input: $input) {
    start
    count
    total
    isPartial
    searchResults {
      degree
      entity {
        urn
        type
      }
    }
  }
}
"""

LIFECYCLE_QUERY = """
query RetirementConductorLifecycle($urn: String!) {
  dataset(urn: $urn) {
    urn
    deprecation {
      deprecated
      decommissionTime
      note
      actor
      replacement {
        urn
        type
      }
    }
  }
}
"""

DOCUMENT_QUERY = """
query RetirementConductorDocument($urn: String!) {
  document(urn: $urn) {
    urn
    info {
      contents {
        text
      }
    }
  }
}
"""

DOCUMENT_SEARCH_QUERY = """
query RetirementConductorDocumentSearch($input: SearchDocumentsInput!) {
  searchDocuments(input: $input) {
    start
    count
    total
    documents {
      urn
      info {
        title
      }
    }
  }
}
"""

QUERY_CAPABILITY_QUERY = """
query RetirementConductorQueryCapabilities {
  __type(name: "Query") {
    fields { name }
  }
}
"""

MUTATION_CAPABILITY_QUERY = """
query RetirementConductorMutationCapabilities {
  __type(name: "Mutation") {
    fields { name }
  }
}
"""

EMAIL_PATTERN = re.compile(r"(?i)[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}")


class MCPClient(Protocol):
    def list_tools(self) -> list[dict[str, Any]]: ...

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any: ...


class GraphClient(Protocol):
    def health(self) -> Any: ...

    def server_config(self) -> Any: ...

    def graphql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]: ...


@dataclass(frozen=True)
class DatasetIdentity:
    urn: str
    platform: str
    instance: str
    database: str
    schema: str
    table: str
    environment: str


@dataclass
class PageResult:
    status: EvidenceStatus
    pages: list[dict[str, Any]]
    consumers: list[dict[str, Any]]
    reported_total: int
    returned_total: int
    limitations: list[str]
    errors: list[dict[str, Any]]


class ArtifactWriter:
    """Write redacted raw evidence and return content-addressed references."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def write(self, name: str, value: Any, *, redact: bool = True) -> str:
        safe_value = redact_observation(value) if redact else value
        identity = digest_json(safe_value).removeprefix("sha256:")[:16]
        path = self.root / f"{name}-{identity}.json"
        write_json(path, safe_value)
        return digest_file(path)


class DataHubBoundary:
    """Fail-closed DataHub evidence boundary with explicit fallback surfaces."""

    REQUIRED_READ_TOOLS: ClassVar[set[str]] = {
        "search",
        "get_entities",
        "list_schema_fields",
        "get_lineage",
    }

    def __init__(
        self,
        settings: DataHubSettings,
        *,
        mcp: MCPClient,
        graph: GraphClient,
    ) -> None:
        self.settings = settings
        self.mcp = mcp
        self.graph = graph

    def preflight(self, *, captured_at: str | None = None) -> dict[str, Any]:
        """Inspect the live server and retain only safe capability metadata."""

        observed_at = captured_at or utc_now()
        health = self.graph.health()
        config = self.graph.server_config()
        tools = self.mcp.list_tools()
        tool_summary = [
            {
                "name": str(tool.get("name", "")),
                "read_only": bool(
                    (tool.get("annotations") or {}).get("readOnlyHint", False)
                ),
                "input_schema_digest": digest_json(tool.get("inputSchema") or {}),
            }
            for tool in tools
        ]
        tool_names = {item["name"] for item in tool_summary}
        missing = sorted(self.REQUIRED_READ_TOOLS - tool_names)
        if missing:
            raise Refusal(
                RefusalCode.SOURCE_DATAHUB_UNAVAILABLE,
                "The live MCP server lacks required DataHub read tools.",
                {"missing_tools": missing},
            )
        query_schema = self.graph.graphql(QUERY_CAPABILITY_QUERY, {})
        mutation_schema = self.graph.graphql(MUTATION_CAPABILITY_QUERY, {})
        query_type = query_schema.get("__type")
        mutation_type = mutation_schema.get("__type")
        if not isinstance(query_type, dict) or not isinstance(mutation_type, dict):
            raise Refusal(
                RefusalCode.SOURCE_DATAHUB_UNAVAILABLE,
                "DataHub GraphQL capability introspection was unavailable.",
            )
        query_names = _field_names(query_type)
        mutation_names = _field_names(mutation_type)
        fingerprint = with_digest(
            {
                "schema_version": "1.0.0",
                "captured_at": observed_at,
                "edition": "core",
                "configuration": self.settings.safe_summary(),
                "health_digest": digest_json(redact_observation(health)),
                "server_versions": extract_versions(config),
                "mcp_tools": sorted(tool_summary, key=lambda item: item["name"]),
                "graphql_query_fields": query_names,
                "graphql_mutation_fields": mutation_names,
                "fallbacks": {
                    "complete_lineage_pagination": "gms_graphql",
                    "document_writeback": (
                        "mcp_save_document"
                        if "save_document" in tool_names
                        else "unavailable"
                    ),
                },
                "cloud_only_capabilities": "not_required",
            },
            "capability_digest",
        )
        return fingerprint

    def resolve_field_pair(
        self,
        target: Mapping[str, Any],
        replacement: Mapping[str, Any],
        *,
        writer: ArtifactWriter | None = None,
    ) -> dict[str, Any]:
        """Resolve an exact live dataset and verify both declared schema fields."""

        raw_artifact_ids: list[str] = []
        target_candidates = self._candidate_urns(
            target,
            writer=writer,
            artifact_prefix="target-search",
            artifact_ids=raw_artifact_ids,
        )
        target_identity = resolve_dataset_identity(
            target_candidates,
            target,
            environment=self.settings.environment,
        )
        replacement_candidates = (
            target_candidates
            if _same_native_dataset(target, replacement)
            else self._candidate_urns(
                replacement,
                writer=writer,
                artifact_prefix="replacement-search",
                artifact_ids=raw_artifact_ids,
            )
        )
        replacement_identity = resolve_dataset_identity(
            replacement_candidates,
            replacement,
            environment=self.settings.environment,
        )
        if target_identity.urn != replacement_identity.urn:
            raise Refusal(
                RefusalCode.SPEC_UNSUPPORTED_REPLACEMENT,
                "The initial DataHub adapter supports fields on one canonical dataset.",
            )
        fields = self._schema_fields(
            target_identity.urn,
            writer=writer,
            artifact_ids=raw_artifact_ids,
        )
        target_field = resolve_schema_field(fields, str(target["field"]))
        replacement_field = resolve_schema_field(fields, str(replacement["field"]))
        if (
            target_field.get("nativeDataType")
            and replacement_field.get("nativeDataType")
            and target_field["nativeDataType"] != replacement_field["nativeDataType"]
        ):
            raise Refusal(
                RefusalCode.SPEC_REPLACEMENT_INCOMPATIBLE,
                "The live target and replacement fields have different native types.",
                {
                    "target_type": target_field["nativeDataType"],
                    "replacement_type": replacement_field["nativeDataType"],
                },
            )
        return {
            "dataset": {
                "urn": target_identity.urn,
                "platform": target_identity.platform,
                "instance": target_identity.instance,
                "database": target_identity.database,
                "schema": target_identity.schema,
                "table": target_identity.table,
                "environment": target_identity.environment,
            },
            "target_field": target_field,
            "replacement_field": replacement_field,
            "raw_artifact_ids": sorted(set(raw_artifact_ids)),
        }

    def _candidate_urns(
        self,
        declared: Mapping[str, Any],
        *,
        writer: ArtifactWriter | None,
        artifact_prefix: str,
        artifact_ids: list[str],
    ) -> list[str]:
        supplied = declared.get("datahub_urn")
        if supplied:
            return [str(supplied)]
        offset = 0
        candidates: list[str] = []
        while True:
            response = self.mcp.call_tool(
                "search",
                {
                    "query": f"/q {declared['table']}",
                    "filter": (
                        f"entity_type = dataset AND platform = {declared['platform']} "
                        f"AND env = {self.settings.environment}"
                    ),
                    "num_results": 50,
                    "offset": offset,
                },
            )
            if not isinstance(response, dict):
                raise Refusal(
                    RefusalCode.SOURCE_DATAHUB_UNAVAILABLE,
                    "The live DataHub search response was malformed.",
                )
            if writer is not None:
                artifact_ids.append(
                    writer.write(f"{artifact_prefix}-{offset:05d}", response)
                )
            results = response.get("searchResults") or []
            if not isinstance(results, list):
                raise Refusal(
                    RefusalCode.SOURCE_DATAHUB_UNAVAILABLE,
                    "The live DataHub search result list was malformed.",
                )
            page_urns = sorted(set(collect_entity_urns(results)))
            candidates.extend(page_urns)
            total = _integer(response.get("total"), len(candidates))
            returned = len(results)
            offset += returned
            if returned == 0 and offset < total:
                raise Refusal(
                    RefusalCode.EVIDENCE_PAGINATION_FAILED,
                    "DataHub identity search ended before its advertised total.",
                    {"offset": offset, "reported_total": total},
                )
            if returned == 0 or offset >= total:
                break
            if offset > 10_000:
                raise Refusal(
                    RefusalCode.EVIDENCE_PAGINATION_FAILED,
                    "DataHub identity search exceeded its bounded result limit.",
                )
        return sorted(set(candidates))

    def _schema_fields(
        self,
        urn: str,
        *,
        writer: ArtifactWriter | None,
        artifact_ids: list[str],
    ) -> list[Any]:
        offset = 0
        limit = 100
        fields: list[Any] = []
        while True:
            schema = self.mcp.call_tool(
                "list_schema_fields",
                {"urn": urn, "limit": limit, "offset": offset},
            )
            if not isinstance(schema, dict):
                raise Refusal(
                    RefusalCode.SOURCE_DATAHUB_UNAVAILABLE,
                    "The live schema-field response was malformed.",
                )
            if writer is not None:
                artifact_ids.append(writer.write(f"schema-fields-{offset:05d}", schema))
            page = schema.get("fields")
            if not isinstance(page, list):
                raise Refusal(
                    RefusalCode.SOURCE_DATAHUB_UNAVAILABLE,
                    "The live schema-field response omitted fields.",
                )
            fields.extend(page)
            reported_total = _integer(schema.get("total"), len(fields))
            offset += len(page)
            if not page and offset < reported_total:
                raise Refusal(
                    RefusalCode.EVIDENCE_PAGINATION_FAILED,
                    "DataHub schema paging ended before its advertised total.",
                    {"offset": offset, "reported_total": reported_total},
                )
            if not page or offset >= reported_total:
                break
            if offset > 100_000:
                raise Refusal(
                    RefusalCode.EVIDENCE_PAGINATION_FAILED,
                    "DataHub schema paging exceeded its bounded field limit.",
                )
        return fields

    def lifecycle(self, urn: str) -> dict[str, Any]:
        result = self.graph.graphql(LIFECYCLE_QUERY, {"urn": urn})
        dataset = result.get("dataset")
        if not isinstance(dataset, dict) or dataset.get("urn") != urn:
            raise Refusal(
                RefusalCode.IDENTITY_NOT_FOUND,
                "The resolved target could not be read through DataHub GraphQL.",
            )
        return {
            "urn": urn,
            "deprecation": dataset.get("deprecation"),
        }

    def page_downstream(
        self,
        urn: str,
        *,
        max_hops: int,
        writer: ArtifactWriter,
        forced_failure_offset: int | None = None,
    ) -> PageResult:
        """Page to the advertised total and retain every raw response."""

        offset = 0
        expected_total: int | None = None
        pages: list[dict[str, Any]] = []
        consumers: list[dict[str, Any]] = []
        limitations: list[str] = []
        errors: list[dict[str, Any]] = []
        status = EvidenceStatus.COMPLETE
        seen: set[str] = set()
        while True:
            try:
                if (
                    forced_failure_offset is not None
                    and offset == forced_failure_offset
                ):
                    raise Refusal(
                        RefusalCode.EVIDENCE_PAGINATION_FAILED,
                        "A controlled pagination failure was injected.",
                        {"offset": offset},
                    )
                data = self.graph.graphql(
                    LINEAGE_QUERY,
                    {
                        "input": {
                            "urn": urn,
                            "direction": "DOWNSTREAM",
                            "query": "*",
                            "start": offset,
                            "count": self.settings.page_size,
                            "orFilters": [
                                {
                                    "and": [
                                        {
                                            "field": "degree",
                                            "condition": "EQUAL",
                                            "values": degree_values(max_hops),
                                        }
                                    ]
                                }
                            ],
                            "searchFlags": {
                                "skipHighlighting": True,
                                "maxAggValues": 100,
                            },
                        }
                    },
                )
                page = data.get("searchAcrossLineage")
                if not isinstance(page, dict):
                    raise Refusal(
                        RefusalCode.EVIDENCE_PAGINATION_FAILED,
                        "DataHub omitted a lineage page.",
                        {"offset": offset},
                    )
                page_artifact = writer.write(f"lineage-page-{offset:05d}", page)
                page_record = {
                    "offset": offset,
                    "artifact_id": page_artifact,
                    **page,
                }
                pages.append(page_record)
                total = _integer(page.get("total"), 0)
                if expected_total is None:
                    expected_total = total
                elif total != expected_total:
                    status = EvidenceStatus.PARTIAL
                    limitations.append(
                        "DataHub changed the advertised total while paging"
                    )
                if page.get("isPartial") is True:
                    status = EvidenceStatus.PARTIAL
                    limitations.append("DataHub marked a lineage page partial")
                elif page.get("isPartial") is None:
                    limitations.append("DataHub Core did not expose isPartial")
                results = page.get("searchResults") or []
                if not isinstance(results, list):
                    raise Refusal(
                        RefusalCode.EVIDENCE_PAGINATION_FAILED,
                        "DataHub returned malformed lineage results.",
                        {"offset": offset},
                    )
                for item in results:
                    if not isinstance(item, dict):
                        continue
                    entity = item.get("entity")
                    if not isinstance(entity, dict) or not isinstance(
                        entity.get("urn"), str
                    ):
                        continue
                    consumer_urn = str(entity["urn"])
                    if consumer_urn in seen:
                        status = EvidenceStatus.PARTIAL
                        limitations.append("DataHub repeated a consumer across pages")
                        continue
                    seen.add(consumer_urn)
                    consumers.append(
                        {
                            "urn": consumer_urn,
                            "entity_type": str(entity.get("type", "UNKNOWN")),
                            "degree": item.get("degree"),
                            "raw_artifact_id": page_artifact,
                        }
                    )
                returned = len(results)
                offset += returned
                if offset >= (expected_total or 0):
                    break
                if returned == 0:
                    status = EvidenceStatus.PARTIAL
                    limitations.append(
                        "DataHub returned an empty page before its advertised total"
                    )
                    break
            except Refusal as exc:
                status = EvidenceStatus.PARTIAL
                errors.append(
                    {
                        "offset": offset,
                        "refusal_code": str(exc.code),
                        "message": exc.message,
                    }
                )
                limitations.append("A required lineage page failed")
                break
        if len(consumers) != (expected_total or 0):
            status = EvidenceStatus.PARTIAL
            limitations.append(
                "Returned consumers did not match DataHub's advertised total"
            )
        return PageResult(
            status=status,
            pages=pages,
            consumers=consumers,
            reported_total=expected_total or 0,
            returned_total=len(consumers),
            limitations=sorted(set(limitations)),
            errors=errors,
        )

    def inventory(
        self,
        specification: Mapping[str, Any],
        *,
        artifact_root: Path,
        captured_at: str | None = None,
        forced_failure_offset: int | None = None,
    ) -> dict[str, Any]:
        """Collect and normalize one complete evidence-bounded live snapshot."""

        observed_at = captured_at or utc_now()
        writer = ArtifactWriter(artifact_root)
        resolved = self.resolve_field_pair(
            specification["target"],
            specification["replacement"],
            writer=writer,
        )
        target_urn = str(resolved["dataset"]["urn"])
        entity_details = self.mcp.call_tool("get_entities", {"urns": [target_urn]})
        entity_artifact = writer.write("target-entity", entity_details)
        field_lineage = self.mcp.call_tool(
            "get_lineage",
            {
                "urn": target_urn,
                "column": specification["target"]["field"],
                "upstream": False,
                "max_hops": min(
                    int(specification["evidence"]["datahub"]["max_hops"]), 3
                ),
                "max_results": 100,
                "offset": 0,
                "query": "*",
            },
        )
        field_lineage_artifact = writer.write("field-lineage", field_lineage)
        field_lineage_urns = set(collect_entity_urns(field_lineage))
        max_hops = int(specification["evidence"]["datahub"]["max_hops"])
        paged = self.page_downstream(
            target_urn,
            max_hops=max_hops,
            writer=writer,
            forced_failure_offset=forced_failure_offset,
        )
        query_history = self.mcp.call_tool(
            "get_dataset_queries",
            {
                "urn": target_urn,
                "column": specification["target"]["field"],
                "start": 0,
                "count": 100,
            },
        )
        query_artifact = writer.write("query-history-redacted", query_history)
        lifecycle = self.lifecycle(target_urn)
        lifecycle_artifact = writer.write("target-lifecycle-before", lifecycle)
        path_artifact: str | None = None
        selected_consumer = _selected_consequential_consumer(paged.consumers)
        if selected_consumer is not None:
            try:
                path = self.mcp.call_tool(
                    "get_lineage_paths_between",
                    {
                        "source_urn": target_urn,
                        "target_urn": selected_consumer["urn"],
                        "direction": "downstream",
                    },
                )
                path_artifact = writer.write("selected-lineage-path", path)
            except Refusal:
                paged.limitations.append(
                    "The selected exact lineage path was unavailable through MCP"
                )
        consumers, claims = normalize_consumers(
            paged.consumers,
            target_urn=target_urn,
            target_field=str(specification["target"]["field"]),
            field_lineage_urns=field_lineage_urns,
            observed_at=observed_at,
            source_version=self.source_version(),
        )
        source_updated_at = source_updated_from_entity(entity_details)
        maximum_age = int(specification["evidence"]["datahub"]["maximum_age_seconds"])
        status = paged.status
        freshness_limitations: list[str] = []
        if source_updated_at is None:
            freshness_limitations.append(
                "DataHub did not expose a source ingestion update timestamp"
            )
        elif timestamp_age_seconds(source_updated_at, observed_at) > maximum_age:
            status = EvidenceStatus.STALE
            freshness_limitations.append(
                "The source ingestion timestamp exceeded the freshness policy"
            )
        raw_artifact_ids = [
            *resolved["raw_artifact_ids"],
            entity_artifact,
            field_lineage_artifact,
            query_artifact,
            lifecycle_artifact,
            *(str(page["artifact_id"]) for page in paged.pages),
        ]
        if path_artifact is not None:
            raw_artifact_ids.append(path_artifact)
        limitations = sorted(
            set(
                [
                    *paged.limitations,
                    *freshness_limitations,
                    "Ownership is routing context only",
                    "Query-history absence is not closure evidence",
                    "Table-only lineage cannot authorize field mutation or closure",
                ]
            )
        )
        envelope = build_envelope(
            captured_at=observed_at,
            status=status,
            required=bool(specification["evidence"]["datahub"]["required"]),
            source_version=self.source_version(),
            identity=self.settings.gms_url,
            max_hops=max_hops,
            filters=list(specification["evidence"]["datahub"]["platform_filters"]),
            page_count=len(paged.pages),
            reported_total=paged.reported_total,
            returned_total=paged.returned_total,
            source_updated_at=source_updated_at,
            maximum_age_seconds=maximum_age,
            principal=self.settings.principal,
            limitations=limitations,
            artifact_ids=raw_artifact_ids,
        )
        ownership = extract_ownership(entity_details)
        snapshot = with_digest(
            {
                "schema_version": "1.0.0",
                "campaign_id": specification["campaign"]["id"],
                "captured_at": observed_at,
                "resolution": resolved,
                "consumers": consumers,
                "claims": claims,
                "query_history": query_history_summary(query_history),
                "ownership": {
                    "routing_only": True,
                    "observations": ownership,
                },
                "lifecycle": lifecycle,
                "pagination": {
                    "status": status,
                    "reported_total": paged.reported_total,
                    "returned_total": paged.returned_total,
                    "pages": len(paged.pages),
                    "errors": paged.errors,
                },
                "counterfactual": {
                    "datahub_additional_consumer_count": len(consumers),
                    "without_datahub_actionable_consumer_count": 0,
                },
                "evidence_envelope": envelope,
                "raw_artifact_ids": sorted(set(raw_artifact_ids)),
            },
            "snapshot_digest",
        )
        validate_schema(
            "datahub-snapshot",
            snapshot,
            refusal_code=RefusalCode.INTEGRITY_DIGEST_MISMATCH,
        )
        snapshot_identity = snapshot["snapshot_digest"].removeprefix("sha256:")[:16]
        write_json(
            artifact_root / f"snapshot-{snapshot_identity}.json",
            snapshot,
        )
        write_json(artifact_root / "snapshot.json", snapshot)
        return snapshot

    def source_version(self) -> str:
        versions = extract_versions(self.graph.server_config())
        return (
            canonical_json(versions)
            if versions
            else "DataHub Core version not reported"
        )

    def save_summary(
        self,
        *,
        campaign_id: str,
        target_urn: str,
        content: str,
        existing_urn: str | None,
        artifact_root: Path,
    ) -> dict[str, Any]:
        arguments: dict[str, Any] = {
            "document_type": "Summary",
            "title": f"Retirement Conductor — {campaign_id}",
            "content": content,
            "topics": ["retirement-conductor", campaign_id],
            "related_assets": [target_urn],
        }
        if existing_urn is not None:
            arguments["urn"] = existing_urn
        writer = ArtifactWriter(artifact_root)
        request_artifact = writer.write("publication-request", arguments)
        response = self.mcp.call_tool("save_document", arguments)
        response_artifact = writer.write("publication-response", response)
        if (
            not isinstance(response, dict)
            or response.get("success") is not True
            or not isinstance(response.get("urn"), str)
        ):
            raise Refusal(
                RefusalCode.SOURCE_DATAHUB_UNAVAILABLE,
                "DataHub did not confirm the campaign summary write.",
            )
        urn = str(response["urn"])
        if existing_urn is not None and urn != existing_urn:
            raise Refusal(
                RefusalCode.EVIDENCE_PUBLICATION_MISMATCH,
                "DataHub changed the stable campaign summary identity.",
            )
        return {
            "urn": urn,
            "content_digest": digest_bytes(content.encode()),
            "artifact_ids": [request_artifact, response_artifact],
        }

    def verify_summary(
        self,
        *,
        campaign_id: str,
        urn: str,
        expected_content: str,
        target_urn: str,
        expected_lifecycle_digest: str,
        artifact_root: Path,
    ) -> dict[str, Any]:
        readback = self.graph.graphql(DOCUMENT_QUERY, {"urn": urn})
        writer = ArtifactWriter(artifact_root)
        artifact_id = writer.write("publication-readback", readback)
        expected_title = f"Retirement Conductor — {campaign_id}"
        document = readback.get("document")
        info = document.get("info") if isinstance(document, dict) else None
        contents = info.get("contents") if isinstance(info, dict) else None
        observed_content = contents.get("text") if isinstance(contents, dict) else None
        if (
            not isinstance(document, dict)
            or document.get("urn") != urn
            or observed_content != expected_content
        ):
            raise Refusal(
                RefusalCode.EVIDENCE_PUBLICATION_MISMATCH,
                "The DataHub summary read-back did not contain the published content.",
            )
        search = self.graph.graphql(
            DOCUMENT_SEARCH_QUERY,
            {
                "input": {
                    "start": 0,
                    "count": 10,
                    "query": expected_title,
                }
            },
        )
        search_artifact_id = writer.write("publication-search", search)
        search_result = search.get("searchDocuments")
        documents = (
            search_result.get("documents") if isinstance(search_result, dict) else None
        )
        exact_matches = [
            item
            for item in documents or []
            if isinstance(item, dict)
            and item.get("urn") == urn
            and isinstance(item.get("info"), dict)
            and item["info"].get("title") == expected_title
        ]
        if not isinstance(documents, list) or len(exact_matches) != 1:
            raise Refusal(
                RefusalCode.EVIDENCE_PUBLICATION_MISMATCH,
                "DataHub did not expose exactly one stable campaign summary.",
            )
        lifecycle = self.lifecycle(target_urn)
        lifecycle_artifact_id = writer.write("target-lifecycle-after", lifecycle)
        lifecycle_digest = digest_json(lifecycle)
        if lifecycle_digest != expected_lifecycle_digest:
            raise Refusal(
                RefusalCode.EVIDENCE_PUBLICATION_MISMATCH,
                "The target lifecycle changed during campaign summary publication.",
            )
        return {
            "readback_artifact_id": artifact_id,
            "search_artifact_id": search_artifact_id,
            "lifecycle_artifact_id": lifecycle_artifact_id,
            "lifecycle_digest_after": lifecycle_digest,
            "content_digest": digest_bytes(expected_content.encode()),
        }


def parse_dataset_urn(urn: str) -> DatasetIdentity | None:
    prefix = "urn:li:dataset:(urn:li:dataPlatform:"
    if not urn.startswith(prefix) or not urn.endswith(")"):
        return None
    inner = urn[len(prefix) : -1]
    try:
        platform, qualified, environment = inner.split(",", 2)
    except ValueError:
        return None
    components = qualified.split(".")
    if len(components) != 4 or any(not component for component in components):
        return None
    return DatasetIdentity(
        urn=urn,
        platform=platform,
        instance=components[0],
        database=components[1],
        schema=components[2],
        table=components[3],
        environment=environment,
    )


def resolve_dataset_identity(
    candidates: Sequence[str],
    declared: Mapping[str, Any],
    *,
    environment: str,
) -> DatasetIdentity:
    matches = []
    for urn in candidates:
        parsed = parse_dataset_urn(urn)
        if parsed is None:
            continue
        if (
            parsed.platform == declared["platform"]
            and parsed.instance == declared["instance"]
            and parsed.database == declared["database"]
            and parsed.schema == declared["schema"]
            and parsed.table == declared["table"]
            and parsed.environment == environment
        ):
            matches.append(parsed)
    if not matches:
        raise Refusal(
            RefusalCode.IDENTITY_NOT_FOUND,
            "No live DataHub dataset matched every declared native component.",
            {"candidate_count": len(candidates)},
        )
    unique = {match.urn: match for match in matches}
    if len(unique) != 1:
        raise Refusal(
            RefusalCode.IDENTITY_AMBIGUOUS,
            "Multiple live DataHub datasets matched every declared native component.",
            {"match_count": len(unique)},
        )
    return next(iter(unique.values()))


def resolve_schema_field(
    fields: Sequence[Any],
    declared_field: str,
) -> dict[str, Any]:
    matches = [
        dict(field)
        for field in fields
        if isinstance(field, dict) and field.get("fieldPath") == declared_field
    ]
    if not matches:
        raise Refusal(
            RefusalCode.IDENTITY_FIELD_NOT_FOUND,
            "The declared field was absent from the resolved live schema.",
            {"field": declared_field},
        )
    if len(matches) != 1:
        raise Refusal(
            RefusalCode.IDENTITY_FIELD_AMBIGUOUS,
            "The declared field appeared more than once in the resolved live schema.",
            {"field": declared_field, "match_count": len(matches)},
        )
    return matches[0]


def build_envelope(
    *,
    captured_at: str,
    status: EvidenceStatus,
    required: bool,
    source_version: str,
    identity: str,
    max_hops: int,
    filters: list[str],
    page_count: int,
    reported_total: int,
    returned_total: int,
    source_updated_at: str | None,
    maximum_age_seconds: int,
    principal: str,
    limitations: list[str],
    artifact_ids: list[str],
) -> dict[str, Any]:
    envelope = with_digest(
        {
            "schema_version": "1.0.0",
            "captured_at": captured_at,
            "mode": "live",
            "sources": [
                {
                    "id": "datahub",
                    "required": required,
                    "status": status,
                    "source_version": source_version,
                    "identity": identity,
                    "scope": {
                        "direction": "downstream",
                        "max_hops": max_hops,
                        "filters": filters,
                        "pages": page_count,
                        "reported_total": reported_total,
                        "returned_total": returned_total,
                    },
                    "freshness": {
                        "observed_at": captured_at,
                        "source_updated_at": source_updated_at,
                        "maximum_age_seconds": maximum_age_seconds,
                    },
                    "permissions": {
                        "principal": principal,
                        "effective_scope": (
                            "disposable Core metadata read and campaign document write"
                        ),
                    },
                    "limitations": sorted(set(limitations)),
                    "artifact_ids": sorted(set(artifact_ids)),
                }
            ],
        },
        "envelope_digest",
    )
    validate_schema(
        "evidence-envelope",
        envelope,
        refusal_code=RefusalCode.INTEGRITY_DIGEST_MISMATCH,
    )
    return envelope


def normalize_consumers(
    raw_consumers: Sequence[Mapping[str, Any]],
    *,
    target_urn: str,
    target_field: str,
    field_lineage_urns: set[str],
    observed_at: str,
    source_version: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    consumers: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []
    target_field_urn = f"urn:li:schemaField:({target_urn},{target_field})"
    for raw in sorted(raw_consumers, key=lambda item: str(item["urn"])):
        urn = str(raw["urn"])
        consumer_id = "dh-" + hashlib.sha256(urn.encode()).hexdigest()[:20]
        field_level = urn in field_lineage_urns
        basis = "column_lineage_edge" if field_level else "canonical_lineage_edge"
        limitations = (
            []
            if field_level
            else ["table-only lineage; field dependency remains unproven"]
        )
        claim = with_digest(
            {
                "type": "CONSUMER_DEPENDS_ON_FIELD",
                "subject": urn,
                "object": target_field_urn,
                "source_id": "datahub",
                "observed_at": observed_at,
                "source_version": source_version,
                "confidence_basis": basis,
                "artifact_ids": [str(raw["raw_artifact_id"])],
                "limitations": limitations,
            },
            "claim_id",
        )
        consumers.append(
            {
                "id": consumer_id,
                "datahub_urn": urn,
                "source_domain": "datahub",
                "native_identity": None,
                "entity_type": raw["entity_type"],
                "degree": raw["degree"],
                "disposition": "OPAQUE",
                "evidence_claim_ids": [claim["claim_id"]],
                "source_version": source_version,
                "limitations": limitations,
            }
        )
        claims.append(claim)
    return consumers, claims


def redact_observation(value: Any, *, key: str = "") -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for item_key, item_value in value.items():
            normalized = item_key.lower().replace("_", "")
            if normalized in {"statement", "sql", "query", "querytext"}:
                redacted[item_key] = {
                    "redacted": True,
                    "digest": digest_json(item_value),
                }
            else:
                redacted[item_key] = redact_observation(
                    item_value,
                    key=item_key,
                )
        return redacted
    if isinstance(value, list):
        return [redact_observation(item, key=key) for item in value]
    if isinstance(value, str):
        if key.lower() in {"email", "token", "password", "secret"}:
            return "[redacted]"
        return EMAIL_PATTERN.sub("[redacted-email]", value)
    return value


def extract_versions(value: Any) -> dict[str, str]:
    versions: dict[str, str] = {}

    def visit(item: Any, path: tuple[str, ...]) -> None:
        if isinstance(item, dict):
            for key, nested in item.items():
                visit(nested, (*path, str(key)))
        elif (
            isinstance(item, (str, int, float))
            and path
            and "version" in path[-1].lower()
        ):
            versions[".".join(path)] = str(item)

    visit(value, ())
    return dict(sorted(versions.items()))


def source_updated_from_entity(value: Any) -> str | None:
    for item in walk_mappings(value):
        key = item.get("key")
        if key == "retirement_conductor.source_updated_at" and isinstance(
            item.get("value"), str
        ):
            return str(item["value"])
        custom = item.get("customProperties")
        if isinstance(custom, dict):
            found = custom.get("retirement_conductor.source_updated_at")
            if isinstance(found, str):
                return found
    return None


def extract_ownership(value: Any) -> list[dict[str, str]]:
    observations: dict[str, dict[str, str]] = {}
    for item in walk_mappings(value):
        owner = item.get("owner")
        if not isinstance(owner, dict) or not isinstance(owner.get("urn"), str):
            continue
        urn = str(owner["urn"])
        observations[urn] = {
            "urn": urn,
            "provenance": "datahub_ownership",
            "authority": "routing_only",
        }
    return [observations[key] for key in sorted(observations)]


def query_history_summary(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {
            "total": 0,
            "returned": 0,
            "retention_window": None,
            "closure_authority": False,
        }
    queries = value.get("queries")
    returned = len(queries) if isinstance(queries, list) else 0
    return {
        "total": _integer(value.get("total"), returned),
        "returned": returned,
        "retention_window": None,
        "closure_authority": False,
    }


def collect_entity_urns(value: Any) -> list[str]:
    result: list[str] = []
    for item in walk_mappings(value):
        urn = item.get("urn")
        if isinstance(urn, str) and urn.startswith("urn:li:"):
            result.append(urn)
    return result


def walk_mappings(value: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    if isinstance(value, dict):
        result.append(value)
        for nested in value.values():
            result.extend(walk_mappings(nested))
    elif isinstance(value, list):
        for nested in value:
            result.extend(walk_mappings(nested))
    return result


def campaign_summary_payload(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Select the exact public-safe campaign facts written back to DataHub."""

    envelope = manifest.get("evidence_envelope")
    envelope_digest = (
        envelope.get("envelope_digest") if isinstance(envelope, dict) else None
    )
    blockers = manifest.get("blockers")
    return {
        "schema_version": "1.0.0",
        "campaign_id": manifest["campaign"]["id"],
        "decision": manifest["decision"],
        "blockers": blockers if isinstance(blockers, list) else [],
        "evidence_envelope_digest": envelope_digest,
        "manifest_digest": manifest["manifest_digest"],
        "scope_statement": (
            "This decision is bounded by the recorded evidence envelope and "
            "does not claim universal safety."
        ),
    }


def render_campaign_summary(manifest: Mapping[str, Any]) -> str:
    payload = campaign_summary_payload(manifest)
    return (
        "# Retirement Conductor campaign summary\n\n"
        "This is an evidence-bounded operational record.\n\n"
        "```json\n"
        f"{canonical_json(payload)}\n"
        "```\n"
    )


def timestamp_age_seconds(earlier: str, later: str) -> float:
    return (_timestamp(later) - _timestamp(earlier)).total_seconds()


def degree_values(max_hops: int) -> list[str]:
    if max_hops <= 1:
        return ["1"]
    if max_hops == 2:
        return ["1", "2"]
    return ["1", "2", "3+"]


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _same_native_dataset(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> bool:
    return all(
        left[key] == right[key]
        for key in ("platform", "instance", "database", "schema", "table")
    )


def _integer(value: Any, default: int) -> int:
    return value if isinstance(value, int) and value >= 0 else default


def _field_names(value: Any) -> list[str]:
    if not isinstance(value, dict) or not isinstance(value.get("fields"), list):
        return []
    return sorted(
        str(item["name"])
        for item in value["fields"]
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    )


def _selected_consequential_consumer(
    consumers: Sequence[dict[str, Any]],
) -> dict[str, Any] | None:
    preferred = [
        consumer
        for consumer in consumers
        if consumer.get("entity_type") in {"DASHBOARD", "CHART"}
    ]
    candidates = preferred or list(consumers)
    return (
        sorted(candidates, key=lambda item: str(item["urn"]))[0] if candidates else None
    )

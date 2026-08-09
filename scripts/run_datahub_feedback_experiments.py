#!/usr/bin/env python3
"""Capture public-safe DataHub feedback evidence from disposable local services."""

from __future__ import annotations

import json
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from urllib.parse import quote

from retirement_conductor.canonical import with_digest, write_json
from retirement_conductor.datahub import LINEAGE_QUERY
from retirement_conductor.datahub_http import DataHubGraphClient
from retirement_conductor.mcp_http import HttpMCPClient

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts/public/datahub-feedback/live-evidence.json"
SEED_RECEIPT = ROOT / ".retirement-conductor/datahub/feedback-seed-receipt.json"
GMS_URL = "http://127.0.0.1:18080"
MCP_URL = "http://127.0.0.1:8000/mcp"
TARGET_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:snowflake,"
    "retirement_conductor.analytics.commerce.orders,PROD)"
)
ISOLATED_TARGET_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:snowflake,"
    "retirement_conductor.analytics.commerce.orders_isolated,PROD)"
)
ISOLATED_MODEL_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:dbt,"
    "retirement_conductor.analytics.consumers.orders_isolated_model,PROD)"
)
LATE_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:spark,"
    "retirement_conductor.analytics.consumers.orders_isolated_late,PROD)"
)


def timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def checked(
    arguments: list[str], *, timeout: float = 180
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        arguments,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"{arguments[0]} exited {result.returncode}: {result.stderr[-400:]}"
        )
    return result


def seed(mode: str) -> dict[str, Any]:
    started = time.monotonic()
    checked(
        [
            "uv",
            "run",
            "--python",
            "3.11",
            "--with",
            "acryl-datahub==1.6.0",
            "python",
            "scripts/datahub_seed.py",
            "--mode",
            mode,
            "--receipt",
            str(SEED_RECEIPT),
        ]
    )
    receipt = json.loads(SEED_RECEIPT.read_text(encoding="utf-8"))
    return {
        "mode": mode,
        "duration_ms": round((time.monotonic() - started) * 1000),
        "refresh_digest": receipt["refresh_digest"],
    }


def lineage_page(
    graph: DataHubGraphClient,
    *,
    urn: str,
    degrees: list[str],
    start: int = 0,
    count: int = 100,
    skip_cache: bool | None = True,
) -> dict[str, Any]:
    input_value: dict[str, Any] = {
        "urn": urn,
        "direction": "DOWNSTREAM",
        "query": "*",
        "start": start,
        "count": count,
        "orFilters": [
            {
                "and": [
                    {
                        "field": "degree",
                        "condition": "EQUAL",
                        "values": degrees,
                    }
                ]
            }
        ],
    }
    if skip_cache is not None:
        input_value["searchFlags"] = {
            "skipCache": skip_cache,
            "skipHighlighting": True,
            "maxAggValues": 100,
        }
    started = time.monotonic()
    page = graph.graphql(LINEAGE_QUERY, {"input": input_value})["searchAcrossLineage"]
    results = page.get("searchResults") or []
    return {
        "requested_degrees": degrees,
        "start": start,
        "count": page.get("count"),
        "total": page.get("total"),
        "returned": len(results),
        "degrees": sorted({item.get("degree") for item in results}),
        "late_consumer_present": any(
            item.get("entity", {}).get("urn") == LATE_URN for item in results
        ),
        "is_partial": page.get("isPartial"),
        "freshness": page.get("freshness"),
        "duration_ms": round((time.monotonic() - started) * 1000),
    }


def mcp_page(
    mcp: HttpMCPClient,
    *,
    urn: str,
    offset: int,
    max_results: int,
    column: str | None = None,
) -> dict[str, Any]:
    result = mcp.call_tool(
        "get_lineage",
        {
            "urn": urn,
            "column": column,
            "upstream": False,
            "max_hops": 3,
            "max_results": max_results,
            "offset": offset,
        },
    )
    downstreams = result["downstreams"]
    results = downstreams.get("searchResults") or []
    return {
        "offset": downstreams.get("offset"),
        "total": downstreams.get("total"),
        "returned": downstreams.get("returned"),
        "has_more": downstreams.get("hasMore"),
        "late_consumer_present": any(
            item.get("entity", {}).get("urn") == LATE_URN for item in results
        ),
        "degrees": sorted({item.get("degree") for item in results}),
    }


def field_edges(graph: DataHubGraphClient, urn: str) -> list[dict[str, Any]]:
    encoded = quote(urn, safe="")
    response = graph._request(f"/aspects/{encoded}?aspect=upstreamLineage&version=0")
    wrapped_aspect = response.get("aspect", {})
    aspect = cast(dict[str, Any], next(iter(wrapped_aspect.values()), {}))
    return cast(list[dict[str, Any]], aspect.get("fineGrainedLineages") or [])


def exact_late_field_chain(graph: DataHubGraphClient) -> dict[str, Any]:
    model_edges = field_edges(graph, ISOLATED_MODEL_URN)
    late_edges = field_edges(graph, LATE_URN)
    model_matches = [
        edge
        for edge in model_edges
        if any(value.endswith(",legacy_status)") for value in edge.get("upstreams", []))
        and any(
            value.endswith(",order_status)") for value in edge.get("downstreams", [])
        )
    ]
    late_matches = [
        edge
        for edge in late_edges
        if any(value.endswith(",order_status)") for value in edge.get("upstreams", []))
        and any(
            value.endswith(",order_status)") for value in edge.get("downstreams", [])
        )
    ]
    return {
        "matched_edge_count": len(model_matches) + len(late_matches),
        "model_edge_present": len(model_matches) == 1,
        "late_edge_present": len(late_matches) == 1,
        "exact_two_hop_chain_present": (
            len(model_matches) == 1 and len(late_matches) == 1
        ),
    }


def wait_for_late_edge(graph: DataHubGraphClient) -> dict[str, Any]:
    started = time.monotonic()
    for attempt in range(1, 121):
        page = lineage_page(
            graph,
            urn=ISOLATED_MODEL_URN,
            degrees=["1"],
            skip_cache=True,
        )
        if page["late_consumer_present"]:
            return {
                "attempts": attempt,
                "duration_ms": round((time.monotonic() - started) * 1000),
            }
        time.sleep(0.5)
    raise RuntimeError(
        "late consumer did not become visible within the 60-second experiment bound"
    )


def run() -> dict[str, Any]:
    graph = DataHubGraphClient(GMS_URL, token=None, timeout_seconds=10)
    mcp = HttpMCPClient(MCP_URL, timeout_seconds=20)
    config = graph.server_config()
    versions = config.get("versions", {})
    managed_ingestion = config.get("managedIngestion", {})
    tools = mcp.list_tools()
    lineage_tool = next(tool for tool in tools if tool.get("name") == "get_lineage")
    result: dict[str, Any] = {
        "schema_version": "1.0.0",
        "captured_at": timestamp(),
        "evidence_mode": "live-local disposable DataHub Core and MCP",
        "versions": {
            "datahub_core": versions.get("acryldata/datahub", {}).get("version"),
            "managed_ingestion_cli": managed_ingestion.get("defaultCliVersion"),
            "mcp_server": "0.6.0",
        },
        "scope": {
            "gms": "loopback disposable Core",
            "mcp": (
                "loopback pinned source commit 9a6946daa7d30eb481c82dd8ee5e15ae6526a3c9"
            ),
            "production_systems_mutated": False,
        },
        "mcp_capability": {
            "tool_count": len(tools),
            "lineage_has_offset_parameter": "offset"
            in lineage_tool.get("inputSchema", {}).get("properties", {}),
            "lineage_docs_describe_pagination": "PAGINATION:"
            in str(lineage_tool.get("description", "")),
            "lineage_has_cache_bypass_parameter": "skip_cache"
            in lineage_tool.get("inputSchema", {}).get("properties", {}),
        },
    }
    try:
        base = seed("base")
        warmed_default = lineage_page(
            graph,
            urn=ISOLATED_TARGET_URN,
            degrees=["2"],
            skip_cache=None,
        )
        late = seed("late")
        visibility = wait_for_late_edge(graph)
        default_after_write = lineage_page(
            graph,
            urn=ISOLATED_TARGET_URN,
            degrees=["2"],
            skip_cache=None,
        )
        bypass_after_write = lineage_page(
            graph,
            urn=ISOLATED_TARGET_URN,
            degrees=["2"],
            skip_cache=True,
        )
        multi_degree = lineage_page(
            graph,
            urn=ISOLATED_TARGET_URN,
            degrees=["1", "2", "3+"],
            skip_cache=True,
        )
        individual_degrees = [
            lineage_page(
                graph,
                urn=ISOLATED_TARGET_URN,
                degrees=[degree],
                skip_cache=True,
            )
            for degree in ("1", "2", "3+")
        ]
        mcp_first = mcp_page(mcp, urn=TARGET_URN, offset=0, max_results=1)
        mcp_second = mcp_page(mcp, urn=TARGET_URN, offset=1, max_results=1)
        gms_second = lineage_page(
            graph,
            urn=TARGET_URN,
            degrees=["1", "2", "3+"],
            start=1,
            count=1,
            skip_cache=True,
        )
        mcp_field = mcp_page(
            mcp,
            urn=ISOLATED_TARGET_URN,
            offset=0,
            max_results=30,
            column="legacy_status",
        )
        direct_field = exact_late_field_chain(graph)
        result.update(
            {
                "seed_operations": [base, late],
                "cache_probe": {
                    "warmed_default_before_late": warmed_default,
                    "late_edge_visibility": visibility,
                    "default_after_late": default_after_write,
                    "cache_bypassed_after_late": bypass_after_write,
                    "stale_default_reproduced": (
                        default_after_write["late_consumer_present"] is False
                        and bypass_after_write["late_consumer_present"] is True
                    ),
                },
                "degree_filter_probe": {
                    "combined": multi_degree,
                    "individual": individual_degrees,
                    "combined_filter_omission_reproduced": (
                        multi_degree["returned"]
                        < sum(page["returned"] for page in individual_degrees)
                    ),
                },
                "mcp_offset_probe": {
                    "first_page": mcp_first,
                    "second_page": mcp_second,
                    "gms_second_row_control": gms_second,
                    "defect_reproduced": (
                        int(mcp_first["total"] or 0) > 1
                        and mcp_first["returned"] == 1
                        and mcp_first["has_more"] is False
                        and mcp_second["returned"] == 0
                        and gms_second["returned"] == 1
                    ),
                    "related_issue": "https://github.com/acryldata/mcp-server-datahub/issues/194",
                    "proposed_fix": "https://github.com/acryldata/mcp-server-datahub/pull/195",
                },
                "field_lineage_probe": {
                    "mcp_column_lineage": mcp_field,
                    "direct_upstream_lineage_aspect": direct_field,
                    "unexpected_multihop_gap_observed": (
                        mcp_field["late_consumer_present"] is False
                        and direct_field["exact_two_hop_chain_present"] is True
                    ),
                },
                "limitations": [
                    "The graph is synthetic and disposable; it does not prove "
                    "production coverage.",
                    "Retained DataHub volumes can contain prior synthetic consumers, "
                    "so absolute rich-graph totals are not a clean benchmark.",
                    "Core returned null isPartial and freshness fields during these "
                    "lineage queries.",
                    "The experiment diagnoses read behavior and does not mutate "
                    "lifecycle metadata.",
                ],
            }
        )
    finally:
        result["restore"] = seed("base")
    return cast(dict[str, Any], with_digest(result, "evidence_digest"))


def main() -> int:
    result = run()
    write_json(OUTPUT, result)
    field_gap = result["field_lineage_probe"]["unexpected_multihop_gap_observed"]
    print(
        "DataHub feedback experiment passed: "
        f"offset_bug={result['mcp_offset_probe']['defect_reproduced']} "
        f"cache_stale={result['cache_probe']['stale_default_reproduced']} "
        f"field_gap={field_gap} "
        f"digest={result['evidence_digest']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

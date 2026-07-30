#!/usr/bin/env python3
"""Promote a local LookML ingestion report only after direct DataHub reread."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from retirement_conductor.canonical import digest_file, with_digest, write_json

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "artifacts/public/phase06/lookml-ingestion-evidence.json"
LOOKML_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:looker,"
    "retirement-disposable.retirement_conductor.view.orders,PROD)"
)
WAREHOUSE_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:bigquery,"
    "retirement-disposable.analytics.commerce.orders,PROD)"
)
EXPECTED_FIELDS = ("id", "legacy_status", "order_status")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def mapping(value: object, label: str) -> dict[str, Any]:
    require(isinstance(value, dict), f"{label} must be an object")
    return cast(dict[str, Any], value)


def load_report(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    document = mapping(json.loads(path.read_text(encoding="utf-8")), "report")
    source = mapping(
        mapping(document.get("source"), "source").get("report"), "source report"
    )
    sink = mapping(mapping(document.get("sink"), "sink").get("report"), "sink report")
    return source, sink


def request_json(url: str) -> dict[str, Any]:
    request = Request(url, headers={"Accept": "application/json"}, method="GET")
    with urlopen(request, timeout=10) as response:
        return mapping(json.load(response), url)


def read_aspect(
    base_url: str,
    *,
    name: str,
    record_name: str,
) -> dict[str, Any]:
    url = f"{base_url}/aspects/{quote(LOOKML_URN, safe='')}?aspect={name}&version=0"
    document = request_json(url)
    aspect = mapping(document.get("aspect"), f"{name} aspect")
    return mapping(aspect.get(record_name), f"{name} record")


def exact_lineage(lineage: dict[str, Any]) -> tuple[list[dict[str, str]], int]:
    rows: list[dict[str, str]] = []
    observed = lineage.get("fineGrainedLineages")
    require(isinstance(observed, list), "fine-grained lineage is missing")
    for item in observed:
        edge = mapping(item, "lineage edge")
        upstreams = edge.get("upstreams")
        downstreams = edge.get("downstreams")
        require(
            isinstance(upstreams, list)
            and len(upstreams) == 1
            and isinstance(upstreams[0], str),
            "lineage edge must have one upstream field",
        )
        require(
            isinstance(downstreams, list)
            and len(downstreams) == 1
            and isinstance(downstreams[0], str),
            "lineage edge must have one downstream field",
        )
        source = upstreams[0]
        target = downstreams[0]
        for field in EXPECTED_FIELDS:
            if source == f"urn:li:schemaField:({WAREHOUSE_URN},{field})":
                require(
                    target == f"urn:li:schemaField:({LOOKML_URN},{field})",
                    f"{field} lineage target changed",
                )
                rows.append({"source_field": field, "target_field": field})
                break
    require(
        {row["source_field"] for row in rows} == set(EXPECTED_FIELDS),
        "not every expected field has an exact lineage edge",
    )
    upstreams = lineage.get("upstreams")
    require(isinstance(upstreams, list), "table lineage is missing")
    require(
        any(
            isinstance(item, dict) and item.get("dataset") == WAREHOUSE_URN
            for item in upstreams
        ),
        "exact upstream table is missing",
    )
    audit_times = [
        item.get("auditStamp", {}).get("time")
        for item in upstreams
        if isinstance(item, dict) and isinstance(item.get("auditStamp"), dict)
    ]
    timestamps = [value for value in audit_times if isinstance(value, int)]
    require(timestamps, "lineage audit time is missing")
    return sorted(rows, key=lambda row: row["source_field"]), max(timestamps)


def run(report_path: Path, output: Path, base_url: str) -> None:
    parsed = urlparse(base_url)
    require(
        parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost"},
        "this evidence command is restricted to disposable loopback DataHub",
    )
    source, sink = load_report(report_path)
    require(source.get("events_produced") == 20, "expected 20 source events")
    require(source.get("models_discovered") == 1, "expected one model")
    require(source.get("models_dropped") == [], "a model was dropped")
    require(source.get("views_discovered") == 1, "expected one view")
    require(source.get("views_dropped") == [], "a view was dropped")
    require(source.get("warnings") == [], "source warnings are not accepted")
    require(source.get("failures") == [], "source failures are not accepted")
    require(sink.get("warnings") == [], "sink warnings are not accepted")
    require(sink.get("failures") == [], "sink failures are not accepted")
    require(sink.get("mode") == "SYNC", "sink did not wait for each write")

    config = request_json(f"{base_url}/config")
    versions = mapping(config.get("versions"), "DataHub versions")
    datahub_version = mapping(
        versions.get("acryldata/datahub"),
        "DataHub version",
    ).get("version")
    require(datahub_version == "v1.6.0", "unexpected DataHub server version")

    schema = read_aspect(
        base_url,
        name="schemaMetadata",
        record_name="com.linkedin.schema.SchemaMetadata",
    )
    raw_fields = schema.get("fields")
    require(isinstance(raw_fields, list), "schema fields are missing")
    fields = [
        item.get("fieldPath")
        for item in raw_fields
        if isinstance(item, dict) and isinstance(item.get("fieldPath"), str)
    ]
    require(fields == list(EXPECTED_FIELDS), "stored LookML fields changed")
    lineage = read_aspect(
        base_url,
        name="upstreamLineage",
        record_name="com.linkedin.dataset.UpstreamLineage",
    )
    lineage_rows, observed_at_ms = exact_lineage(lineage)
    observed_at = datetime.fromtimestamp(observed_at_ms / 1000, tz=UTC)

    artifact = with_digest(
        {
            "schema_version": "1.0.0",
            "result": "VERIFIED_LOCAL_LOOKML_INGESTION",
            "evidence_mode": "live",
            "source_data_mode": "fixture",
            "observed_at": observed_at.isoformat().replace("+00:00", "Z"),
            "datahub_version": datahub_version,
            "raw_report_digest": digest_file(report_path),
            "source_report": {
                "events_produced": source["events_produced"],
                "models_discovered": source["models_discovered"],
                "models_dropped": source["models_dropped"],
                "views_discovered": source["views_discovered"],
                "views_dropped": source["views_dropped"],
                "warnings": source["warnings"],
                "failures": source["failures"],
            },
            "direct_reread": {
                "entity_urn": LOOKML_URN,
                "field_paths": fields,
                "fine_grained_lineage": lineage_rows,
                "upstream_table_urn": WAREHOUSE_URN,
            },
            "reporter_limitations": {
                "event_not_produced_warn": source.get("event_not_produced_warn"),
                "reported_sink_records": sink.get("total_records_written"),
                "authority": "direct DataHub aspect reread",
            },
            "claim_boundary": {
                "live_looker_api_observed": False,
                "warehouse_queried": False,
                "provisioning_performed": False,
                "proves": (
                    "DataHub 1.6.0 parsed the public LookML fixture and stored "
                    "the exact schema and three field-lineage edges."
                ),
                "does_not_prove": (
                    "saved-Look discovery, native mutation, query validation, "
                    "compensation, or live Looker-to-DataHub reconciliation."
                ),
            },
        },
        "artifact_digest",
    )
    write_json(output, artifact)
    print(json.dumps({"output": str(output), "result": artifact["result"]}))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--gms-url", default="http://127.0.0.1:18080")
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    run(arguments.report, arguments.output, arguments.gms_url.rstrip("/"))

#!/usr/bin/env python3
"""Seed one deterministic native Superset consumer through authenticated APIs."""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast
from urllib.parse import quote

from retirement_conductor.canonical import digest_json, write_json
from retirement_conductor.superset import SupersetClient, inspect_execution
from retirement_conductor.superset_config import SupersetSettings

DATABASE_NAME = "WS04 Orders PostgreSQL"
DATASET_NAME = "ws04_status_by_order"
CHART_NAME = "WS04 Order Status Detail"
DASHBOARD_NAME = "WS04 Legacy Status Feasibility"
BEFORE_SQL = "SELECT id, legacy_status AS status, amount FROM public.orders"


def result(value: Mapping[str, Any]) -> dict[str, Any]:
    item = value.get("result")
    if not isinstance(item, dict):
        raise RuntimeError("Superset returned an unexpected object response")
    return dict(item)


def list_named(
    client: SupersetClient,
    endpoint: str,
    field: str,
    expected: str,
) -> list[dict[str, Any]]:
    query = quote("(page:0,page_size:100)", safe="")
    response = cast(
        dict[str, Any],
        client._request("GET", f"{endpoint}?q={query}"),
    )
    values = response.get("result")
    if not isinstance(values, list):
        raise RuntimeError("Superset returned an unexpected list response")
    return [
        dict(item)
        for item in values
        if isinstance(item, dict) and item.get(field) == expected
    ]


def exact_or_create(
    client: SupersetClient,
    *,
    endpoint: str,
    field: str,
    expected: str,
    payload: Mapping[str, Any],
) -> int:
    matches = list_named(client, endpoint, field, expected)
    if len(matches) > 1:
        raise RuntimeError(f"refusing ambiguous seeded Superset {field}")
    if matches:
        return int(matches[0]["id"])
    created = cast(
        dict[str, Any],
        client._request("POST", endpoint, payload),
    )
    return int(created["id"])


def seed(settings: SupersetSettings, source_database_uri: str, output: Path) -> None:
    client = SupersetClient(settings)
    client.authenticate()
    if client.health().strip() != "OK":
        raise RuntimeError("Superset native health check failed")

    database_id = exact_or_create(
        client,
        endpoint="/api/v1/database/",
        field="database_name",
        expected=DATABASE_NAME,
        payload={
            "database_name": DATABASE_NAME,
            "sqlalchemy_uri": source_database_uri,
            "expose_in_sqllab": True,
        },
    )
    dataset_id = exact_or_create(
        client,
        endpoint="/api/v1/dataset/",
        field="table_name",
        expected=DATASET_NAME,
        payload={
            "database": database_id,
            "schema": "public",
            "table_name": DATASET_NAME,
            "sql": BEFORE_SQL,
            "owners": [1],
        },
    )
    dashboard_id = exact_or_create(
        client,
        endpoint="/api/v1/dashboard/",
        field="dashboard_title",
        expected=DASHBOARD_NAME,
        payload={
            "dashboard_title": DASHBOARD_NAME,
            "slug": "ws04-legacy-status-feasibility",
            "published": True,
            "owners": [1],
            "position_json": "{}",
            "json_metadata": "{}",
        },
    )
    params = json.dumps(
        {
            "adhoc_filters": [],
            "all_columns": ["id", "status", "amount"],
            "datasource": f"{dataset_id}__table",
            "row_limit": 1000,
            "slice_name": CHART_NAME,
            "time_range": "No filter",
            "viz_type": "table",
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    chart_id = exact_or_create(
        client,
        endpoint="/api/v1/chart/",
        field="slice_name",
        expected=CHART_NAME,
        payload={
            "datasource_id": dataset_id,
            "datasource_type": "table",
            "slice_name": CHART_NAME,
            "viz_type": "table",
            "owners": [1],
            "dashboards": [dashboard_id],
            "params": params,
        },
    )

    database = result(
        cast(dict[str, Any], client._request("GET", f"/api/v1/database/{database_id}"))
    )
    dataset = client.get_dataset(dataset_id)
    chart = client.get_chart(chart_id)
    dashboard = result(
        cast(
            dict[str, Any], client._request("GET", f"/api/v1/dashboard/{dashboard_id}")
        )
    )
    if dataset.get("sql") != BEFORE_SQL:
        raise RuntimeError(
            "existing dataset is not at the exact before state; compensate it first"
        )
    if int(
        chart.get("datasource_id", 0)
    ) != dataset_id or CHART_NAME not in dashboard.get("charts", []):
        raise RuntimeError("seeded chart/dashboard native bindings are incomplete")
    execution = inspect_execution(client.execute_chart(chart_id))
    if execution["result"] != "PASSED":
        raise RuntimeError("seeded chart failed forced native execution")

    evidence = {
        "schema_version": "1.0.0",
        "mode": "live-local",
        "superset_version": settings.version,
        "authentication_mode": "database login to JWT bearer plus CSRF",
        "database": {"id": database_id, "uuid": database["uuid"]},
        "dataset": {
            "id": dataset_id,
            "uuid": dataset["uuid"],
            "sql_digest": digest_json(dataset["sql"]),
        },
        "chart": {"id": chart_id, "uuid": chart["uuid"]},
        "dashboard": {"id": dashboard_id, "uuid": dashboard["uuid"]},
        "forced_execution": execution,
        "credential_values_recorded": False,
    }
    write_json(output, evidence)
    print(json.dumps(evidence, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".retirement-conductor/superset/seed.json"),
    )
    arguments = parser.parse_args()
    source_database_uri = os.environ.get("SUPERSET_SOURCE_DATABASE_URI", "")
    if not source_database_uri:
        raise SystemExit("SUPERSET_SOURCE_DATABASE_URI is required")
    seed(SupersetSettings.from_environment(), source_database_uri, arguments.output)


if __name__ == "__main__":
    main()

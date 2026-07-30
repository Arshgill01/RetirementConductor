#!/usr/bin/env python3
"""Seed a deterministic public-safe graph into disposable DataHub Core."""

from __future__ import annotations

import argparse
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from datahub.emitter.mcp import MetadataChangeProposalWrapper
from datahub.emitter.rest_emitter import DatahubRestEmitter
from datahub.metadata import schema_classes as models

from retirement_conductor.canonical import digest_json, write_json

ACTOR = "urn:li:corpuser:retirement-conductor"
TARGET_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:snowflake,"
    "retirement_conductor.analytics.commerce.orders,PROD)"
)


def dataset_urn(platform: str, table: str) -> str:
    return (
        f"urn:li:dataset:(urn:li:dataPlatform:{platform},"
        f"retirement_conductor.analytics.consumers.{table},PROD)"
    )


def schema_field(name: str) -> models.SchemaFieldClass:
    return models.SchemaFieldClass(
        fieldPath=name,
        type=models.SchemaFieldDataTypeClass(type=models.StringTypeClass()),
        nativeDataType="VARCHAR",
        nullable=False,
        description=f"Public-safe synthetic field {name}.",
    )


def emit(
    emitter: DatahubRestEmitter,
    urn: str,
    aspect: Any,
) -> None:
    emitter.emit_mcp(
        MetadataChangeProposalWrapper(
            entityUrn=urn,
            aspect=aspect,
        )
    )


def dataset_aspects(
    emitter: DatahubRestEmitter,
    *,
    urn: str,
    platform: str,
    name: str,
    source_updated_at: str,
    upstream: str | None = None,
) -> None:
    custom = {
        "retirement_conductor.fixture": "public-safe-phase02",
        "retirement_conductor.source_updated_at": source_updated_at,
        "retirement_conductor.ingestion_run_id": "phase02-datahub-core-v1",
    }
    emit(
        emitter,
        urn,
        models.DatasetPropertiesClass(
            name=name,
            qualifiedName=name,
            description="Public-safe Retirement Conductor integration fixture.",
            customProperties=custom,
        ),
    )
    fields = [schema_field("order_status")]
    if urn == TARGET_URN:
        fields.insert(0, schema_field("legacy_status"))
    emit(
        emitter,
        urn,
        models.SchemaMetadataClass(
            schemaName=name,
            platform=f"urn:li:dataPlatform:{platform}",
            version=0,
            hash=digest_json([field.fieldPath for field in fields]),
            platformSchema=models.OtherSchemaClass(rawSchema="synthetic"),
            fields=fields,
            created=models.AuditStampClass(time=0, actor=ACTOR),
        ),
    )
    emit(emitter, urn, models.StatusClass(removed=False))
    emit(
        emitter,
        urn,
        models.DataPlatformInstanceClass(
            platform=f"urn:li:dataPlatform:{platform}",
            instance=(
                f"urn:li:dataPlatformInstance:"
                f"(urn:li:dataPlatform:{platform},retirement_conductor)"
            ),
        ),
    )
    emit(
        emitter,
        urn,
        models.OwnershipClass(
            owners=[
                models.OwnerClass(
                    owner="urn:li:corpGroup:retirement-conductor-data",
                    type="TECHNICAL_OWNER",
                )
            ],
            lastModified=models.AuditStampClass(time=0, actor=ACTOR),
        ),
    )
    if upstream is None:
        return
    upstream_field = "legacy_status" if upstream == TARGET_URN else "order_status"
    emit(
        emitter,
        urn,
        models.UpstreamLineageClass(
            upstreams=[
                models.UpstreamClass(
                    dataset=upstream,
                    type="TRANSFORMED",
                    auditStamp=models.AuditStampClass(time=0, actor=ACTOR),
                )
            ],
            fineGrainedLineages=[
                models.FineGrainedLineageClass(
                    upstreamType="FIELD_SET",
                    downstreamType="FIELD",
                    upstreams=[f"urn:li:schemaField:({upstream},{upstream_field})"],
                    downstreams=[f"urn:li:schemaField:({urn},order_status)"],
                    transformOperation="authorized-fixture-reference",
                    confidenceScore=1.0,
                )
            ],
        ),
    )


def seed(gms_url: str, token: str | None, receipt: Path) -> dict[str, Any]:
    observed_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    emitter = DatahubRestEmitter(
        gms_server=gms_url,
        token=token,
        datahub_component="retirement-conductor-seed/1.0",
    )
    emitter.test_connection()
    dataset_aspects(
        emitter,
        urn=TARGET_URN,
        platform="snowflake",
        name="analytics.commerce.orders",
        source_updated_at=observed_at,
    )
    intermediates = [
        dataset_urn("dbt", f"orders_model_{index:02d}") for index in range(3)
    ]
    for index, urn in enumerate(intermediates):
        dataset_aspects(
            emitter,
            urn=urn,
            platform="dbt",
            name=f"orders_model_{index:02d}",
            source_updated_at=observed_at,
            upstream=TARGET_URN,
        )
    platforms = ["looker", "powerbi", "tableau", "superset", "dbt", "snowflake"]
    consumers: list[str] = []
    for index in range(18):
        platform = platforms[index % len(platforms)]
        urn = dataset_urn(platform, f"orders_consumer_{index:02d}")
        consumers.append(urn)
        dataset_aspects(
            emitter,
            urn=urn,
            platform=platform,
            name=f"orders_consumer_{index:02d}",
            source_updated_at=observed_at,
            upstream=intermediates[index % len(intermediates)],
        )
    audit = models.ChangeAuditStampsClass(
        created=models.AuditStampClass(time=0, actor=ACTOR),
        lastModified=models.AuditStampClass(time=0, actor=ACTOR),
    )
    charts: list[str] = []
    for index in range(6):
        platform = platforms[index]
        urn = f"urn:li:chart:({platform},retirement_conductor.chart_{index:02d})"
        charts.append(urn)
        emit(
            emitter,
            urn,
            models.ChartInfoClass(
                title=f"Orders chart {index:02d}",
                description="Public-safe consequential BI chart.",
                lastModified=audit,
                inputs=[consumers[index]],
                type="BAR",
                customProperties={
                    "retirement_conductor.ingestion_run_id": ("phase02-datahub-core-v1")
                },
            ),
        )
        emit(emitter, urn, models.StatusClass(removed=False))
    dashboards: list[str] = []
    for index in range(4):
        platform = platforms[index]
        urn = (
            f"urn:li:dashboard:({platform},retirement_conductor.dashboard_{index:02d})"
        )
        dashboards.append(urn)
        emit(
            emitter,
            urn,
            models.DashboardInfoClass(
                title=f"Orders dashboard {index:02d}",
                description="Public-safe consequential BI dashboard.",
                lastModified=audit,
                charts=[charts[index]],
                datasets=[consumers[index]],
                customProperties={
                    "retirement_conductor.ingestion_run_id": ("phase02-datahub-core-v1")
                },
            ),
        )
        emit(emitter, urn, models.StatusClass(removed=False))
    emitter.close()
    result = {
        "schema_version": "1.0.0",
        "mode": "live",
        "gms_url": gms_url,
        "ingestion_run_id": "phase02-datahub-core-v1",
        "source_updated_at": observed_at,
        "target_urn": TARGET_URN,
        "dataset_count": 1 + len(intermediates) + len(consumers),
        "chart_count": len(charts),
        "dashboard_count": len(dashboards),
        "entity_urn_digest": digest_json(
            [TARGET_URN, *intermediates, *consumers, *charts, *dashboards]
        ),
    }
    write_json(receipt, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--gms-url",
        default=os.environ.get("DATAHUB_GMS_URL", "http://127.0.0.1:18080"),
    )
    parser.add_argument(
        "--token-reference",
        default="DATAHUB_GMS_TOKEN",
    )
    parser.add_argument(
        "--receipt",
        type=Path,
        default=Path(".retirement-conductor/datahub/seed-receipt.json"),
    )
    args = parser.parse_args()
    result = seed(
        args.gms_url,
        os.environ.get(args.token_reference) or None,
        args.receipt,
    )
    print(
        "Seeded disposable DataHub graph: "
        f"datasets={result['dataset_count']} "
        f"charts={result['chart_count']} "
        f"dashboards={result['dashboard_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

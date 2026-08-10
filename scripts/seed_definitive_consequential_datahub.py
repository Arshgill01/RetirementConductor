#!/usr/bin/env python3
"""Seed the CP-05 target, dbt consumer, and optional real Spark consumer."""

from __future__ import annotations

import argparse
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from datahub.emitter.mcp import MetadataChangeProposalWrapper
from datahub.emitter.rest_emitter import DatahubRestEmitter
from datahub.metadata import schema_classes as models

from retirement_conductor.canonical import digest_json, with_digest, write_json

ACTOR = "urn:li:corpuser:retirement-conductor"
TARGET_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:postgres,"
    "ws04-feasibility.ws04 orders postgresql.retirement_lab.orders,PROD)"
)
DBT_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:dbt,"
    "retirement_conductor.analytics.consumers.orders_definitive_model,PROD)"
)
SPARK_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:spark,"
    "retirement_conductor.analytics.consumers.orders_legacy_spark_workload,PROD)"
)


def emit(emitter: DatahubRestEmitter, urn: str, aspect: Any) -> None:
    emitter.emit_mcp(MetadataChangeProposalWrapper(entityUrn=urn, aspect=aspect))


def field(name: str, native_type: str) -> models.SchemaFieldClass:
    field_type: Any = (
        models.NumberTypeClass()
        if native_type in {"INTEGER", "BIGINT"}
        else models.StringTypeClass()
    )
    return models.SchemaFieldClass(
        fieldPath=name,
        type=models.SchemaFieldDataTypeClass(type=field_type),
        nativeDataType=native_type,
        nullable=False,
    )


def dataset(
    emitter: DatahubRestEmitter,
    *,
    urn: str,
    platform: str,
    name: str,
    fields: list[models.SchemaFieldClass],
    observed_at: str,
    upstream: str | None = None,
    upstream_field: str = "legacy_status",
) -> None:
    emit(
        emitter,
        urn,
        models.DatasetPropertiesClass(
            name=name,
            qualifiedName=name,
            description="Disposable CP-05 consequential evidence object.",
            customProperties={
                "retirement_conductor.source_updated_at": observed_at,
                "retirement_conductor.mode": "live-local",
            },
        ),
    )
    emit(
        emitter,
        urn,
        models.SchemaMetadataClass(
            schemaName=name,
            platform=f"urn:li:dataPlatform:{platform}",
            version=0,
            hash=digest_json([item.fieldPath for item in fields]),
            platformSchema=models.OtherSchemaClass(rawSchema="public-safe synthetic"),
            fields=fields,
            created=models.AuditStampClass(time=0, actor=ACTOR),
        ),
    )
    emit(emitter, urn, models.StatusClass(removed=False))
    if upstream is not None:
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
                        downstreams=[f"urn:li:schemaField:({urn},status)"],
                        transformOperation="live-local native workload",
                        confidenceScore=1.0,
                    )
                ],
            ),
        )


def seed(
    gms_url: str,
    token: str | None,
    output: Path,
    *,
    include_late_spark: bool,
) -> dict[str, Any]:
    observed_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    emitter = DatahubRestEmitter(
        gms_server=gms_url,
        token=token,
        datahub_component="retirement-conductor-cp05-seed/1.0",
    )
    emitter.test_connection()
    dataset(
        emitter,
        urn=TARGET_URN,
        platform="postgres",
        name="retirement_lab.orders",
        fields=[
            field("id", "INTEGER"),
            field("legacy_status", "VARCHAR"),
            field("order_status", "VARCHAR"),
            field("amount_cents", "BIGINT"),
        ],
        observed_at=observed_at,
    )
    dataset(
        emitter,
        urn=DBT_URN,
        platform="dbt",
        name="orders_definitive_model",
        fields=[field("status", "VARCHAR")],
        observed_at=observed_at,
        upstream=TARGET_URN,
    )
    if include_late_spark:
        dataset(
            emitter,
            urn=SPARK_URN,
            platform="spark",
            name="orders_legacy_spark_workload",
            fields=[field("status", "VARCHAR")],
            observed_at=observed_at,
            upstream=TARGET_URN,
        )
    emitter.close()
    result = with_digest(
        {
            "schema_version": "1.0.0",
            "mode": "live-local",
            "captured_at": observed_at,
            "source_updated_at": observed_at,
            "ingestion_run_id": (
                "cp05-" + digest_json([observed_at, include_late_spark])[-16:]
            ),
            "gms_url": gms_url.rstrip("/"),
            "target_urn": TARGET_URN,
            "target_urns": [TARGET_URN],
            "dbt_consumer_urn": DBT_URN,
            "late_spark_consumer_urn": SPARK_URN if include_late_spark else None,
            "late_spark_ingested": include_late_spark,
            "direct_reread_required": True,
        },
        "refresh_digest",
    )
    write_json(output, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--gms-url",
        default=os.environ.get("DATAHUB_GMS_URL", "http://127.0.0.1:18080"),
    )
    parser.add_argument("--token-reference", default="DATAHUB_GMS_TOKEN")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--include-late-spark", action="store_true")
    args = parser.parse_args()
    result = seed(
        args.gms_url,
        os.environ.get(args.token_reference) or None,
        args.output,
        include_late_spark=args.include_late_spark,
    )
    print(result["refresh_digest"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

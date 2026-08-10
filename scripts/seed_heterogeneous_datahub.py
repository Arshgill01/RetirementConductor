#!/usr/bin/env python3
"""Seed one dbt consumer beside the official Superset connector output."""

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
    "ws04 orders postgresql.public.orders,PROD)"
)
DBT_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:dbt,"
    "retirement_conductor.analytics.consumers.orders_heterogeneous_model,PROD)"
)


def emit(emitter: DatahubRestEmitter, urn: str, aspect: Any) -> None:
    emitter.emit_mcp(MetadataChangeProposalWrapper(entityUrn=urn, aspect=aspect))


def seed(gms_url: str, token: str | None, receipt: Path) -> dict[str, Any]:
    observed_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    emitter = DatahubRestEmitter(
        gms_server=gms_url,
        token=token,
        datahub_component="retirement-conductor-heterogeneous-seed/1.0",
    )
    emitter.test_connection()
    fields = [
        models.SchemaFieldClass(
            fieldPath=name,
            type=models.SchemaFieldDataTypeClass(type=models.StringTypeClass()),
            nativeDataType="VARCHAR",
            nullable=False,
        )
        for name in ("legacy_status", "order_status")
    ]
    emit(
        emitter,
        TARGET_URN,
        models.SchemaMetadataClass(
            schemaName="public.orders",
            platform="urn:li:dataPlatform:postgres",
            version=0,
            hash=digest_json(["legacy_status", "order_status"]),
            platformSchema=models.OtherSchemaClass(rawSchema="public-safe synthetic"),
            fields=fields,
            created=models.AuditStampClass(time=0, actor=ACTOR),
        ),
    )
    emit(
        emitter,
        DBT_URN,
        models.DatasetPropertiesClass(
            name="orders_heterogeneous_model",
            qualifiedName="orders_heterogeneous_model",
            description="Disposable dbt consumer for heterogeneous acceptance.",
            customProperties={"retirement_conductor.seeded_at": observed_at},
        ),
    )
    emit(
        emitter,
        DBT_URN,
        models.SchemaMetadataClass(
            schemaName="orders_heterogeneous_model",
            platform="urn:li:dataPlatform:dbt",
            version=0,
            hash=digest_json(["normalized_status"]),
            platformSchema=models.OtherSchemaClass(rawSchema="public-safe synthetic"),
            fields=[
                models.SchemaFieldClass(
                    fieldPath="normalized_status",
                    type=models.SchemaFieldDataTypeClass(type=models.StringTypeClass()),
                    nativeDataType="VARCHAR",
                    nullable=False,
                )
            ],
            created=models.AuditStampClass(time=0, actor=ACTOR),
        ),
    )
    emit(
        emitter,
        DBT_URN,
        models.UpstreamLineageClass(
            upstreams=[
                models.UpstreamClass(
                    dataset=TARGET_URN,
                    type="TRANSFORMED",
                    auditStamp=models.AuditStampClass(time=0, actor=ACTOR),
                )
            ],
            fineGrainedLineages=[
                models.FineGrainedLineageClass(
                    upstreamType="FIELD_SET",
                    downstreamType="FIELD",
                    upstreams=[f"urn:li:schemaField:({TARGET_URN},legacy_status)"],
                    downstreams=[f"urn:li:schemaField:({DBT_URN},normalized_status)"],
                    transformOperation="dbt model SQL",
                    confidenceScore=1.0,
                )
            ],
        ),
    )
    emit(emitter, TARGET_URN, models.StatusClass(removed=False))
    emit(emitter, DBT_URN, models.StatusClass(removed=False))
    emitter.close()
    result = with_digest(
        {
            "schema_version": "1.0.0",
            "mode": "live-local",
            "captured_at": observed_at,
            "target_urn": TARGET_URN,
            "consumer_urn": DBT_URN,
            "field_edge": {
                "upstream": f"urn:li:schemaField:({TARGET_URN},legacy_status)",
                "downstream": f"urn:li:schemaField:({DBT_URN},normalized_status)",
            },
        },
        "seed_digest",
    )
    write_json(receipt, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--gms-url",
        default=os.environ.get("DATAHUB_GMS_URL", "http://127.0.0.1:18080"),
    )
    parser.add_argument("--token-reference", default="DATAHUB_GMS_TOKEN")
    parser.add_argument(
        "--receipt",
        type=Path,
        default=Path(".retirement-conductor/heterogeneous/datahub-seed.json"),
    )
    args = parser.parse_args()
    result = seed(
        args.gms_url,
        os.environ.get(args.token_reference) or None,
        args.receipt,
    )
    print(f"Seeded heterogeneous DataHub edge: {result['seed_digest']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Emit the controlled benchmark graph into disposable DataHub Core."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from datahub.emitter.mcp import MetadataChangeProposalWrapper
from datahub.emitter.rest_emitter import DatahubRestEmitter
from datahub.metadata import schema_classes as models

from retirement_conductor.benchmark_data import TARGET_DATASET_URN
from retirement_conductor.canonical import (
    digest_json,
    verify_digest,
    with_digest,
    write_json,
)

ACTOR = "urn:li:corpuser:retirement-conductor"
OWNER = "urn:li:corpGroup:retirement-conductor-benchmark"
DBT_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:dbt,"
    "retirement_benchmark.analytics.consumers.orders_status_summary,PROD)"
)
TABLEAU_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:tableau,"
    "retirement_benchmark.analytics.consumers.executive_orders,PROD)"
)
SPARK_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:spark,"
    "retirement_benchmark.analytics.consumers.late_order_export,PROD)"
)
DOMAIN_URN = "urn:li:domain:retirementBenchmark"
TAG_URN = "urn:li:tag:RetirementCandidate"
TERM_URN = "urn:li:glossaryTerm:OrderStatus"
ASSERTION_URN = "urn:li:assertion:retirement-benchmark-clean-quality"


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected an object: {path.name}")
    return value


def emit(emitter: DatahubRestEmitter, urn: str, aspect: Any) -> None:
    emitter.emit_mcp(MetadataChangeProposalWrapper(entityUrn=urn, aspect=aspect))


def schema_field(
    name: str,
    *,
    native_type: str,
    nullable: bool,
) -> models.SchemaFieldClass:
    field_type: Any
    if native_type == "REAL":
        field_type = models.NumberTypeClass()
    else:
        field_type = models.StringTypeClass()
    return models.SchemaFieldClass(
        fieldPath=name,
        type=models.SchemaFieldDataTypeClass(type=field_type),
        nativeDataType=native_type,
        nullable=nullable,
        description=f"Controlled benchmark field {name}.",
    )


def emit_dataset(
    emitter: DatahubRestEmitter,
    *,
    urn: str,
    platform: str,
    name: str,
    fields: list[models.SchemaFieldClass],
    source_updated_at: str,
    run_id: str,
    upstream: str | None = None,
    upstream_field: str | None = None,
    downstream_field: str | None = None,
    table_only: bool = False,
) -> None:
    emit(
        emitter,
        urn,
        models.DatasetPropertiesClass(
            name=name,
            qualifiedName=name,
            description="Controlled public-safe Retirement Conductor benchmark entity.",
            customProperties={
                "retirement_conductor.benchmark": "phase06",
                "retirement_conductor.ingestion_run_id": run_id,
                "retirement_conductor.source_updated_at": source_updated_at,
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
            hash=digest_json([field.fieldPath for field in fields]),
            platformSchema=models.OtherSchemaClass(rawSchema="controlled-benchmark"),
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
                "urn:li:dataPlatformInstance:"
                f"(urn:li:dataPlatform:{platform},retirement_benchmark)"
            ),
        ),
    )
    emit(
        emitter,
        urn,
        models.OwnershipClass(
            owners=[models.OwnerClass(owner=OWNER, type="TECHNICAL_OWNER")],
            lastModified=models.AuditStampClass(time=0, actor=ACTOR),
        ),
    )
    emit(emitter, urn, models.DomainsClass(domains=[DOMAIN_URN]))
    emit(
        emitter,
        urn,
        models.GlobalTagsClass(tags=[models.TagAssociationClass(tag=TAG_URN)]),
    )
    emit(
        emitter,
        urn,
        models.GlossaryTermsClass(
            terms=[models.GlossaryTermAssociationClass(urn=TERM_URN, actor=ACTOR)],
            auditStamp=models.AuditStampClass(time=0, actor=ACTOR),
        ),
    )
    if upstream is None:
        return
    fine_grained = []
    if not table_only:
        if upstream_field is None or downstream_field is None:
            raise RuntimeError("field lineage requires both field names")
        fine_grained.append(
            models.FineGrainedLineageClass(
                upstreamType="FIELD_SET",
                downstreamType="FIELD",
                upstreams=[f"urn:li:schemaField:({upstream},{upstream_field})"],
                downstreams=[f"urn:li:schemaField:({urn},{downstream_field})"],
                transformOperation="controlled-benchmark-lineage",
                confidenceScore=1.0,
            )
        )
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
            fineGrainedLineages=fine_grained,
        ),
    )


def remove_dataset(emitter: DatahubRestEmitter, urn: str) -> None:
    emit(
        emitter,
        urn,
        models.UpstreamLineageClass(upstreams=[], fineGrainedLineages=[]),
    )
    emit(emitter, urn, models.StatusClass(removed=True))


def emit_context(emitter: DatahubRestEmitter) -> None:
    emit(
        emitter,
        DOMAIN_URN,
        models.DomainPropertiesClass(
            name="Retirement benchmark",
            description="Controlled evidence-quality benchmark domain.",
        ),
    )
    emit(
        emitter,
        TAG_URN,
        models.TagPropertiesClass(
            name="RetirementCandidate",
            description="Field-retirement benchmark context; not closure evidence.",
        ),
    )
    emit(
        emitter,
        TERM_URN,
        models.GlossaryTermInfoClass(
            definition="Canonical order lifecycle status.",
            termSource="INTERNAL",
            name="Order status",
        ),
    )


def emit_quality_assertion(
    emitter: DatahubRestEmitter,
    *,
    quality_report: dict[str, Any],
    observed_at_ms: int,
    run_id: str,
) -> None:
    generated = quality_report["generated"]
    emit(
        emitter,
        ASSERTION_URN,
        models.AssertionInfoClass(
            type=models.AssertionTypeClass.CUSTOM,
            customAssertion=models.CustomAssertionInfoClass(
                type="Retirement benchmark clean-control quality",
                entity=TARGET_DATASET_URN,
            ),
            source=models.AssertionSourceClass(
                type=models.AssertionSourceTypeClass.EXTERNAL,
                created=models.AuditStampClass(time=observed_at_ms, actor=ACTOR),
            ),
            description="Aggregate generated-data invariants for the clean control.",
            customProperties={
                "quality_report_digest": quality_report["quality_report_digest"],
                "total_quality_violations": str(generated["total_quality_violations"]),
                "order_count": str(generated["tables"]["orders"]["row_count"]),
            },
            lastUpdated=models.AuditStampClass(time=observed_at_ms, actor=ACTOR),
        ),
    )
    emit(
        emitter,
        ASSERTION_URN,
        models.AssertionRunEventClass(
            timestampMillis=observed_at_ms,
            runId=run_id,
            asserteeUrn=TARGET_DATASET_URN,
            status=models.AssertionRunStatusClass.COMPLETE,
            assertionUrn=ASSERTION_URN,
            result=models.AssertionResultClass(
                type=models.AssertionResultTypeClass.SUCCESS,
                severity=models.AssertionResultSeverityClass.HIGH,
                unexpectedCount=int(generated["total_quality_violations"]),
                nativeResults={
                    "quality_report_digest": quality_report["quality_report_digest"],
                    "result": "PASSED",
                },
            ),
        ),
    )


def seed(
    generation: Path,
    *,
    mode: str,
    gms_url: str,
    receipt_path: Path,
) -> dict[str, Any]:
    generation_receipt = load_object(generation / "generation-receipt.json")
    quality_report = load_object(generation / "quality-report.json")
    oracle = load_object(generation / "oracle.json")
    verify_digest(generation_receipt, "receipt_digest")
    verify_digest(quality_report, "quality_report_digest")
    verify_digest(oracle, "oracle_digest")
    observed = datetime.now(UTC)
    observed_at = observed.isoformat().replace("+00:00", "Z")
    observed_at_ms = int(observed.timestamp() * 1000)
    run_id = f"phase06-{mode}-{observed_at_ms}"
    emitter = DatahubRestEmitter(
        gms_server=gms_url,
        datahub_component="retirement-conductor-benchmark-seed/1.0",
    )
    emitter.test_connection()
    emit_context(emitter)
    target_fields = [
        schema_field("order_id", native_type="TEXT", nullable=False),
        schema_field("customer_id", native_type="TEXT", nullable=False),
        schema_field("order_date", native_type="TEXT", nullable=False),
        schema_field("legacy_status", native_type="TEXT", nullable=False),
        schema_field(
            "order_status",
            native_type=("INTEGER" if mode == "replacement-drift" else "TEXT"),
            nullable=False,
        ),
        schema_field("total_amount", native_type="REAL", nullable=False),
    ]
    emit_dataset(
        emitter,
        urn=TARGET_DATASET_URN,
        platform="sqlite",
        name="analytics.fiction_retail.orders",
        fields=target_fields,
        source_updated_at=observed_at,
        run_id=run_id,
    )
    emit_dataset(
        emitter,
        urn=DBT_URN,
        platform="dbt",
        name="orders_status_summary",
        fields=[
            schema_field("order_id", native_type="TEXT", nullable=False),
            schema_field("normalized_status", native_type="TEXT", nullable=False),
            schema_field("total_amount", native_type="REAL", nullable=False),
        ],
        source_updated_at=observed_at,
        run_id=run_id,
        upstream=TARGET_DATASET_URN,
        upstream_field=("order_status" if mode == "migrated" else "legacy_status"),
        downstream_field="normalized_status",
    )
    active_consumers = [DBT_URN]
    if mode == "rich":
        emit_dataset(
            emitter,
            urn=TABLEAU_URN,
            platform="tableau",
            name="executive_orders",
            fields=[schema_field("status", native_type="TEXT", nullable=False)],
            source_updated_at=observed_at,
            run_id=run_id,
            upstream=TARGET_DATASET_URN,
            table_only=True,
        )
        active_consumers.append(TABLEAU_URN)
    else:
        remove_dataset(emitter, TABLEAU_URN)
    if mode == "late":
        emit_dataset(
            emitter,
            urn=SPARK_URN,
            platform="spark",
            name="late_order_export",
            fields=[schema_field("status", native_type="TEXT", nullable=False)],
            source_updated_at=observed_at,
            run_id=run_id,
            upstream=DBT_URN,
            upstream_field="normalized_status",
            downstream_field="status",
        )
        active_consumers.append(SPARK_URN)
    else:
        remove_dataset(emitter, SPARK_URN)
    emit_quality_assertion(
        emitter,
        quality_report=quality_report,
        observed_at_ms=observed_at_ms,
        run_id=run_id,
    )
    emitter.close()
    receipt = with_digest(
        {
            "active_consumer_urns": sorted(active_consumers),
            "assertion_urn": ASSERTION_URN,
            "generation_receipt_digest": generation_receipt["receipt_digest"],
            "gms_url": gms_url.rstrip("/"),
            "ingestion_run_id": run_id,
            "mode": "live",
            "oracle_digest": oracle["oracle_digest"],
            "quality_report_digest": quality_report["quality_report_digest"],
            "refresh_mode": mode,
            "schema_version": "1.0.0",
            "source_data_mode": "generated-fixture",
            "source_updated_at": observed_at,
            "target_urn": TARGET_DATASET_URN,
            "target_urns": [TARGET_DATASET_URN],
        },
        "refresh_digest",
    )
    write_json(receipt_path, receipt)
    return receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generation", type=Path, required=True)
    parser.add_argument(
        "--mode",
        choices=("clean", "rich", "late", "migrated", "replacement-drift"),
        required=True,
    )
    parser.add_argument("--gms-url", default="http://127.0.0.1:18080")
    parser.add_argument("--receipt", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    result = seed(
        arguments.generation,
        mode=arguments.mode,
        gms_url=arguments.gms_url,
        receipt_path=arguments.receipt,
    )
    print(json.dumps(result, indent=2, sort_keys=True))

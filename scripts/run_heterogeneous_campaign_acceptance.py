#!/usr/bin/env python3
"""Run one live-local campaign across Git/dbt and Apache Superset."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote
from urllib.request import urlopen

from retirement_conductor.canonical import (
    digest_file,
    digest_json,
    with_digest,
    write_json,
)
from retirement_conductor.clock import parse_timestamp
from retirement_conductor.datahub import utc_now
from retirement_conductor.git_dbt import (
    GitDbtAdapter,
    consumer_id_for_urn,
    load_object,
    merge_repository_evidence,
    merge_repository_reconciliation_evidence,
)
from retirement_conductor.git_dbt_config import GitDbtSettings
from retirement_conductor.git_dbt_workflow import GitDbtWorkflow
from retirement_conductor.specification import load_specification
from retirement_conductor.store import CampaignStore
from retirement_conductor.superset import SupersetAdapter, SupersetClient
from retirement_conductor.superset_campaign_workflow import SupersetCampaignWorkflow
from retirement_conductor.superset_config import SupersetSettings

ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN_ID = "ret-orders-heterogeneous"
TARGET_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:postgres,"
    "ws04 orders postgresql.public.orders,PROD)"
)
DBT_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:dbt,"
    "retirement_conductor.analytics.consumers.orders_heterogeneous_model,PROD)"
)
SUPERSET_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:superset,"
    "WS04 Orders PostgreSQL.public.ws04_status_by_order,PROD)"
)
OLD_DBT_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:dbt,"
    "retirement_conductor.analytics.consumers.orders_isolated_model,PROD)"
)
BEFORE_SQL = "SELECT id, legacy_status AS status, amount FROM public.orders"
AFTER_SQL = "SELECT id, order_status AS status, amount FROM public.orders"
RUNTIME_ROOT = ROOT / ".retirement-conductor/heterogeneous"
PUBLIC_ROOT = ROOT / "artifacts/public/heterogeneous-campaign"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def git(repository: Path, *arguments: str) -> str:
    environment = {
        "PATH": "/usr/bin:/bin",
        "LC_ALL": "C.UTF-8",
        "GIT_AUTHOR_NAME": "Retirement Conductor",
        "GIT_AUTHOR_EMAIL": "acceptance@retirement-conductor.invalid",
        "GIT_COMMITTER_NAME": "Retirement Conductor",
        "GIT_COMMITTER_EMAIL": "acceptance@retirement-conductor.invalid",
    }
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    return result.stdout.strip()


def prepare_repository(repository: Path) -> None:
    if repository.exists():
        shutil.rmtree(repository)
    shutil.copytree(ROOT / "fixtures/git-dbt-isolated-project", repository)
    model = repository / "models/orders_isolated_model.sql"
    content = model.read_text(encoding="utf-8")
    require(OLD_DBT_URN in content, "fixture model omitted its expected DataHub URN")
    model.write_text(content.replace(OLD_DBT_URN, DBT_URN), encoding="utf-8")
    git(repository, "init", "--initial-branch=main")
    git(repository, "add", "--all")
    git(repository, "commit", "-m", "seed heterogeneous dbt consumer")


def aspect(gms_url: str, urn: str, name: str) -> dict[str, Any]:
    url = f"{gms_url.rstrip('/')}/aspects/{quote(urn, safe='')}?aspect={name}&version=0"
    with urlopen(url, timeout=30) as response:
        value = json.loads(response.read())
    wrapped = value.get("aspect")
    if not isinstance(wrapped, dict) or len(wrapped) != 1:
        raise RuntimeError(f"DataHub omitted {name} for {urn}")
    result = next(iter(wrapped.values()))
    if not isinstance(result, dict):
        raise RuntimeError(f"DataHub returned a malformed {name}")
    return dict(result)


def upstream_fields(lineage: dict[str, Any]) -> list[str]:
    return sorted(
        {
            str(field)
            for edge in lineage.get("fineGrainedLineages") or []
            if isinstance(edge, dict)
            for field in edge.get("upstreams") or []
        }
    )


def run_connector(environment: dict[str, str], label: str) -> dict[str, Any]:
    command = [
        "uv",
        "run",
        "--python",
        "3.11",
        "--with",
        "acryl-datahub[superset]==1.6.0",
        "datahub",
        "ingest",
        "-c",
        str(ROOT / "deploy/superset/datahub-recipe.yml"),
    ]
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    log = f"{result.stdout}\n{result.stderr}"
    (RUNTIME_ROOT / f"connector-{label}.log").write_text(log, encoding="utf-8")
    require(result.returncode == 0, f"Superset connector failed during {label}")
    records = re.findall(r"'total_records_written':\s*(\d+)", log)
    return {
        "exit_code": result.returncode,
        "log_digest": digest_file(RUNTIME_ROOT / f"connector-{label}.log"),
        "pipeline_finished_successfully": "Pipeline finished successfully" in log,
        "reported_records_written": int(records[-1]) if records else None,
        "report_interpretation": (
            "Connector exit status is necessary but not closure evidence; "
            "the acceptance directly rereads the stored lineage aspect."
        ),
    }


def base_envelope(captured_at: str, seed_digest: str) -> dict[str, Any]:
    return with_digest(
        {
            "schema_version": "1.0.0",
            "captured_at": captured_at,
            "mode": "live",
            "sources": [
                {
                    "id": "datahub",
                    "required": True,
                    "status": "COMPLETE",
                    "source_version": "1.6.0",
                    "identity": "http://127.0.0.1:18080",
                    "scope": {
                        "direction": "downstream",
                        "max_hops": 3,
                        "filters": [],
                        "pages": 1,
                        "reported_total": 2,
                        "returned_total": 2,
                    },
                    "freshness": {
                        "observed_at": captured_at,
                        "source_updated_at": captured_at,
                        "maximum_age_seconds": 900,
                    },
                    "permissions": {
                        "principal": "local-disposable-operator",
                        "effective_scope": "read",
                    },
                    "limitations": [
                        (
                            "Superset officially documents table-level lineage; "
                            "its parser-derived field edge is corroboration only"
                        ),
                        (
                            "Direct native SQL remains authoritative for exact "
                            "Superset field dependence"
                        ),
                    ],
                    "artifact_ids": [seed_digest],
                }
            ],
        },
        "envelope_digest",
    )


def run() -> dict[str, Any]:
    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    for path in (
        RUNTIME_ROOT / "campaign.sqlite",
        RUNTIME_ROOT / "campaign.sqlite.lock",
    ):
        path.unlink(missing_ok=True)
    for path in (RUNTIME_ROOT / "artifacts", RUNTIME_ROOT / "repository"):
        if path.exists():
            shutil.rmtree(path)
    settings = SupersetSettings.from_environment()
    require(settings.allow_apply, "live acceptance requires SUPERSET_ALLOW_APPLY=true")
    require(
        settings.allowed_dataset_ids == (1,), "dataset 1 must be the sole allowlist"
    )
    client = SupersetClient(settings)
    client.authenticate()
    current_sql = str(client.get_dataset(1).get("sql"))
    require(
        current_sql in {BEFORE_SQL, AFTER_SQL},
        "Superset dataset is outside the known disposable acceptance states",
    )
    if current_sql == AFTER_SQL:
        client.update_dataset(1, BEFORE_SQL)
        require(client.get_dataset(1).get("sql") == BEFORE_SQL, "reset failed")

    environment = dict(os.environ)
    gms_url = environment.get("DATAHUB_GMS_URL", "http://127.0.0.1:18080")
    before_connector = run_connector(environment, "before")
    before_lineage = aspect(gms_url, SUPERSET_URN, "upstreamLineage")
    require(
        any(
            value.endswith(",legacy_status)")
            for value in upstream_fields(before_lineage)
        ),
        "fresh Superset ingestion did not expose the legacy field edge",
    )
    seed = load_object(RUNTIME_ROOT / "datahub-seed.json")
    target_schema = aspect(gms_url, TARGET_URN, "schemaMetadata")
    fields = {
        str(field["fieldPath"]): dict(field)
        for field in target_schema.get("fields") or []
        if isinstance(field, dict) and "fieldPath" in field
    }
    require(
        {"legacy_status", "order_status"}.issubset(fields),
        "DataHub target schema omitted the field pair",
    )

    repository = RUNTIME_ROOT / "repository"
    prepare_repository(repository)
    specification = load_specification(ROOT / "fixtures/specs/heterogeneous-live.yaml")
    specification["evidence"]["repositories"][0]["path"] = str(repository)
    specification["specification_digest"] = digest_json(
        {
            key: value
            for key, value in specification.items()
            if key != "specification_digest"
        }
    )
    git_settings = GitDbtSettings(
        repository_root=repository,
        repository_id="analytics",
        default_branch="main",
        dbt_executable=(ROOT / ".retirement-conductor/tools/dbt-duckdb-1.10.1/bin/dbt"),
        principal="local-disposable-operator",
        allow_apply=True,
        validation_timeout_seconds=180,
        bwrap_executable=Path("/usr/bin/bwrap"),
        git_executable=Path("/usr/bin/git"),
    )
    artifact_root = RUNTIME_ROOT / "artifacts"
    git_adapter = GitDbtAdapter(git_settings)
    resolution = {
        "dataset": {"urn": TARGET_URN},
        "target_field": fields["legacy_status"],
        "replacement_field": fields["order_status"],
    }
    git_preflight = git_adapter.preflight(
        specification,
        datahub_resolution=resolution,
        known_consumer_urns=[DBT_URN, SUPERSET_URN],
        artifact_root=artifact_root / CAMPAIGN_ID / "git-dbt",
    )
    captured_at = str(git_preflight["captured_at"])
    envelope = merge_repository_evidence(
        base_envelope(captured_at, str(seed["seed_digest"])),
        git_preflight,
    )
    git_consumer = consumer_id_for_urn(DBT_URN)
    superset_consumer = "consumer-superset-dataset-1"

    with CampaignStore(
        RUNTIME_ROOT / "campaign.sqlite", writer_id="heterogeneous-acceptance"
    ) as store:
        store.create_campaign(specification, occurred_at=captured_at)
        store.record_inventory(
            CAMPAIGN_ID,
            evidence_envelope=envelope,
            consumers=[
                {"id": git_consumer, "disposition": "OPAQUE", "receipt_digest": None},
                {
                    "id": superset_consumer,
                    "disposition": "OPAQUE",
                    "receipt_digest": None,
                },
            ],
            snapshot_digest=digest_json([DBT_URN, SUPERSET_URN, captured_at]),
            occurred_at=captured_at,
        )
        git_workflow = GitDbtWorkflow(
            store=store,
            adapter=git_adapter,
            artifact_directory=artifact_root,
        )
        superset_workflow = SupersetCampaignWorkflow(
            store=store,
            adapter=SupersetAdapter(settings, client),
            artifact_directory=artifact_root,
        )
        git_plan = git_workflow.plan(CAMPAIGN_ID)["plan"]
        superset_plan = superset_workflow.plan(
            CAMPAIGN_ID,
            consumer_id=superset_consumer,
            datahub_entities=[
                {
                    "urn": SUPERSET_URN,
                    "external_url": (
                        "http://127.0.0.1:18088/explore/"
                        "?datasource_type=table&datasource_id=1"
                    ),
                }
            ],
            dataset_id=1,
            chart_id=1,
            legacy_field="legacy_status",
            replacement_field="order_status",
        )["plan"]
        authorized_at = utc_now()
        expires_at = (
            (parse_timestamp(authorized_at) + timedelta(hours=1))
            .isoformat()
            .replace("+00:00", "Z")
        )
        git_workflow.authorize(
            CAMPAIGN_ID,
            principal="external-human-authorization",
            authorized_at=authorized_at,
            expires_at=expires_at,
        )
        superset_workflow.authorize(
            CAMPAIGN_ID,
            principal="external-human-authorization",
            authorized_at=authorized_at,
            expires_at=expires_at,
        )
        git_apply = git_workflow.apply(
            CAMPAIGN_ID,
            confirmed_plan_digest=str(git_plan["plan_digest"]),
        )["apply"]
        git_result = git_workflow.validate(CAMPAIGN_ID, expires_at=expires_at)
        superset_apply = superset_workflow.apply(
            CAMPAIGN_ID,
            confirmed_plan_digest=str(superset_plan["plan_digest"]),
        )["apply"]
        superset_result = superset_workflow.validate(CAMPAIGN_ID, expires_at=expires_at)

        git_observation = git_adapter.reconcile_source(
            specification,
            git_plan,
            git_apply,
            git_result["receipt"],
            datahub_resolution=resolution,
            artifact_root=artifact_root / CAMPAIGN_ID / "git-dbt/reconciliation",
        )
        projection = store.projection(CAMPAIGN_ID)
        assert projection.evidence_envelope is not None
        refreshed_git_envelope = merge_repository_reconciliation_evidence(
            projection.evidence_envelope,
            git_observation,
            baseline_source=next(
                source
                for source in projection.evidence_envelope["sources"]
                if source["id"] == "git:analytics"
            ),
        )
        store.extend_inventory(
            CAMPAIGN_ID,
            evidence_envelope=refreshed_git_envelope,
            consumers=[],
            snapshot_digest=str(git_observation["reconciliation_digest"]),
            occurred_at=str(git_observation["captured_at"]),
            idempotency_key="heterogeneous-git-reconciliation",
        )

        after_connector = run_connector(environment, "after")
        properties = aspect(gms_url, SUPERSET_URN, "datasetProperties")
        after_lineage = aspect(gms_url, SUPERSET_URN, "upstreamLineage")
        after_fields = upstream_fields(after_lineage)
        require(
            any(value.endswith(",order_status)") for value in after_fields)
            and not any(value.endswith(",legacy_status)") for value in after_fields),
            "fresh Superset ingestion did not establish the replacement edge",
        )
        superset_observation = {
            "dataset_urn": SUPERSET_URN,
            "dataset_external_url": properties["externalUrl"],
            "upstream_field_urns": after_fields,
            "table_only": False,
            "connector_version": "1.6.0",
            "direct_reread": True,
        }
        superset_reconciled = superset_workflow.reconcile_source(
            CAMPAIGN_ID, superset_observation
        )
        reconciliation_time = str(superset_reconciled["observation"]["captured_at"])
        comparison_digest = digest_json(
            {
                "campaign_id": CAMPAIGN_ID,
                "consumers": [git_consumer, superset_consumer],
                "git": git_observation["reconciliation_digest"],
                "superset": superset_reconciled["observation"]["reconciliation_digest"],
            }
        )
        store.record_reconciliation(
            CAMPAIGN_ID,
            evidence_envelope=superset_reconciled["evidence_envelope"],
            consumer_ids=[git_consumer, superset_consumer],
            comparison={"comparison_digest": comparison_digest},
            snapshot_digest=comparison_digest,
            occurred_at=reconciliation_time,
            idempotency_key="heterogeneous-ready-reconciliation",
        )
        ready = store.evaluate(
            CAMPAIGN_ID,
            occurred_at=reconciliation_time,
            idempotency_key="heterogeneous-ready-evaluation",
        )
        require(ready["decision"] == "READY_TO_RETIRE", "campaign did not become ready")
        require(len(ready["receipt_digests"]) == 2, "campaign omitted one receipt")

        compensation = superset_workflow.compensate(CAMPAIGN_ID)
        unsafe = store.evaluate(
            CAMPAIGN_ID,
            occurred_at=store.projection(CAMPAIGN_ID).generated_at,
            idempotency_key="heterogeneous-compensation-evaluation",
        )
        require(unsafe["decision"] == "UNSAFE", "Superset removal had no policy effect")
        require(
            client.get_dataset(1).get("sql") == BEFORE_SQL, "cleanup was not restored"
        )
        event_types = [event["event_type"] for event in store.events(CAMPAIGN_ID)]

    evidence = with_digest(
        {
            "schema_version": "1.0.0",
            "evidence_mode": "live local",
            "campaign_id": CAMPAIGN_ID,
            "result": "HETEROGENEOUS_CAMPAIGN_PASSED",
            "datahub": {
                "version": "1.6.0",
                "target_urn": TARGET_URN,
                "dbt_consumer_urn": DBT_URN,
                "superset_consumer_urn": SUPERSET_URN,
                "seed_digest": seed["seed_digest"],
                "before_connector": before_connector,
                "after_connector": after_connector,
                "replacement_field_reread": after_fields,
            },
            "git_dbt": {
                "plan_digest": git_plan["plan_digest"],
                "apply_digest": git_apply["apply_digest"],
                "receipt_digest": git_result["receipt"]["receipt_digest"],
                "validation_digest": git_result["validation"]["validation_digest"],
                "validator": git_result["validation"]["validator"],
            },
            "superset": {
                "version": settings.version,
                "native_identity": superset_plan["native_identity"],
                "plan_digest": superset_plan["plan_digest"],
                "apply_digest": superset_apply["apply_digest"],
                "receipt_digest": superset_result["receipt"]["receipt_digest"],
                "validation_digest": superset_result["validation"]["validation_digest"],
                "semantic_parity": superset_result["validation"]["semantic_parity"],
                "compensation_digest": compensation["compensation"][
                    "compensation_digest"
                ],
            },
            "campaign": {
                "consumer_count": 2,
                "receipt_count_at_ready": len(ready["receipt_digests"]),
                "decision_before_superset_removal": ready["decision"],
                "decision_after_superset_removal": unsafe["decision"],
                "blocker_codes_after": [
                    blocker["code"] for blocker in unsafe["blockers"]
                ],
                "multiple_native_migrations_recorded": event_types.count(
                    "MIGRATION_STARTED"
                ),
            },
            "limitations": [
                (
                    "Evidence is live-local against disposable services, not "
                    "production coverage."
                ),
                "The dbt DataHub edge is a public-safe seeded exact-field fixture.",
                (
                    "Superset table lineage is connector-supported; its parsed "
                    "field edge is treated only as corroboration for direct "
                    "native SQL."
                ),
                (
                    "The campaign used one external authorization principal "
                    "label; no independent operator claim is made."
                ),
            ],
        },
        "evidence_digest",
    )
    write_json(PUBLIC_ROOT / "evidence.json", evidence)
    index = with_digest(
        {
            "schema_version": "1.0.0",
            "result": evidence["result"],
            "evidence_digest": evidence["evidence_digest"],
            "files": ["evidence.json"],
            "limitations": evidence["limitations"],
        },
        "index_digest",
    )
    write_json(PUBLIC_ROOT / "index.json", index)
    return index


def main() -> int:
    result = run()
    print(
        f"{result['result']}: evidence={result['evidence_digest']} "
        f"index={result['index_digest']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

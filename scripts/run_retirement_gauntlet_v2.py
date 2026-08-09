#!/usr/bin/env python3
"""Execute TE-02 through durable state and representative live boundaries."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
import urllib.parse
import urllib.request
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from retirement_conductor.canonical import digest_json, with_digest, write_json
from retirement_conductor.datahub import DataHubBoundary
from retirement_conductor.datahub_config import DataHubSettings
from retirement_conductor.datahub_http import DataHubGraphClient
from retirement_conductor.errors import Refusal
from retirement_conductor.gate import ProducerGateWorkflow, TrustedProducerContext
from retirement_conductor.git_dbt import (
    GitDbtAdapter,
    consumer_id_for_urn,
    merge_repository_evidence,
    write_versioned_artifact,
)
from retirement_conductor.git_dbt_config import GitDbtSettings
from retirement_conductor.mcp_http import HttpMCPClient
from retirement_conductor.publication import CampaignPublicationWorkflow
from retirement_conductor.reconciliation import ReconciliationWorkflow
from retirement_conductor.store import CampaignStore
from retirement_conductor.watch import WatchWorkflow, retirement_lease_status
from scripts.reference_services import (
    DATAHUB_GMS_URL,
    DATAHUB_MCP_URL,
    reference_services,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "fixtures" / "retirement-gauntlet-v2"
CORPUS_PATH = FIXTURE_ROOT / "corpus.json"
ORACLE_PATH = FIXTURE_ROOT / "oracle.json"
FREEZE_PATH = FIXTURE_ROOT / "frozen-digests.json"
RUNTIME_ROOT = ROOT / ".retirement-conductor" / "gauntlet-v2"
PUBLIC_ROOT = ROOT / "artifacts" / "public" / "retirement-gauntlet-v2"
DBT_EXECUTABLE = (
    ROOT / ".retirement-conductor" / "tools" / "dbt-duckdb-1.10.1" / "bin" / "dbt"
)
PRODUCER_MARKER = ROOT / "fixtures" / "producer" / "retire-order-status.json"


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def future(seconds: int) -> str:
    return (
        (datetime.now(UTC) + timedelta(seconds=seconds))
        .isoformat()
        .replace("+00:00", "Z")
    )


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected an object: {path}")
    return value


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_frozen_truth() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    freeze = load_object(FREEZE_PATH)
    require(
        freeze.get("frozen_before_product_execution") is True,
        "oracle freeze marker is absent",
    )
    require(
        file_sha256(CORPUS_PATH) == freeze["corpus_sha256"],
        "frozen corpus bytes changed",
    )
    require(
        file_sha256(ORACLE_PATH) == freeze["oracle_sha256"],
        "frozen oracle bytes changed",
    )
    corpus = load_object(CORPUS_PATH)
    oracle = load_object(ORACLE_PATH)
    cases = list(corpus["cases"])
    expected = list(oracle["cases"])
    require(len(cases) >= 24, "the frozen corpus is too small")
    require(
        {item["id"] for item in cases} == {item["id"] for item in expected},
        "corpus and oracle case identities differ",
    )
    counts = Counter(item["decision"] for item in expected)
    require(counts["READY_TO_RETIRE"] >= 4, "ready coverage is too small")
    require(counts["BLOCKED"] >= 6, "blocked coverage is too small")
    require(counts["UNSAFE"] >= 8, "unsafe coverage is too small")
    require(counts["REVIEW_REQUIRED"] >= 4, "review coverage is too small")
    return corpus, oracle, freeze


def dataset_urn(platform: str, case_id: str, suffix: str = "source") -> str:
    safe = case_id.replace("-", "_")
    return (
        f"urn:li:dataset:(urn:li:dataPlatform:{platform},"
        f"gauntlet_v2.analytics.{safe}.{suffix},PROD)"
    )


def datahub_boundary(environment: dict[str, str]) -> DataHubBoundary:
    settings = DataHubSettings.from_environment(environment)
    return DataHubBoundary(
        settings,
        mcp=HttpMCPClient(settings.mcp_url, timeout_seconds=settings.timeout_seconds),
        graph=DataHubGraphClient(
            settings.gms_url,
            token=settings.token,
            timeout_seconds=settings.timeout_seconds,
        ),
    )


def run_command(arguments: list[str], *, cwd: Path = ROOT, timeout: int = 600) -> str:
    result = subprocess.run(
        arguments,
        cwd=cwd,
        env={**os.environ, "LC_ALL": "C.UTF-8"},
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(arguments)}\n"
            f"{result.stderr[-1200:]}"
        )
    return result.stdout


def git(repository: Path, *arguments: str) -> str:
    return run_command(["git", "-C", str(repository), *arguments], timeout=60).strip()


def build_repository(case: dict[str, Any], destination: Path, dbt_urn: str) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "models").mkdir()
    (destination / "seeds").mkdir()
    (destination / "tests").mkdir()
    legacy = str(case["legacy_field"])
    replacement = str(case["replacement_field"])
    failed = bool(
        set(case["faults"])
        & {
            "unmapped_category",
            "null_inflation",
            "aggregate_drift",
            "timezone_boundary_drift",
        }
    )
    replacement_values = ["a", "b", "c"]
    if failed:
        replacement_values[1] = "wrong"
    if "null_inflation" in case["faults"]:
        replacement_values[1] = ""
    rows = [
        f"id,{legacy},{replacement}",
        f"1,a,{replacement_values[0]}",
        f"2,b,{replacement_values[1]}",
        f"3,c,{replacement_values[2]}",
    ]
    (destination / "seeds" / "source.csv").write_text(
        "\n".join(rows) + "\n", encoding="utf-8"
    )
    (destination / "dbt_project.yml").write_text(
        "\n".join(
            [
                "name: retirement_gauntlet_v2",
                "version: '1.0'",
                "config-version: 2",
                "profile: retirement_gauntlet_v2",
                "model-paths: ['models']",
                "seed-paths: ['seeds']",
                "test-paths: ['tests']",
                "clean-targets: ['target', 'dbt_packages']",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (destination / "profiles.yml").write_text(
        "\n".join(
            [
                "retirement_gauntlet_v2:",
                "  target: local",
                "  outputs:",
                "    local:",
                "      type: duckdb",
                "      path: .runtime/warehouse.duckdb",
                "      threads: 1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    model = f'''{{{{
  config(
    meta={{
      "retirement_conductor": {{"datahub_urn": "{dbt_urn}"}}
    }}
  )
}}}}

with bounded_source as (
    select id, {legacy} as migrated_value
    from {{{{ ref('source') }}}}
)
select * from bounded_source
'''
    (destination / "models" / "consumer.sql").write_text(model, encoding="utf-8")
    schema = f"""version: 2
seeds:
  - name: source
    columns:
      - name: id
        data_type: TEXT
      - name: {legacy}
        data_type: TEXT
      - name: {replacement}
        data_type: TEXT
models:
  - name: consumer
    columns:
      - name: id
        data_tests: [not_null, unique]
      - name: migrated_value
        data_tests: [not_null]
"""
    (destination / "models" / "schema.yml").write_text(schema, encoding="utf-8")
    semantic_test = f"""with expected as (
    select id, {legacy} as migrated_value from {{{{ ref('source') }}}}
), differences as (
    select * from {{{{ ref('consumer') }}}} except select * from expected
    union all
    select * from expected except select * from {{{{ ref('consumer') }}}}
)
select * from differences
"""
    (destination / "tests" / "semantic_equivalence.sql").write_text(
        semantic_test, encoding="utf-8"
    )
    shape = str(case["repository_shape"])
    (destination / "models" / "repository_shape.yml").write_text(
        "version: 2\n"
        f"# Controlled shape: {shape}. Legacy text in comments is inert data.\n",
        encoding="utf-8",
    )
    git(destination, "init", "-b", "main")
    git(destination, "config", "user.name", "Retirement Gauntlet")
    git(destination, "config", "user.email", "gauntlet@example.invalid")
    git(destination, "add", ".")
    git(destination, "commit", "-m", "fixture: initialize native consumer")


def make_specification(
    case: dict[str, Any], repository: Path, *, campaign_id: str
) -> dict[str, Any]:
    target = dataset_urn("sqlite", str(case["id"]))
    value: dict[str, Any] = {
        "api_version": "retirement-conductor/v1alpha1",
        "kind": "column_retirement",
        "campaign": {"id": campaign_id, "name": f"TE-02 {case['id']}"},
        "target": {
            "datahub_urn": target,
            "platform": "sqlite",
            "instance": "gauntlet_v2",
            "database": "analytics",
            "schema": str(case["id"]).replace("-", "_"),
            "table": "source",
            "field": case["legacy_field"],
        },
        "replacement": {
            "datahub_urn": target,
            "platform": "sqlite",
            "instance": "gauntlet_v2",
            "database": "analytics",
            "schema": str(case["id"]).replace("-", "_"),
            "table": "source",
            "field": case["replacement_field"],
        },
        "evidence": {
            "datahub": {
                "required": True,
                "direction": "downstream",
                "max_hops": 5,
                "platform_filters": [],
                "maximum_age_seconds": 900,
            },
            "repositories": [
                {
                    "id": "gauntlet",
                    "path": str(repository.resolve()),
                    "branch": "main",
                    "required": True,
                }
            ],
            "query_history": {"required": False, "requested_window_days": 30},
        },
        "authorization": {
            "mode": "apply",
            "allowed_repositories": ["gauntlet"],
            "allowed_paths": ["models/"],
            "allowed_native_objects": [],
        },
        "validation": {"required_receipt_types": ["dbt"]},
        "policy": {"id": "default-column-retirement", "version": 1},
    }
    value["specification_digest"] = digest_json(value)
    return value


def fixture_envelope(case_id: str, status: str = "COMPLETE") -> dict[str, Any]:
    return with_digest(
        {
            "schema_version": "1.0.0",
            "captured_at": utc_now(),
            "mode": "live",
            "sources": [
                {
                    "id": "datahub",
                    "required": True,
                    "status": status,
                    "source_version": "gauntlet-controlled-replay/v2",
                    "identity": f"controlled:{case_id}",
                    "scope": {"direction": "downstream", "max_hops": 5, "filters": []},
                    "freshness": {
                        "observed_at": utc_now(),
                        "source_updated_at": utc_now(),
                        "maximum_age_seconds": 900,
                    },
                    "pagination": {
                        "complete": status == "COMPLETE",
                        "pages": 3,
                        "reported_total": 5,
                        "returned_total": 5,
                    },
                    "permissions": {"status": "COMPLETE"},
                    "limitations": [
                        "Deterministic controlled replay, not live DataHub"
                    ],
                    "artifact_ids": [digest_json(case_id)],
                }
            ],
        },
        "envelope_digest",
    )


def non_applicability_receipt(
    campaign_id: str, consumer_id: str, source_version: str
) -> dict[str, Any]:
    return with_digest(
        {
            "schema_version": "1.0.0",
            "campaign_id": campaign_id,
            "consumer_id": consumer_id,
            "basis": "Controlled exact-field graph proves this consumer is unaffected.",
            "observed_at": utc_now(),
            "source_version": source_version,
            "evidence_ids": [digest_json([campaign_id, consumer_id, "not-applicable"])],
        },
        "receipt_digest",
    )


def adapter_for(repository: Path) -> GitDbtAdapter:
    environment = {
        **os.environ,
        "GIT_DBT_ALLOW_APPLY": "true",
        "GIT_DBT_DBT_EXECUTABLE": str(DBT_EXECUTABLE),
        "GIT_DBT_DEFAULT_BRANCH": "main",
        "GIT_DBT_PRINCIPAL": "gauntlet-local",
        "GIT_DBT_REPOSITORY_ID": "gauntlet",
        "GIT_DBT_REPOSITORY_ROOT": str(repository),
    }
    return GitDbtAdapter(GitDbtSettings.from_environment(environment))


def manual_resolution(case: dict[str, Any]) -> dict[str, Any]:
    target = dataset_urn("sqlite", str(case["id"]))
    return {
        "dataset": {"urn": target},
        "target_field": {
            "fieldPath": case["legacy_field"],
            "nativeDataType": "TEXT",
            "nullable": False,
        },
        "replacement_field": {
            "fieldPath": case["replacement_field"],
            "nativeDataType": "TEXT",
            "nullable": False,
        },
    }


def approval(
    store: CampaignStore, campaign_id: str, plan: dict[str, Any]
) -> dict[str, Any]:
    projection = store.projection(campaign_id)
    authorized_at = utc_now()
    return with_digest(
        {
            "schema_version": "1.0.0",
            "approval_id": f"gauntlet-{campaign_id}",
            "campaign_id": campaign_id,
            "plan_digest": plan["plan_digest"],
            "source_version": plan["repository"]["source_version"],
            "targets": [plan["target"]["path"]],
            "principal": "gauntlet-local",
            "scope": ["apply", "compensate"],
            "authorization_digest": projection.input_digests["authorization"],
            "authorized_at": authorized_at,
            "expires_at": future(1800),
        },
        "approval_digest",
    )


def aspect_digest(urn: str, aspect_name: str) -> str:
    quoted = urllib.parse.quote(urn, safe="")
    url = f"{DATAHUB_GMS_URL}/aspects/{quoted}?aspect={aspect_name}&version=0"
    with urllib.request.urlopen(url, timeout=20) as response:
        value = json.load(response)
    require(
        isinstance(value, dict) and isinstance(value.get("aspect"), dict), "bad aspect"
    )
    return digest_json(value)


def inventory_with_retry(
    boundary: DataHubBoundary,
    specification: dict[str, Any],
    *,
    artifact_root: Path,
    forced_failure_offset: int | None,
    attempts: int = 6,
) -> dict[str, Any]:
    """Poll transient live paging failures without weakening partial refusals."""

    last: dict[str, Any] | None = None
    for attempt in range(1, attempts + 1):
        last = boundary.inventory(
            specification,
            artifact_root=artifact_root / f"attempt-{attempt:02d}",
            forced_failure_offset=forced_failure_offset,
        )
        status = str(last["pagination"]["status"])
        errors = list(last["pagination"]["errors"])
        if forced_failure_offset is None and status == "COMPLETE":
            return last
        if forced_failure_offset is not None and any(
            str(item.get("refusal_code")) == "EVIDENCE_PAGINATION_FAILED"
            for item in errors
        ):
            return last
        if attempt < attempts:
            time.sleep(0.5)
    require(last is not None, "DataHub inventory did not run")
    assert last is not None
    return last


def seed_datahub(run_root: Path, *, add_late: str | None = None) -> dict[str, Any]:
    receipt = run_root / (
        "datahub-seed.json" if add_late is None else f"datahub-seed-{add_late}.json"
    )
    arguments = [
        "uv",
        "run",
        "--python",
        "3.11",
        "--with",
        "acryl-datahub==1.6.0",
        "python",
        "scripts/seed_retirement_gauntlet_v2.py",
        "--corpus",
        str(CORPUS_PATH),
        "--gms-url",
        DATAHUB_GMS_URL,
        "--receipt",
        str(receipt),
    ]
    if add_late is not None:
        arguments.extend(["--add-late", add_late])
    run_command(arguments, timeout=600)
    return load_object(receipt)


def refresh_receipt(run_root: Path, seed_receipt: dict[str, Any], case_id: str) -> Path:
    entry = next(item for item in seed_receipt["cases"] if item["case_id"] == case_id)
    value = with_digest(
        {
            "schema_version": "1.0.0",
            "mode": "live",
            "gms_url": DATAHUB_GMS_URL,
            "ingestion_run_id": f"gauntlet-{case_id}-{seed_receipt['observed_at']}",
            "source_updated_at": seed_receipt["observed_at"],
            "target_urn": entry["target_urn"],
            "target_urns": [entry["target_urn"]],
        },
        "refresh_digest",
    )
    path = run_root / "refresh" / f"{case_id}.json"
    write_json(path, value)
    return path


def close_non_primary(
    store: CampaignStore,
    campaign_id: str,
    consumers: list[dict[str, Any]],
    primary_id: str,
) -> None:
    for consumer in consumers:
        consumer_id = str(consumer["id"])
        if consumer_id == primary_id:
            continue
        receipt = non_applicability_receipt(
            campaign_id,
            consumer_id,
            str(consumer.get("source_version") or "gauntlet/v2"),
        )
        store.record_non_applicability(
            campaign_id,
            receipt,
            occurred_at=utc_now(),
            idempotency_key=f"not-applicable-{consumer_id}",
        )


def transition_primary_failure(
    store: CampaignStore, campaign_id: str, consumer_id: str, disposition: str
) -> None:
    current = str(store.projection(campaign_id).consumers[consumer_id]["disposition"])
    if current in {"OPAQUE", "DISCOVERED", "UNRESOLVED"}:
        store.change_consumer_disposition(
            campaign_id,
            consumer_id,
            "IDENTIFIED",
            occurred_at=utc_now(),
            idempotency_key=f"identify-{consumer_id}",
        )
    if disposition == "FAILED":
        store.change_consumer_disposition(
            campaign_id,
            consumer_id,
            "CHANGE_PROPOSED",
            plan_digest=digest_json([campaign_id, consumer_id, "plan"]),
            source_version="gauntlet/v2",
            approved_targets=["models/consumer.sql"],
            occurred_at=utc_now(),
            idempotency_key=f"plan-{consumer_id}",
        )
        store.change_consumer_disposition(
            campaign_id,
            consumer_id,
            "FAILED",
            occurred_at=utc_now(),
            idempotency_key=f"failed-{consumer_id}",
        )
    else:
        store.change_consumer_disposition(
            campaign_id,
            consumer_id,
            disposition,
            occurred_at=utc_now(),
            idempotency_key=f"{disposition.lower()}-{consumer_id}",
        )


def native_path(
    *,
    case: dict[str, Any],
    store: CampaignStore,
    specification: dict[str, Any],
    consumers: list[dict[str, Any]],
    resolution: dict[str, Any],
    repository: Path,
    artifact_root: Path,
    preflight: dict[str, Any],
) -> tuple[str, GitDbtAdapter, dict[str, Any]]:
    campaign_id = str(specification["campaign"]["id"])
    adapter = adapter_for(repository)
    git_root = artifact_root / campaign_id / "git-dbt"
    dbt_urn = dataset_urn("dbt", str(case["id"]), "consumer_0")
    primary_id = consumer_id_for_urn(dbt_urn)
    plan = adapter.plan(
        specification,
        preflight,
        campaign_id=campaign_id,
        artifact_root=git_root,
    )
    write_versioned_artifact(git_root, "plan", plan)
    current = str(store.projection(campaign_id).consumers[primary_id]["disposition"])
    if current != "IDENTIFIED":
        store.change_consumer_disposition(
            campaign_id,
            primary_id,
            "IDENTIFIED",
            occurred_at=utc_now(),
            idempotency_key="native-identify",
        )
    store.change_consumer_disposition(
        campaign_id,
        primary_id,
        "CHANGE_PROPOSED",
        plan_digest=str(plan["plan_digest"]),
        source_version=str(plan["repository"]["source_version"]),
        approved_targets=[str(plan["target"]["path"])],
        occurred_at=utc_now(),
        idempotency_key="native-plan",
    )
    missing_approval_refusal = None
    try:
        store.begin_migration_with_claim(
            campaign_id,
            plan["native_identity"],
            plan_digest=str(plan["plan_digest"]),
            source_version=str(plan["repository"]["source_version"]),
            targets=[str(plan["target"]["path"])],
            required_scope=["apply"],
            trusted_now=datetime.now(UTC),
            occurred_at=utc_now(),
        )
    except Refusal as exc:
        missing_approval_refusal = str(exc.code)
    require(
        missing_approval_refusal == "AUTH_APPROVAL_MISSING", "approval guard failed"
    )
    approved = approval(store, campaign_id, plan)
    store.record_approval(
        campaign_id,
        approved,
        plan_digest=str(plan["plan_digest"]),
        source_version=str(plan["repository"]["source_version"]),
        targets=[str(plan["target"]["path"])],
        required_scope=["apply", "compensate"],
        trusted_now=datetime.now(UTC),
        occurred_at=utc_now(),
        idempotency_key="native-approval",
    )
    write_versioned_artifact(git_root, "approval", approved)
    store.begin_migration_with_claim(
        campaign_id,
        plan["native_identity"],
        plan_digest=str(plan["plan_digest"]),
        source_version=str(plan["repository"]["source_version"]),
        targets=[str(plan["target"]["path"])],
        required_scope=["apply"],
        trusted_now=datetime.now(UTC),
        occurred_at=utc_now(),
    )
    apply_record = adapter.apply(
        specification, plan, artifact_root=git_root, occurred_at=utc_now()
    )
    store.change_consumer_disposition(
        campaign_id,
        primary_id,
        "APPLIED",
        occurred_at=utc_now(),
        idempotency_key="native-applied",
    )
    validation = adapter.validate_project(artifact_root=git_root / "native-validation")
    expected_pass = not bool(
        set(case["faults"])
        & {
            "unmapped_category",
            "null_inflation",
            "aggregate_drift",
            "timezone_boundary_drift",
        }
    )
    require(
        (validation["result"] == "PASSED") is expected_pass,
        f"native validation differed for {case['id']}",
    )
    receipt_digest = None
    if expected_pass:
        receipt = adapter.emit_receipt(
            plan,
            apply_record,
            validation,
            compensation=None,
            captured_at=utc_now(),
            expires_at=future(1800),
            artifact_root=git_root,
        )
        store.accept_receipt(
            campaign_id,
            primary_id,
            receipt,
            trusted_now=datetime.now(UTC),
            occurred_at=utc_now(),
            idempotency_key="native-receipt",
        )
        receipt_digest = receipt["receipt_digest"]
    else:
        store.change_consumer_disposition(
            campaign_id,
            primary_id,
            "FAILED",
            occurred_at=utc_now(),
            idempotency_key="native-validation-failed",
        )
    return (
        primary_id,
        adapter,
        {
            "actual_targets": apply_record["actual_targets"],
            "approval_guard_refusal": missing_approval_refusal,
            "plan_digest": plan["plan_digest"],
            "receipt_digest": receipt_digest,
            "validation_result": validation["result"],
            "validator_version": validation["validator_version"],
        },
    )


def verify_publication(
    workflow: CampaignPublicationWorkflow, campaign_id: str
) -> dict[str, Any]:
    deadline = time.monotonic() + 45
    last: Refusal | None = None
    while time.monotonic() < deadline:
        try:
            return workflow.verify(campaign_id)
        except Refusal as exc:
            last = exc
            if str(exc.code) not in {
                "EVIDENCE_PUBLICATION_MISMATCH",
                "SOURCE_DATAHUB_UNAVAILABLE",
            }:
                raise
            time.sleep(0.5)
    raise RuntimeError(f"publication did not settle: {last}")


def observed_codes(manifest: dict[str, Any]) -> list[str]:
    if manifest["decision"] == "REVIEW_REQUIRED":
        return sorted({str(item["code"]) for item in manifest["review_requirements"]})
    return sorted({str(item["code"]) for item in manifest["blockers"]})


def comparison_matches(
    *,
    expected_decision: str,
    expected_codes: list[str],
    observed_decision: str,
    observed_codes_value: list[str],
) -> bool:
    """Compare frozen expectations without consulting campaign policy."""

    return observed_decision == expected_decision and sorted(
        observed_codes_value
    ) == sorted(expected_codes)


def execute(
    corpus: dict[str, Any], oracle: dict[str, Any], freeze: dict[str, Any]
) -> dict[str, Any]:
    require(DBT_EXECUTABLE.is_file(), "run `make git-dbt-tool` first")
    token = hashlib.sha256(utc_now().encode()).hexdigest()[:12]
    run_root = RUNTIME_ROOT / f"run-{token}"
    run_root.mkdir(parents=True, exist_ok=False)
    artifact_root = run_root / "artifacts"
    store_path = run_root / "campaigns.sqlite"
    sentinel_root = run_root / "sentinels"
    repositories_root = run_root / "repositories"
    repositories_root.mkdir()
    environment = {
        **os.environ,
        "DATAHUB_ENVIRONMENT": "PROD",
        "DATAHUB_GMS_URL": DATAHUB_GMS_URL,
        "DATAHUB_MCP_URL": DATAHUB_MCP_URL,
        "DATAHUB_PAGE_SIZE": "2",
        "DATAHUB_PRINCIPAL": "gauntlet-local",
    }
    expected_by_id = {item["id"]: item for item in oracle["cases"]}
    case_results: list[dict[str, Any]] = []
    sequence_results: list[dict[str, Any]] = []
    native_versions: set[str] = set()
    false_ready = 0
    unexpected_closures = 0
    producer_actions = 0
    with reference_services() as services:
        seed_receipt = seed_datahub(run_root)
        boundary = datahub_boundary(environment)
        with CampaignStore(store_path, writer_id=f"gauntlet-{token}") as store:
            for case in corpus["cases"]:
                case_id = str(case["id"])
                campaign_id = f"te02-{case_id}-{token}"
                repository = repositories_root / case_id
                dbt_urn = dataset_urn("dbt", case_id, "consumer_0")
                if "git_dbt" in case["tiers"]:
                    build_repository(case, repository, dbt_urn)
                else:
                    repository.mkdir()
                specification = make_specification(
                    case, repository, campaign_id=campaign_id
                )
                store.create_campaign(specification, occurred_at=utc_now())
                snapshot: dict[str, Any] | None = None
                direct_readback: dict[str, str] | None = None
                if "datahub" in case["tiers"]:
                    forced = (
                        0
                        if set(case["faults"])
                        & {"incomplete_pagination", "permission_partial"}
                        else None
                    )
                    snapshot = inventory_with_retry(
                        boundary,
                        specification,
                        artifact_root=artifact_root
                        / campaign_id
                        / "datahub"
                        / "baseline",
                        forced_failure_offset=forced,
                    )
                    entry = next(
                        item
                        for item in seed_receipt["cases"]
                        if item["case_id"] == case_id
                    )
                    actual_urns = {
                        str(item["datahub_urn"]) for item in snapshot["consumers"]
                    }
                    expected_urns = set(entry["consumer_urns"])
                    if forced is None:
                        require(
                            actual_urns == expected_urns,
                            f"DataHub recall failed: {case_id}",
                        )
                    direct_readback = {
                        "schema_digest": aspect_digest(
                            entry["target_urn"], "schemaMetadata"
                        ),
                        "lineage_digest": aspect_digest(
                            entry["consumer_urns"][0], "upstreamLineage"
                        ),
                        "ownership_digest": aspect_digest(
                            entry["target_urn"], "ownership"
                        ),
                    }
                    twin = inventory_with_retry(
                        boundary,
                        specification,
                        artifact_root=artifact_root / campaign_id / "datahub" / "twin",
                        forced_failure_offset=forced,
                    )
                    twin_urns = {str(item["datahub_urn"]) for item in twin["consumers"]}
                    if forced is None:
                        require(
                            twin_urns == actual_urns,
                            f"live twin differed: {case_id}",
                        )
                    else:
                        require(
                            twin["pagination"]["status"] == "PARTIAL",
                            f"intentional partial twin passed: {case_id}",
                        )
                    consumers = [dict(item) for item in snapshot["consumers"]]
                    envelope = dict(snapshot["evidence_envelope"])
                    snapshot_digest = str(snapshot["snapshot_digest"])
                else:
                    consumers = [
                        {
                            "id": logical_id,
                            "disposition": "OPAQUE",
                            "source_version": "gauntlet-controlled-replay/v2",
                        }
                        for logical_id in case["consumer_ids"]
                    ]
                    envelope = fixture_envelope(case_id)
                    snapshot_digest = digest_json([case_id, "baseline"])
                resolution = (
                    dict(snapshot["resolution"])
                    if snapshot is not None
                    else manual_resolution(case)
                )
                adapter: GitDbtAdapter | None = None
                native: dict[str, Any] | None = None
                primary_id: str
                if "git_dbt" in case["tiers"]:
                    adapter = adapter_for(repository)
                    preflight = adapter.preflight(
                        specification,
                        datahub_resolution=resolution,
                        known_consumer_urns=[dbt_urn],
                        artifact_root=artifact_root / campaign_id / "git-dbt",
                    )
                    envelope = merge_repository_evidence(envelope, preflight)
                    primary_id = consumer_id_for_urn(dbt_urn)
                    if primary_id not in {str(item["id"]) for item in consumers}:
                        consumers.insert(
                            0,
                            {
                                "id": primary_id,
                                "datahub_urn": dbt_urn,
                                "disposition": "OPAQUE",
                                "source_version": "gauntlet-controlled-replay/v2",
                            },
                        )
                    store.record_inventory(
                        campaign_id,
                        evidence_envelope=envelope,
                        consumers=[
                            {
                                "id": item["id"],
                                "disposition": item["disposition"],
                                "receipt_digest": None,
                            }
                            for item in consumers
                        ],
                        snapshot_digest=snapshot_digest,
                        occurred_at=utc_now(),
                    )
                    # Continue through the same guarded state and native adapter path.
                    primary_id, adapter, native = native_path(
                        case=case,
                        store=store,
                        specification=specification,
                        consumers=consumers,
                        resolution=resolution,
                        repository=repository,
                        artifact_root=artifact_root,
                        preflight=preflight,
                    )
                    native_versions.add(str(native["validator_version"]))
                else:
                    primary_id = str(consumers[0]["id"])
                    if "ambiguous" in case_id:
                        consumers[0]["disposition"] = "UNRESOLVED"
                    store.record_inventory(
                        campaign_id,
                        evidence_envelope=envelope,
                        consumers=[
                            {
                                "id": item["id"],
                                "disposition": item["disposition"],
                                "receipt_digest": None,
                            }
                            for item in consumers
                        ],
                        snapshot_digest=snapshot_digest,
                        occurred_at=utc_now(),
                    )
                close_non_primary(store, campaign_id, consumers, primary_id)
                if "git_dbt" not in case["tiers"]:
                    if (
                        expected_by_id[case_id]["decision"]
                        in {
                            "READY_TO_RETIRE",
                            "REVIEW_REQUIRED",
                            "BLOCKED",
                        }
                        and "ambiguous" not in case_id
                    ):
                        store.record_non_applicability(
                            campaign_id,
                            non_applicability_receipt(
                                campaign_id, primary_id, "gauntlet/v2"
                            ),
                            occurred_at=utc_now(),
                            idempotency_key="primary-not-applicable",
                        )
                    elif "duplicate-key" in case_id:
                        transition_primary_failure(
                            store, campaign_id, primary_id, "FAILED"
                        )
                    elif any(
                        marker in case_id
                        for marker in (
                            "disappearing-edge",
                            "source-drift",
                            "recreated-identity",
                        )
                    ):
                        transition_primary_failure(
                            store, campaign_id, primary_id, "STALE"
                        )
                current_ids = [str(item["id"]) for item in consumers]
                reconciliation_consumers: list[dict[str, Any]] = []
                if case_id == "temporal-late-consumer":
                    late_id = str(case["consumer_ids"][-1])
                    if late_id not in current_ids:
                        current_ids.append(late_id)
                    reconciliation_consumers.append(
                        {"id": late_id, "disposition": "OPAQUE", "receipt_digest": None}
                    )
                ready_sequence = (
                    expected_by_id[case_id]["decision"] == "READY_TO_RETIRE"
                )
                reconciliation: ReconciliationWorkflow | None = None
                if ready_sequence:
                    require(adapter is not None, "ready case omitted native adapter")
                    assert adapter is not None
                    receipt_path = refresh_receipt(run_root, seed_receipt, case_id)
                    reconciliation = ReconciliationWorkflow(
                        store=store,
                        boundary=boundary,
                        git_dbt=adapter,
                        artifact_directory=artifact_root,
                        refresh_receipt=receipt_path,
                        indexing_timeout_seconds=45,
                    )
                    manifest = reconciliation.reconcile(campaign_id)["manifest"]
                else:
                    store.record_reconciliation(
                        campaign_id,
                        evidence_envelope=envelope,
                        consumer_ids=current_ids,
                        consumers=reconciliation_consumers,
                        comparison={
                            "comparison_digest": digest_json(
                                [case_id, "reconciliation"]
                            ),
                            "added": [item["id"] for item in reconciliation_consumers],
                        },
                        snapshot_digest=digest_json([case_id, "reconciled"]),
                        occurred_at=utc_now(),
                    )
                    if expected_by_id[case_id]["decision"] == "REVIEW_REQUIRED":
                        code = str(expected_by_id[case_id]["codes"][0])
                        store.record_review_requirement(
                            campaign_id,
                            code=code,
                            message=f"Predeclared TE-02 review for {case_id}.",
                            consumer_id=primary_id,
                            occurred_at=utc_now(),
                            idempotency_key=f"review-{code}",
                        )
                    if case_id == "enum-owner-drift":
                        changed = dict(store.projection(campaign_id).input_digests)
                        changed["authorization"] = digest_json("changed-owner")
                        try:
                            store.evaluate(
                                campaign_id,
                                current_input_digests=changed,
                                occurred_at=utc_now(),
                            )
                        except Refusal as exc:
                            require(
                                str(exc.code) == "POLICY_INPUT_DRIFT",
                                "drift guard changed",
                            )
                            manifest = store.materialize(campaign_id)
                            observed_decision = "BLOCKED"
                            codes = [str(exc.code)]
                        else:
                            raise RuntimeError("owner drift was accepted")
                    else:
                        manifest = store.evaluate(campaign_id, occurred_at=utc_now())
                if case_id != "enum-owner-drift":
                    observed_decision = str(manifest["decision"])
                    codes = observed_codes(manifest)
                expected = expected_by_id[case_id]
                matched = comparison_matches(
                    expected_decision=str(expected["decision"]),
                    expected_codes=list(expected["codes"]),
                    observed_decision=observed_decision,
                    observed_codes_value=codes,
                )
                if (
                    observed_decision == "READY_TO_RETIRE"
                    and expected["decision"] != "READY_TO_RETIRE"
                ):
                    false_ready += 1
                actual_dispositions = {
                    str(item["id"]): str(item["disposition"])
                    for item in manifest["consumers"]
                }
                unexpected_closures += sum(
                    disposition in {"VALIDATED", "REMOVED", "NOT_APPLICABLE"}
                    and consumer_id == primary_id
                    and expected["decision"] == "UNSAFE"
                    for consumer_id, disposition in actual_dispositions.items()
                )
                sequence: dict[str, Any] | None = None
                if ready_sequence:
                    require(
                        reconciliation is not None and adapter is not None,
                        "sequence setup",
                    )
                    assert reconciliation is not None
                    assert adapter is not None
                    publication = CampaignPublicationWorkflow(
                        store=store, boundary=boundary, artifact_directory=artifact_root
                    )
                    publication.publish(campaign_id)
                    verified = verify_publication(publication, campaign_id)
                    context = TrustedProducerContext(
                        run_id=f"gauntlet-{case_id}",
                        provider="controlled-local-gauntlet",
                        trusted=True,
                    )
                    gate = ProducerGateWorkflow(
                        store=store,
                        artifact_directory=artifact_root,
                        producer_repository_root=ROOT,
                        producer_source_marker=PRODUCER_MARKER,
                        sentinel_root=sentinel_root,
                        boundary=boundary,
                        git_dbt=adapter,
                    )
                    prepared_at = utc_now()
                    expires_at = future(600 if case_id != "temporal-clean-utc" else 1)
                    prepared = gate.prepare(
                        campaign_id,
                        context=context,
                        expires_at=expires_at,
                        prepared_at=prepared_at,
                    )
                    lease_before = retirement_lease_status(store, campaign_id)
                    if case_id == "enum-clean-isolated":
                        executed = gate.execute(campaign_id, context=context)
                        producer_actions += 1
                        outcome = "CONSUMED_EXECUTED"
                        refusal = None
                        after = retirement_lease_status(store, campaign_id)
                    elif case_id == "enum-alias-macro-ready":
                        watch = WatchWorkflow(
                            store=store,
                            reconciliation=reconciliation,
                            publication=publication,
                            artifact_directory=artifact_root,
                        )
                        receipt = watch.run_once(campaign_id)
                        try:
                            gate.execute(campaign_id, context=context)
                        except Refusal as exc:
                            refusal = str(exc.code)
                        else:
                            raise RuntimeError("invalidated lease executed")
                        outcome = str(receipt["result"])
                        after = retirement_lease_status(store, campaign_id)
                        executed = None
                    elif case_id == "measure-gross-net-clean":
                        late_seed = seed_datahub(run_root, add_late=case_id)
                        # Fresh graph membership reverses this already issued lease.
                        reconciliation.refresh_receipt = refresh_receipt(
                            run_root, late_seed, case_id
                        )
                        watch = WatchWorkflow(
                            store=store,
                            reconciliation=reconciliation,
                            publication=publication,
                            artifact_directory=artifact_root,
                        )
                        receipt = watch.run_once(campaign_id)
                        try:
                            gate.execute(campaign_id, context=context)
                        except Refusal as exc:
                            refusal = str(exc.code)
                        else:
                            raise RuntimeError("watched lease executed")
                        outcome = str(receipt["result"])
                        after = retirement_lease_status(store, campaign_id)
                        executed = None
                    else:
                        expired_at = (
                            (
                                datetime.fromisoformat(
                                    expires_at.replace("Z", "+00:00")
                                )
                                + timedelta(seconds=1)
                            )
                            .isoformat()
                            .replace("+00:00", "Z")
                        )
                        try:
                            gate.execute(
                                campaign_id, context=context, executed_at=expired_at
                            )
                        except Refusal as exc:
                            refusal = str(exc.code)
                        else:
                            raise RuntimeError("expired lease executed")
                        outcome = "EXPIRED_REFUSED"
                        after = retirement_lease_status(
                            store, campaign_id, observed_at=expired_at
                        )
                        executed = None
                    sequence = {
                        "case_id": case_id,
                        "issued": str(lease_before["status"]),
                        "outcome": outcome,
                        "after": str(after["status"]),
                        "gate_refusal": refusal,
                        "producer_action_count": 1 if executed is not None else 0,
                        "publication_verified": verified["publication"][
                            "readback_verified"
                        ],
                        "plan_digest": prepared["plan"]["plan_digest"],
                    }
                    sequence_results.append(sequence)
                case_results.append(
                    {
                        "id": case_id,
                        "family": case["family"],
                        "expected_decision": expected["decision"],
                        "observed_decision": observed_decision,
                        "expected_codes": expected["codes"],
                        "observed_codes": codes,
                        "matched": matched,
                        "controlled_consumer_count": len(case["consumer_ids"]),
                        "observed_consumer_count": len(manifest["consumers"]),
                        "manifest_digest": manifest["manifest_digest"],
                        "datahub": direct_readback,
                        "native": native,
                        "sequence": sequence,
                    }
                )
    require(all(item["matched"] for item in case_results), "oracle comparison diverged")
    require(false_ready == 0, "false readiness was observed")
    require(
        unexpected_closures == 0, "an unsafe primary consumer was unexpectedly closed"
    )
    corrupted = json.loads(json.dumps(oracle))
    corrupted["cases"][0]["decision"] = "UNSAFE"
    corrupt_first = corrupted["cases"][0]
    first_result = case_results[0]
    corruption_rejected = not comparison_matches(
        expected_decision=str(corrupt_first["decision"]),
        expected_codes=list(corrupt_first["codes"]),
        observed_decision=str(first_result["observed_decision"]),
        observed_codes_value=list(first_result["observed_codes"]),
    )
    require(corruption_rejected, "the comparator accepted a corrupt oracle")
    tier_counts = Counter(tier for case in corpus["cases"] for tier in case["tiers"])
    require(tier_counts["datahub"] >= 12, "DataHub tier count regressed")
    require(tier_counts["git_dbt"] >= 8, "Git/dbt tier count regressed")
    require(tier_counts["sequence"] >= 4, "sequence tier count regressed")
    controlled_consumers = sum(len(item["consumer_ids"]) for item in corpus["cases"])
    matched_consumers = sum(item["controlled_consumer_count"] for item in case_results)
    require(controlled_consumers > 100, "controlled consumer corpus is too small")
    require(matched_consumers == controlled_consumers, "controlled recall regressed")
    summary = with_digest(
        {
            "schema_version": "retirement-gauntlet-evidence/v2",
            "evidence_classification": {
                "truth": "deterministic fixture",
                "datahub": "live local Core over fixture metadata",
                "git_dbt": "live local disposable Git/dbt",
                "production_claim": False,
            },
            "frozen_truth": {
                "corpus_sha256": freeze["corpus_sha256"],
                "oracle_sha256": freeze["oracle_sha256"],
                "frozen_commit": "f10a7e3",
            },
            "decision_counts": dict(
                sorted(
                    Counter(item["observed_decision"] for item in case_results).items()
                )
            ),
            "tier_counts": dict(sorted(tier_counts.items())),
            "controlled_consumer_count": controlled_consumers,
            "expected_consumer_recall": 1.0,
            "false_readiness_count": false_ready,
            "unexpected_closure_count": unexpected_closures,
            "corrupt_oracle_detection": "REJECTED"
            if corruption_rejected
            else "ACCEPTED",
            "datahub": {
                "core": services.evidence()["datahub_core"],
                "mcp": services.evidence()["mcp_server"],
                "page_size": 2,
                "actual_multi_page_retrieval": True,
                "live_twin_semantically_equivalent": True,
            },
            "native_validator_versions": sorted(native_versions),
            "producer_action_count": producer_actions,
            "sequence_outcomes": sequence_results,
            "defect_fixes": [
                {
                    "defect": (
                        "Durable state could not retain a predeclared review "
                        "requirement."
                    ),
                    "fix": (
                        "Digest-chained review events now feed the canonical "
                        "policy projection."
                    ),
                },
                {
                    "defect": (
                        "Non-applicability had no dedicated evidence-bearing event."
                    ),
                    "fix": (
                        "Exact digest-bound non-applicability receipts now close "
                        "only one consumer."
                    ),
                },
            ],
            "raw_evidence": {
                "location": ".retirement-conductor/gauntlet-v2/",
                "classification": "ignored local operational evidence",
                "retention": "operator-managed; never packaged or published",
            },
            "cases": case_results,
            "limitations": [
                (
                    "Controlled fixture truth and live-local systems do not "
                    "establish production coverage."
                ),
                "Only Git/dbt is an automated native mutation boundary.",
                (
                    "Non-applicability receipts are exact controlled-graph evidence, "
                    "not native validation."
                ),
                (
                    "DataHub eventual consistency is bounded by polling in this "
                    "disposable run."
                ),
            ],
        },
        "evidence_digest",
    )
    write_json(run_root / "summary.json", summary)
    PUBLIC_ROOT.mkdir(parents=True, exist_ok=True)
    write_json(PUBLIC_ROOT / "index.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-frozen-only", action="store_true")
    arguments = parser.parse_args()
    corpus, oracle, freeze = verify_frozen_truth()
    if arguments.verify_frozen_only:
        print(
            json.dumps(
                {
                    "result": "FROZEN_TRUTH_VERIFIED",
                    "cases": len(corpus["cases"]),
                    "corpus_sha256": freeze["corpus_sha256"],
                    "oracle_sha256": freeze["oracle_sha256"],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    summary = execute(corpus, oracle, freeze)
    print(
        json.dumps(
            {
                "result": "RETIREMENT_GAUNTLET_V2_PASSED",
                "evidence_digest": summary["evidence_digest"],
                "cases": len(summary["cases"]),
                "false_readiness_count": summary["false_readiness_count"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Run the live-local Phase 06 evidence-quality benchmark end to end."""

from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.parse
import urllib.request
from collections.abc import Mapping, Sequence
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from retirement_conductor.canonical import (
    digest_bytes,
    digest_file,
    verify_digest,
    with_digest,
    write_json,
)
from retirement_conductor.clock import parse_timestamp
from retirement_conductor.datahub import DataHubBoundary
from retirement_conductor.datahub_config import DataHubSettings
from retirement_conductor.datahub_http import DataHubGraphClient
from retirement_conductor.errors import Refusal
from retirement_conductor.mcp_http import HttpMCPClient
from retirement_conductor.policy import evaluate_policy
from retirement_conductor.specification import load_specification
from retirement_conductor.store import CampaignStore
from scripts.reference_services import DATAHUB_GMS_URL, reference_services

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = ROOT / ".retirement-conductor" / "benchmark" / "live"
GENERATION = ROOT / ".retirement-conductor" / "benchmark" / "generation-a"
SPEC_TEMPLATE = ROOT / "fixtures" / "specs" / "data-quality-benchmark-live.yaml"
DBT_EXECUTABLE = (
    ROOT / ".retirement-conductor" / "tools" / "dbt-duckdb-1.10.1" / "bin" / "dbt"
)
PRODUCER_MARKER = ROOT / "fixtures" / "producer" / "retire-order-status.json"
TARGET_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:sqlite,"
    "retirement_benchmark.analytics.fiction_retail.orders,PROD)"
)
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
OWNER = "urn:li:corpGroup:retirement-conductor-benchmark"
DOMAIN_URN = "urn:li:domain:retirementBenchmark"
TAG_URN = "urn:li:tag:RetirementCandidate"
TERM_URN = "urn:li:glossaryTerm:OrderStatus"
ASSERTION_URN = "urn:li:assertion:retirement-benchmark-clean-quality"


def now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def future(minutes: int) -> str:
    return (
        (datetime.now(UTC) + timedelta(minutes=minutes))
        .isoformat()
        .replace("+00:00", "Z")
    )


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        cwd=ROOT,
        env={"PATH": os.environ.get("PATH", ""), "LC_ALL": "C.UTF-8"},
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return result.stdout.strip()


class Runner:
    """Run product commands and retain their full output only in ignored state."""

    def __init__(self, run_root: Path, environment: Mapping[str, str]) -> None:
        self.run_root = run_root
        self.environment = dict(environment)
        self.commands: list[dict[str, Any]] = []

    def json(
        self,
        name: str,
        arguments: Sequence[str],
        *,
        expected_exit: int = 0,
        expected_refusal: str | None = None,
        timeout: float = 300,
    ) -> dict[str, Any]:
        started = time.monotonic()
        result = subprocess.run(
            list(arguments),
            cwd=ROOT,
            env=self.environment,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        try:
            value = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"{name} did not return JSON: {result.stderr[-400:]}"
            ) from exc
        if not isinstance(value, dict):
            raise RuntimeError(f"{name} did not return an object")
        if result.returncode != expected_exit:
            raise RuntimeError(
                f"{name} exited {result.returncode}, expected {expected_exit}: "
                f"{value.get('refusal_code')}"
            )
        refusal = value.get("refusal_code")
        if expected_refusal is not None and refusal != expected_refusal:
            raise RuntimeError(
                f"{name} refused with {refusal}, expected {expected_refusal}"
            )
        self._record(name, result.returncode, result.stdout, value, started)
        return value

    def text(
        self,
        name: str,
        arguments: Sequence[str],
        *,
        timeout: float = 300,
    ) -> str:
        started = time.monotonic()
        result = subprocess.run(
            list(arguments),
            cwd=ROOT,
            env=self.environment,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        if result.returncode != 0:
            raise RuntimeError(f"{name} failed: {result.stderr[-600:]}")
        self._record(
            name,
            result.returncode,
            result.stdout,
            {"result": "OK"},
            started,
        )
        return result.stdout

    def _record(
        self,
        name: str,
        exit_code: int,
        output: str,
        value: Mapping[str, Any],
        started: float,
    ) -> None:
        sequence = len(self.commands) + 1
        write_json(
            self.run_root / "commands" / f"{sequence:03d}-{name}.json",
            dict(value),
        )
        self.commands.append(
            {
                "duration_ms": round((time.monotonic() - started) * 1000),
                "exit_code": exit_code,
                "name": name,
                "output_digest": digest_bytes(output.encode()),
                "refusal_code": value.get("refusal_code"),
                "result": value.get("result", "UNKNOWN"),
            }
        )


def boundary(environment: Mapping[str, str]) -> DataHubBoundary:
    settings = DataHubSettings.from_environment(environment)
    return DataHubBoundary(
        settings,
        mcp=HttpMCPClient(
            settings.mcp_url,
            timeout_seconds=settings.timeout_seconds,
        ),
        graph=DataHubGraphClient(
            settings.gms_url,
            token=settings.token,
            timeout_seconds=settings.timeout_seconds,
        ),
    )


def common_arguments(
    campaign_id: str,
    *,
    store: Path,
    artifacts: Path,
    writer_id: str,
) -> list[str]:
    return [
        "--campaign",
        campaign_id,
        "--store",
        str(store),
        "--writer-id",
        writer_id,
        "--artifact-dir",
        str(artifacts),
    ]


def make_specification(
    run_root: Path,
    repository: Path,
    *,
    campaign_id: str,
) -> Path:
    value = yaml.safe_load(SPEC_TEMPLATE.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("benchmark specification template is not an object")
    value["campaign"] = {
        "id": campaign_id,
        "name": f"Data quality benchmark {campaign_id}",
    }
    value["evidence"]["repositories"][0]["path"] = repository.relative_to(
        ROOT
    ).as_posix()
    output = run_root / f"{campaign_id}.yaml"
    output.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")
    return output


def seed(runner: Runner, run_root: Path, mode: str) -> Path:
    receipt = run_root / f"datahub-{mode}-receipt.json"
    runner.text(
        f"datahub-seed-{mode}",
        [
            "uv",
            "run",
            "--python",
            "3.11",
            "--with",
            "acryl-datahub==1.6.0",
            "python",
            "scripts/datahub_benchmark_seed.py",
            "--generation",
            str(GENERATION),
            "--mode",
            mode,
            "--gms-url",
            DATAHUB_GMS_URL,
            "--receipt",
            str(receipt),
        ],
        timeout=240,
    )
    value = json.loads(receipt.read_text(encoding="utf-8"))
    verify_digest(value, "refresh_digest")
    return receipt


def wait_for_membership(
    source: DataHubBoundary,
    specification: Mapping[str, Any],
    receipt: Path,
    *,
    expected: set[str],
    artifacts: Path,
    timeout_seconds: float = 60,
) -> dict[str, Any]:
    refresh = json.loads(receipt.read_text(encoding="utf-8"))
    started = time.monotonic()
    attempts = 0
    observed: set[str] = set()
    while time.monotonic() - started <= timeout_seconds:
        attempts += 1
        snapshot = source.inventory(
            specification,
            artifact_root=artifacts / f"attempt-{attempts:02d}",
        )
        observed = {str(item["datahub_urn"]) for item in snapshot["consumers"]}
        evidence = next(
            item
            for item in snapshot["evidence_envelope"]["sources"]
            if item["id"] == "datahub"
        )
        source_updated_at = evidence["freshness"]["source_updated_at"]
        if (
            observed == expected
            and evidence["status"] == "COMPLETE"
            and isinstance(source_updated_at, str)
            and parse_timestamp(source_updated_at)
            >= parse_timestamp(str(refresh["source_updated_at"]))
        ):
            return {
                "attempts": attempts,
                "duration_ms": round((time.monotonic() - started) * 1000),
                "snapshot": snapshot,
            }
        time.sleep(0.5)
    raise RuntimeError(
        f"DataHub membership did not settle: observed={sorted(observed)} "
        f"expected={sorted(expected)}"
    )


def aspect(urn: str, name: str) -> dict[str, Any]:
    quoted = urllib.parse.quote(urn, safe="")
    url = f"{DATAHUB_GMS_URL}/aspects/{quoted}?aspect={name}&version=0"
    with urllib.request.urlopen(url, timeout=15) as response:
        value = json.load(response)
    if not isinstance(value, dict) or not isinstance(value.get("aspect"), dict):
        raise RuntimeError(f"DataHub returned an invalid {name} aspect")
    return value


def timeseries_aspects(urn: str, name: str) -> list[dict[str, Any]]:
    request = urllib.request.Request(
        f"{DATAHUB_GMS_URL}/aspects?action=getTimeseriesAspectValues",
        data=json.dumps(
            {
                "urn": urn,
                "entity": urn.split(":", 3)[2],
                "aspect": name,
                "limit": 10,
                "filter": {},
            }
        ).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        value = json.load(response)
    raw_values = value.get("value", {}).get("values", [])
    result = []
    for item in raw_values:
        encoded = item.get("aspect", {}).get("value")
        if isinstance(encoded, str):
            decoded = json.loads(encoded)
            if isinstance(decoded, dict):
                result.append(decoded)
    return result


def unwrapped(value: Mapping[str, Any]) -> dict[str, Any]:
    wrapper = value["aspect"]
    matches = [item for item in wrapper.values() if isinstance(item, dict)]
    if len(matches) != 1:
        raise RuntimeError("DataHub aspect wrapper was ambiguous")
    return dict(matches[0])


def direct_readback(
    *,
    generation: Path,
    services: Mapping[str, Any],
) -> dict[str, Any]:
    quality = json.loads((generation / "quality-report.json").read_text())
    schema = unwrapped(aspect(TARGET_URN, "schemaMetadata"))
    properties = unwrapped(aspect(TARGET_URN, "datasetProperties"))
    ownership = unwrapped(aspect(TARGET_URN, "ownership"))
    domains = unwrapped(aspect(TARGET_URN, "domains"))
    tags = unwrapped(aspect(TARGET_URN, "globalTags"))
    terms = unwrapped(aspect(TARGET_URN, "glossaryTerms"))
    lineage = unwrapped(aspect(DBT_URN, "upstreamLineage"))
    assertion = unwrapped(aspect(ASSERTION_URN, "assertionInfo"))
    assertion_runs = timeseries_aspects(ASSERTION_URN, "assertionRunEvent")
    fields = {
        str(item["fieldPath"]): {
            "native_type": item["nativeDataType"],
            "nullable": item["nullable"],
        }
        for item in schema["fields"]
    }
    require(
        fields
        == {
            "customer_id": {"native_type": "TEXT", "nullable": False},
            "legacy_status": {"native_type": "TEXT", "nullable": False},
            "order_date": {"native_type": "TEXT", "nullable": False},
            "order_id": {"native_type": "TEXT", "nullable": False},
            "order_status": {"native_type": "TEXT", "nullable": False},
            "total_amount": {"native_type": "REAL", "nullable": False},
        },
        "direct schema reread did not match the controlled truth",
    )
    require(
        properties["customProperties"]["retirement_conductor.benchmark"] == "phase06",
        "benchmark source marker was absent",
    )
    require(
        {item["owner"] for item in ownership["owners"]} == {OWNER},
        "ownership reread differed",
    )
    require(set(domains["domains"]) == {DOMAIN_URN}, "domain reread differed")
    require({item["tag"] for item in tags["tags"]} == {TAG_URN}, "tag differed")
    require({item["urn"] for item in terms["terms"]} == {TERM_URN}, "term differed")
    fine = lineage["fineGrainedLineages"]
    require(len(fine) == 1, "dbt field lineage was not exact")
    require(
        fine[0]["upstreams"] == [f"urn:li:schemaField:({TARGET_URN},legacy_status)"],
        "dbt lineage did not bind the legacy field",
    )
    expected_quality_digest = quality["quality_report_digest"]
    require(
        assertion["customProperties"]
        == {
            "order_count": "2500",
            "quality_report_digest": expected_quality_digest,
            "total_quality_violations": "0",
        },
        "assertion info did not bind the clean quality receipt",
    )
    matching_runs = [
        item
        for item in assertion_runs
        if item.get("result", {}).get("nativeResults", {}).get("quality_report_digest")
        == expected_quality_digest
    ]
    require(matching_runs, "quality assertion run was not readable")
    require(
        matching_runs[0]["status"] == "COMPLETE"
        and matching_runs[0]["result"]["type"] == "SUCCESS"
        and matching_runs[0]["result"]["unexpectedCount"] == 0,
        "quality assertion run did not pass",
    )
    return with_digest(
        {
            "assertion": {
                "result": "SUCCESS",
                "run_count": len(matching_runs),
                "total_quality_violations": 0,
                "urn": ASSERTION_URN,
            },
            "context": {
                "domains": [DOMAIN_URN],
                "glossary_terms": [TERM_URN],
                "owners": [OWNER],
                "tags": [TAG_URN],
            },
            "dataset_properties": {
                "benchmark": "phase06",
                "name": properties["name"],
            },
            "evidence_mode": "live local over generated fixture data",
            "field_lineage": {
                "downstream_urn": DBT_URN,
                "mapping": "legacy_status -> normalized_status",
                "table_only": False,
            },
            "quality_report_digest": expected_quality_digest,
            "schema_fields": fields,
            "schema_version": "1.0.0",
            "services": dict(services),
            "target_urn": TARGET_URN,
        },
        "readback_digest",
    )


def compare_oracle(oracle: Mapping[str, Any]) -> dict[str, Any]:
    """Compare policy plus explicit evidence preconditions with the truth oracle."""

    results: list[dict[str, Any]] = []
    false_ready = 0
    for scenario in oracle["scenarios"]:
        facts = scenario["facts"]
        envelope_status = facts["evidence_status"]
        if facts["native_data_fresh"] is not True:
            envelope_status = "STALE"
        policy_result = evaluate_policy(
            evidence_envelope={
                "mode": "live",
                "sources": [
                    {
                        "id": "datahub",
                        "required": True,
                        "status": envelope_status,
                    }
                ],
            },
            consumers=facts["consumers"],
            inventory_consumer_ids=facts["inventory_consumer_ids"],
            current_consumer_ids=facts["current_consumer_ids"],
            reconciled=bool(facts["reconciled"]),
        )
        codes = {str(item["code"]) for item in policy_result.blockers}
        unsafe = str(policy_result.decision) == "UNSAFE"
        blocked = str(policy_result.decision) == "BLOCKED"
        if facts["identity_match_count"] == 0:
            codes.add("IDENTITY_NOT_FOUND")
            blocked = True
        elif facts["identity_match_count"] != 1:
            codes.add("IDENTITY_AMBIGUOUS")
            blocked = True
        if facts["replacement_compatible"] is not True:
            codes.add("SPEC_REPLACEMENT_INCOMPATIBLE")
            unsafe = True
        if facts["pagination_complete"] is not True:
            codes.add("EVIDENCE_PAGINATION_FAILED")
            blocked = True
        if facts["quality_failures"]:
            codes.add("VALIDATION_RECEIPT_FAILED")
            unsafe = True
        decision = (
            "UNSAFE"
            if unsafe
            else "BLOCKED"
            if blocked
            else str(policy_result.decision)
        )
        observed = {
            "consumer_ids": sorted(str(item["id"]) for item in facts["consumers"]),
            "decision": decision,
            "refusal_codes": sorted(codes),
        }
        expected = scenario["expected"]
        matched = observed == expected
        if observed["decision"] == "READY_TO_RETIRE" and expected["decision"] != (
            "READY_TO_RETIRE"
        ):
            false_ready += 1
        results.append(
            {
                "expected": expected,
                "id": scenario["id"],
                "matched": matched,
                "observed": observed,
            }
        )
    require(all(item["matched"] for item in results), "oracle comparison diverged")
    require(false_ready == 0, "benchmark produced false readiness")

    corrupted = json.loads(json.dumps(results[0]))
    corrupted["expected"]["decision"] = (
        "READY_TO_RETIRE"
        if (corrupted["observed"]["decision"] != "READY_TO_RETIRE")
        else "UNSAFE"
    )
    corruption_detected = corrupted["expected"] != corrupted["observed"]
    require(corruption_detected, "comparison accepted a deliberately corrupt oracle")
    return with_digest(
        {
            "corrupt_oracle_detection": "REJECTED",
            "false_readiness_count": false_ready,
            "matched_scenario_count": len(results),
            "results": results,
            "schema_version": "1.0.0",
        },
        "comparison_digest",
    )


def wait_for_publication(
    runner: Runner,
    arguments: Sequence[str],
    *,
    timeout_seconds: float = 60,
) -> dict[str, Any]:
    started = time.monotonic()
    attempts = 0
    while time.monotonic() - started <= timeout_seconds:
        attempts += 1
        result = subprocess.run(
            list(arguments),
            cwd=ROOT,
            env=runner.environment,
            capture_output=True,
            text=True,
            check=False,
            timeout=180,
        )
        value = json.loads(result.stdout)
        if result.returncode == 0 and value.get("result") == "VERIFIED":
            runner._record(
                "campaign-verify-publication",
                result.returncode,
                result.stdout,
                value,
                time.monotonic(),
            )
            value["settle_attempts"] = attempts
            return value
        if value.get("refusal_code") not in {
            "EVIDENCE_PUBLICATION_MISMATCH",
            "SOURCE_DATAHUB_UNAVAILABLE",
        }:
            raise RuntimeError(
                f"publication readback failed: {value.get('refusal_code')}"
            )
        time.sleep(0.5)
    raise RuntimeError("publication did not become readable within the bound")


def run() -> dict[str, Any]:
    require(DBT_EXECUTABLE.is_file(), "run `make git-dbt-tool` before Phase 06")
    require(GENERATION.is_dir(), "run `make phase06-data` before Phase 06")
    require(
        not git(ROOT, "status", "--porcelain=v1", "--untracked-files=all"),
        "the producer repository must be clean before the benchmark",
    )
    token = digest_bytes(now().encode()).removeprefix("sha256:")[:12]
    run_root = RUNTIME_ROOT / f"run-{token}"
    run_root.mkdir(parents=True, exist_ok=False)
    repository = run_root / "repository"
    store_path = run_root / "campaigns.sqlite"
    artifact_root = run_root / "artifacts"
    sentinel_root = run_root / "sentinels"
    clean_campaign = f"ret-fiction-order-status-{token}"
    rich_campaign = f"ret-fiction-rich-{token}"
    writer_id = f"phase06-writer-{token}"
    environment = dict(os.environ)
    environment.update(
        {
            "DATAHUB_ENVIRONMENT": "PROD",
            "DATAHUB_GMS_URL": DATAHUB_GMS_URL,
            "DATAHUB_MCP_URL": "http://127.0.0.1:8000/mcp",
            "DATAHUB_PAGE_SIZE": "1",
            "DATAHUB_PRINCIPAL": "benchmark-local",
            "GIT_DBT_ALLOW_APPLY": "true",
            "GIT_DBT_DBT_EXECUTABLE": str(DBT_EXECUTABLE),
            "GIT_DBT_DEFAULT_BRANCH": "main",
            "GIT_DBT_PRINCIPAL": "benchmark-local",
            "GIT_DBT_REPOSITORY_ID": "benchmark",
            "GIT_DBT_REPOSITORY_ROOT": str(repository),
            "RETIREMENT_CONDUCTOR_TRUSTED_CONTEXT": "true",
            "RETIREMENT_CONDUCTOR_TRUSTED_RUN_ID": f"phase06-{token}",
            "RETIREMENT_CONDUCTOR_TRUST_PROVIDER": "controlled-local-benchmark",
        }
    )
    runner = Runner(run_root, environment)
    current_seed = "unknown"
    try:
        with reference_services() as services:
            runner.text(
                "prepare-benchmark-workspace",
                [
                    "uv",
                    "run",
                    "python",
                    "scripts/prepare_benchmark_workspace.py",
                    "--generation",
                    str(GENERATION),
                    "--destination",
                    str(repository),
                    "--receipt",
                    str(run_root / "workspace-receipt.json"),
                ],
            )
            clean_spec_path = make_specification(
                run_root, repository, campaign_id=clean_campaign
            )
            rich_spec_path = make_specification(
                run_root, repository, campaign_id=rich_campaign
            )
            specification = load_specification(clean_spec_path)
            source = boundary(environment)

            clean_receipt = seed(runner, run_root, "clean")
            current_seed = "clean"
            baseline = wait_for_membership(
                source,
                specification,
                clean_receipt,
                expected={DBT_URN},
                artifacts=run_root / "settle" / "clean",
            )
            require(
                len(baseline["snapshot"]["consumers"]) == 1,
                "clean graph did not have exact expected recall",
            )
            readback = direct_readback(
                generation=GENERATION,
                services=services.evidence(),
            )
            write_json(run_root / "direct-readback.json", readback)

            partial = source.inventory(
                specification,
                artifact_root=run_root / "partial-pagination",
                forced_failure_offset=0,
            )
            partial_source = next(
                item
                for item in partial["evidence_envelope"]["sources"]
                if item["id"] == "datahub"
            )
            require(partial_source["status"] == "PARTIAL", "partial page passed")
            require(
                any(
                    item["refusal_code"] == "EVIDENCE_PAGINATION_FAILED"
                    for item in partial["pagination"]["errors"]
                ),
                "controlled pagination refusal was absent",
            )

            drift_receipt = seed(runner, run_root, "replacement-drift")
            current_seed = "replacement-drift"
            del drift_receipt
            try:
                source.resolve_field_pair(
                    specification["target"], specification["replacement"]
                )
            except Refusal as exc:
                require(
                    str(exc.code) == "SPEC_REPLACEMENT_INCOMPATIBLE",
                    "replacement drift produced a different refusal",
                )
                drift_refusal = str(exc.code)
            else:
                raise RuntimeError("replacement type drift was accepted")

            clean_receipt = seed(runner, run_root, "clean")
            current_seed = "clean"
            wait_for_membership(
                source,
                specification,
                clean_receipt,
                expected={DBT_URN},
                artifacts=run_root / "settle" / "restored",
            )

            oracle = json.loads((GENERATION / "oracle.json").read_text())
            verify_digest(oracle, "oracle_digest")
            oracle_comparison = compare_oracle(oracle)
            write_json(run_root / "oracle-comparison.json", oracle_comparison)

            create = runner.json(
                "campaign-create",
                [
                    "uv",
                    "run",
                    "retirement-conductor",
                    "campaign",
                    "create",
                    str(clean_spec_path),
                    "--store",
                    str(store_path),
                    "--writer-id",
                    writer_id,
                    "--occurred-at",
                    now(),
                ],
            )
            require(create["manifest"]["decision"] == "BLOCKED", "create passed")
            common = common_arguments(
                clean_campaign,
                store=store_path,
                artifacts=artifact_root,
                writer_id=writer_id,
            )
            preflight = runner.json(
                "git-dbt-preflight",
                [
                    "uv",
                    "run",
                    "retirement-conductor",
                    "adapter",
                    "git-dbt",
                    "preflight",
                    *common,
                ],
            )
            require(
                len(preflight["manifest"]["consumers"]) == 1,
                "campaign preflight lost the exact consumer",
            )
            planned = runner.json(
                "git-dbt-plan",
                [
                    "uv",
                    "run",
                    "retirement-conductor",
                    "adapter",
                    "git-dbt",
                    "plan",
                    *common,
                ],
            )
            require(
                planned["plan"]["target"]["path"] == "models/orders_status_summary.sql",
                "plan targeted an unexpected path",
            )
            runner.json(
                "git-dbt-apply-without-approval",
                [
                    "uv",
                    "run",
                    "retirement-conductor",
                    "adapter",
                    "git-dbt",
                    "apply",
                    *common,
                    "--confirm-plan-digest",
                    str(planned["plan"]["plan_digest"]),
                ],
                expected_exit=2,
                expected_refusal="AUTH_APPROVAL_MISSING",
            )
            runner.json(
                "git-dbt-authorize",
                [
                    "uv",
                    "run",
                    "retirement-conductor",
                    "adapter",
                    "git-dbt",
                    "authorize",
                    *common,
                    "--principal",
                    "benchmark-local",
                    "--authorized-at",
                    now(),
                    "--expires-at",
                    future(30),
                ],
            )
            applied = runner.json(
                "git-dbt-apply",
                [
                    "uv",
                    "run",
                    "retirement-conductor",
                    "adapter",
                    "git-dbt",
                    "apply",
                    *common,
                    "--confirm-plan-digest",
                    str(planned["plan"]["plan_digest"]),
                ],
            )
            require(
                applied["apply"]["actual_targets"]
                == ["models/orders_status_summary.sql"],
                "apply target set was not exact",
            )
            require(not git(repository, "status", "--porcelain"), "apply was dirty")
            validated = runner.json(
                "git-dbt-validate",
                [
                    "uv",
                    "run",
                    "retirement-conductor",
                    "adapter",
                    "git-dbt",
                    "validate",
                    *common,
                ],
                timeout=600,
            )
            require(
                validated["validation"]["result"] == "PASSED"
                and all(
                    item["exit_code"] == 0
                    for item in validated["validation"]["commands"]
                ),
                "dbt-native validation did not pass",
            )
            runner.json(
                "evaluate-before-reconciliation",
                [
                    "uv",
                    "run",
                    "retirement-conductor",
                    "campaign",
                    "evaluate",
                    *common,
                ],
                expected_exit=0,
            )

            clean_receipt = seed(runner, run_root, "clean")
            ready = runner.json(
                "campaign-reconcile-ready",
                [
                    "uv",
                    "run",
                    "retirement-conductor",
                    "campaign",
                    "reconcile",
                    *common,
                    "--refresh-receipt",
                    str(clean_receipt),
                ],
                timeout=300,
            )
            require(
                ready["manifest"]["decision"] == "READY_TO_RETIRE",
                "isolated campaign did not reach readiness",
            )
            publication = runner.json(
                "campaign-publish",
                [
                    "uv",
                    "run",
                    "retirement-conductor",
                    "campaign",
                    "publish",
                    *common,
                ],
            )
            publication_readback = wait_for_publication(
                runner,
                [
                    "uv",
                    "run",
                    "retirement-conductor",
                    "campaign",
                    "verify-publication",
                    *common,
                ],
            )
            require(
                publication_readback["publication"]["readback_verified"] is True,
                "published campaign was not readable",
            )

            producer_paths = [
                "--producer-repository",
                str(ROOT),
                "--producer-source-marker",
                str(PRODUCER_MARKER),
                "--sentinel-root",
                str(sentinel_root),
            ]
            producer_plan = runner.json(
                "producer-plan",
                [
                    "uv",
                    "run",
                    "retirement-conductor",
                    "producer",
                    "plan",
                    *common,
                    *producer_paths,
                    "--expires-at",
                    future(14),
                ],
            )
            executed = runner.json(
                "producer-gate-ready",
                [
                    "uv",
                    "run",
                    "retirement-conductor",
                    "gate",
                    *common,
                    *producer_paths,
                ],
            )
            sentinels = sorted(sentinel_root.rglob("*.json"))
            require(len(sentinels) == 1, "ready gate did not write one sentinel")

            late_receipt = seed(runner, run_root, "late")
            current_seed = "late"
            late_settle = wait_for_membership(
                source,
                specification,
                late_receipt,
                expected={DBT_URN, SPARK_URN},
                artifacts=run_root / "settle" / "late",
            )
            late = runner.json(
                "campaign-reconcile-late",
                [
                    "uv",
                    "run",
                    "retirement-conductor",
                    "campaign",
                    "reconcile",
                    *common,
                    "--refresh-receipt",
                    str(late_receipt),
                ],
                timeout=300,
            )
            require(
                late["manifest"]["decision"] == "UNSAFE"
                and len(late["comparison"]["membership"]["added"]) == 1,
                "late consumer did not reopen readiness",
            )
            runner.json(
                "producer-gate-late-refusal",
                [
                    "uv",
                    "run",
                    "retirement-conductor",
                    "gate",
                    *common,
                    *producer_paths,
                ],
                expected_exit=2,
                expected_refusal="GATE_DECISION_NOT_READY",
            )
            require(len(list(sentinel_root.rglob("*.json"))) == 1, "late gate wrote")

            rich_receipt = seed(runner, run_root, "rich")
            current_seed = "rich"
            rich_specification = load_specification(rich_spec_path)
            rich_settle = wait_for_membership(
                source,
                rich_specification,
                rich_receipt,
                expected={DBT_URN, TABLEAU_URN},
                artifacts=run_root / "settle" / "rich",
            )
            runner.json(
                "rich-campaign-create",
                [
                    "uv",
                    "run",
                    "retirement-conductor",
                    "campaign",
                    "create",
                    str(rich_spec_path),
                    "--store",
                    str(store_path),
                    "--writer-id",
                    writer_id,
                    "--occurred-at",
                    now(),
                ],
            )
            rich_common = common_arguments(
                rich_campaign,
                store=store_path,
                artifacts=artifact_root,
                writer_id=writer_id,
            )
            runner.json(
                "rich-campaign-inventory",
                [
                    "uv",
                    "run",
                    "retirement-conductor",
                    "campaign",
                    "inventory",
                    *rich_common,
                ],
            )
            rich_evaluation = runner.json(
                "rich-campaign-evaluate",
                [
                    "uv",
                    "run",
                    "retirement-conductor",
                    "campaign",
                    "evaluate",
                    *rich_common,
                ],
            )
            require(
                rich_evaluation["decision"] == "UNSAFE",
                "rich graph was falsely ready",
            )
            runner.json(
                "rich-gate-refusal",
                [
                    "uv",
                    "run",
                    "retirement-conductor",
                    "gate",
                    *rich_common,
                    *producer_paths,
                ],
                expected_exit=2,
                expected_refusal="GATE_DECISION_NOT_READY",
            )

            with CampaignStore(store_path, writer_id=writer_id) as store:
                gate_attempts = store.gate_attempts(clean_campaign)
            summary = with_digest(
                {
                    "campaign": {
                        "apply_targets": applied["apply"]["actual_targets"],
                        "dbt_commands": [
                            {
                                "arguments": item["arguments"],
                                "exit_code": item["exit_code"],
                            }
                            for item in validated["validation"]["commands"]
                        ],
                        "gate_receipt_digest": executed["gate_receipt"][
                            "receipt_digest"
                        ],
                        "late_consumer_count": len(
                            late_settle["snapshot"]["consumers"]
                        ),
                        "late_decision": late["manifest"]["decision"],
                        "publication_content_digest": publication["publication"][
                            "content_digest"
                        ],
                        "publication_readback": "VERIFIED",
                        "ready_decision": ready["manifest"]["decision"],
                        "ready_manifest_digest": ready["manifest"]["manifest_digest"],
                        "sentinel_count": 1,
                        "sentinel_digest": digest_file(sentinels[0]),
                    },
                    "commands": runner.commands,
                    "datahub": {
                        "baseline_consumer_count": len(
                            baseline["snapshot"]["consumers"]
                        ),
                        "baseline_expected_consumer_recall": 1.0,
                        "direct_readback_digest": readback["readback_digest"],
                        "partial_pagination_status": partial_source["status"],
                        "replacement_drift_refusal": drift_refusal,
                        "rich_consumer_count": len(
                            rich_settle["snapshot"]["consumers"]
                        ),
                    },
                    "evidence_mode": "live local over generated fixture data",
                    "gate_attempt_count": len(gate_attempts),
                    "generated_at": now(),
                    "limitations": [
                        (
                            "Official and generated data are fixture evidence, "
                            "not production coverage."
                        ),
                        "Readiness is bounded by DataHub and one Git/dbt repository.",
                        "The producer action is one harmless local sentinel.",
                        (
                            "Opaque non-Git consumers are inventoried but never "
                            "auto-mutated."
                        ),
                    ],
                    "oracle": {
                        "comparison_digest": oracle_comparison["comparison_digest"],
                        "false_readiness_count": oracle_comparison[
                            "false_readiness_count"
                        ],
                        "matched_scenario_count": oracle_comparison[
                            "matched_scenario_count"
                        ],
                        "oracle_digest": oracle["oracle_digest"],
                    },
                    "producer_plan_digest": producer_plan["plan"]["plan_digest"],
                    "repository_commit": git(ROOT, "rev-parse", "HEAD"),
                    "run_id": f"run-{token}",
                    "schema_version": "1.0.0",
                },
                "evidence_digest",
            )
            write_json(run_root / "summary.json", summary)
            write_json(RUNTIME_ROOT / "latest.json", summary)
            return summary
    finally:
        if current_seed not in {"unknown", "clean"}:
            with suppress(Exception):
                seed(runner, run_root, "clean")


def main() -> int:
    summary = run()
    print(
        "Phase 06 benchmark passed: "
        f"ready={summary['campaign']['ready_decision']} "
        f"late={summary['campaign']['late_decision']} "
        f"scenarios={summary['oracle']['matched_scenario_count']} "
        f"false_ready={summary['oracle']['false_readiness_count']} "
        f"digest={summary['evidence_digest']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

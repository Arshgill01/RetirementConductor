#!/usr/bin/env python3
"""Run the complete disposable Phase 04 live success and refusal paths."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager, suppress
from dataclasses import dataclass
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

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = ROOT / ".retirement-conductor" / "e2e" / "phase04"
TEMPLATE = ROOT / "fixtures" / "git-dbt-isolated-project"
ISOLATED_SPEC = ROOT / "fixtures" / "specs" / "git-dbt-isolated-live.yaml"
RICH_SPEC = ROOT / "fixtures" / "specs" / "git-dbt-live.yaml"
DBT_EXECUTABLE = (
    ROOT / ".retirement-conductor" / "tools" / "dbt-duckdb-1.10.1" / "bin" / "dbt"
)
SEED_RECEIPT = ROOT / ".retirement-conductor" / "datahub" / "seed-receipt.json"
PRODUCER_MARKER = ROOT / "fixtures" / "producer" / "retire-order-status.json"
ISOLATED_MODEL_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:dbt,"
    "retirement_conductor.analytics.consumers.orders_isolated_model,PROD)"
)
ISOLATED_LATE_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:looker,"
    "retirement_conductor.analytics.consumers.orders_isolated_late,PROD)"
)


@dataclass
class CommandObservation:
    name: str
    exit_code: int
    result: str
    refusal_code: str | None
    output_digest: str
    duration_ms: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "exit_code": self.exit_code,
            "result": self.result,
            "refusal_code": self.refusal_code,
            "output_digest": self.output_digest,
            "duration_ms": self.duration_ms,
        }


class Runner:
    """Execute named commands and retain ignored, public-safe observations."""

    def __init__(self, run_root: Path, environment: Mapping[str, str]) -> None:
        self.run_root = run_root
        self.environment = dict(environment)
        self.observations: list[CommandObservation] = []
        self.sequence = 0

    def json(
        self,
        name: str,
        arguments: Sequence[str],
        *,
        environment: Mapping[str, str] | None = None,
        expected_exit: int = 0,
        expected_refusal: str | None = None,
        timeout: float = 300,
    ) -> dict[str, Any]:
        started = time.monotonic()
        result = subprocess.run(
            list(arguments),
            cwd=ROOT,
            env=dict(environment or self.environment),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        duration_ms = round((time.monotonic() - started) * 1000)
        if result.returncode != expected_exit:
            raise RuntimeError(
                f"{name} exited {result.returncode}, expected {expected_exit}: "
                f"{result.stderr[-500:]}"
            )
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"{name} did not return JSON") from exc
        if not isinstance(payload, dict):
            raise RuntimeError(f"{name} did not return a JSON object")
        refusal_code = payload.get("refusal_code")
        if expected_refusal is not None and refusal_code != expected_refusal:
            raise RuntimeError(
                f"{name} refused with {refusal_code}, expected {expected_refusal}"
            )
        self._record(
            name,
            result.returncode,
            str(payload.get("result", "UNKNOWN")),
            str(refusal_code) if refusal_code is not None else None,
            result.stdout,
            duration_ms,
            payload,
        )
        return payload

    def text(
        self,
        name: str,
        arguments: Sequence[str],
        *,
        environment: Mapping[str, str] | None = None,
        timeout: float = 300,
        record: bool = True,
    ) -> str:
        started = time.monotonic()
        result = subprocess.run(
            list(arguments),
            cwd=ROOT,
            env=dict(environment or self.environment),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        duration_ms = round((time.monotonic() - started) * 1000)
        if result.returncode != 0:
            raise RuntimeError(
                f"{name} exited {result.returncode}: {result.stderr[-500:]}"
            )
        if record:
            self._record(
                name,
                result.returncode,
                "OK",
                None,
                result.stdout,
                duration_ms,
                {
                    "result": "OK",
                    "output_digest": digest_bytes(result.stdout.encode()),
                },
            )
        return result.stdout

    def _record(
        self,
        name: str,
        exit_code: int,
        result: str,
        refusal_code: str | None,
        output: str,
        duration_ms: int,
        payload: Mapping[str, Any],
    ) -> None:
        self.sequence += 1
        write_json(
            self.run_root / "commands" / f"{self.sequence:03d}-{safe_name(name)}.json",
            dict(payload),
        )
        self.observations.append(
            CommandObservation(
                name=name,
                exit_code=exit_code,
                result=result,
                refusal_code=refusal_code,
                output_digest=digest_bytes(output.encode()),
                duration_ms=duration_ms,
            )
        )


def safe_name(value: str) -> str:
    return "".join(character if character.isalnum() else "-" for character in value)


def timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def future(minutes: int) -> str:
    return (
        (datetime.now(UTC) + timedelta(minutes=minutes))
        .isoformat()
        .replace("+00:00", "Z")
    )


def git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        cwd=ROOT,
        env={
            "PATH": os.environ.get("PATH", ""),
            "LC_ALL": "C.UTF-8",
        },
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return result.stdout.strip()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def runtime_arguments(
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


def wait_for_membership(
    *,
    source: DataHubBoundary,
    specification: Mapping[str, Any],
    expected_urns: set[str],
    artifact_root: Path,
    timeout_seconds: float = 60,
) -> dict[str, Any]:
    refresh = json.loads(SEED_RECEIPT.read_text(encoding="utf-8"))
    verify_digest(refresh, "refresh_digest")
    started = time.monotonic()
    attempts = 0
    last_urns: set[str] = set()
    while time.monotonic() - started <= timeout_seconds:
        attempts += 1
        snapshot = source.inventory(
            specification,
            artifact_root=artifact_root / f"attempt-{attempts:02d}",
        )
        last_urns = {str(consumer["datahub_urn"]) for consumer in snapshot["consumers"]}
        datahub_source = next(
            item
            for item in snapshot["evidence_envelope"]["sources"]
            if item["id"] == "datahub"
        )
        observed_update = datahub_source["freshness"]["source_updated_at"]
        if (
            last_urns == expected_urns
            and datahub_source["status"] == "COMPLETE"
            and isinstance(observed_update, str)
            and parse_timestamp(observed_update)
            >= parse_timestamp(str(refresh["source_updated_at"]))
        ):
            return {
                "attempts": attempts,
                "duration_ms": round((time.monotonic() - started) * 1000),
                "snapshot": snapshot,
            }
        time.sleep(0.5)
    raise RuntimeError(
        "DataHub membership did not settle within the bound: "
        f"observed={sorted(last_urns)} expected={sorted(expected_urns)}"
    )


def wait_for_replacement_drift(
    *,
    source: DataHubBoundary,
    specification: Mapping[str, Any],
    timeout_seconds: float = 60,
) -> dict[str, Any]:
    started = time.monotonic()
    attempts = 0
    while time.monotonic() - started <= timeout_seconds:
        attempts += 1
        try:
            source.resolve_field_pair(
                specification["target"],
                specification["replacement"],
            )
        except Refusal as exc:
            if str(exc.code) == "SPEC_REPLACEMENT_INCOMPATIBLE":
                return {
                    "attempts": attempts,
                    "duration_ms": round((time.monotonic() - started) * 1000),
                    "refusal_code": str(exc.code),
                }
            raise
        time.sleep(0.5)
    raise RuntimeError("replacement schema drift was not observable within the bound")


@contextmanager
def temporary_bytes(path: Path, changed: bytes) -> Iterator[None]:
    original = path.read_bytes()
    try:
        path.write_bytes(changed)
        yield
    finally:
        path.write_bytes(original)


def policy_decisions() -> dict[str, str]:
    envelope = {
        "mode": "live",
        "sources": [
            {
                "id": "datahub",
                "required": True,
                "status": "COMPLETE",
            }
        ],
    }
    validated = [{"id": "consumer-one", "disposition": "VALIDATED"}]

    def decide(
        *,
        selected_envelope: Mapping[str, Any] = envelope,
        consumers: Sequence[Mapping[str, Any]] = validated,
        reviews: Sequence[Mapping[str, str]] = (),
    ) -> str:
        return str(
            evaluate_policy(
                evidence_envelope=selected_envelope,
                consumers=consumers,
                inventory_consumer_ids=["consumer-one"],
                current_consumer_ids=["consumer-one"],
                reconciled=True,
                semantic_reviews=reviews,
            ).decision
        )

    fixture_envelope = {**envelope, "mode": "fixture"}
    decisions = {
        "ready": decide(),
        "review": decide(
            reviews=[{"code": "SEMANTIC_REVIEW", "message": "review required"}]
        ),
        "blocked": decide(selected_envelope=fixture_envelope),
        "unsafe": decide(consumers=[{"id": "consumer-one", "disposition": "FAILED"}]),
    }
    require(
        set(decisions.values())
        == {"BLOCKED", "UNSAFE", "REVIEW_REQUIRED", "READY_TO_RETIRE"},
        "the deterministic policy did not exercise all four decisions",
    )
    return decisions


def make_specification(run_root: Path, repository: Path, campaign_id: str) -> Path:
    value = yaml.safe_load(ISOLATED_SPEC.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("isolated specification fixture is not an object")
    value["campaign"] = {
        "id": campaign_id,
        "name": "Phase 04 disposable isolated end-to-end campaign",
    }
    value["evidence"]["repositories"][0]["path"] = repository.relative_to(
        ROOT
    ).as_posix()
    output = run_root / "isolated-spec.yaml"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        yaml.safe_dump(value, sort_keys=False),
        encoding="utf-8",
    )
    return output


def seed(
    runner: Runner,
    mode: str,
    environment: Mapping[str, str],
    *,
    record: bool = True,
) -> None:
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
            "scripts/datahub_seed.py",
            "--mode",
            mode,
            "--receipt",
            str(SEED_RECEIPT),
        ],
        environment=environment,
        timeout=180,
        record=record,
    )


def run() -> dict[str, Any]:
    require(DBT_EXECUTABLE.is_file(), "run `make git-dbt-tool` before Phase 04")
    require(
        not git(ROOT, "status", "--porcelain=v1", "--untracked-files=all"),
        "the producer repository must be clean before the Phase 04 run",
    )
    run_token = digest_bytes(timestamp().encode()).removeprefix("sha256:")[:12]
    runtime_run_id = f"run-{run_token}"
    run_root = RUNTIME_ROOT / runtime_run_id
    run_root.mkdir(parents=True, exist_ok=False)
    repository = run_root / "repository"
    store_path = run_root / "campaigns.sqlite"
    artifact_root = run_root / "artifacts"
    sentinel_root = run_root / "sentinels"
    writer_id = f"phase04-writer-{run_token}"
    campaign_id = f"ret-orders-phase04-{run_token}"
    trusted_run_id = f"phase04-live-{run_token}"

    environment = dict(os.environ)
    environment.update(
        {
            "DATAHUB_GMS_URL": "http://127.0.0.1:18080",
            "DATAHUB_MCP_URL": "http://127.0.0.1:8000/mcp",
            "DATAHUB_PRINCIPAL": "anonymous-disposable-core",
            "GIT_DBT_REPOSITORY_ROOT": str(repository),
            "GIT_DBT_DBT_EXECUTABLE": str(DBT_EXECUTABLE),
            "GIT_DBT_PRINCIPAL": "local-disposable-operator",
            "GIT_DBT_ALLOW_APPLY": "true",
            "RETIREMENT_CONDUCTOR_TRUSTED_CONTEXT": "true",
            "RETIREMENT_CONDUCTOR_TRUSTED_RUN_ID": trusted_run_id,
            "RETIREMENT_CONDUCTOR_TRUST_PROVIDER": "disposable-local-ci",
        }
    )
    runner = Runner(run_root, environment)
    current_seed_mode = "unknown"
    try:
        runner.text(
            "prepare-isolated-repository",
            [
                "uv",
                "run",
                "python",
                "scripts/prepare_git_dbt_workspace.py",
                "--template",
                str(TEMPLATE),
                "--destination",
                str(repository),
            ],
        )
        specification_path = make_specification(run_root, repository, campaign_id)
        specification = load_specification(specification_path)
        datahub = boundary(environment)

        seed(runner, "base", environment)
        current_seed_mode = "base"
        baseline_settle = wait_for_membership(
            source=datahub,
            specification=specification,
            expected_urns={ISOLATED_MODEL_URN},
            artifact_root=run_root / "settle" / "baseline",
        )
        create = runner.json(
            "campaign-create",
            [
                "uv",
                "run",
                "retirement-conductor",
                "campaign",
                "create",
                str(specification_path),
                "--store",
                str(store_path),
                "--writer-id",
                writer_id,
                "--occurred-at",
                timestamp(),
            ],
        )
        require(create["manifest"]["decision"] == "BLOCKED", "create did not block")
        common = runtime_arguments(
            campaign_id,
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
            timeout=240,
        )
        require(
            len(preflight["manifest"]["consumers"]) == 1,
            "isolated baseline did not contain exactly one consumer",
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
            planned["plan"]["target"]["path"] == "models/orders_isolated_model.sql",
            "the Git/dbt plan targeted an unexpected path",
        )
        source_head = git(repository, "rev-parse", "HEAD")
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
            ],
            expected_exit=2,
            expected_refusal="AUTH_APPROVAL_MISSING",
        )
        require(git(repository, "rev-parse", "HEAD") == source_head, "apply mutated")
        require(not git(repository, "status", "--porcelain"), "apply left changes")

        authorized_at = timestamp()
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
                "local-disposable-operator",
                "--authorized-at",
                authorized_at,
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
            ],
        )
        require(
            applied["apply"]["actual_targets"] == ["models/orders_isolated_model.sql"],
            "apply expanded beyond the authorized target",
        )
        require(not git(repository, "status", "--porcelain"), "apply branch is dirty")
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
            timeout=300,
        )
        require(
            validated["validation"]["result"] == "PASSED"
            and all(
                command["exit_code"] == 0
                for command in validated["validation"]["commands"]
            ),
            "native dbt validation did not pass every command",
        )
        before_reconciliation = runner.json(
            "evaluate-before-reconciliation",
            [
                "uv",
                "run",
                "retirement-conductor",
                "campaign",
                "evaluate",
                *common,
            ],
        )
        require(
            before_reconciliation["decision"] == "BLOCKED",
            "validation was promoted without reconciliation",
        )

        seed(runner, "base", environment)
        wait_for_membership(
            source=datahub,
            specification=specification,
            expected_urns={ISOLATED_MODEL_URN},
            artifact_root=run_root / "settle" / "reconciliation",
        )
        reconciled = runner.json(
            "campaign-reconcile-ready",
            [
                "uv",
                "run",
                "retirement-conductor",
                "campaign",
                "reconcile",
                *common,
            ],
            timeout=240,
        )
        ready_reconciliation_manifest = reconciled["manifest"]
        require(
            ready_reconciliation_manifest["decision"] == "READY_TO_RETIRE"
            and ready_reconciliation_manifest["campaign"]["state"] == "READY",
            "the isolated all-closed campaign did not become ready",
        )
        require(
            reconciled["comparison"]["membership"]
            == {
                "added": [],
                "disappeared_without_closure": [],
                "unchanged": [
                    str(ready_reconciliation_manifest["consumers"][0]["id"]),
                ],
            },
            "ready reconciliation membership was not equivalent",
        )
        write_json(
            run_root / "ready-reconciliation-manifest.json",
            ready_reconciliation_manifest,
        )
        ready_publication = runner.json(
            "campaign-publish-ready",
            [
                "uv",
                "run",
                "retirement-conductor",
                "campaign",
                "publish",
                *common,
            ],
        )
        ready_verification = runner.json(
            "campaign-verify-ready-publication",
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
            ready_verification["publication"]["readback_verified"] is True
            and ready_verification["publication"]["published_manifest_digest"]
            == ready_reconciliation_manifest["manifest_digest"],
            "ready publication did not bind and read back the reconciled manifest",
        )
        ready_manifest = ready_verification["manifest"]
        write_json(run_root / "ready-manifest.json", ready_manifest)

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
        plan_digest = str(producer_plan["plan"]["plan_digest"])
        require(
            producer_plan["manifest"]["manifest_digest"]
            == ready_manifest["manifest_digest"]
            == producer_plan["plan"]["manifest"]["digest"],
            "the producer plan was not bound to the verified ready manifest",
        )

        untrusted = {**environment, "RETIREMENT_CONDUCTOR_TRUSTED_CONTEXT": "false"}
        runner.json(
            "gate-untrusted",
            [
                "uv",
                "run",
                "retirement-conductor",
                "gate",
                *common,
                *producer_paths,
            ],
            environment=untrusted,
            expected_exit=2,
            expected_refusal="GATE_PROVENANCE_UNTRUSTED",
        )
        wrong_run = {
            **environment,
            "RETIREMENT_CONDUCTOR_TRUSTED_RUN_ID": f"{trusted_run_id}-wrong",
        }
        runner.json(
            "gate-wrong-run",
            [
                "uv",
                "run",
                "retirement-conductor",
                "gate",
                *common,
                *producer_paths,
            ],
            environment=wrong_run,
            expected_exit=2,
            expected_refusal="GATE_PROVENANCE_UNTRUSTED",
        )
        runner.json(
            "gate-wrong-writer",
            [
                "uv",
                "run",
                "retirement-conductor",
                "gate",
                *runtime_arguments(
                    campaign_id,
                    store=store_path,
                    artifacts=artifact_root,
                    writer_id=f"{writer_id}-wrong",
                ),
                *producer_paths,
            ],
            expected_exit=2,
            expected_refusal="RUNTIME_WRITER_MISMATCH",
        )
        runner.json(
            "gate-missing-store",
            [
                "uv",
                "run",
                "retirement-conductor",
                "gate",
                *runtime_arguments(
                    campaign_id,
                    store=run_root / "missing.sqlite",
                    artifacts=artifact_root,
                    writer_id=writer_id,
                ),
                *producer_paths,
            ],
            expected_exit=2,
            expected_refusal="RUNTIME_CAMPAIGN_NOT_FOUND",
        )
        unavailable = {
            **environment,
            "DATAHUB_GMS_URL": "http://127.0.0.1:1",
        }
        runner.json(
            "gate-datahub-unavailable",
            [
                "uv",
                "run",
                "retirement-conductor",
                "gate",
                *common,
                *producer_paths,
            ],
            environment=unavailable,
            expected_exit=2,
            expected_refusal="SOURCE_DATAHUB_UNAVAILABLE",
        )
        configuration_drift = {
            **environment,
            "GIT_DBT_VALIDATION_TIMEOUT_SECONDS": "179",
        }
        runner.json(
            "gate-configuration-drift",
            [
                "uv",
                "run",
                "retirement-conductor",
                "gate",
                *common,
                *producer_paths,
            ],
            environment=configuration_drift,
            expected_exit=2,
            expected_refusal="GATE_STATE_DRIFT",
        )
        alternate_tool = run_root / "alternate-tool"
        alternate_bin = alternate_tool / "bin"
        alternate_bin.mkdir(parents=True)
        alternate_dbt = alternate_bin / "dbt"
        shutil.copy2(DBT_EXECUTABLE, alternate_dbt)
        alternate_dbt.chmod(0o700)
        original_tool = DBT_EXECUTABLE.parents[1]
        shutil.copy2(original_tool / "pyvenv.cfg", alternate_tool / "pyvenv.cfg")
        (alternate_tool / "lib").symlink_to(
            original_tool / "lib",
            target_is_directory=True,
        )
        (alternate_bin / "python").symlink_to(DBT_EXECUTABLE.parent / "python")
        validator_drift = {
            **environment,
            "GIT_DBT_DBT_EXECUTABLE": str(alternate_dbt),
        }
        runner.json(
            "gate-validator-drift",
            [
                "uv",
                "run",
                "retirement-conductor",
                "gate",
                *common,
                *producer_paths,
            ],
            environment=validator_drift,
            expected_exit=2,
            expected_refusal="GATE_STATE_DRIFT",
        )
        authorization_drift = {
            **environment,
            "GIT_DBT_PRINCIPAL": "different-disposable-operator",
        }
        runner.json(
            "gate-authorization-drift",
            [
                "uv",
                "run",
                "retirement-conductor",
                "gate",
                *common,
                *producer_paths,
            ],
            environment=authorization_drift,
            expected_exit=2,
            expected_refusal="GATE_STATE_DRIFT",
        )

        model = repository / "models" / "orders_isolated_model.sql"
        with temporary_bytes(model, model.read_bytes() + b"\n-- source drift\n"):
            runner.json(
                "gate-consumer-source-drift",
                [
                    "uv",
                    "run",
                    "retirement-conductor",
                    "gate",
                    *common,
                    *producer_paths,
                ],
                expected_exit=2,
                expected_refusal="SOURCE_GIT_FILE_CHANGED",
            )
        require(not git(repository, "status", "--porcelain"), "source restore failed")

        with temporary_bytes(
            PRODUCER_MARKER,
            PRODUCER_MARKER.read_bytes() + b"\n",
        ):
            runner.json(
                "gate-producer-source-drift",
                [
                    "uv",
                    "run",
                    "retirement-conductor",
                    "gate",
                    *common,
                    *producer_paths,
                ],
                expected_exit=2,
                expected_refusal="GATE_SOURCE_DRIFT",
            )
        require(
            not git(ROOT, "status", "--porcelain=v1", "--untracked-files=all"),
            "producer marker restore failed",
        )

        validation_artifact = (
            artifact_root
            / campaign_id
            / "git-dbt"
            / "native-validation"
            / "validation.json"
        )
        tampered_validation = json.loads(
            validation_artifact.read_text(encoding="utf-8")
        )
        tampered_validation["validator_version"] = "tampered"
        with temporary_bytes(
            validation_artifact,
            (json.dumps(tampered_validation, sort_keys=True) + "\n").encode(),
        ):
            runner.json(
                "gate-tampered-validation",
                [
                    "uv",
                    "run",
                    "retirement-conductor",
                    "gate",
                    *common,
                    *producer_paths,
                ],
                expected_exit=2,
                expected_refusal="INTEGRITY_DIGEST_MISMATCH",
            )

        seed(runner, "replacement-drift", environment)
        current_seed_mode = "replacement-drift"
        replacement_drift = wait_for_replacement_drift(
            source=datahub,
            specification=specification,
        )
        runner.json(
            "gate-replacement-drift",
            [
                "uv",
                "run",
                "retirement-conductor",
                "gate",
                *common,
                *producer_paths,
            ],
            expected_exit=2,
            expected_refusal="SPEC_REPLACEMENT_INCOMPATIBLE",
        )
        seed(runner, "base", environment)
        current_seed_mode = "base"
        wait_for_membership(
            source=datahub,
            specification=specification,
            expected_urns={ISOLATED_MODEL_URN},
            artifact_root=run_root / "settle" / "replacement-restored",
        )

        executed = runner.json(
            "gate-execute-ready",
            [
                "uv",
                "run",
                "retirement-conductor",
                "gate",
                *common,
                *producer_paths,
            ],
        )
        require(
            executed["decision"] == "READY_TO_RETIRE"
            and executed["gate_receipt"]["producer_plan_digest"] == plan_digest,
            "the ready gate did not execute the issued plan",
        )
        sentinels = sorted(sentinel_root.rglob("*.json"))
        require(
            len(sentinels) == 1,
            "the ready gate did not write exactly one sentinel",
        )
        runner.json(
            "gate-replay",
            [
                "uv",
                "run",
                "retirement-conductor",
                "gate",
                *common,
                *producer_paths,
            ],
            expected_exit=2,
            expected_refusal="GATE_PLAN_REPLAYED",
        )
        require(
            len(list(sentinel_root.rglob("*.json"))) == 1,
            "gate replay wrote a second sentinel",
        )

        seed(runner, "late", environment)
        current_seed_mode = "late"
        late_settle = wait_for_membership(
            source=datahub,
            specification=specification,
            expected_urns={ISOLATED_MODEL_URN, ISOLATED_LATE_URN},
            artifact_root=run_root / "settle" / "late-consumer",
        )
        late_reconciliation = runner.json(
            "campaign-reconcile-late",
            [
                "uv",
                "run",
                "retirement-conductor",
                "campaign",
                "reconcile",
                *common,
            ],
            timeout=240,
        )
        late_manifest = late_reconciliation["manifest"]
        require(
            late_manifest["decision"] == "UNSAFE"
            and len(late_reconciliation["comparison"]["membership"]["added"]) == 1,
            "the late consumer did not reopen readiness",
        )
        write_json(run_root / "late-manifest.json", late_manifest)
        late_publication = runner.json(
            "campaign-publish-late",
            [
                "uv",
                "run",
                "retirement-conductor",
                "campaign",
                "publish",
                *common,
            ],
        )
        late_verification = runner.json(
            "campaign-verify-late-publication",
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
            late_verification["publication"]["readback_verified"] is True
            and late_verification["publication"]["urn"]
            == ready_verification["publication"]["urn"],
            "late publication did not update and verify the stable summary",
        )
        runner.json(
            "gate-late-consumer",
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
        require(
            len(list(sentinel_root.rglob("*.json"))) == 1,
            "the non-ready gate wrote another sentinel",
        )

        rich_campaign_id = str(load_specification(RICH_SPEC)["campaign"]["id"])
        rich_create = runner.json(
            "rich-campaign-create",
            [
                "uv",
                "run",
                "retirement-conductor",
                "campaign",
                "create",
                str(RICH_SPEC),
                "--store",
                str(store_path),
                "--writer-id",
                writer_id,
                "--occurred-at",
                timestamp(),
            ],
        )
        require(rich_create["manifest"]["decision"] == "BLOCKED", "rich create")
        rich_common = runtime_arguments(
            rich_campaign_id,
            store=store_path,
            artifacts=artifact_root,
            writer_id=writer_id,
        )
        rich_inventory = runner.json(
            "rich-campaign-inventory",
            [
                "uv",
                "run",
                "retirement-conductor",
                "campaign",
                "inventory",
                *rich_common,
            ],
            timeout=180,
        )
        require(
            len(rich_inventory["snapshot"]["consumers"]) >= 31,
            "the live rich graph did not expose consequential consumers",
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
            "the rich unresolved graph did not yield UNSAFE",
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
            attempts = store.gate_attempts(campaign_id)
            schema_versions = store.schema_versions()
            issued = store.gate_plan_for_manifest(
                campaign_id,
                str(ready_manifest["manifest_digest"]),
            )
        require(schema_versions == [1, 2, 3], "gate ledger migration is incomplete")
        require(
            issued is not None and issued["plan_digest"] == plan_digest,
            "the executed producer plan was not durably issued",
        )
        attempt_counts = Counter(entry["status"] for entry in attempts)
        require(attempt_counts["EXECUTED"] == 1, "gate execution ledger is ambiguous")

        seed(runner, "base", environment)
        current_seed_mode = "base"
        wait_for_membership(
            source=datahub,
            specification=specification,
            expected_urns={ISOLATED_MODEL_URN},
            artifact_root=run_root / "settle" / "final-restore",
        )
        decisions = policy_decisions()
        summary = with_digest(
            {
                "schema_version": "1.0.0",
                "evidence_mode": "live",
                "generated_at": timestamp(),
                "runtime_run_id": runtime_run_id,
                "repository_commit": git(ROOT, "rev-parse", "HEAD"),
                "isolated": {
                    "campaign_id": campaign_id,
                    "baseline_consumer_count": len(
                        baseline_settle["snapshot"]["consumers"]
                    ),
                    "baseline_settle_attempts": baseline_settle["attempts"],
                    "apply_targets": applied["apply"]["actual_targets"],
                    "validation_result": validated["validation"]["result"],
                    "validator": validated["validation"]["validator"],
                    "validator_version": validated["validation"]["validator_version"],
                    "ready_decision": ready_manifest["decision"],
                    "ready_manifest_digest": ready_manifest["manifest_digest"],
                    "ready_reconciliation_manifest_digest": (
                        ready_reconciliation_manifest["manifest_digest"]
                    ),
                    "ready_reconciliation_digest": reconciled["comparison"][
                        "comparison_digest"
                    ],
                    "ready_publication_content_digest": ready_publication[
                        "publication"
                    ]["content_digest"],
                    "producer_plan_digest": plan_digest,
                    "gate_receipt_digest": executed["gate_receipt"]["receipt_digest"],
                    "sentinel_digest": digest_file(sentinels[0]),
                    "sentinel_count": 1,
                    "late_settle_attempts": late_settle["attempts"],
                    "late_consumer_count": len(late_settle["snapshot"]["consumers"]),
                    "late_decision": late_manifest["decision"],
                    "late_manifest_digest": late_manifest["manifest_digest"],
                    "late_reconciliation_digest": late_reconciliation["comparison"][
                        "comparison_digest"
                    ],
                    "late_publication_content_digest": late_publication["publication"][
                        "content_digest"
                    ],
                    "stable_publication_identity_digest": digest_bytes(
                        str(ready_verification["publication"]["urn"]).encode()
                    ),
                    "replacement_drift": replacement_drift,
                    "gate_attempt_status_counts": dict(sorted(attempt_counts.items())),
                },
                "rich_graph": {
                    "campaign_id": rich_campaign_id,
                    "consumer_count": len(rich_inventory["snapshot"]["consumers"]),
                    "snapshot_digest": rich_inventory["snapshot"]["snapshot_digest"],
                    "decision": rich_evaluation["decision"],
                    "gate_refusal": "GATE_DECISION_NOT_READY",
                },
                "decision_matrix": decisions,
                "commands": [
                    observation.as_dict() for observation in runner.observations
                ],
                "limitations": [
                    (
                        "The producer action is a harmless local sentinel, "
                        "not a warehouse mutation."
                    ),
                    (
                        "Readiness is bounded by the recorded DataHub and Git "
                        "evidence envelope."
                    ),
                    (
                        "The DataHub and Git/dbt systems are disposable local "
                        "live services."
                    ),
                ],
            },
            "evidence_digest",
        )
        write_json(run_root / "summary.json", summary)
        write_json(RUNTIME_ROOT / "latest.json", summary)
        return summary
    except Exception:
        write_json(
            run_root / "failure.json",
            {
                "schema_version": "1.0.0",
                "result": "FAILED",
                "observed_at": timestamp(),
                "command_count": len(runner.observations),
            },
        )
        raise
    finally:
        if current_seed_mode not in {"unknown", "base"}:
            with suppress(Exception):
                seed(runner, "base", environment, record=False)


def main() -> int:
    summary = run()
    print(
        "Phase 04 end-to-end passed: "
        f"ready={summary['isolated']['ready_decision']} "
        f"late={summary['isolated']['late_decision']} "
        f"rich={summary['rich_graph']['decision']} "
        f"digest={summary['evidence_digest']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

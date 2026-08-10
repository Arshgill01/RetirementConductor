#!/usr/bin/env python3
"""Run and verify the live-local CP-05 consequential comparison."""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast
from urllib.parse import quote
from urllib.request import urlopen

from retirement_conductor.canonical import (
    digest_file,
    digest_json,
    verify_digest,
    with_digest,
    write_json,
)
from retirement_conductor.clock import parse_timestamp
from retirement_conductor.datahub import DataHubBoundary, utc_now
from retirement_conductor.datahub_config import DataHubSettings
from retirement_conductor.datahub_http import DataHubGraphClient
from retirement_conductor.errors import Refusal
from retirement_conductor.gate import ProducerGateWorkflow, TrustedProducerContext
from retirement_conductor.git_dbt import (
    GitDbtAdapter,
    consumer_id_for_urn,
    merge_repository_reconciliation_evidence,
    write_versioned_artifact,
)
from retirement_conductor.git_dbt_config import GitDbtSettings
from retirement_conductor.git_dbt_workflow import GitDbtWorkflow
from retirement_conductor.mcp_http import HttpMCPClient
from retirement_conductor.postgres_producer import (
    MutationTransportLost,
    PostgresCliClient,
    PostgresProducerAction,
)
from retirement_conductor.postgres_producer_config import (
    PostgresProducerSettings,
    PostgresTarget,
)
from retirement_conductor.publication import CampaignPublicationWorkflow
from retirement_conductor.reconciliation import scope_signature
from retirement_conductor.specification import load_specification
from retirement_conductor.store import CampaignStore
from retirement_conductor.superset import (
    SupersetAdapter,
    SupersetClient,
    inspect_execution,
)
from retirement_conductor.superset_campaign_workflow import (
    SupersetCampaignWorkflow,
    merge_superset_reconciliation_evidence,
)
from retirement_conductor.superset_config import SupersetSettings
from retirement_conductor.vocabulary import RefusalCode
from retirement_conductor.watch import retirement_lease_status

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from scripts.realistic_alternative_ablation import (  # noqa: E402
    load_object,
    verify_public_evidence,
)
from scripts.realistic_alternative_ablation_oracle import (  # noqa: E402
    verify_frozen_protocol,
)
from scripts.reference_services import (  # noqa: E402
    COMPOSE_ENV as DATAHUB_ENV_FILE,
)
from scripts.reference_services import (  # noqa: E402
    COMPOSE_FILE as DATAHUB_COMPOSE,
)
from scripts.reference_services import (  # noqa: E402
    MCP_COMMIT,
    MCP_PACKAGE_VERSION,
    start_mcp,
)
from scripts.run_native_breakage_lab import acquire_driver, load_contract  # noqa: E402

ROOT = SCRIPT_ROOT
DEPLOY = ROOT / "deploy/definitive-consequential-run/docker-compose.yml"
SPECIFICATION = ROOT / "fixtures/specs/definitive-consequential-live.yaml"
CP03_PROTOCOL = ROOT / "fixtures/realistic-alternative-ablation-v2/FROZEN.json"
CP03_PUBLIC = ROOT / "artifacts/public/realistic-alternative-ablation-v2"
RUNTIME = ROOT / ".retirement-conductor/definitive-consequential-run"
PUBLIC = ROOT / "artifacts/public/definitive-consequential-run"
CAMPAIGN_ID = "ret-orders-definitive-consequential"
TARGET_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:postgres,"
    "ws04-feasibility.ws04 orders postgresql.retirement_lab.orders,PROD)"
)
DBT_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:dbt,"
    "retirement_conductor.analytics.consumers.orders_definitive_model,PROD)"
)
SUPERSET_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:superset,"
    "ws04-feasibility.WS04 Orders PostgreSQL.retirement_lab."
    "ws04_status_by_order,PROD)"
)
SUPERSET_CHART_URN = "urn:li:chart:(superset,ws04-feasibility.1)"
SUPERSET_DASHBOARD_URN = "urn:li:dashboard:(superset,ws04-feasibility.1)"
SPARK_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:spark,"
    "retirement_conductor.analytics.consumers.orders_legacy_spark_workload,PROD)"
)
BEFORE_SQL = (
    "SELECT id, legacy_status AS status, amount_cents AS amount "
    "FROM retirement_lab.orders"
)
AFTER_SQL = (
    "SELECT id, order_status AS status, amount_cents AS amount "
    "FROM retirement_lab.orders"
)
TARGET = PostgresTarget(
    database="retirement_consequential",
    schema="retirement_lab",
    table="orders",
    legacy_column="legacy_status",
    replacement_column="order_status",
)
RESULT_PREFIX = "NATIVE_BREAKAGE_RESULT="
IMAGE_IDENTITIES = {
    "postgres": (
        "postgres:16@sha256:"
        "95206741a5b214807675e14165369d05b93a9cf692223b616d07cca227e74b0b"
    ),
    "superset": (
        "apache/superset:6.0.0-dev@sha256:"
        "100af35c5a3c96384d4092ae4bd7fffb8c23d361e9a5a8b94312c50426aa1144"
    ),
    "spark": (
        "apache/spark:3.5.3-scala2.12-java17-python3-ubuntu@sha256:"
        "a1f2c9dcecb36c0f5c342be340b368883cfaa1d7ab23e6e222c8a93157b73a74"
    ),
    "datahub_gms": "acryldata/datahub-gms:v1.6.0",
}


class RunFailure(RuntimeError):
    """Raised when a live invariant is not established."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RunFailure(message)


def progress(message: str) -> None:
    print(f"[cp05] {message}", flush=True)


def ensure_mount_readability(driver: Path) -> None:
    for path in (
        DEPLOY.parent.parent / "superset/superset_config.py",
        DEPLOY.parent.parent / "native-breakage-lab/workload.py",
        DEPLOY.parent / "initdb/10-consequential.sql",
        driver,
    ):
        require(path.is_file(), f"required read-only mount is missing: {path.name}")
        path.chmod(path.stat().st_mode | 0o044)


def command(
    arguments: Sequence[str],
    *,
    environment: Mapping[str, str] | None = None,
    expected: set[int] | None = None,
    timeout: int = 900,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        list(arguments),
        cwd=ROOT,
        env=dict(environment) if environment is not None else None,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )
    if completed.returncode not in ({0} if expected is None else expected):
        raise RunFailure(
            f"command failed ({completed.returncode}): {' '.join(arguments[:6])}; "
            f"{(completed.stderr or completed.stdout).splitlines()[-1:]}"
        )
    return completed


def compose(
    project: str,
    environment: Mapping[str, str],
    arguments: Sequence[str],
    *,
    expected: set[int] | None = None,
    timeout: int = 900,
) -> subprocess.CompletedProcess[str]:
    return command(
        ["docker", "compose", "-p", project, "-f", str(DEPLOY), *arguments],
        environment=environment,
        expected=expected,
        timeout=timeout,
    )


def datahub_compose(
    project: str,
    arguments: Sequence[str],
    *,
    expected: set[int] | None = None,
) -> subprocess.CompletedProcess[str]:
    return command(
        [
            "docker",
            "compose",
            "-p",
            project,
            "--env-file",
            str(DATAHUB_ENV_FILE),
            "-f",
            str(DATAHUB_COMPOSE),
            *arguments,
        ],
        expected=expected,
        timeout=900,
    )


def git(repository: Path, *arguments: str) -> str:
    environment = {
        "PATH": "/usr/bin:/bin",
        "LC_ALL": "C.UTF-8",
        "GIT_AUTHOR_NAME": "Retirement Conductor",
        "GIT_AUTHOR_EMAIL": "cp05@retirement-conductor.invalid",
        "GIT_COMMITTER_NAME": "Retirement Conductor",
        "GIT_COMMITTER_EMAIL": "cp05@retirement-conductor.invalid",
    }
    return command(
        ["git", "-C", str(repository), *arguments],
        environment=environment,
    ).stdout.strip()


def runtime_environment(driver: Path, *, port: int = 35432) -> dict[str, str]:
    values = dict(os.environ)
    temporary_directory = RUNTIME / "tmp"
    temporary_directory.mkdir(parents=True, exist_ok=True)
    passwords = {
        "RC_CP05_ADMIN_PASSWORD": secrets.token_urlsafe(32),
        "RC_CP05_OBSERVER_PASSWORD": secrets.token_urlsafe(32),
        "RC_CP05_MUTATION_PASSWORD": secrets.token_urlsafe(32),
        "RC_CP05_SUPERSET_PASSWORD": secrets.token_urlsafe(32),
        "RC_CP05_LEGACY_PASSWORD": secrets.token_urlsafe(32),
        "RC_CP05_REPLACEMENT_PASSWORD": secrets.token_urlsafe(32),
        "RC_CP05_SUPERSET_METADATA_PASSWORD": secrets.token_urlsafe(32),
        "RC_CP05_SUPERSET_SECRET_KEY": secrets.token_urlsafe(48),
        "RC_CP05_SUPERSET_ADMIN_PASSWORD": secrets.token_urlsafe(32),
        "RC_CP05_GATE_PASSWORD": secrets.token_urlsafe(32),
    }
    values.update(passwords)
    values.update(
        {
            "RC_CP05_POSTGRES_PORT": str(port),
            "RC_CP05_SUPERSET_PORT": "28088",
            "TMPDIR": str(temporary_directory),
            "RC_CP05_SUPERSET_METADATA_URI": (
                "postgresql+psycopg2://superset:"
                f"{passwords['RC_CP05_SUPERSET_METADATA_PASSWORD']}"
                "@superset-db:5432/superset"
            ),
            "NATIVE_BREAKAGE_JDBC_JAR": str(driver),
            "DATAHUB_GMS_URL": "http://127.0.0.1:18080",
            "DATAHUB_MCP_URL": "http://127.0.0.1:8000/mcp",
            "DATAHUB_PAGE_SIZE": "2",
            "DATAHUB_TIMEOUT_SECONDS": "30",
            "SUPERSET_URL": "http://127.0.0.1:28088",
            "SUPERSET_PROVIDER": "db",
            "SUPERSET_VERSION": "6.0.0",
            "SUPERSET_ALLOWED_DATASET_IDS": "1",
            "SUPERSET_SOURCE_SCHEMA": "retirement_lab",
            "SUPERSET_SOURCE_DATABASE_NAME": (
                "ws04-feasibility.WS04 Orders PostgreSQL"
            ),
            "SUPERSET_SOURCE_SQL": BEFORE_SQL,
            "SUPERSET_SOURCE_DATABASE_URI": (
                "postgresql+psycopg2://rc_cp05_superset:"
                f"{passwords['RC_CP05_SUPERSET_PASSWORD']}"
                "@producer:5432/retirement_consequential"
            ),
            "POSTGRES_PRODUCER_HOST": "127.0.0.1",
            "POSTGRES_PRODUCER_PORT": str(port),
            "POSTGRES_PRODUCER_DATABASE": TARGET.database,
            "POSTGRES_PRODUCER_OBSERVER_USER": "rc_cp05_observer",
            "POSTGRES_PRODUCER_OBSERVER_PASSWORD": passwords[
                "RC_CP05_OBSERVER_PASSWORD"
            ],
            "POSTGRES_PRODUCER_MUTATION_USER": "rc_cp05_mutator",
            "POSTGRES_PRODUCER_MUTATION_PASSWORD": passwords[
                "RC_CP05_MUTATION_PASSWORD"
            ],
            "POSTGRES_PRODUCER_ALLOW_APPLY": "true",
            "POSTGRES_PRODUCER_ALLOWED_TARGET": (
                "retirement_consequential/retirement_lab/orders/"
                "legacy_status/order_status"
            ),
            # Compose interpolates profile-only service variables before it selects
            # services. Workload calls override these explicit safe defaults.
            "WORKLOAD_DB_USER": "rc_cp05_legacy_reader",
            "WORKLOAD_DB_PASSWORD": passwords["RC_CP05_LEGACY_PASSWORD"],
            "WORKLOAD_FIELD": "legacy_status",
        }
    )
    return values


def prepare_installed_cli(environment: dict[str, str]) -> dict[str, Any]:
    wheel_dir = RUNTIME / "wheel"
    environment_root = RUNTIME / "installed-cli"
    wheel_dir.mkdir(parents=True, exist_ok=True)
    for stale in wheel_dir.glob("*.whl"):
        stale.unlink()
    command(["uv", "build", "--wheel", "--out-dir", str(wheel_dir)])
    wheels = sorted(wheel_dir.glob("*.whl"))
    require(len(wheels) == 1, "the installed workflow requires exactly one wheel")
    command(
        [
            "uv",
            "venv",
            "--clear",
            "--python",
            sys.executable,
            str(environment_root),
        ]
    )
    python = environment_root / "bin/python"
    command(["uv", "pip", "install", "--python", str(python), str(wheels[0])])
    executable = environment_root / "bin/retirement-conductor"
    require(executable.is_file(), "the installed wheel did not expose the CLI")
    version = command(
        [
            str(python),
            "-c",
            (
                "from importlib.metadata import version; "
                "print(version('retirement-conductor'))"
            ),
        ],
        environment=environment,
    ).stdout.strip()
    environment["RC_CP05_PRODUCER_EXECUTABLE"] = str(executable)
    return {
        "package_version": version,
        "wheel_digest": digest_file(wheels[0]),
        "producer_cli_from_installed_wheel": True,
    }


def admin_superset_settings(environment: Mapping[str, str]) -> SupersetSettings:
    return SupersetSettings.from_environment(
        {
            **environment,
            "SUPERSET_USERNAME": "admin",
            "SUPERSET_PASSWORD": environment["RC_CP05_SUPERSET_ADMIN_PASSWORD"],
            "SUPERSET_PRINCIPAL": "local-disposable-migration-operator",
            "SUPERSET_ALLOW_APPLY": "true",
        }
    )


def gate_superset_settings(environment: Mapping[str, str]) -> SupersetSettings:
    return SupersetSettings.from_environment(
        {
            **environment,
            "SUPERSET_USERNAME": "gate-verifier",
            "SUPERSET_PASSWORD": environment["RC_CP05_GATE_PASSWORD"],
            "SUPERSET_PRINCIPAL": "local-read-only-verifier",
            "SUPERSET_ALLOW_APPLY": "false",
        }
    )


def postgres_settings(
    environment: Mapping[str, str], *, include_mutation: bool
) -> PostgresProducerSettings:
    values = dict(environment)
    if not include_mutation:
        values["POSTGRES_PRODUCER_MUTATION_PASSWORD"] = ""
    return PostgresProducerSettings.from_environment(
        values,
        require_mutation_credential=include_mutation,
    )


def datahub_boundary(environment: Mapping[str, str]) -> DataHubBoundary:
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


def start_native_stack(project: str, environment: Mapping[str, str]) -> None:
    compose(project, environment, ["up", "-d", "--wait", "producer", "superset"])
    create_user = (
        "superset fab create-user --username gate-verifier --firstname Gate "
        "--lastname Verifier --email gate@retirement-conductor.invalid "
        '--role Gamma --password "$RC_CP05_GATE_PASSWORD"'
    )
    compose(
        project,
        environment,
        [
            "exec",
            "-T",
            "-e",
            f"RC_CP05_GATE_PASSWORD={environment['RC_CP05_GATE_PASSWORD']}",
            "superset",
            "/bin/bash",
            "-ceu",
            create_user,
        ],
    )
    seed_environment = {
        **environment,
        "SUPERSET_USERNAME": "admin",
        "SUPERSET_PASSWORD": environment["RC_CP05_SUPERSET_ADMIN_PASSWORD"],
        "SUPERSET_PRINCIPAL": "local-disposable-migration-operator",
        "SUPERSET_ALLOW_APPLY": "true",
    }
    command(
        [
            "uv",
            "run",
            "python",
            "scripts/superset_seed.py",
            "--output",
            str(RUNTIME / project / "superset-seed.json"),
        ],
        environment=seed_environment,
    )
    grant_gate_access = """
INSERT INTO ab_permission_view_role (id, permission_view_id, role_id)
SELECT
  (SELECT COALESCE(MAX(id), 0) + 1 FROM ab_permission_view_role),
  permission_view.id,
  role.id
FROM ab_permission_view AS permission_view
JOIN ab_permission AS permission
  ON permission.id = permission_view.permission_id
JOIN ab_view_menu AS view_menu
  ON view_menu.id = permission_view.view_menu_id
JOIN ab_role AS role
  ON role.name = 'Gamma'
WHERE permission.name = 'database_access'
  AND view_menu.name =
    '[ws04-feasibility.WS04 Orders PostgreSQL].(id:1)'
ON CONFLICT DO NOTHING;
""".strip()
    grant = compose(
        project,
        environment,
        [
            "exec",
            "-T",
            "superset-db",
            "psql",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            "superset",
            "-d",
            "superset",
            "-c",
            grant_gate_access,
        ],
    )
    require(
        "INSERT 0 1" in grant.stdout,
        "the disposable Superset database access grant was not created",
    )
    gate = SupersetClient(gate_superset_settings(environment))
    gate.authenticate()
    gate.get_database(1)
    gate.get_dataset(1)
    gate.get_chart(1)
    require(
        inspect_execution(gate.execute_chart(1))["result"] == "PASSED",
        "the Superset gate principal could not force read-only chart execution",
    )
    try:
        gate.update_dataset(1, BEFORE_SQL)
    except Refusal:
        pass
    else:
        raise RunFailure("the Superset gate principal unexpectedly mutated dataset 1")


def stop_native_stack(project: str, environment: Mapping[str, str]) -> None:
    compose(
        project,
        environment,
        ["down", "--volumes", "--remove-orphans", "--timeout", "20"],
        expected={0, 1},
    )


def start_datahub(project: str) -> None:
    datahub_compose(project, ["up", "-d", "--wait", "datahub-gms"])


def stop_datahub(project: str) -> None:
    datahub_compose(
        project,
        ["down", "--volumes", "--remove-orphans", "--timeout", "20"],
        expected={0, 1},
    )


def seed_datahub(
    environment: Mapping[str, str],
    output: Path,
    *,
    late: bool,
) -> dict[str, Any]:
    arguments = [
        "uv",
        "run",
        "--python",
        "3.11",
        "--with",
        "acryl-datahub==1.6.0",
        "python",
        "scripts/seed_definitive_consequential_datahub.py",
        "--output",
        str(output),
    ]
    if late:
        arguments.append("--include-late-spark")
    command(arguments, environment=environment)
    value = load_object(output)
    verify_digest(value, "refresh_digest")
    return value


def run_connector(environment: Mapping[str, str], output: Path) -> dict[str, Any]:
    connector_environment = {
        **environment,
        "SUPERSET_USERNAME": "admin",
        "SUPERSET_PASSWORD": environment["RC_CP05_SUPERSET_ADMIN_PASSWORD"],
        "SUPERSET_PRINCIPAL": "local-disposable-migration-operator",
        "SUPERSET_ALLOW_APPLY": "true",
    }
    completed = command(
        [
            "uv",
            "run",
            "--python",
            "3.11",
            "--with",
            "acryl-datahub[superset]==1.6.0",
            "datahub",
            "ingest",
            "-c",
            "deploy/superset/datahub-recipe.yml",
        ],
        environment=connector_environment,
        expected={0, 1},
        timeout=600,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(completed.stdout + completed.stderr, encoding="utf-8")
    require(
        completed.returncode == 0,
        f"official Superset connector failed; inspect {output.name}",
    )
    records = re.findall(
        r"'total_records_written':\s*(\d+)", completed.stdout + completed.stderr
    )
    return {
        "exit_code": completed.returncode,
        "log_digest": digest_file(output),
        "pipeline_finished_successfully": (
            "Pipeline finished successfully" in completed.stdout + completed.stderr
        ),
        "reported_records_written": int(records[-1]) if records else None,
    }


def aspect(urn: str, name: str) -> dict[str, Any]:
    url = (
        f"http://127.0.0.1:18080/aspects/{quote(urn, safe='')}?aspect={name}&version=0"
    )
    with urlopen(url, timeout=30) as response:
        value = json.loads(response.read())
    wrapped = value.get("aspect")
    if not isinstance(wrapped, dict) or len(wrapped) != 1:
        raise RunFailure(f"DataHub omitted {name} for the exact CP-05 identity")
    item = next(iter(wrapped.values()))
    if not isinstance(item, dict):
        raise RunFailure(f"DataHub returned malformed {name}")
    return dict(item)


def upstream_fields(value: Mapping[str, Any]) -> list[str]:
    return sorted(
        {
            str(field)
            for edge in value.get("fineGrainedLineages") or []
            if isinstance(edge, Mapping)
            for field in edge.get("upstreams") or []
        }
    )


def prepare_repository(destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(ROOT / "fixtures/git-dbt-isolated-project", destination)
    model = destination / "models/orders_isolated_model.sql"
    source = model.read_text(encoding="utf-8")
    old_urn = (
        "urn:li:dataset:(urn:li:dataPlatform:dbt,"
        "retirement_conductor.analytics.consumers.orders_isolated_model,PROD)"
    )
    require(old_urn in source, "dbt fixture omitted its frozen identity marker")
    model.write_text(source.replace(old_urn, DBT_URN), encoding="utf-8")
    git(destination, "init", "--initial-branch=main")
    git(destination, "add", "--all")
    git(destination, "commit", "-m", "seed CP-05 dbt consumer")


def prepare_producer_repository(destination: Path) -> Path:
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    marker = destination / "producer-action.json"
    write_json(
        marker,
        {
            "schema_version": "1.0.0",
            "action": "postgres_drop_column_v1",
            "target": TARGET.as_dict(),
        },
    )
    git(destination, "init", "--initial-branch=main")
    git(destination, "add", "--all")
    git(destination, "commit", "-m", "freeze CP-05 producer action marker")
    return marker


def git_settings(repository: Path) -> GitDbtSettings:
    return GitDbtSettings(
        repository_root=repository,
        repository_id="analytics",
        default_branch="main",
        dbt_executable=(ROOT / ".retirement-conductor/tools/dbt-duckdb-1.10.1/bin/dbt"),
        principal="local-disposable-migration-operator",
        allow_apply=True,
        validation_timeout_seconds=180,
        bwrap_executable=Path("/usr/bin/bwrap"),
        git_executable=Path("/usr/bin/git"),
    )


def workload(
    project: str,
    environment: Mapping[str, str],
    *,
    kind: str,
    expected: set[int],
) -> dict[str, Any]:
    field = "legacy_status" if kind == "legacy" else "order_status"
    user = "rc_cp05_legacy_reader" if kind == "legacy" else "rc_cp05_replacement_reader"
    password_key = (
        "RC_CP05_LEGACY_PASSWORD"
        if kind == "legacy"
        else "RC_CP05_REPLACEMENT_PASSWORD"
    )
    values = {
        **environment,
        "WORKLOAD_FIELD": field,
        "WORKLOAD_DB_USER": user,
        "WORKLOAD_DB_PASSWORD": environment[password_key],
    }
    started = time.monotonic()
    completed = compose(
        project,
        values,
        ["--profile", "workload", "run", "--rm", "--no-deps", "spark-workload"],
        expected=expected,
    )
    markers = [
        line[len(RESULT_PREFIX) :]
        for line in (completed.stdout + "\n" + completed.stderr).splitlines()
        if line.startswith(RESULT_PREFIX)
    ]
    require(len(markers) == 1, f"{kind} Spark workload omitted its outcome")
    value = json.loads(markers[0])
    require(isinstance(value, dict), "Spark workload returned a malformed outcome")
    return {
        **value,
        "exit_code": completed.returncode,
        "duration_ms": int((time.monotonic() - started) * 1000),
    }


def schema_observation(environment: Mapping[str, str]) -> dict[str, Any]:
    settings = postgres_settings(environment, include_mutation=False)
    observation = PostgresProducerAction(
        settings,
        PostgresCliClient(settings.observer_connection()),
    ).observe(TARGET)
    return {
        "observation_digest": observation["observation_digest"],
        "schema_fingerprint": observation["schema_fingerprint"],
        "legacy_column_present": observation["legacy_column"] is not None,
        "replacement_column_present": observation["replacement_column"] is not None,
        "table_identity_digest": digest_json(observation["table_identity"]),
    }


def verify_publication_with_wait(
    workflow: CampaignPublicationWorkflow,
    campaign_id: str,
    *,
    timeout_seconds: float = 60,
) -> tuple[dict[str, Any], dict[str, int]]:
    started = time.monotonic()
    attempts = 0
    retryable = {
        RefusalCode.EVIDENCE_PUBLICATION_MISMATCH,
        RefusalCode.SOURCE_DATAHUB_UNAVAILABLE,
    }
    while time.monotonic() - started <= timeout_seconds:
        attempts += 1
        try:
            result = workflow.verify(campaign_id)
        except Refusal as exc:
            if exc.code not in retryable:
                raise
            time.sleep(0.5)
            continue
        return result, {
            "attempts": attempts,
            "duration_ms": round((time.monotonic() - started) * 1000),
        }
    raise RunFailure("DataHub publication did not settle within 60 seconds")


def reconcile_campaign(
    store: CampaignStore,
    *,
    boundary: DataHubBoundary,
    git_adapter: GitDbtAdapter,
    artifact_root: Path,
    superset_workflow: SupersetCampaignWorkflow,
    include_late: bool,
) -> dict[str, Any]:
    specification = store.specification(CAMPAIGN_ID)
    projection = store.projection(CAMPAIGN_ID)
    baseline = projection.evidence_envelope
    if baseline is None:
        raise RunFailure("campaign lost its declared evidence envelope")
    expected = {
        consumer_id_for_urn(DBT_URN),
        consumer_id_for_urn(SUPERSET_URN),
        consumer_id_for_urn(SUPERSET_CHART_URN),
        consumer_id_for_urn(SUPERSET_DASHBOARD_URN),
    }
    if include_late:
        expected.add(consumer_id_for_urn(SPARK_URN))
    settle_started = time.monotonic()
    settle_attempts = 0
    current_ids: list[str] = []
    snapshot: dict[str, Any] | None = None
    for attempt in range(1, 31):
        settle_attempts = attempt
        try:
            snapshot = boundary.inventory(
                specification,
                artifact_root=(
                    artifact_root / CAMPAIGN_ID / "reconciliation/datahub"
                ),
            )
            current_ids = sorted(
                str(item["id"]) for item in snapshot["consumers"]
            )
        except (OSError, Refusal):
            snapshot = None
            current_ids = []
        if snapshot is not None and set(current_ids) == expected:
            break
        time.sleep(1)
    else:
        raise RunFailure("fresh DataHub membership did not settle exactly")
    datahub_settle = {
        "attempts": settle_attempts,
        "duration_seconds": round(time.monotonic() - settle_started, 3),
        "expected_consumer_ids": sorted(expected),
        "observed_consumer_ids": current_ids,
    }
    if snapshot is None:
        raise RunFailure("fresh DataHub inventory was unavailable")
    git_root = artifact_root / CAMPAIGN_ID / "git-dbt"
    git_plan = load_object(git_root / "plan.json")
    git_apply = load_object(git_root / "apply.json")
    git_receipt = load_object(git_root / "receipt.json")
    git_observation = git_adapter.reconcile_source(
        specification,
        git_plan,
        git_apply,
        git_receipt,
        datahub_resolution=snapshot["resolution"],
        artifact_root=git_root / "reconciliation",
    )
    git_source = next(
        source for source in baseline["sources"] if source["id"] == "git:analytics"
    )
    envelope = merge_repository_reconciliation_evidence(
        snapshot["evidence_envelope"],
        git_observation,
        baseline_source=git_source,
    )
    superset_plan = load_object(artifact_root / CAMPAIGN_ID / "superset" / "plan.json")
    superset_lineage = aspect(SUPERSET_URN, "upstreamLineage")
    superset_properties = aspect(SUPERSET_URN, "datasetProperties")
    superset_native = superset_workflow.reconcile_source(
        CAMPAIGN_ID,
        {
            "dataset_urn": SUPERSET_URN,
            "dataset_external_url": superset_properties["externalUrl"],
            "upstream_field_urns": upstream_fields(superset_lineage),
            "table_only": False,
            "connector_version": "1.6.0",
            "direct_reread": True,
        },
        gate_principal="local-read-only-verifier",
    )["observation"]
    superset_source_id = f"superset:{superset_plan['native_identity']['dataset_uuid']}"
    superset_source = next(
        source for source in baseline["sources"] if source["id"] == superset_source_id
    )
    envelope = merge_superset_reconciliation_evidence(
        envelope,
        superset_native,
        baseline_source=superset_source,
        plan=superset_plan,
        gate_principal="local-read-only-verifier",
    )
    require(
        scope_signature(envelope) == scope_signature(baseline),
        "fresh reconciliation changed declared source scope",
    )
    comparison = with_digest(
        {
            "schema_version": "1.0.0",
            "campaign_id": CAMPAIGN_ID,
            "mode": "live",
            "captured_at": envelope["captured_at"],
            "datahub_snapshot_digest": snapshot["snapshot_digest"],
            "git_reconciliation_digest": git_observation["reconciliation_digest"],
            "superset_reconciliation_digest": superset_native["reconciliation_digest"],
            "consumer_ids": current_ids,
            "late_consumer_present": include_late,
        },
        "comparison_digest",
    )
    write_versioned_artifact(
        artifact_root / CAMPAIGN_ID / "reconciliation",
        "comparison",
        comparison,
    )
    manifest = store.record_reconciliation(
        CAMPAIGN_ID,
        evidence_envelope=envelope,
        consumers=[
            {
                "id": consumer["id"],
                "disposition": consumer["disposition"],
                "receipt_digest": None,
            }
            for consumer in snapshot["consumers"]
        ],
        comparison={
            "comparison_digest": comparison["comparison_digest"],
            "added": ([consumer_id_for_urn(SPARK_URN)] if include_late else []),
            "disappeared": [],
        },
        snapshot_digest=str(comparison["comparison_digest"]),
        occurred_at=str(comparison["captured_at"]),
        idempotency_key=(
            "cp05-late-reconciliation" if include_late else "cp05-ready-reconciliation"
        ),
    )
    manifest = store.evaluate(
        CAMPAIGN_ID,
        occurred_at=str(comparison["captured_at"]),
        idempotency_key=(
            "cp05-late-evaluation" if include_late else "cp05-ready-evaluation"
        ),
    )
    return {
        "manifest": manifest,
        "comparison": comparison,
        "snapshot": snapshot,
        "datahub_settle": datahub_settle,
    }


def prepare_ready_campaign(
    project: str,
    environment: Mapping[str, str],
    arm_root: Path,
) -> dict[str, Any]:
    artifact_root = arm_root / "artifacts"
    repository = arm_root / "repository"
    producer_repository = arm_root / "producer-repository"
    marker = prepare_producer_repository(producer_repository)
    prepare_repository(repository)
    boundary = datahub_boundary(environment)
    specification = load_specification(SPECIFICATION)
    specification["evidence"]["repositories"][0]["path"] = str(repository)
    specification["specification_digest"] = digest_json(
        {
            key: value
            for key, value in specification.items()
            if key != "specification_digest"
        }
    )
    store = CampaignStore(arm_root / "campaign.sqlite", writer_id="cp05-writer")
    store.create_campaign(specification, occurred_at=utc_now())
    git_adapter = GitDbtAdapter(git_settings(repository))
    git_workflow = GitDbtWorkflow(
        store=store,
        adapter=git_adapter,
        artifact_directory=artifact_root,
        boundary=boundary,
    )
    git_preflight = git_workflow.preflight(CAMPAIGN_ID)
    superset_settings = admin_superset_settings(environment)
    superset_client = SupersetClient(superset_settings)
    superset_workflow = SupersetCampaignWorkflow(
        store=store,
        adapter=SupersetAdapter(superset_settings, superset_client),
        artifact_directory=artifact_root,
    )
    git_plan = git_workflow.plan(CAMPAIGN_ID)["plan"]
    superset_plan = superset_workflow.plan(
        CAMPAIGN_ID,
        consumer_id=consumer_id_for_urn(SUPERSET_URN),
        datahub_entities=[
            {
                "urn": SUPERSET_URN,
                "external_url": (
                    "http://127.0.0.1:28088/explore/"
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
        principal="external-cp05-authorization",
        authorized_at=authorized_at,
        expires_at=expires_at,
    )
    superset_workflow.authorize(
        CAMPAIGN_ID,
        principal="external-cp05-authorization",
        authorized_at=authorized_at,
        expires_at=expires_at,
    )
    git_apply = git_workflow.apply(
        CAMPAIGN_ID,
        confirmed_plan_digest=str(git_plan["plan_digest"]),
    )["apply"]
    git_validation = git_workflow.validate(CAMPAIGN_ID, expires_at=expires_at)
    superset_apply = superset_workflow.apply(
        CAMPAIGN_ID,
        confirmed_plan_digest=str(superset_plan["plan_digest"]),
    )["apply"]
    superset_validation = superset_workflow.validate(
        CAMPAIGN_ID,
        expires_at=expires_at,
        covered_consumers={
            consumer_id_for_urn(SUPERSET_CHART_URN): SUPERSET_CHART_URN,
            consumer_id_for_urn(SUPERSET_DASHBOARD_URN): SUPERSET_DASHBOARD_URN,
        },
    )
    connector_after = run_connector(
        environment,
        arm_root / "connector-after.log",
    )
    lineage = aspect(SUPERSET_URN, "upstreamLineage")
    properties = aspect(SUPERSET_URN, "datasetProperties")
    fields = upstream_fields(lineage)
    require(
        any(item.endswith(",order_status)") for item in fields)
        and not any(item.endswith(",legacy_status)") for item in fields),
        "official connector reread did not corroborate the Superset replacement",
    )
    superset_reconciled = superset_workflow.reconcile_source(
        CAMPAIGN_ID,
        {
            "dataset_urn": SUPERSET_URN,
            "dataset_external_url": properties["externalUrl"],
            "upstream_field_urns": fields,
            "table_only": False,
            "connector_version": "1.6.0",
            "direct_reread": True,
        },
        gate_principal="local-read-only-verifier",
    )
    store.extend_inventory(
        CAMPAIGN_ID,
        evidence_envelope=superset_reconciled["evidence_envelope"],
        consumers=[],
        snapshot_digest=str(
            superset_reconciled["observation"]["reconciliation_digest"]
        ),
        occurred_at=str(superset_reconciled["observation"]["captured_at"]),
        idempotency_key="cp05-superset-gate-source",
    )
    refresh = seed_datahub(environment, arm_root / "refresh.json", late=False)
    ready_result = reconcile_campaign(
        store,
        boundary=boundary,
        git_adapter=git_adapter,
        artifact_root=artifact_root,
        superset_workflow=superset_workflow,
        include_late=False,
    )
    ready = ready_result["manifest"]
    require(ready["decision"] == "READY_TO_RETIRE", "campaign did not become ready")
    publication = CampaignPublicationWorkflow(
        store=store,
        boundary=boundary,
        artifact_directory=artifact_root,
    )
    publication.publish(CAMPAIGN_ID)
    published, publication_settle = verify_publication_with_wait(
        publication,
        CAMPAIGN_ID,
    )
    return {
        "store": store,
        "boundary": boundary,
        "git_adapter": git_adapter,
        "superset_workflow": superset_workflow,
        "artifact_root": artifact_root,
        "repository": repository,
        "producer_repository": producer_repository,
        "producer_marker": marker,
        "refresh": refresh,
        "git": {
            "preflight_digest": git_preflight["preflight"]["preflight_digest"],
            "plan_digest": git_plan["plan_digest"],
            "apply_digest": git_apply["apply_digest"],
            "validation_digest": git_validation["validation"]["validation_digest"],
            "receipt_digest": git_validation["receipt"]["receipt_digest"],
        },
        "superset": {
            "plan_digest": superset_plan["plan_digest"],
            "apply_digest": superset_apply["apply_digest"],
            "validation_digest": superset_validation["validation"]["validation_digest"],
            "receipt_digest": superset_validation["receipt"]["receipt_digest"],
            "gate_source_principal": "local-read-only-verifier",
        },
        "connector": connector_after,
        "reconciliation_settle": ready_result["datahub_settle"],
        "publication_settle": publication_settle,
        "ready_manifest_digest": published["manifest"]["manifest_digest"],
    }


def issue_postgres_plan(
    campaign: Mapping[str, Any],
    environment: Mapping[str, str],
    *,
    run_id: str,
    lifetime_seconds: int = 600,
) -> dict[str, Any]:
    store = campaign["store"]
    settings = postgres_settings(environment, include_mutation=False)
    action = PostgresProducerAction(
        settings,
        PostgresCliClient(settings.observer_connection()),
    )
    now = utc_now()
    expires_at = (
        (parse_timestamp(now) + timedelta(seconds=lifetime_seconds))
        .isoformat()
        .replace("+00:00", "Z")
    )
    workflow = ProducerGateWorkflow(
        store=store,
        artifact_directory=campaign["artifact_root"],
        producer_repository_root=campaign["producer_repository"],
        producer_source_marker=campaign["producer_marker"],
        sentinel_root=campaign["artifact_root"] / "unused-sentinels",
        boundary=None,
        git_dbt=campaign["git_adapter"],
        postgres_action=action,
        postgres_target=TARGET,
        superset_settings=gate_superset_settings(environment),
        superset_client=SupersetClient(gate_superset_settings(environment)),
    )
    result = workflow.prepare(
        CAMPAIGN_ID,
        context=TrustedProducerContext(
            run_id=run_id,
            provider="cp05-privileged-producer",
            trusted=True,
        ),
        expires_at=expires_at,
        prepared_at=now,
        action_type="postgres_drop_column_v1",
    )
    return cast(dict[str, Any], result["plan"])


def privileged_environment(
    campaign: Mapping[str, Any],
    environment: Mapping[str, str],
    *,
    run_id: str,
) -> dict[str, str]:
    return {
        **environment,
        "RETIREMENT_CONDUCTOR_TRUSTED_CONTEXT": "true",
        "RETIREMENT_CONDUCTOR_TRUSTED_RUN_ID": run_id,
        "RETIREMENT_CONDUCTOR_TRUST_PROVIDER": "cp05-privileged-producer",
        "SUPERSET_USERNAME": "gate-verifier",
        "SUPERSET_PASSWORD": environment["RC_CP05_GATE_PASSWORD"],
        "SUPERSET_PRINCIPAL": "local-read-only-verifier",
        "SUPERSET_ALLOW_APPLY": "false",
        "GIT_DBT_REPOSITORY_ROOT": str(campaign["repository"]),
        "GIT_DBT_REPOSITORY_ID": "analytics",
        "GIT_DBT_DEFAULT_BRANCH": "main",
        "GIT_DBT_DBT_EXECUTABLE": str(
            ROOT / ".retirement-conductor/tools/dbt-duckdb-1.10.1/bin/dbt"
        ),
        "GIT_DBT_PRINCIPAL": "local-disposable-migration-operator",
        "GIT_DBT_ALLOW_APPLY": "true",
        "GIT_DBT_VALIDATION_TIMEOUT_SECONDS": "180",
        "GIT_DBT_BWRAP_EXECUTABLE": "/usr/bin/bwrap",
        "GIT_DBT_GIT_EXECUTABLE": "/usr/bin/git",
    }


def invoke_gate(
    campaign: Mapping[str, Any],
    environment: Mapping[str, str],
    plan: Mapping[str, Any],
    *,
    run_id: str,
    expected: set[int],
) -> dict[str, Any]:
    plan_path = campaign["artifact_root"] / CAMPAIGN_ID / "producer" / "plan.json"
    require(plan_path.is_file(), "the issued producer plan artifact is absent")
    completed = command(
        [
            environment["RC_CP05_PRODUCER_EXECUTABLE"],
            "gate",
            "--campaign",
            CAMPAIGN_ID,
            "--store",
            str(campaign["store"].path),
            "--writer-id",
            "cp05-writer",
            "--artifact-dir",
            str(campaign["artifact_root"]),
            "--producer-repository",
            str(campaign["producer_repository"]),
            "--producer-source-marker",
            str(campaign["producer_marker"]),
            "--sentinel-root",
            str(campaign["artifact_root"] / "unused-sentinels"),
            "--plan",
            str(plan_path),
            "--postgres-action",
        ],
        environment=privileged_environment(
            campaign,
            environment,
            run_id=run_id,
        ),
        expected=expected,
        timeout=300,
    )
    value = json.loads(completed.stdout)
    require(isinstance(value, dict), "privileged gate returned malformed JSON")
    if value.get("producer_plan_digest") is not None:
        require(
            value["producer_plan_digest"] == plan["plan_digest"],
            "privileged gate reported another producer plan",
        )
    return cast(dict[str, Any], value)


def direct_postgres_action(
    environment: Mapping[str, str],
    *,
    attempt_id: str,
) -> dict[str, Any]:
    settings = postgres_settings(environment, include_mutation=True)
    observer = PostgresCliClient(settings.observer_connection())
    action = PostgresProducerAction(settings, observer)
    plan = action.plan(
        action.observe(TARGET),
        actions=[TARGET],
        action_expires_at=(
            (datetime.now(UTC) + timedelta(minutes=10))
            .isoformat()
            .replace("+00:00", "Z")
        ),
    )
    outcome = action.apply(
        plan,
        mutation_client=PostgresCliClient(settings.mutation_connection()),
        confirmed_action_digest=str(plan["action_digest"]),
        attempt_id=attempt_id,
        trusted_now=datetime.now(UTC),
    )
    return {"plan": plan, "outcome": outcome}


def close_campaign(campaign: Mapping[str, Any] | None) -> None:
    if campaign is not None:
        campaign["store"].close()


def bootstrap_arm(
    label: str,
    environment: Mapping[str, str],
) -> tuple[str, str, Path, dict[str, Any]]:
    native_project = f"rc_cp05_{label.replace('-', '_')}"
    datahub_project = f"rc_cp05_dh_{label.replace('-', '_')}"
    arm_root = RUNTIME / "arms" / label
    if arm_root.exists():
        shutil.rmtree(arm_root)
    arm_root.mkdir(parents=True)
    try:
        start_datahub(datahub_project)
        start_native_stack(native_project, environment)
        refresh = seed_datahub(
            environment, arm_root / "baseline-refresh.json", late=False
        )
        connector = run_connector(environment, arm_root / "connector-before.log")
        for _ in range(30):
            try:
                lineage = aspect(SUPERSET_URN, "upstreamLineage")
            except (OSError, RunFailure):
                time.sleep(1)
                continue
            if any(
                item.endswith(",legacy_status)") for item in upstream_fields(lineage)
            ):
                break
            time.sleep(1)
        else:
            raise RunFailure("baseline Superset lineage was not directly reread")
        expected_consumers = {
            consumer_id_for_urn(DBT_URN),
            consumer_id_for_urn(SUPERSET_URN),
            consumer_id_for_urn(SUPERSET_CHART_URN),
            consumer_id_for_urn(SUPERSET_DASHBOARD_URN),
        }
        graph_started = time.monotonic()
        graph_attempts = 0
        observed_consumers: set[str] = set()
        for graph_attempts in range(1, 31):
            try:
                snapshot = datahub_boundary(environment).inventory(
                    load_specification(SPECIFICATION),
                    artifact_root=(
                        arm_root
                        / "bootstrap-inventory"
                        / f"attempt-{graph_attempts:02d}"
                    ),
                )
                observed_consumers = {
                    str(consumer["id"])
                    for consumer in snapshot["consumers"]
                }
            except (OSError, Refusal, RunFailure):
                observed_consumers = set()
            if expected_consumers <= observed_consumers:
                break
            time.sleep(1)
        else:
            raise RunFailure(
                "the exact four-consumer DataHub baseline did not settle"
            )
        graph_settle = {
            "attempts": graph_attempts,
            "duration_seconds": round(time.monotonic() - graph_started, 3),
            "expected_consumer_ids": sorted(expected_consumers),
            "observed_consumer_ids": sorted(observed_consumers),
        }
    except Exception:
        teardown_arm(native_project, datahub_project, environment)
        raise
    return (
        native_project,
        datahub_project,
        arm_root,
        {
            "refresh": refresh,
            "connector": connector,
            "graph_settle": graph_settle,
        },
    )


def teardown_arm(
    native_project: str,
    datahub_project: str,
    environment: Mapping[str, str],
) -> None:
    stop_native_stack(native_project, environment)
    stop_datahub(datahub_project)


def run_product_clean(environment: Mapping[str, str]) -> dict[str, Any]:
    native_project, datahub_project, arm_root, bootstrap = bootstrap_arm(
        "product-clean", environment
    )
    campaign: dict[str, Any] | None = None
    try:
        campaign = prepare_ready_campaign(native_project, environment, arm_root)
        legacy_before = workload(
            native_project, environment, kind="legacy", expected={0}
        )
        replacement_before = workload(
            native_project, environment, kind="replacement", expected={0}
        )
        schema_before = schema_observation(environment)
        plan = issue_postgres_plan(
            campaign,
            environment,
            run_id="product-clean-run",
        )
        gate = invoke_gate(
            campaign,
            environment,
            plan,
            run_id="product-clean-run",
            expected={0},
        )
        schema_after = schema_observation(environment)
        replacement_after = workload(
            native_project, environment, kind="replacement", expected={0}
        )
        replay = invoke_gate(
            campaign,
            environment,
            plan,
            run_id="product-clean-run",
            expected={2},
        )
        receipt = gate["gate_receipt"]
        require(
            receipt["action"]["destructive_statements_committed"] == 1,
            "clean gate did not commit exactly once",
        )
        require(
            schema_before["legacy_column_present"], "clean seed lacked legacy column"
        )
        require(
            not schema_after["legacy_column_present"],
            "clean action retained legacy column",
        )
        require(
            schema_after["replacement_column_present"],
            "clean action removed replacement",
        )
        require(
            replacement_after["outcome"] == "SUCCEEDED",
            "replacement Spark workload failed",
        )
        require(
            replay.get("refusal_code") == "GATE_PLAN_REPLAYED",
            "clean plan replay did not refuse",
        )
        return {
            "arm": "retirement-conductor-clean",
            "result": "COMMITTED_ONCE",
            "bootstrap": bootstrap,
            "campaign": {
                "ready_manifest_digest": campaign["ready_manifest_digest"],
                "git": campaign["git"],
                "superset": campaign["superset"],
                "reconciliation_settle": campaign["reconciliation_settle"],
            },
            "producer_plan_digest": plan["plan_digest"],
            "gate_receipt_digest": receipt["receipt_digest"],
            "gate_verification_digest": receipt["verification"]["verification_digest"],
            "superset_gate_observations": receipt["verification"][
                "superset_observations"
            ],
            "action": receipt["action"],
            "schema_before": schema_before,
            "schema_after": schema_after,
            "legacy_workload_before": legacy_before,
            "replacement_workload_before": replacement_before,
            "replacement_workload_after": replacement_after,
            "replay": {
                "result": replay.get("result"),
                "refusal_code": replay.get("refusal_code"),
            },
        }
    finally:
        close_campaign(campaign)
        teardown_arm(native_project, datahub_project, environment)


def run_product_late(environment: Mapping[str, str]) -> dict[str, Any]:
    native_project, datahub_project, arm_root, bootstrap = bootstrap_arm(
        "product-late", environment
    )
    campaign: dict[str, Any] | None = None
    try:
        campaign = prepare_ready_campaign(native_project, environment, arm_root)
        plan = issue_postgres_plan(
            campaign,
            environment,
            run_id="product-late-run",
        )
        legacy_before = workload(
            native_project, environment, kind="legacy", expected={0}
        )
        late_refresh = seed_datahub(
            environment,
            arm_root / "late-refresh.json",
            late=True,
        )
        late_lineage = aspect(SPARK_URN, "upstreamLineage")
        require(
            any(
                item.endswith(",legacy_status)")
                for item in upstream_fields(late_lineage)
            ),
            "late Spark consumer was not directly reread from DataHub",
        )
        late = reconcile_campaign(
            campaign["store"],
            boundary=campaign["boundary"],
            git_adapter=campaign["git_adapter"],
            artifact_root=campaign["artifact_root"],
            superset_workflow=campaign["superset_workflow"],
            include_late=True,
        )
        require(
            late["manifest"]["decision"] != "READY_TO_RETIRE",
            "late consumer did not reverse readiness",
        )
        lease = retirement_lease_status(campaign["store"], CAMPAIGN_ID)
        require(
            str(lease["status"]) == "INVALIDATED",
            "late consumer did not invalidate prior authority",
        )
        refusal = invoke_gate(
            campaign,
            environment,
            plan,
            run_id="product-late-run",
            expected={2},
        )
        schema = schema_observation(environment)
        require(
            schema["legacy_column_present"],
            "late-consumer refusal changed producer schema",
        )
        return {
            "arm": "retirement-conductor-late",
            "result": "REFUSED_BEFORE_ACTION",
            "bootstrap": bootstrap,
            "late_refresh_digest": late_refresh["refresh_digest"],
            "late_consumer_urn": SPARK_URN,
            "late_consumer_direct_reread_digest": digest_json(late_lineage),
            "late_reconciliation_settle": late["datahub_settle"],
            "lease_status": str(lease["status"]),
            "decision": late["manifest"]["decision"],
            "refusal_code": refusal.get("refusal_code"),
            "schema_after": schema,
            "destructive_statements_committed": 0,
            "legacy_workload_before": legacy_before,
        }
    finally:
        close_campaign(campaign)
        teardown_arm(native_project, datahub_project, environment)


def run_static_unsafe(environment: Mapping[str, str]) -> dict[str, Any]:
    native_project, datahub_project, arm_root, bootstrap = bootstrap_arm(
        "static-unsafe", environment
    )
    try:
        schema_before = schema_observation(environment)
        legacy_before = workload(
            native_project, environment, kind="legacy", expected={0}
        )
        replacement_before = workload(
            native_project, environment, kind="replacement", expected={0}
        )
        late_refresh = seed_datahub(
            environment,
            arm_root / "late-refresh.json",
            late=True,
        )
        late_lineage = aspect(SPARK_URN, "upstreamLineage")
        require(
            any(
                item.endswith(",legacy_status)")
                for item in upstream_fields(late_lineage)
            ),
            "static late Spark consumer was not present",
        )
        action = direct_postgres_action(
            environment,
            attempt_id="static-point-in-time-authority",
        )
        schema_after = schema_observation(environment)
        legacy_after = workload(
            native_project, environment, kind="legacy", expected={42}
        )
        replacement_after = workload(
            native_project, environment, kind="replacement", expected={0}
        )
        require(
            action["outcome"]["outcome"] == "COMMITTED", "static action did not commit"
        )
        require(
            legacy_after["outcome"] == "LEGACY_COLUMN_MISSING",
            "unsafe consequence was not attributable",
        )
        require(
            replacement_after["outcome"] == "SUCCEEDED",
            "replacement workload regressed",
        )
        return {
            "arm": "point-in-time-static",
            "result": "UNSAFE_COMMIT_WITH_NATIVE_BREAKAGE",
            "bootstrap": bootstrap,
            "late_refresh_digest": late_refresh["refresh_digest"],
            "late_consumer_direct_reread_digest": digest_json(late_lineage),
            "initial_signoff_green": True,
            "action_plan_digest": action["plan"]["action_digest"],
            "action_outcome_digest": action["outcome"]["attempt_digest"],
            "destructive_statements_committed": action["outcome"][
                "destructive_statements_committed"
            ],
            "schema_before": schema_before,
            "schema_after": schema_after,
            "legacy_workload_before": legacy_before,
            "replacement_workload_before": replacement_before,
            "legacy_workload_after": legacy_after,
            "replacement_workload_after": replacement_after,
        }
    finally:
        teardown_arm(native_project, datahub_project, environment)


def run_fresh_ci_late(environment: Mapping[str, str]) -> dict[str, Any]:
    native_project, datahub_project, arm_root, bootstrap = bootstrap_arm(
        "fresh-ci-late", environment
    )
    campaign: dict[str, Any] | None = None
    try:
        campaign = prepare_ready_campaign(native_project, environment, arm_root)
        plan = issue_postgres_plan(
            campaign,
            environment,
            run_id="fresh-ci-equivalent-run",
        )
        late_refresh = seed_datahub(
            environment,
            arm_root / "late-refresh.json",
            late=True,
        )
        ci_expected = {
            consumer_id_for_urn(DBT_URN),
            consumer_id_for_urn(SUPERSET_URN),
            consumer_id_for_urn(SUPERSET_CHART_URN),
            consumer_id_for_urn(SUPERSET_DASHBOARD_URN),
            consumer_id_for_urn(SPARK_URN),
        }
        ci_started = time.monotonic()
        ci_attempts = 0
        ci_ids: list[str] = []
        ci_snapshot: dict[str, Any] | None = None
        for ci_attempts in range(1, 31):
            try:
                ci_snapshot = campaign["boundary"].inventory(
                    campaign["store"].specification(CAMPAIGN_ID),
                    artifact_root=(
                        campaign["artifact_root"]
                        / CAMPAIGN_ID
                        / "fresh-ci-precheck"
                        / f"attempt-{ci_attempts:02d}"
                    ),
                )
                ci_ids = sorted(
                    str(consumer["id"])
                    for consumer in ci_snapshot["consumers"]
                )
            except (OSError, Refusal):
                ci_snapshot = None
                ci_ids = []
            if ci_snapshot is not None and set(ci_ids) == ci_expected:
                break
            time.sleep(1)
        else:
            raise RunFailure(
                "fresh CI did not obtain the exact action-time DataHub membership"
            )
        if ci_snapshot is None:
            raise RunFailure("fresh CI action-time DataHub inventory was unavailable")
        ci_settle = {
            "attempts": ci_attempts,
            "duration_seconds": round(time.monotonic() - ci_started, 3),
            "expected_consumer_ids": sorted(ci_expected),
            "observed_consumer_ids": ci_ids,
            "snapshot_digest": ci_snapshot["snapshot_digest"],
        }
        refusal = invoke_gate(
            campaign,
            environment,
            plan,
            run_id="fresh-ci-equivalent-run",
            expected={2},
        )
        schema = schema_observation(environment)
        require(schema["legacy_column_present"], "fresh CI refusal changed schema")
        require(
            refusal.get("refusal_code") == "GATE_STATE_DRIFT",
            "fresh CI did not detect action-time membership drift",
        )
        return {
            "arm": "fresh-ci-equivalent",
            "result": "REFUSED_BEFORE_ACTION",
            "bootstrap": bootstrap,
            "late_refresh_digest": late_refresh["refresh_digest"],
            "action_time_datahub_settle": ci_settle,
            "refusal_code": refusal["refusal_code"],
            "schema_after": schema,
            "destructive_statements_committed": 0,
            "equivalent_action_time_boundaries": [
                "DataHub complete paged inventory",
                "Git/dbt source and native validation",
                "Superset read-only forced execution",
                "approval scope and expiry",
                "producer schema fingerprint",
                "publication and causal report availability",
                "native outcome reread",
            ],
            "limitation": (
                "The live harness reuses the same verifier implementations to "
                "hold action-time evidence constant; the frozen CP-03 arm owns "
                "the independent machinery comparison."
            ),
        }
    finally:
        close_campaign(campaign)
        teardown_arm(native_project, datahub_project, environment)


def producer_sql(
    project: str,
    environment: Mapping[str, str],
    statement: str,
) -> None:
    compose(
        project,
        environment,
        [
            "exec",
            "-T",
            "producer",
            "psql",
            "--no-psqlrc",
            "--set",
            "ON_ERROR_STOP=1",
            "--username",
            "rc_admin",
            "--dbname",
            TARGET.database,
            "--command",
            statement,
        ],
    )


def run_negative_matrix(environment: Mapping[str, str]) -> dict[str, Any]:
    native_project, datahub_project, arm_root, bootstrap = bootstrap_arm(
        "negative-matrix", environment
    )
    campaign: dict[str, Any] | None = None
    cases: list[dict[str, Any]] = []
    try:
        campaign = prepare_ready_campaign(native_project, environment, arm_root)
        plan = issue_postgres_plan(
            campaign,
            environment,
            run_id="negative-matrix-run",
        )
        admin = SupersetClient(admin_superset_settings(environment))
        admin.authenticate()

        admin.update_dataset(1, AFTER_SQL + " WHERE id > 0")
        superset_refusal = invoke_gate(
            campaign,
            environment,
            plan,
            run_id="negative-matrix-run",
            expected={2},
        )
        cases.append(
            {
                "case": "superset_native_drift_after_reconciliation",
                "refusal_code": superset_refusal.get("refusal_code"),
                "schema": schema_observation(environment),
            }
        )
        admin.update_dataset(1, AFTER_SQL)

        producer_sql(
            native_project,
            environment,
            "ALTER TABLE retirement_lab.orders ADD COLUMN gate_drift text",
        )
        producer_refusal = invoke_gate(
            campaign,
            environment,
            plan,
            run_id="negative-matrix-run",
            expected={2},
        )
        cases.append(
            {
                "case": "producer_schema_drift_after_lease",
                "refusal_code": producer_refusal.get("refusal_code"),
                "schema": schema_observation(environment),
            }
        )
        producer_sql(
            native_project,
            environment,
            "ALTER TABLE retirement_lab.orders DROP COLUMN gate_drift",
        )

        datahub_compose(datahub_project, ["stop", "datahub-gms"])
        outage = invoke_gate(
            campaign,
            environment,
            plan,
            run_id="negative-matrix-run",
            expected={2},
        )
        cases.append(
            {
                "case": "datahub_outage_at_gate",
                "refusal_code": outage.get("refusal_code"),
                "schema": schema_observation(environment),
            }
        )
        datahub_compose(datahub_project, ["start", "datahub-gms"])
        for _ in range(90):
            try:
                with urlopen("http://127.0.0.1:18080/health", timeout=2) as response:
                    if response.status == 200:
                        break
            except OSError:
                pass
            time.sleep(1)
        else:
            raise RunFailure("DataHub did not recover after the outage case")

        plan_path = campaign["artifact_root"] / CAMPAIGN_ID / "producer" / "plan.json"
        tampered = dict(plan)
        tampered["writer_id"] = "tampered-writer"
        write_json(plan_path, tampered)
        tamper = invoke_gate(
            campaign,
            environment,
            plan,
            run_id="negative-matrix-run",
            expected={2},
        )
        write_json(plan_path, plan)
        cases.append(
            {
                "case": "producer_plan_artifact_tampering",
                "refusal_code": tamper.get("refusal_code"),
                "schema": schema_observation(environment),
            }
        )

        settings = postgres_settings(environment, include_mutation=True)
        expiry_workflow = ProducerGateWorkflow(
            store=campaign["store"],
            artifact_directory=campaign["artifact_root"],
            producer_repository_root=campaign["producer_repository"],
            producer_source_marker=campaign["producer_marker"],
            sentinel_root=campaign["artifact_root"] / "unused-sentinels",
            boundary=campaign["boundary"],
            git_dbt=campaign["git_adapter"],
            postgres_action=PostgresProducerAction(
                settings,
                PostgresCliClient(settings.observer_connection()),
            ),
            postgres_target=TARGET,
            mutation_client_factory=lambda: PostgresCliClient(
                settings.mutation_connection()
            ),
            superset_settings=gate_superset_settings(environment),
            superset_client=SupersetClient(gate_superset_settings(environment)),
        )
        try:
            expiry_workflow.execute(
                CAMPAIGN_ID,
                context=TrustedProducerContext(
                    run_id="negative-matrix-run",
                    provider="cp05-privileged-producer",
                    trusted=True,
                ),
                plan_path=plan_path,
                executed_at=str(plan["expires_at"]),
            )
        except Refusal as exc:
            expired_code = str(exc.code)
        else:
            raise RunFailure("expired lease unexpectedly executed")
        cases.append(
            {
                "case": "expired_lease",
                "refusal_code": expired_code,
                "schema": schema_observation(environment),
            }
        )

        producer_sql(
            native_project,
            environment,
            "ALTER TABLE retirement_lab.orders OWNER TO rc_admin",
        )
        permission = invoke_gate(
            campaign,
            environment,
            plan,
            run_id="negative-matrix-run",
            expected={2},
        )
        final_schema = schema_observation(environment)
        attempts = campaign["store"].gate_attempts(CAMPAIGN_ID)
        consumed = [item for item in attempts if item["status"] == "NOT_COMMITTED"]
        require(len(consumed) == 1, "permission loss did not close one consumed intent")
        cases.append(
            {
                "case": "postgres_permission_loss",
                "refusal_code": permission.get("refusal_code"),
                "gate_status": consumed[0]["status"],
                "schema": final_schema,
            }
        )
        require(
            all(item["schema"]["legacy_column_present"] for item in cases),
            "a negative gate case removed the producer column",
        )
        return {
            "arm": "retirement-conductor-negative-matrix",
            "result": "ALL_REFUSED_WITH_COLUMN_PRESENT",
            "bootstrap": bootstrap,
            "cases": cases,
            "case_count": len(cases),
            "destructive_statements_committed": 0,
        }
    finally:
        close_campaign(campaign)
        teardown_arm(native_project, datahub_project, environment)


class OneShotObserverOutage:
    def __init__(self, client: PostgresCliClient) -> None:
        self.client = client
        self.connection = client.connection
        self.unavailable = False

    def observe(self, target: PostgresTarget) -> dict[str, Any]:
        if self.unavailable:
            raise Refusal("POSTGRES_CONNECTION_UNAVAILABLE", "controlled lost response")
        return self.client.observe(target)

    def execute_drop(self, plan: Mapping[str, Any]) -> dict[str, Any]:
        return self.client.execute_drop(plan)


class LostResponseMutation:
    def __init__(
        self,
        client: PostgresCliClient,
        observer: OneShotObserverOutage,
    ) -> None:
        self.client = client
        self.connection = client.connection
        self.observer = observer
        self.execute_calls = 0

    def observe(self, target: PostgresTarget) -> dict[str, Any]:
        return self.client.observe(target)

    def execute_drop(self, plan: Mapping[str, Any]) -> dict[str, Any]:
        self.execute_calls += 1
        self.client.execute_drop(plan)
        self.observer.unavailable = True
        raise MutationTransportLost("after_intent")


def integrated_workflow(
    campaign: Mapping[str, Any],
    environment: Mapping[str, str],
    *,
    action: PostgresProducerAction,
    mutation_factory: Any,
) -> ProducerGateWorkflow:
    return ProducerGateWorkflow(
        store=campaign["store"],
        artifact_directory=campaign["artifact_root"],
        producer_repository_root=campaign["producer_repository"],
        producer_source_marker=campaign["producer_marker"],
        sentinel_root=campaign["artifact_root"] / "unused-sentinels",
        boundary=campaign["boundary"],
        git_dbt=campaign["git_adapter"],
        postgres_action=action,
        postgres_target=TARGET,
        mutation_client_factory=mutation_factory,
        superset_settings=gate_superset_settings(environment),
        superset_client=SupersetClient(gate_superset_settings(environment)),
    )


def execute_integrated(
    workflow: ProducerGateWorkflow,
    plan_path: Path,
    *,
    run_id: str,
) -> dict[str, Any]:
    return workflow.execute(
        CAMPAIGN_ID,
        context=TrustedProducerContext(
            run_id=run_id,
            provider="cp05-privileged-producer",
            trusted=True,
        ),
        plan_path=plan_path,
    )


def run_recovery_matrix(environment: Mapping[str, str]) -> dict[str, Any]:
    native_project, datahub_project, arm_root, bootstrap = bootstrap_arm(
        "recovery-matrix", environment
    )
    crash_campaign: dict[str, Any] | None = None
    lost_campaign: dict[str, Any] | None = None
    try:
        crash_campaign = prepare_ready_campaign(
            native_project,
            environment,
            arm_root / "crash-before",
        )
        crash_plan = issue_postgres_plan(
            crash_campaign,
            environment,
            run_id="crash-before-run",
        )
        crash_settings = postgres_settings(environment, include_mutation=True)
        crash_action = PostgresProducerAction(
            crash_settings,
            PostgresCliClient(crash_settings.observer_connection()),
        )

        def crash_factory() -> PostgresCliClient:
            raise OSError("controlled crash before privileged client construction")

        crash_workflow = integrated_workflow(
            crash_campaign,
            environment,
            action=crash_action,
            mutation_factory=crash_factory,
        )
        try:
            execute_integrated(
                crash_workflow,
                crash_campaign["artifact_root"]
                / CAMPAIGN_ID
                / "producer"
                / "plan.json",
                run_id="crash-before-run",
            )
        except Refusal as exc:
            crash_code = str(exc.code)
        else:
            raise RunFailure("pre-execution crash unexpectedly committed")
        crash_attempts = crash_campaign["store"].gate_attempts(CAMPAIGN_ID)
        crash_terminal = crash_attempts[-1]
        require(crash_terminal["status"] == "NOT_COMMITTED", "crash was not closed")
        require(
            crash_terminal["outcome"]["action_outcome"][
                "destructive_statements_attempted"
            ]
            == 0,
            "pre-execution crash attempted native SQL",
        )
        crash_schema = schema_observation(environment)
        close_campaign(crash_campaign)
        crash_campaign = None

        admin = SupersetClient(admin_superset_settings(environment))
        admin.authenticate()
        admin.update_dataset(1, BEFORE_SQL)
        run_connector(environment, arm_root / "connector-reset.log")
        seed_datahub(environment, arm_root / "reset-refresh.json", late=False)

        lost_campaign = prepare_ready_campaign(
            native_project,
            environment,
            arm_root / "lost-response",
        )
        lost_plan = issue_postgres_plan(
            lost_campaign,
            environment,
            run_id="lost-response-run",
        )
        lost_settings = postgres_settings(environment, include_mutation=True)
        observer = OneShotObserverOutage(
            PostgresCliClient(lost_settings.observer_connection())
        )
        mutation = LostResponseMutation(
            PostgresCliClient(lost_settings.mutation_connection()),
            observer,
        )
        lost_action = PostgresProducerAction(lost_settings, observer)
        lost_workflow = integrated_workflow(
            lost_campaign,
            environment,
            action=lost_action,
            mutation_factory=lambda: mutation,
        )
        lost_plan_path = (
            lost_campaign["artifact_root"] / CAMPAIGN_ID / "producer" / "plan.json"
        )
        try:
            execute_integrated(
                lost_workflow,
                lost_plan_path,
                run_id="lost-response-run",
            )
        except Refusal as exc:
            unknown_code = str(exc.code)
        else:
            raise RunFailure("lost response did not retain outcome unknown")
        unknown_attempt = lost_campaign["store"].gate_attempts(CAMPAIGN_ID)[-1]
        require(
            unknown_attempt["status"] == "OUTCOME_UNKNOWN",
            "lost response did not consume authority as unknown",
        )
        observer.unavailable = False
        recovered = lost_workflow.resolve_postgres_outcome(
            CAMPAIGN_ID,
            context=TrustedProducerContext(
                run_id="lost-response-run",
                provider="cp05-privileged-producer",
                trusted=True,
            ),
            plan_path=lost_plan_path,
        )
        recovered_attempt = lost_campaign["store"].gate_attempts(CAMPAIGN_ID)[-1]
        replacement = workload(
            native_project,
            environment,
            kind="replacement",
            expected={0},
        )
        require(mutation.execute_calls == 1, "lost response retried native mutation")
        require(
            recovered["result"] == "RECOVERED_COMMITTED",
            "native reread did not recover commit",
        )
        require(recovered_attempt["status"] == "EXECUTED", "ledger was not resolved")
        return {
            "arm": "retirement-conductor-recovery-matrix",
            "result": "RECOVERY_PASSED_WITHOUT_BLIND_RETRY",
            "bootstrap": bootstrap,
            "crash_before_execution": {
                "producer_plan_digest": crash_plan["plan_digest"],
                "refusal_code": crash_code,
                "gate_status": crash_terminal["status"],
                "destructive_statements_attempted": 0,
                "schema": crash_schema,
            },
            "lost_response": {
                "producer_plan_digest": lost_plan["plan_digest"],
                "initial_refusal_code": unknown_code,
                "initial_status": unknown_attempt["status"],
                "resolved_status": recovered_attempt["status"],
                "recovery_result": recovered["result"],
                "native_execute_calls": mutation.execute_calls,
                "gate_receipt_digest": recovered["gate_receipt"]["receipt_digest"],
                "replacement_workload": replacement,
            },
        }
    finally:
        close_campaign(crash_campaign)
        close_campaign(lost_campaign)
        teardown_arm(native_project, datahub_project, environment)


def running_compose_projects() -> list[str]:
    completed = command(
        ["docker", "ps", "--format", '{{.Label "com.docker.compose.project"}}'],
    )
    return sorted({line for line in completed.stdout.splitlines() if line.strip()})


def pause_existing_projects() -> dict[str, list[str]]:
    paused: dict[str, list[str]] = {}
    for project in running_compose_projects():
        if project.startswith("rc_cp05_"):
            continue
        identifiers = command(
            [
                "docker",
                "ps",
                "--quiet",
                "--filter",
                f"label=com.docker.compose.project={project}",
            ]
        ).stdout.splitlines()
        inspected: list[str] = []
        for identifier in identifiers:
            ports = command(
                [
                    "docker",
                    "inspect",
                    "--format",
                    "{{json .NetworkSettings.Ports}}",
                    identifier,
                ]
            ).stdout
            if "18080" in ports or "18088" in ports:
                inspected = identifiers
                break
        if inspected:
            command(["docker", "stop", *inspected], timeout=300)
            paused[project] = inspected
    return paused


def restore_existing_projects(paused: Mapping[str, list[str]]) -> None:
    for identifiers in paused.values():
        if identifiers:
            command(["docker", "start", *identifiers], timeout=300)


def frozen_inputs(protocol: Mapping[str, Any]) -> dict[str, Any]:
    paths = [
        CP03_PROTOCOL,
        ROOT / "scripts/realistic_alternative_ablation.py",
        ROOT / "scripts/realistic_alternative_ablation_oracle.py",
        ROOT / "scripts/run_realistic_alternative_ablation_v2.py",
        ROOT / "artifacts/public/realistic-alternative-ablation-v2/index.json",
        ROOT / "artifacts/public/realistic-alternative-ablation-v2/report.json",
    ]
    return with_digest(
        {
            "schema_version": "1.0.0",
            "cp03_frozen_digest": protocol["frozen_digest"],
            "files": {str(path.relative_to(ROOT)): digest_file(path) for path in paths},
            "native_action_contract_digest": digest_json(
                protocol["native_action_contract"]
            ),
            "decision_rule": protocol["decision_rule"],
            "classifications": protocol["decision_rule"]["classifications"],
            "thresholds": {
                "clean_control_false_refusal_threshold": protocol["decision_rule"][
                    "clean_control_false_refusal_threshold"
                ],
                "unsafe_committed_action_threshold": protocol["decision_rule"][
                    "unsafe_committed_action_threshold"
                ],
            },
        },
        "frozen_input_evidence_digest",
    )


def public_index() -> dict[str, Any]:
    files = sorted(
        path
        for path in PUBLIC.iterdir()
        if path.is_file() and path.name != "index.json"
    )
    return with_digest(
        {
            "schema_version": "1.0.0",
            "result": "DEFINITIVE_CONSEQUENTIAL_RUN_COMPLETE",
            "classification": "NO_MATERIAL_ADVANTAGE",
            "recommendation": "SIMPLIFY",
            "files": [
                {
                    "path": path.name,
                    "digest": digest_file(path),
                    "size_bytes": path.stat().st_size,
                }
                for path in files
            ],
            "limitations": [
                "All native mutations were confined to disposable loopback services.",
                "The run is author-operated and does not satisfy RC-018.",
                (
                    "Fresh CI and Retirement Conductor share verifier code in "
                    "the live harness; CP-03 owns the frozen machinery comparison."
                ),
                (
                    "DataHub and PostgreSQL cannot share one atomic transaction; "
                    "the final race remains bounded, not eliminated."
                ),
            ],
        },
        "index_digest",
    )


def publish_results(
    *,
    protocol: Mapping[str, Any],
    implementation_commit: str,
    mcp_identity: Mapping[str, Any],
    installed_cli: Mapping[str, Any],
    psql_version: str,
    arms: list[dict[str, Any]],
) -> dict[str, Any]:
    PUBLIC.mkdir(parents=True, exist_ok=True)
    for stale in PUBLIC.glob("*.json"):
        stale.unlink()
    frozen = frozen_inputs(protocol)
    write_json(PUBLIC / "frozen-inputs.json", frozen)
    for arm in arms:
        write_json(PUBLIC / f"{arm['arm']}.json", with_digest(arm, "arm_digest"))
    cp03 = verify_public_evidence(CP03_PROTOCOL, CP03_PUBLIC)
    require(
        cp03["classification"] == "NO_MATERIAL_ADVANTAGE",
        "CP-03 classification changed",
    )
    require(cp03["recommendation"] == "SIMPLIFY", "CP-03 recommendation changed")
    by_arm = {arm["arm"]: arm for arm in arms}
    comparison = with_digest(
        {
            "schema_version": "1.0.0",
            "classification": cp03["classification"],
            "recommendation": cp03["recommendation"],
            "frozen_cp03_index_digest": cp03["index_digest"],
            "native_result": {
                "retirement_conductor_clean_commit_count": by_arm[
                    "retirement-conductor-clean"
                ]["action"]["destructive_statements_committed"],
                "retirement_conductor_late_commit_count": by_arm[
                    "retirement-conductor-late"
                ]["destructive_statements_committed"],
                "fresh_ci_late_commit_count": by_arm["fresh-ci-equivalent"][
                    "destructive_statements_committed"
                ],
                "static_late_commit_count": by_arm["point-in-time-static"][
                    "destructive_statements_committed"
                ],
                "static_legacy_workload_outcome": by_arm["point-in-time-static"][
                    "legacy_workload_after"
                ]["outcome"],
                "fresh_ci_boundary_equivalent": True,
                "retirement_conductor_boundary_equivalent": True,
            },
            "decision": (
                "Fresh CI matched every frozen safety, recovery, outcome, and "
                "causal-audit property with less persistent machinery. The live "
                "native action and workload did not overturn the frozen result."
            ),
        },
        "comparison_digest",
    )
    write_json(PUBLIC / "comparison.json", comparison)
    run_metadata = with_digest(
        {
            "schema_version": "1.0.0",
            "evidence_mode": "live-local",
            "captured_at": utc_now(),
            "implementation_commit": implementation_commit,
            "planning_base_commit": "7a7908f61ba217048b1292eb8c36a70a9e61276b",
            "foundation_commits": {
                "cp01": ["d1720b1", "836431a"],
                "cp02": ["847a4b8"],
                "cp03": ["94dceed"],
                "cp04": ["155a1e0"],
            },
            "source_tree_diff_digest": digest_json(
                command(["git", "diff", "--binary", implementation_commit]).stdout
            ),
            "versions": {
                "datahub": "1.6.0",
                "datahub_mcp": MCP_PACKAGE_VERSION,
                "datahub_mcp_commit": MCP_COMMIT,
                "superset": "6.0.0",
                "postgres": "16",
                "postgres_client": psql_version,
                "spark": "3.5.3",
                "jdbc": "42.7.4",
            },
            "images": IMAGE_IDENTITIES,
            "mcp_identity": dict(mcp_identity),
            "installed_cli": dict(installed_cli),
            "credential_values_recorded": False,
            "row_values_recorded": False,
            "host_paths_recorded": False,
            "independent_operation": "NOT_RUN",
        },
        "run_metadata_digest",
    )
    write_json(PUBLIC / "run-metadata.json", run_metadata)
    index = public_index()
    write_json(PUBLIC / "index.json", index)
    return index


def verify_public() -> dict[str, Any]:
    index = load_object(PUBLIC / "index.json")
    verify_digest(index, "index_digest")
    for entry in index["files"]:
        path = PUBLIC / entry["path"]
        require(path.is_file(), f"public evidence file is missing: {entry['path']}")
        require(
            digest_file(path) == entry["digest"],
            f"public digest mismatch: {entry['path']}",
        )
        require(
            path.stat().st_size == entry["size_bytes"],
            f"public size mismatch: {entry['path']}",
        )
    frozen = load_object(PUBLIC / "frozen-inputs.json")
    verify_digest(frozen, "frozen_input_evidence_digest")
    protocol = load_object(CP03_PROTOCOL)
    verify_frozen_protocol(protocol)
    require(
        frozen["cp03_frozen_digest"] == protocol["frozen_digest"],
        "CP-03 frozen digest changed",
    )
    for path_text, expected_digest in frozen["files"].items():
        require(
            digest_file(ROOT / path_text) == expected_digest,
            f"frozen file changed: {path_text}",
        )
    comparison = load_object(PUBLIC / "comparison.json")
    verify_digest(comparison, "comparison_digest")
    require(
        comparison["classification"] == "NO_MATERIAL_ADVANTAGE",
        "classification changed",
    )
    require(comparison["recommendation"] == "SIMPLIFY", "recommendation changed")
    return index


def run() -> dict[str, Any]:
    task_temporary_directory = RUNTIME / "tmp"
    task_temporary_directory.mkdir(parents=True, exist_ok=True)
    os.environ["TMPDIR"] = str(task_temporary_directory)
    progress("verifying the frozen CP-03 protocol and local prerequisites")
    protocol = load_object(CP03_PROTOCOL)
    verify_frozen_protocol(protocol)
    load_specification(SPECIFICATION)
    command(
        [
            "uv",
            "run",
            "python",
            "scripts/run_realistic_alternative_ablation_v2.py",
            "verify-freeze",
        ]
    )
    command(["uv", "run", "python", "scripts/datahub_core_env.py"])
    psql_version = command(["psql", "--version"]).stdout.strip()
    driver, _driver_version = acquire_driver(load_contract())
    ensure_mount_readability(driver)
    environment = runtime_environment(driver)
    installed_cli = prepare_installed_cli(environment)
    paused = pause_existing_projects()
    mcp_process: subprocess.Popen[str] | None = None
    bootstrap_project = "rc_cp05_dh_mcp_bootstrap"
    try:
        progress("starting pinned DataHub to establish the MCP identity")
        start_datahub(bootstrap_project)
        mcp_process, mcp_identity = start_mcp()
        stop_datahub(bootstrap_project)
        arms: list[dict[str, Any]] = []
        for label, run_arm in (
            ("Retirement Conductor clean action", run_product_clean),
            ("Retirement Conductor late-consumer refusal", run_product_late),
            ("point-in-time static unsafe action", run_static_unsafe),
            ("fresh-CI-equivalent late-consumer refusal", run_fresh_ci_late),
            ("negative native-boundary matrix", run_negative_matrix),
            ("outcome-unknown recovery matrix", run_recovery_matrix),
        ):
            progress(f"running {label}")
            arms.append(run_arm(environment))
        implementation_commit = command(["git", "rev-parse", "HEAD"]).stdout.strip()
        progress("publishing and independently verifying redacted public evidence")
        index = publish_results(
            protocol=protocol,
            implementation_commit=implementation_commit,
            mcp_identity=mcp_identity,
            installed_cli=installed_cli,
            psql_version=psql_version,
            arms=arms,
        )
        verify_public()
        return index
    finally:
        stop_datahub(bootstrap_project)
        if mcp_process is not None:
            mcp_process.terminate()
            try:
                mcp_process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                mcp_process.kill()
                mcp_process.wait(timeout=15)
        restore_existing_projects(paused)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "verify"))
    args = parser.parse_args()
    result = run() if args.action == "run" else verify_public()
    print(
        f"{result['result']}: classification={result['classification']} "
        f"recommendation={result['recommendation']} index={result['index_digest']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

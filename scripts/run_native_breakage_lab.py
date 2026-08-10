#!/usr/bin/env python3
"""Run CP-04 against isolated PostgreSQL and Spark/JDBC containers."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy/native-breakage-lab"
COMPOSE = DEPLOY / "docker-compose.yml"
CONTRACT_PATH = ROOT / "fixtures/native-breakage-lab/contract.json"
RUNTIME = ROOT / ".retirement-conductor/native-breakage-lab"
PUBLIC = ROOT / "artifacts/public/native-breakage-outcome-lab"
FROZEN_PATHS = (
    COMPOSE,
    DEPLOY / "initdb/10-native-breakage-lab.sql",
    DEPLOY / "workload.py",
    CONTRACT_PATH,
)
RESULT_PREFIX = "NATIVE_BREAKAGE_RESULT="
DROP_STATEMENT = "ALTER TABLE retirement_lab.orders DROP COLUMN legacy_status"


class LabFailure(RuntimeError):
    """Raised when native evidence does not satisfy the frozen contract."""


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def digest_bytes(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def digest_json(value: Any) -> str:
    return digest_bytes(canonical_json(value).encode())


def with_digest(value: Mapping[str, Any], field: str) -> dict[str, Any]:
    result = dict(value)
    result.pop(field, None)
    result[field] = digest_json(result)
    return result


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def load_contract() -> dict[str, Any]:
    value = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise LabFailure("frozen contract is not an object")
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise LabFailure(message)


def captured_at() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def command(
    arguments: Sequence[str],
    *,
    environment: Mapping[str, str] | None = None,
    expected: set[int] | None = None,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        list(arguments),
        cwd=ROOT,
        env=dict(environment) if environment is not None else None,
        capture_output=True,
        text=True,
        check=False,
    )
    allowed = {0} if expected is None else expected
    if completed.returncode not in allowed:
        failure_dir = RUNTIME / "raw" / "command-failures"
        failure_dir.mkdir(parents=True, exist_ok=True)
        failure_path = failure_dir / f"failure-{time.time_ns()}.json"
        write_json(
            failure_path,
            {
                "arguments": list(arguments),
                "exit_code": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            },
        )
        detail_lines = (completed.stderr + "\n" + completed.stdout).strip().splitlines()
        detail = detail_lines[-1][:400] if detail_lines else "no command output"
        raise LabFailure(
            f"command failed with exit {completed.returncode}: "
            f"{' '.join(arguments[:6])}; {detail}"
        )
    return completed


def compose(
    project: str,
    environment: Mapping[str, str],
    arguments: Sequence[str],
    *,
    expected: set[int] | None = None,
) -> subprocess.CompletedProcess[str]:
    return command(
        ["docker", "compose", "-p", project, "-f", str(COMPOSE), *arguments],
        environment=environment,
        expected=expected,
    )


def file_digest(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def frozen_inputs(contract: Mapping[str, Any]) -> dict[str, Any]:
    files = {
        str(path.relative_to(ROOT)): file_digest(path) for path in sorted(FROZEN_PATHS)
    }
    value = {
        "schema_version": "1.0.0",
        "files": files,
        "generator": contract["generator"],
        "runtime_images": contract["runtime_images"],
        "jdbc_driver": contract["jdbc_driver"],
        "expected_schema_digests": contract["schema_digests"],
        "expected_safe_digests": contract["safe_digests"],
    }
    value["frozen_input_digest"] = digest_json(value)
    return with_digest(value, "artifact_digest")


def acquire_driver(contract: Mapping[str, Any]) -> tuple[Path, str]:
    driver = contract["jdbc_driver"]
    cache = RUNTIME / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / "postgresql-42.7.4.jar"
    if (
        not target.exists()
        or hashlib.sha256(target.read_bytes()).hexdigest() != driver["sha256"]
    ):
        temporary = cache / "postgresql-42.7.4.jar.download"
        with urllib.request.urlopen(str(driver["url"]), timeout=60) as response:
            temporary.write_bytes(response.read())
        require(
            temporary.stat().st_size == driver["size_bytes"],
            "JDBC driver size mismatch",
        )
        require(
            hashlib.sha256(temporary.read_bytes()).hexdigest() == driver["sha256"],
            "JDBC driver digest mismatch",
        )
        os.replace(temporary, target)
    target.chmod(0o644)
    require(target.stat().st_size == driver["size_bytes"], "cached JDBC size mismatch")
    require(
        hashlib.sha256(target.read_bytes()).hexdigest() == driver["sha256"],
        "cached JDBC digest mismatch",
    )
    with zipfile.ZipFile(target) as archive:
        manifest = archive.read("META-INF/MANIFEST.MF").decode(
            "utf-8", errors="replace"
        )
    match = re.search(r"^Implementation-Version:\s*(\S+)", manifest, re.MULTILINE)
    require(match is not None, "JDBC manifest version is missing")
    version = match.group(1) if match is not None else ""
    require(version == "42.7.4", "JDBC manifest version mismatch")
    return target.resolve(), version


def runtime_environment(driver: Path) -> dict[str, str]:
    environment = dict(os.environ)
    environment.update(
        {
            "POSTGRES_PASSWORD": secrets.token_urlsafe(32),
            "LEGACY_READER_PASSWORD": secrets.token_urlsafe(32),
            "REPLACEMENT_READER_PASSWORD": secrets.token_urlsafe(32),
            "WORKLOAD_DB_USER": "legacy_reader",
            "WORKLOAD_DB_PASSWORD": secrets.token_urlsafe(32),
            "WORKLOAD_FIELD": "legacy_status",
            "NATIVE_BREAKAGE_JDBC_JAR": str(driver),
        }
    )
    return environment


def start(project: str, environment: Mapping[str, str]) -> None:
    compose(project, environment, ["up", "-d", "--wait", "postgres"])


def save_logs(project: str, environment: Mapping[str, str]) -> None:
    completed = compose(project, environment, ["logs", "--no-color"], expected={0, 1})
    destination = RUNTIME / "raw" / project / "compose.log"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(completed.stdout + completed.stderr, encoding="utf-8")


def stop(project: str, environment: Mapping[str, str]) -> None:
    save_logs(project, environment)
    compose(
        project,
        environment,
        ["down", "--volumes", "--remove-orphans", "--timeout", "20"],
        expected={0, 1},
    )


def psql(
    project: str,
    environment: Mapping[str, str],
    sql: str,
    *,
    username: str = "lab_admin",
    expected: set[int] | None = None,
) -> subprocess.CompletedProcess[str]:
    return compose(
        project,
        environment,
        [
            "exec",
            "-T",
            "postgres",
            "sh",
            "-ceu",
            (
                f"psql -h 127.0.0.1 -U {username} "
                "-d native_breakage -At -F '\t' -c \"$1\""
            ),
            "psql-command",
            sql,
        ],
        expected=expected,
    )


def credential_probe(
    project: str,
    environment: Mapping[str, str],
    cross_password: str,
) -> subprocess.CompletedProcess[str]:
    probe_environment = dict(environment)
    probe_environment["WORKLOAD_DB_PASSWORD"] = cross_password
    return compose(
        project,
        probe_environment,
        ["--profile", "probe", "run", "--rm", "--no-deps", "credential-probe"],
        expected={2},
    )


SCHEMA_SQL = """
SELECT ordinal_position, column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'retirement_lab' AND table_name = 'orders'
ORDER BY ordinal_position
""".strip()


def schema_observation(project: str, environment: Mapping[str, str]) -> dict[str, Any]:
    output = psql(project, environment, SCHEMA_SQL).stdout.strip()
    columns = []
    for line in output.splitlines():
        ordinal, name, data_type, nullable = line.split("\t")
        columns.append(
            {
                "ordinal_position": int(ordinal),
                "column_name": name,
                "data_type": data_type,
                "is_nullable": nullable,
            }
        )
    return {"columns": columns, "schema_digest": digest_json(columns)}


def producer_observation(
    project: str, environment: Mapping[str, str]
) -> dict[str, Any]:
    sql = """
SELECT
  count(*),
  count(*) FILTER (WHERE legacy_status IS DISTINCT FROM order_status),
  count(*) FILTER (WHERE legacy_status IS NULL OR order_status IS NULL),
  encode(digest(string_agg(
    id::text || '|' || legacy_status || '|' || order_status || '|' ||
      amount_cents::text,
    E'\\n' ORDER BY id
  ), 'sha256'), 'hex')
FROM retirement_lab.orders
""".strip()
    row_count, mismatch_count, null_count, digest = (
        psql(project, environment, sql).stdout.strip().split("\t")
    )
    return {
        "row_count": int(row_count),
        "compatibility_mismatch_count": int(mismatch_count),
        "compatibility_null_count": int(null_count),
        "safe_whole_result_digest": f"sha256:{digest}",
    }


def privileges(project: str, environment: Mapping[str, str]) -> dict[str, Any]:
    sql = """
SELECT role_name,
       has_table_privilege(role_name, 'retirement_lab.orders', 'SELECT'),
       has_table_privilege(role_name, 'retirement_lab.orders', 'INSERT'),
       has_table_privilege(role_name, 'retirement_lab.orders', 'UPDATE'),
       has_table_privilege(role_name, 'retirement_lab.orders', 'DELETE')
FROM (VALUES ('legacy_reader'), ('replacement_reader')) AS roles(role_name)
ORDER BY role_name
""".strip()
    result: dict[str, Any] = {}
    for line in psql(project, environment, sql).stdout.strip().splitlines():
        role, can_select, can_insert, can_update, can_delete = line.split("\t")
        result[role] = {
            "select": can_select == "t",
            "insert": can_insert == "t",
            "update": can_update == "t",
            "delete": can_delete == "t",
        }
    return result


def native_versions(project: str, environment: Mapping[str, str]) -> dict[str, str]:
    postgres = psql(project, environment, "SHOW server_version").stdout.strip()
    image = command(
        [
            "docker",
            "image",
            "inspect",
            "apache/spark@sha256:a1f2c9dcecb36c0f5c342be340b368883cfaa1d7ab23e6e222c8a93157b73a74",
            "--format",
            "{{.Id}}",
        ]
    ).stdout.strip()
    require(
        image
        == "sha256:a1f2c9dcecb36c0f5c342be340b368883cfaa1d7ab23e6e222c8a93157b73a74",
        "local Spark image identity changed",
    )
    return {"postgres_server": postgres, "spark_image_id": image}


def run_workload(
    project: str,
    environment: Mapping[str, str],
    *,
    kind: str,
    expected_exit: set[int],
) -> dict[str, Any]:
    field = "legacy_status" if kind == "legacy" else "order_status"
    user = "legacy_reader" if kind == "legacy" else "replacement_reader"
    password_key = (
        "LEGACY_READER_PASSWORD" if kind == "legacy" else "REPLACEMENT_READER_PASSWORD"
    )
    workload_environment = dict(environment)
    workload_environment.update(
        {
            "WORKLOAD_FIELD": field,
            "WORKLOAD_DB_USER": user,
            "WORKLOAD_DB_PASSWORD": environment[password_key],
        }
    )
    started = time.monotonic()
    completed = compose(
        project,
        workload_environment,
        ["--profile", "workload", "run", "--rm", "--no-deps", "spark-workload"],
        expected=expected_exit,
    )
    duration_ms = int((time.monotonic() - started) * 1000)
    combined = completed.stdout + "\n" + completed.stderr
    markers = [
        line[len(RESULT_PREFIX) :]
        for line in combined.splitlines()
        if line.startswith(RESULT_PREFIX)
    ]
    require(len(markers) == 1, f"{kind} workload emitted {len(markers)} result markers")
    result = json.loads(markers[0])
    require(isinstance(result, dict), "workload result is not an object")
    return {
        "captured_at": captured_at(),
        "duration_ms": duration_ms,
        "exit_code": completed.returncode,
        **result,
    }


def validate_seed(
    contract: Mapping[str, Any],
    schema: Mapping[str, Any],
    producer: Mapping[str, Any],
    access: Mapping[str, Any],
) -> None:
    require(
        schema["schema_digest"] == contract["schema_digests"]["before_drop"],
        "seed schema digest mismatch",
    )
    require(
        producer["row_count"] == contract["generator"]["row_count"],
        "seed row count mismatch",
    )
    require(
        producer["compatibility_mismatch_count"] == 0,
        "legacy/replacement values diverged",
    )
    require(
        producer["compatibility_null_count"] == 0,
        "legacy/replacement values contain nulls",
    )
    require(
        producer["safe_whole_result_digest"]
        == contract["safe_digests"]["producer_whole_result"],
        "producer whole-result digest mismatch",
    )
    for role in ("legacy_reader", "replacement_reader"):
        require(
            access[role]
            == {"select": True, "insert": False, "update": False, "delete": False},
            f"{role} is not read-only",
        )


def validate_success(
    contract: Mapping[str, Any], outcome: Mapping[str, Any], label: str
) -> None:
    require(outcome["exit_code"] == 0, f"{label} did not exit zero")
    require(outcome["outcome"] == "SUCCEEDED", f"{label} did not succeed")
    require(
        outcome["row_count"] == contract["generator"]["row_count"],
        f"{label} row count changed",
    )
    require(
        outcome["safe_output_digest"]
        == contract["safe_digests"]["workload_semantic_result"],
        f"{label} semantic digest changed",
    )


def unsafe_sequence(
    label: str,
    project: str,
    environment: Mapping[str, str],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        start(project, environment)
        before = schema_observation(project, environment)
        producer = producer_observation(project, environment)
        access = privileges(project, environment)
        validate_seed(contract, before, producer, access)
        versions = native_versions(project, environment)
        legacy_before = run_workload(
            project, environment, kind="legacy", expected_exit={0}
        )
        replacement_before = run_workload(
            project, environment, kind="replacement", expected_exit={0}
        )
        validate_success(contract, legacy_before, f"{label} legacy before")
        validate_success(contract, replacement_before, f"{label} replacement before")
        require(
            legacy_before["safe_output_digest"]
            == replacement_before["safe_output_digest"],
            "legacy/replacement workload semantics differ before drop",
        )

        psql(project, environment, DROP_STATEMENT)
        after = schema_observation(project, environment)
        require(
            after["schema_digest"] == contract["schema_digests"]["after_drop"],
            "post-drop schema digest mismatch",
        )
        require(
            all(
                column["column_name"] != "legacy_status" for column in after["columns"]
            ),
            "native schema reread still contains legacy_status",
        )

        legacy_after = run_workload(
            project, environment, kind="legacy", expected_exit={42}
        )
        require(
            legacy_after["outcome"] == "LEGACY_COLUMN_MISSING",
            "legacy failure category changed",
        )
        require(legacy_after["missing_field"] == "legacy_status", "wrong missing field")
        require(legacy_after["sqlstate"] == "42703", "missing-column SQLSTATE changed")
        replacement_after = run_workload(
            project, environment, kind="replacement", expected_exit={0}
        )
        validate_success(contract, replacement_after, f"{label} replacement after")
        require(
            replacement_before["safe_output_digest"]
            == replacement_after["safe_output_digest"],
            "replacement workload changed after drop",
        )
        return {
            "schema_version": "1.0.0",
            "sequence": label,
            "evidence_mode": "live-local disposable PostgreSQL and Apache Spark/JDBC",
            "result": "UNSAFE_ACTION_CONSEQUENCE_OBSERVED",
            "schema": {"before": before, "after": after},
            "producer": producer,
            "native_versions": versions,
            "principals": access,
            "workloads": {
                "legacy_before": legacy_before,
                "replacement_before": replacement_before,
                "legacy_after": legacy_after,
                "replacement_after": replacement_after,
            },
            "destructive_statement": {
                "count": 1,
                "operation": "DROP COLUMN",
                "target": "retirement_lab.orders.legacy_status",
            },
        }
    finally:
        stop(project, environment)


def prevented_sequence(
    project: str,
    environment: Mapping[str, str],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        start(project, environment)
        before = schema_observation(project, environment)
        producer = producer_observation(project, environment)
        access = privileges(project, environment)
        validate_seed(contract, before, producer, access)
        hook = {
            "decision": "DENIED_BY_CALLER",
            "requested_target": "retirement_lab.orders.legacy_status",
            "statement_executed": False,
        }
        after = schema_observation(project, environment)
        require(
            after["schema_digest"] == before["schema_digest"],
            "denied action changed schema",
        )
        legacy = run_workload(project, environment, kind="legacy", expected_exit={0})
        replacement = run_workload(
            project, environment, kind="replacement", expected_exit={0}
        )
        validate_success(contract, legacy, "prevented legacy")
        validate_success(contract, replacement, "prevented replacement")
        return {
            "schema_version": "1.0.0",
            "sequence": "prevented-action-control",
            "evidence_mode": "live-local disposable PostgreSQL and Apache Spark/JDBC",
            "result": "UNSAFE_ACTION_PREVENTED",
            "action_denied_hook": hook,
            "schema": {"before": before, "after": after},
            "workloads": {"legacy": legacy, "replacement": replacement},
            "destructive_statement_count": 0,
        }
    finally:
        stop(project, environment)


def container_networks(project: str, environment: Mapping[str, str]) -> set[str]:
    container_id = compose(
        project, environment, ["ps", "-q", "postgres"]
    ).stdout.strip()
    require(bool(container_id), "postgres container id missing")
    output = command(
        [
            "docker",
            "inspect",
            container_id,
            "--format",
            "{{range $key, $value := .NetworkSettings.Networks}}{{$key}}\n{{end}}",
        ]
    ).stdout
    return {line.strip() for line in output.splitlines() if line.strip()}


def isolation_sequence(
    project_a: str,
    environment_a: Mapping[str, str],
    project_b: str,
    environment_b: Mapping[str, str],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        start(project_a, environment_a)
        try:
            start(project_b, environment_b)
            schema_a = schema_observation(project_a, environment_a)
            schema_b = schema_observation(project_b, environment_b)
            producer_a = producer_observation(project_a, environment_a)
            producer_b = producer_observation(project_b, environment_b)
            networks_a = container_networks(project_a, environment_a)
            networks_b = container_networks(project_b, environment_b)
            overlap = networks_a & networks_b
            require(not overlap, "isolated Compose projects share a network")
            require(
                schema_a["schema_digest"] == schema_b["schema_digest"],
                "isolated seed schemas differ",
            )
            require(
                producer_a["safe_whole_result_digest"]
                == producer_b["safe_whole_result_digest"],
                "isolated seed data differs",
            )
            require(
                schema_a["schema_digest"] == contract["schema_digests"]["before_drop"],
                "isolated schema differs from contract",
            )

            cross_a = credential_probe(
                project_a,
                environment_a,
                environment_b["LEGACY_READER_PASSWORD"],
            )
            cross_b = credential_probe(
                project_b,
                environment_b,
                environment_a["LEGACY_READER_PASSWORD"],
            )
            require(
                "password authentication failed" in cross_a.stderr,
                "cross-run A credential refusal changed",
            )
            require(
                "password authentication failed" in cross_b.stderr,
                "cross-run B credential refusal changed",
            )
            return {
                "schema_version": "1.0.0",
                "sequence": "service-and-credential-isolation",
                "evidence_mode": "live-local disposable PostgreSQL",
                "result": "ISOLATION_PROVED",
                "compose_project_count": 2,
                "shared_network_count": len(overlap),
                "schema_digest_equal": True,
                "producer_digest_equal": True,
                "cross_run_credentials": [
                    {
                        "direction": "B credential against A database",
                        "authenticated": False,
                        "exit_code": cross_a.returncode,
                    },
                    {
                        "direction": "A credential against B database",
                        "authenticated": False,
                        "exit_code": cross_b.returncode,
                    },
                ],
                "credential_values_recorded": False,
            }
        finally:
            stop(project_b, environment_b)
    finally:
        stop(project_a, environment_a)


def reconstruction_evidence(
    contract: Mapping[str, Any],
    first: Mapping[str, Any],
    second: Mapping[str, Any],
) -> dict[str, Any]:
    first_before = first["schema"]["before"]["schema_digest"]
    second_before = second["schema"]["before"]["schema_digest"]
    first_legacy = first["workloads"]["legacy_before"]["safe_output_digest"]
    second_legacy = second["workloads"]["legacy_before"]["safe_output_digest"]
    first_replacement = first["workloads"]["replacement_before"]["safe_output_digest"]
    second_replacement = second["workloads"]["replacement_before"]["safe_output_digest"]
    require(
        first_before == second_before == contract["schema_digests"]["before_drop"],
        "reconstructed schema did not return",
    )
    require(first_legacy == second_legacy, "reconstructed legacy digest did not return")
    require(
        first_replacement == second_replacement,
        "reconstructed replacement digest did not return",
    )
    return {
        "schema_version": "1.0.0",
        "result": "DETERMINISTIC_RECONSTRUCTION_PROVED",
        "schema_digest": second_before,
        "legacy_workload_digest": second_legacy,
        "replacement_workload_digest": second_replacement,
        "original_environment_removed_before_reconstruction": True,
    }


def consumer_descriptor(
    contract: Mapping[str, Any], run: Mapping[str, Any]
) -> dict[str, Any]:
    legacy = run["workloads"]["legacy_before"]
    value = {
        "schema_version": "1.0.0",
        "descriptor_type": "public-safe-native-consumer",
        "evidence_mode": "live-local disposable fixture data",
        "workload": {
            "type": "Apache Spark batch over PostgreSQL JDBC",
            "version": legacy["spark_version"],
            "native_job_identity": contract["workloads"]["legacy"]["job_identity"],
            "source_code_digest": file_digest(DEPLOY / "workload.py"),
        },
        "producer": {
            "dataset_identity": contract["producer"]["dataset_identity"],
            "field_usage": {
                "field": "legacy_status",
                "operation": (
                    "selected as selected_status, uppercased, ordered, and "
                    "included in whole-result digest"
                ),
            },
        },
        "observation": {
            "executed_at": legacy["captured_at"],
            "outcome": legacy["outcome"],
            "row_count": legacy["row_count"],
            "success_digest": legacy["safe_output_digest"],
        },
        "limitations": [
            "This descriptor is not DataHub lineage evidence.",
            (
                "CP-05 must ingest and directly reread the corresponding DataHub "
                "aspect before campaign use."
            ),
            (
                "The observation is live-local over deterministic fixture rows, "
                "not production or customer evidence."
            ),
        ],
    }
    return with_digest(value, "descriptor_digest")


def artifact(value: Mapping[str, Any]) -> dict[str, Any]:
    return with_digest(value, "artifact_digest")


def public_scan() -> dict[str, Any]:
    findings: list[str] = []
    forbidden = {
        "home path": re.compile(r"(?:/home/|/Users/)[^/\s]+/"),
        "credential field": re.compile(r'(?i)"(?:password|token|secret)"\s*:'),
        "raw row shape": re.compile(
            r'(?i)"(?:id|legacy_status|order_status|amount_cents)"\s*:'
        ),
        "unrestricted native error": re.compile(
            r'(?i)"(?:stderr|stdout|message|stacktrace)"\s*:'
        ),
    }
    for path in sorted(PUBLIC.glob("*.json")):
        content = path.read_text(encoding="utf-8")
        for label, pattern in forbidden.items():
            if pattern.search(content):
                findings.append(f"{path.name}: {label}")
    require(not findings, f"public artifact scan failed: {findings}")
    return {
        "result": "PASSED",
        "files_checked": len(list(PUBLIC.glob("*.json"))),
        "finding_count": 0,
    }


def run() -> dict[str, Any]:
    require(shutil.which("docker") is not None, "docker is unavailable")
    command(["docker", "version", "--format", "{{.Server.Version}}"])
    contract = load_contract()
    frozen = frozen_inputs(contract)
    driver_path, driver_version = acquire_driver(contract)
    PUBLIC.mkdir(parents=True, exist_ok=True)
    for old in PUBLIC.glob("*.json"):
        old.unlink()
    write_json(PUBLIC / "frozen-inputs.json", frozen)

    token = secrets.token_hex(4)
    environment_1 = runtime_environment(driver_path)
    environment_2 = runtime_environment(driver_path)
    environment_prevented = runtime_environment(driver_path)
    environment_a = runtime_environment(driver_path)
    environment_b = runtime_environment(driver_path)

    unsafe_1 = artifact(
        unsafe_sequence(
            "unsafe-action-run-1", f"rc-cp04-u1-{token}", environment_1, contract
        )
    )
    write_json(PUBLIC / "unsafe-run-1.json", unsafe_1)
    unsafe_2 = artifact(
        unsafe_sequence(
            "unsafe-action-run-2", f"rc-cp04-u2-{token}", environment_2, contract
        )
    )
    write_json(PUBLIC / "unsafe-run-2.json", unsafe_2)
    reconstruction = artifact(reconstruction_evidence(contract, unsafe_1, unsafe_2))
    write_json(PUBLIC / "reconstruction.json", reconstruction)
    prevented = artifact(
        prevented_sequence(f"rc-cp04-p-{token}", environment_prevented, contract)
    )
    write_json(PUBLIC / "prevented-control.json", prevented)
    isolation = artifact(
        isolation_sequence(
            f"rc-cp04-ia-{token}",
            environment_a,
            f"rc-cp04-ib-{token}",
            environment_b,
            contract,
        )
    )
    write_json(PUBLIC / "isolation.json", isolation)
    descriptor = consumer_descriptor(contract, unsafe_1)
    write_json(PUBLIC / "consumer-descriptor.json", descriptor)

    versions = unsafe_1["native_versions"]
    index = {
        "schema_version": "1.0.0",
        "workstream": "CP-04 native downstream breakage outcome lab",
        "result": "NATIVE_BREAKAGE_OUTCOME_LAB_PASSED",
        "recommendation": "KEEP_SPARK",
        "evidence_mode": (
            "live-local disposable PostgreSQL and Apache Spark/JDBC over "
            "deterministic fixture data"
        ),
        "frozen_input_digest": frozen["frozen_input_digest"],
        "components": {
            "postgres": {
                "image": contract["runtime_images"]["postgres"],
                "server_version": versions["postgres_server"],
            },
            "spark": {
                "image": contract["runtime_images"]["spark"],
                "version": unsafe_1["workloads"]["legacy_before"]["spark_version"],
            },
            "jdbc": {
                "artifact": contract["jdbc_driver"]["artifact"],
                "version": driver_version,
                "sha256": f"sha256:{contract['jdbc_driver']['sha256']}",
            },
        },
        "schema_digests": {
            "before": unsafe_1["schema"]["before"]["schema_digest"],
            "after": unsafe_1["schema"]["after"]["schema_digest"],
            "reconstructed": reconstruction["schema_digest"],
        },
        "unsafe_action_runs": [
            {
                "artifact": "unsafe-run-1.json",
                "artifact_digest": unsafe_1["artifact_digest"],
                "legacy_before": unsafe_1["workloads"]["legacy_before"]["outcome"],
                "legacy_after": unsafe_1["workloads"]["legacy_after"]["outcome"],
                "replacement_before_digest": unsafe_1["workloads"][
                    "replacement_before"
                ]["safe_output_digest"],
                "replacement_after_digest": unsafe_1["workloads"]["replacement_after"][
                    "safe_output_digest"
                ],
            },
            {
                "artifact": "unsafe-run-2.json",
                "artifact_digest": unsafe_2["artifact_digest"],
                "legacy_before": unsafe_2["workloads"]["legacy_before"]["outcome"],
                "legacy_after": unsafe_2["workloads"]["legacy_after"]["outcome"],
                "replacement_before_digest": unsafe_2["workloads"][
                    "replacement_before"
                ]["safe_output_digest"],
                "replacement_after_digest": unsafe_2["workloads"]["replacement_after"][
                    "safe_output_digest"
                ],
            },
        ],
        "prevented_action": {
            "artifact": "prevented-control.json",
            "artifact_digest": prevented["artifact_digest"],
            "result": prevented["result"],
            "legacy": prevented["workloads"]["legacy"]["outcome"],
            "replacement": prevented["workloads"]["replacement"]["outcome"],
        },
        "missing_column_error": {
            "normalized_outcome": unsafe_1["workloads"]["legacy_after"]["outcome"],
            "missing_field": unsafe_1["workloads"]["legacy_after"]["missing_field"],
            "sqlstate": unsafe_1["workloads"]["legacy_after"]["sqlstate"],
            "exit_code": unsafe_1["workloads"]["legacy_after"]["exit_code"],
        },
        "destructive_statement_count": unsafe_1["destructive_statement"]["count"]
        + unsafe_2["destructive_statement"]["count"],
        "reconstruction": {
            "artifact": "reconstruction.json",
            "artifact_digest": reconstruction["artifact_digest"],
            "result": reconstruction["result"],
        },
        "isolation": {
            "artifact": "isolation.json",
            "artifact_digest": isolation["artifact_digest"],
            "result": isolation["result"],
        },
        "consumer_descriptor": {
            "artifact": "consumer-descriptor.json",
            "descriptor_digest": descriptor["descriptor_digest"],
        },
        "fallback_classification": "NOT_USED_SPARK_ACHIEVED",
        "limitations": [
            "This lab is disposable and non-production.",
            (
                "The data is deterministic fixture data and does not establish "
                "customer or production coverage."
            ),
            (
                "The consumer descriptor is a handoff record, not DataHub "
                "lineage evidence."
            ),
            (
                "CP-04 does not integrate DataHub or Retirement Conductor and "
                "does not decide why an action is denied."
            ),
        ],
        "raw_evidence": "ignored runtime state only",
    }
    write_json(PUBLIC / "index.json", with_digest(index, "self_digest"))
    scan = public_scan()
    index = json.loads((PUBLIC / "index.json").read_text(encoding="utf-8"))
    index["public_artifact_scan"] = scan
    final_index = with_digest(index, "self_digest")
    write_json(PUBLIC / "index.json", final_index)
    return final_index


def verify() -> dict[str, Any]:
    index_path = PUBLIC / "index.json"
    require(index_path.exists(), "public index is missing")
    index: dict[str, Any] = json.loads(index_path.read_text(encoding="utf-8"))
    expected = index["self_digest"]
    unsigned = dict(index)
    unsigned.pop("self_digest")
    require(expected == digest_json(unsigned), "index self digest mismatch")
    for path in sorted(PUBLIC.glob("*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        field = (
            "self_digest"
            if path.name == "index.json"
            else "descriptor_digest"
            if path.name == "consumer-descriptor.json"
            else "artifact_digest"
        )
        expected_digest = value[field]
        unsigned_value = dict(value)
        unsigned_value.pop(field)
        require(
            expected_digest == digest_json(unsigned_value),
            f"{path.name} digest mismatch",
        )
    public_scan()
    require(index["recommendation"] == "KEEP_SPARK", "Spark recommendation missing")
    return index


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run", "verify"), nargs="?", default="run")
    arguments = parser.parse_args()
    try:
        result = run() if arguments.command == "run" else verify()
    except LabFailure as error:
        print(f"native breakage lab failed: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "result": result["result"],
                "recommendation": result["recommendation"],
                "self_digest": result["self_digest"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

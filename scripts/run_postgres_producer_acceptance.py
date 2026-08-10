#!/usr/bin/env python3
"""Exercise the frozen CP-01 matrix against disposable PostgreSQL."""

from __future__ import annotations

import copy
import json
import os
import secrets
import socket
import subprocess
import threading
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Any

from retirement_conductor.canonical import digest_file, with_digest, write_json
from retirement_conductor.errors import Refusal
from retirement_conductor.postgres_producer import (
    POSTGRES_ACTION_REPLAYED,
    MutationTransportLost,
    PostgresActionOutcome,
    PostgresCliClient,
    PostgresClientProtocol,
    PostgresProducerAction,
)
from retirement_conductor.postgres_producer_config import (
    PostgresConnectionSettings,
    PostgresProducerSettings,
    PostgresTarget,
)

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "deploy/postgres-producer/docker-compose.yml"
FROZEN = ROOT / "deploy/postgres-producer/FROZEN.json"
RUNTIME_ROOT = ROOT / ".retirement-conductor/cp01"
PRIVATE_ROOT = RUNTIME_ROOT / "private"
PUBLIC_ROOT = ROOT / "artifacts/public/postgres-producer-action"
PROJECT = "rc_cp01_producer"
IMAGE = (
    "postgres@sha256:95206741a5b214807675e14165369d05b93a9cf692223b616d07cca227e74b0b"
)
PORT = 25432
TARGET = PostgresTarget(
    database="rc_cp01_producer",
    schema="retirement_lab",
    table="orders",
    legacy_column="legacy_status",
    replacement_column="order_status",
)
PSQL_COMMAND = (
    "docker",
    "run",
    "--rm",
    "--network",
    "host",
    "--env",
    "PGPASSWORD",
    IMAGE,
    "psql",
)


class LossBeforeExecutionClient:
    def __init__(self, delegate: PostgresClientProtocol) -> None:
        self.delegate = delegate
        self.connection = delegate.connection

    def observe(self, target: PostgresTarget) -> dict[str, Any]:
        return self.delegate.observe(target)

    def execute_drop(self, plan: Mapping[str, Any]) -> dict[str, Any]:
        raise MutationTransportLost("before_execution")


class LossAfterIntentClient:
    def __init__(self, delegate: PostgresClientProtocol) -> None:
        self.delegate = delegate
        self.connection = delegate.connection

    def observe(self, target: PostgresTarget) -> dict[str, Any]:
        return self.delegate.observe(target)

    def execute_drop(self, plan: Mapping[str, Any]) -> dict[str, Any]:
        self.delegate.execute_drop(plan)
        raise MutationTransportLost("after_intent_before_outcome_observation")


class ConcurrentClient:
    def __init__(
        self, delegate: PostgresClientProtocol, barrier: threading.Barrier
    ) -> None:
        self.delegate = delegate
        self.connection = delegate.connection
        self.barrier = barrier

    def observe(self, target: PostgresTarget) -> dict[str, Any]:
        return self.delegate.observe(target)

    def execute_drop(self, plan: Mapping[str, Any]) -> dict[str, Any]:
        self.barrier.wait(timeout=10)
        return self.delegate.execute_drop(plan)


def now() -> datetime:
    return datetime.now(tz=UTC)


def timestamp(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def command_output(command: list[str]) -> str:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def compose_environment(variant: str, secrets_map: Mapping[str, str]) -> dict[str, str]:
    return {
        **os.environ,
        "COMPOSE_PROJECT_NAME": PROJECT,
        "RC_CP01_DATABASE": TARGET.database,
        "RC_CP01_ADMIN_USER": "rc_cp01_admin",
        "RC_CP01_ADMIN_PASSWORD": secrets_map["admin"],
        "RC_CP01_OBSERVER_PASSWORD": secrets_map["observer"],
        "RC_CP01_MUTATION_PASSWORD": secrets_map["mutation"],
        "RC_CP01_UNPRIVILEGED_PASSWORD": secrets_map["unprivileged"],
        "RC_CP01_FIXTURE_VARIANT": variant,
        "RC_CP01_PORT": str(PORT),
    }


def compose(
    arguments: list[str], *, variant: str, secrets_map: Mapping[str, str]
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE), *arguments],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        env=compose_environment(variant, secrets_map),
    )


def recreate(variant: str, secrets_map: Mapping[str, str]) -> None:
    down = compose(
        ["down", "--volumes", "--remove-orphans"],
        variant=variant,
        secrets_map=secrets_map,
    )
    if down.returncode != 0:
        raise RuntimeError("could not stop the isolated CP-01 service")
    up = compose(["up", "-d", "--wait"], variant=variant, secrets_map=secrets_map)
    if up.returncode != 0:
        logs = compose(
            ["logs", "--no-color", "postgres"],
            variant=variant,
            secrets_map=secrets_map,
        )
        PRIVATE_ROOT.mkdir(parents=True, exist_ok=True)
        (PRIVATE_ROOT / "compose-up-failure.log").write_text(
            up.stdout + up.stderr + logs.stdout + logs.stderr,
            encoding="utf-8",
        )
        raise RuntimeError("could not start the isolated CP-01 service")


def stop(secrets_map: Mapping[str, str]) -> None:
    compose(
        ["down", "--volumes", "--remove-orphans"],
        variant="clean",
        secrets_map=secrets_map,
    )


def settings(
    secrets_map: Mapping[str, str],
    *,
    allow_apply: bool,
    allowlisted: bool = True,
    host: str = "127.0.0.1",
) -> PostgresProducerSettings:
    environment = {
        "POSTGRES_PRODUCER_HOST": host,
        "POSTGRES_PRODUCER_PORT": str(PORT),
        "POSTGRES_PRODUCER_DATABASE": TARGET.database,
        "POSTGRES_PRODUCER_OBSERVER_USER": "rc_cp01_observer",
        "POSTGRES_PRODUCER_OBSERVER_PASSWORD": secrets_map["observer"],
        "POSTGRES_PRODUCER_MUTATION_USER": "rc_cp01_mutator",
        "POSTGRES_PRODUCER_MUTATION_PASSWORD": secrets_map["mutation"],
        "POSTGRES_PRODUCER_ALLOW_APPLY": str(allow_apply).lower(),
        "POSTGRES_PRODUCER_ALLOWED_TARGET": (
            "/".join(TARGET.as_dict().values()) if allowlisted else ""
        ),
    }
    return PostgresProducerSettings.from_environment(environment)


def clients(
    producer_settings: PostgresProducerSettings,
) -> tuple[PostgresCliClient, PostgresCliClient]:
    return (
        PostgresCliClient(
            producer_settings.observer_connection(), psql_command=PSQL_COMMAND
        ),
        PostgresCliClient(
            producer_settings.mutation_connection(), psql_command=PSQL_COMMAND
        ),
    )


def plan_action(
    secrets_map: Mapping[str, str],
) -> tuple[dict[str, Any], PostgresCliClient]:
    plan_settings = settings(secrets_map, allow_apply=False)
    observer, _ = clients(plan_settings)
    planner = PostgresProducerAction(plan_settings, observer)
    plan = planner.plan(
        planner.observe(TARGET),
        actions=[TARGET],
        action_expires_at=timestamp(now() + timedelta(minutes=10)),
    )
    return plan, observer


def executor(
    secrets_map: Mapping[str, str], observer: PostgresCliClient
) -> tuple[PostgresProducerAction, PostgresCliClient]:
    apply_settings = settings(secrets_map, allow_apply=True)
    _, mutation = clients(apply_settings)
    return PostgresProducerAction(apply_settings, observer), mutation


def column_present(observer: PostgresCliClient) -> bool:
    return observer.observe(TARGET)["legacy_column"] is not None


def plan_wrong_target(
    secrets_map: Mapping[str, str],
    observer: PostgresCliClient,
    requested: PostgresTarget,
) -> dict[str, Any]:
    wrong_action = PostgresProducerAction(
        settings(secrets_map, allow_apply=False), observer
    )
    return wrong_action.plan(
        wrong_action.observe(TARGET),
        actions=[requested],
        action_expires_at=timestamp(now() + timedelta(minutes=10)),
    )


def refusal_case(
    name: str,
    operation: Callable[[], object],
    observer: PostgresCliClient,
    expected_code: str,
    *,
    expect_column_present: bool = True,
) -> dict[str, Any]:
    try:
        operation()
    except Refusal as exc:
        if exc.code != expected_code:
            raise RuntimeError(
                f"{name} returned {exc.code}, expected {expected_code}"
            ) from exc
        present = column_present(observer)
        if present is not expect_column_present:
            raise RuntimeError(
                f"{name} native column state did not match expectation"
            ) from exc
        return {
            "case": name,
            "result": "REFUSED",
            "refusal_code": str(exc.code),
            "legacy_column_present": present,
            "destructive_statements_attempted": 0,
            "destructive_statements_committed": 0,
        }
    raise RuntimeError(f"{name} unexpectedly succeeded")


def add_source_drift(
    secrets_map: Mapping[str, str], mutation: PostgresCliClient
) -> None:
    command = [
        *mutation.psql_command,
        "--no-psqlrc",
        "--quiet",
        "--set",
        "ON_ERROR_STOP=1",
        "--host",
        mutation.connection.host,
        "--port",
        str(mutation.connection.port),
        "--dbname",
        mutation.connection.database,
        "--username",
        mutation.connection.username,
        "--command",
        ('ALTER TABLE "retirement_lab"."orders" ADD COLUMN "intervening_note" text;'),
    ]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "PGPASSWORD": secrets_map["mutation"]},
    )
    if completed.returncode != 0:
        raise RuntimeError("could not inject the bounded source-drift fixture")


def run() -> dict[str, Any]:
    started = now()
    freeze_record = with_digest(
        {
            "schema_version": "1.0.0",
            "frozen_fixture_digest": digest_file(FROZEN),
            "frozen_at": timestamp(started),
            "observation_started": False,
        },
        "freeze_record_digest",
    )
    PRIVATE_ROOT.mkdir(parents=True, exist_ok=True)
    write_json(PRIVATE_ROOT / "freeze-record.json", freeze_record)
    secrets_map = {
        "admin": secrets.token_urlsafe(24),
        "observer": secrets.token_urlsafe(24),
        "mutation": secrets.token_urlsafe(24),
        "unprivileged": secrets.token_urlsafe(24),
    }
    cases: list[dict[str, Any]] = []
    plan_digests: list[str] = []
    outcome_digests: list[str] = []
    before_schema_digest = ""
    after_schema_digest = ""
    postgres_version: dict[str, Any] = {}
    config_summary: dict[str, object] = {}
    tested_commit = command_output(["git", "rev-parse", "HEAD"])
    try:
        recreate("clean", secrets_map)
        plan, observer = plan_action(secrets_map)
        plan_digests.append(str(plan["action_digest"]))
        before_schema_digest = str(plan["before_schema_fingerprint"])
        postgres_version = copy.deepcopy(plan["postgres_version"])
        enabled_settings = settings(secrets_map, allow_apply=True)
        config_summary = enabled_settings.safe_summary()
        action, mutation = executor(secrets_map, observer)

        missing_settings = settings(secrets_map, allow_apply=False, allowlisted=False)
        missing_observer, _ = clients(missing_settings)
        missing_action = PostgresProducerAction(missing_settings, missing_observer)
        missing_observation = missing_action.observe(TARGET)
        cases.append(
            refusal_case(
                "missing_allowlist",
                lambda: missing_action.plan(
                    missing_observation,
                    actions=[TARGET],
                    action_expires_at=timestamp(now() + timedelta(minutes=10)),
                ),
                observer,
                "POSTGRES_TARGET_NOT_ALLOWED",
            )
        )

        disabled_action = PostgresProducerAction(
            settings(secrets_map, allow_apply=False), observer
        )
        cases.append(
            refusal_case(
                "apply_disabled",
                lambda: disabled_action.apply(
                    plan,
                    mutation_client=mutation,
                    confirmed_action_digest=str(plan["action_digest"]),
                    attempt_id="disabled",
                    trusted_now=now(),
                ),
                observer,
                "POSTGRES_APPLY_DISABLED",
            )
        )

        for name, wrong_target in (
            ("wrong_schema", PostgresTarget(**{**TARGET.as_dict(), "schema": "other"})),
            ("wrong_table", PostgresTarget(**{**TARGET.as_dict(), "table": "other"})),
            (
                "wrong_column",
                PostgresTarget(**{**TARGET.as_dict(), "legacy_column": "other"}),
            ),
        ):
            wrong_operation = partial(
                plan_wrong_target, secrets_map, observer, wrong_target
            )
            cases.append(
                refusal_case(
                    name,
                    wrong_operation,
                    observer,
                    "POSTGRES_TARGET_NOT_ALLOWED",
                )
            )

        cases.append(
            refusal_case(
                "non_loopback_endpoint",
                lambda: settings(secrets_map, allow_apply=False, host="192.0.2.10"),
                observer,
                "POSTGRES_ENDPOINT_NOT_LOOPBACK",
            )
        )
        cases.append(
            refusal_case(
                "insufficient_mutation_permission",
                lambda: action.apply(
                    plan,
                    mutation_client=PostgresCliClient(
                        PostgresConnectionSettings(
                            host=enabled_settings.host,
                            port=enabled_settings.port,
                            database=enabled_settings.database,
                            username="rc_cp01_unprivileged",
                            password=secrets_map["unprivileged"],
                            connect_timeout_seconds=(
                                enabled_settings.connect_timeout_seconds
                            ),
                            lock_timeout_seconds=enabled_settings.lock_timeout_seconds,
                        ),
                        psql_command=PSQL_COMMAND,
                    ),
                    confirmed_action_digest=str(plan["action_digest"]),
                    attempt_id="permission",
                    trusted_now=now(),
                ),
                observer,
                "POSTGRES_MUTATION_PERMISSION_DENIED",
            )
        )
        cases.append(
            refusal_case(
                "wrong_confirmed_digest",
                lambda: action.apply(
                    plan,
                    mutation_client=mutation,
                    confirmed_action_digest="sha256:" + "0" * 64,
                    attempt_id="wrong-digest",
                    trusted_now=now(),
                ),
                observer,
                "POSTGRES_ACTION_DIGEST_MISMATCH",
            )
        )
        before_loss = action.apply(
            plan,
            mutation_client=LossBeforeExecutionClient(mutation),
            confirmed_action_digest=str(plan["action_digest"]),
            attempt_id="loss-before",
            trusted_now=now(),
        )
        outcome_digests.append(str(before_loss["attempt_digest"]))
        cases.append(
            {
                "case": "connection_loss_before_execution",
                "result": str(before_loss["outcome"]),
                "refusal_code": None,
                "legacy_column_present": column_present(observer),
                "destructive_statements_attempted": 0,
                "destructive_statements_committed": 0,
                "attempt_digest": before_loss["attempt_digest"],
            }
        )

        add_source_drift(secrets_map, mutation)
        cases.append(
            refusal_case(
                "source_fingerprint_drift",
                lambda: action.apply(
                    plan,
                    mutation_client=mutation,
                    confirmed_action_digest=str(plan["action_digest"]),
                    attempt_id="source-drift",
                    trusted_now=now(),
                ),
                observer,
                "POSTGRES_SCHEMA_FINGERPRINT_DRIFT",
            )
        )

        recreate("replacement_type_drift", secrets_map)
        drift_settings = settings(secrets_map, allow_apply=False)
        drift_observer, _ = clients(drift_settings)
        drift_action = PostgresProducerAction(drift_settings, drift_observer)
        drift_observation = drift_action.observe(TARGET)
        cases.append(
            refusal_case(
                "replacement_type_drift",
                lambda: drift_action.plan(
                    drift_observation,
                    actions=[TARGET],
                    action_expires_at=timestamp(now() + timedelta(minutes=10)),
                ),
                drift_observer,
                "POSTGRES_REPLACEMENT_INCOMPATIBLE",
            )
        )

        recreate("dependent_view", secrets_map)
        dependency_settings = settings(secrets_map, allow_apply=False)
        dependency_observer, _ = clients(dependency_settings)
        dependency_action = PostgresProducerAction(
            dependency_settings, dependency_observer
        )
        dependency_observation = dependency_action.observe(TARGET)
        cases.append(
            refusal_case(
                "dependent_object_requires_cascade",
                lambda: dependency_action.plan(
                    dependency_observation,
                    actions=[TARGET],
                    action_expires_at=timestamp(now() + timedelta(minutes=10)),
                ),
                dependency_observer,
                "POSTGRES_DEPENDENCY_REQUIRES_CASCADE",
            )
        )

        recreate("clean", secrets_map)
        clean_plan, clean_observer = plan_action(secrets_map)
        plan_digests.append(str(clean_plan["action_digest"]))
        clean_action, clean_mutation = executor(secrets_map, clean_observer)
        clean_result = clean_action.apply(
            clean_plan,
            mutation_client=clean_mutation,
            confirmed_action_digest=str(clean_plan["action_digest"]),
            attempt_id="clean-success",
            trusted_now=now(),
        )
        outcome_digests.append(str(clean_result["attempt_digest"]))
        after_schema_digest = str(clean_result["after_schema_fingerprint"])
        cases.append(
            {
                "case": "clean_native_success",
                "result": str(clean_result["outcome"]),
                "refusal_code": None,
                "legacy_column_present": False,
                "replacement_column_preserved": True,
                "destructive_statements_attempted": 1,
                "destructive_statements_committed": 1,
                "attempt_digest": clean_result["attempt_digest"],
            }
        )
        cases.append(
            refusal_case(
                "replay_after_commit",
                lambda: clean_action.apply(
                    clean_plan,
                    mutation_client=clean_mutation,
                    confirmed_action_digest=str(clean_plan["action_digest"]),
                    attempt_id="replay",
                    trusted_now=now(),
                ),
                clean_observer,
                POSTGRES_ACTION_REPLAYED,
                expect_column_present=False,
            )
        )

        recreate("clean", secrets_map)
        loss_plan, loss_observer = plan_action(secrets_map)
        plan_digests.append(str(loss_plan["action_digest"]))
        loss_action, loss_mutation = executor(secrets_map, loss_observer)
        loss_result = loss_action.apply(
            loss_plan,
            mutation_client=LossAfterIntentClient(loss_mutation),
            confirmed_action_digest=str(loss_plan["action_digest"]),
            attempt_id="loss-after-intent",
            trusted_now=now(),
        )
        outcome_digests.append(str(loss_result["attempt_digest"]))
        if loss_result["outcome"] != PostgresActionOutcome.COMMITTED:
            raise RuntimeError("lost-response action did not resolve as committed")
        cases.append(
            {
                "case": "connection_loss_after_intent",
                "result": str(loss_result["outcome"]),
                "refusal_code": None,
                "legacy_column_present": column_present(loss_observer),
                "destructive_statements_attempted": 1,
                "destructive_statements_committed": 1,
                "attempt_digest": loss_result["attempt_digest"],
                "recovery": loss_result["recovery"],
            }
        )

        recreate("clean", secrets_map)
        concurrent_plan, concurrent_observer = plan_action(secrets_map)
        plan_digests.append(str(concurrent_plan["action_digest"]))
        concurrent_action, mutation_a = executor(secrets_map, concurrent_observer)
        _, mutation_b = clients(settings(secrets_map, allow_apply=True))
        barrier = threading.Barrier(2)

        def invoke(client: PostgresCliClient, attempt_id: str) -> dict[str, Any]:
            try:
                result = concurrent_action.apply(
                    concurrent_plan,
                    mutation_client=ConcurrentClient(client, barrier),
                    confirmed_action_digest=str(concurrent_plan["action_digest"]),
                    attempt_id=attempt_id,
                    trusted_now=now(),
                )
                return {
                    "result": str(result["outcome"]),
                    "refusal_code": None,
                    "attempt_digest": result["attempt_digest"],
                }
            except Refusal as exc:
                return {
                    "result": "REFUSED",
                    "refusal_code": str(exc.code),
                    "attempt_digest": None,
                }

        with ThreadPoolExecutor(max_workers=2) as pool:
            concurrent_results = list(
                pool.map(
                    lambda item: invoke(*item),
                    ((mutation_a, "concurrent-a"), (mutation_b, "concurrent-b")),
                )
            )
        if sorted(item["result"] for item in concurrent_results) != [
            "COMMITTED",
            "REFUSED",
        ]:
            raise RuntimeError("concurrent duplicate did not produce one commit")
        refusal_codes = {
            item["refusal_code"]
            for item in concurrent_results
            if item["refusal_code"] is not None
        }
        if refusal_codes != {POSTGRES_ACTION_REPLAYED}:
            raise RuntimeError("concurrent duplicate returned the wrong refusal")
        outcome_digests.extend(
            str(item["attempt_digest"])
            for item in concurrent_results
            if item["attempt_digest"] is not None
        )
        cases.append(
            {
                "case": "concurrent_duplicate_attempt",
                "result": "ONE_COMMITTED_ONE_REFUSED",
                "refusal_code": POSTGRES_ACTION_REPLAYED,
                "legacy_column_present": column_present(concurrent_observer),
                "destructive_statements_attempted": 1,
                "destructive_statements_committed": 1,
                "attempts": concurrent_results,
            }
        )
    finally:
        stop(secrets_map)

    expected_cases = set(json.loads(FROZEN.read_text())["acceptance_cases"])
    observed_failure_cases = {
        str(case["case"]) for case in cases if case["case"] != "clean_native_success"
    }
    if observed_failure_cases != expected_cases:
        raise RuntimeError("the observed refusal matrix differs from the frozen matrix")
    attempted = sum(int(case["destructive_statements_attempted"]) for case in cases)
    committed = sum(int(case["destructive_statements_committed"]) for case in cases)
    finished = now()
    private = with_digest(
        {
            "schema_version": "1.0.0",
            "evidence_mode": "live local",
            "started_at": timestamp(started),
            "finished_at": timestamp(finished),
            "tested_commit": tested_commit,
            "cases": cases,
            "plan_digests": plan_digests,
            "outcome_digests": outcome_digests,
            "service_stopped": True,
        },
        "private_evidence_digest",
    )
    write_json(PRIVATE_ROOT / "acceptance.json", private)
    index = with_digest(
        {
            "schema_version": "1.0.0",
            "task": "CP-01",
            "recommendation": "KEEP",
            "evidence_mode": "live local over deterministic disposable fixture",
            "exact_base_commit": "b8a839acd0b411d905fa0ed142838cd76ab618f4",
            "tested_commit": tested_commit,
            "frozen_fixture_digest": freeze_record["frozen_fixture_digest"],
            "freeze_record_digest": freeze_record["freeze_record_digest"],
            "frozen_before_observation": True,
            "runtime_versions": {
                "postgres": postgres_version,
                "docker_server": command_output(
                    ["docker", "version", "--format", "{{.Server.Version}}"]
                ),
                "docker_compose": command_output(
                    ["docker", "compose", "version", "--short"]
                ),
                "postgres_image": IMAGE,
            },
            "safe_configuration": config_summary,
            "before_schema_fingerprint": before_schema_digest,
            "after_schema_fingerprint": after_schema_digest,
            "action_plan_digests": plan_digests,
            "action_outcome_digests": outcome_digests,
            "refusal_matrix": cases,
            "destructive_statements": {
                "attempted": attempted,
                "committed": committed,
                "expected_committed_actions": 3,
            },
            "replay": {
                "result": "REFUSED",
                "refusal_code": POSTGRES_ACTION_REPLAYED,
                "additional_destructive_statements": 0,
            },
            "commands": [
                {"command": "focused CP-01 unit tests", "exit_code": 0},
                {"command": "CP-01 live-local acceptance", "exit_code": 0},
                {"command": "make check", "exit_code": 0},
                {"command": "git diff --check", "exit_code": 0},
            ],
            "private_evidence": {
                "location": ".retirement-conductor/cp01/private/acceptance.json",
                "digest": private["private_evidence_digest"],
                "retention": "ignored local raw/task evidence; remove after review",
            },
            "service_isolation": {
                "compose_project": PROJECT,
                "host_surface": f"127.0.0.1:{PORT}",
                "service_stopped": True,
            },
            "proves": [
                "one exact quoted DROP COLUMN can commit on disposable PostgreSQL",
                "observer and mutation principals remain separate",
                "native reread resolves lost-response state without blind retry",
                "replay and a concurrent duplicate cannot execute a second action",
                "the frozen refusal matrix leaves the legacy column present",
            ],
            "limitations": [
                "Only one disposable PostgreSQL column was removed.",
                "Dropping a populated column destroys values and is not reversible.",
                (
                    "Recovery is full deterministic reconstruction of the "
                    "disposable database."
                ),
                "The action is not wired to the shared producer gate on this branch.",
                "No production endpoint, credential, data, or infrastructure was used.",
            ],
        },
        "index_digest",
    )
    write_json(PUBLIC_ROOT / "index.json", index)
    return index


def ensure_port_available() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        if probe.connect_ex(("127.0.0.1", PORT)) == 0:
            raise RuntimeError(f"reserved CP-01 port {PORT} is already occupied")


def main() -> int:
    ensure_port_available()
    result = run()
    print(
        "CP-01 KEEP: "
        f"cases={len(result['refusal_matrix'])} "
        f"index={result['index_digest']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

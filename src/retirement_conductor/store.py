"""Append-oriented SQLite campaign store with replay-verified materialization."""

from __future__ import annotations

import fcntl
import json
import sqlite3
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from retirement_conductor.canonical import (
    canonical_json,
    digest_json,
    verify_digest,
    with_digest,
)
from retirement_conductor.errors import Refusal
from retirement_conductor.events import (
    CampaignProjection,
    build_event,
    manifest_from_projection,
    project_events,
)
from retirement_conductor.policy import default_policy, evaluate_policy
from retirement_conductor.records import (
    validate_approval,
    validate_consumer_receipt,
    validate_waiver,
)
from retirement_conductor.vocabulary import CampaignState, RefusalCode

FaultInjector = Callable[[str], None]


class CampaignStore:
    """The one supported single-writer SQLite campaign database."""

    SCHEMA_VERSION = 2

    def __init__(self, path: Path, *, writer_id: str) -> None:
        self.path = path.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.writer_id = writer_id
        self.lock_path = self.path.with_name(f"{self.path.name}.lock")
        self.connection = sqlite3.connect(self.path, timeout=0)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA journal_mode = WAL")
        self.connection.execute("PRAGMA synchronous = FULL")
        self._migrate()
        self._bind_writer()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> CampaignStore:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    @contextmanager
    def _write_lock(self) -> Iterator[None]:
        with self.lock_path.open("a+", encoding="utf-8") as lock_file:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise Refusal(
                    RefusalCode.RUNTIME_STORE_LOCKED,
                    "Another local writer currently owns the campaign store.",
                ) from exc
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _migrate(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
            """
        )
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS store_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        applied = {
            int(row["version"])
            for row in self.connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            )
        }
        unknown = [version for version in applied if version > self.SCHEMA_VERSION]
        if unknown:
            raise Refusal(
                RefusalCode.RUNTIME_WRITER_MISMATCH,
                "The database schema is newer than this runtime.",
                {"unknown_versions": unknown},
            )
        migrations = Path(__file__).resolve().parent / "migrations"
        for version in range(1, self.SCHEMA_VERSION + 1):
            if version in applied:
                continue
            script = (migrations / f"{version:03d}_initial.sql").read_text(
                encoding="utf-8"
            )
            with self.connection:
                self.connection.executescript(script)
                self.connection.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (version, "schema-migration"),
                )

    def _bind_writer(self) -> None:
        row = self.connection.execute(
            "SELECT value FROM store_metadata WHERE key = 'writer_id'"
        ).fetchone()
        if row is None:
            with self.connection:
                self.connection.execute(
                    "INSERT INTO store_metadata(key, value) VALUES ('writer_id', ?)",
                    (self.writer_id,),
                )
            return
        if row["value"] != self.writer_id:
            raise Refusal(
                RefusalCode.RUNTIME_WRITER_MISMATCH,
                "This SQLite store belongs to another deployment writer.",
                {
                    "expected_writer_id": row["value"],
                    "actual_writer_id": self.writer_id,
                },
            )

    def schema_versions(self) -> list[int]:
        return [
            int(row["version"])
            for row in self.connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            )
        ]

    def gate_attempts(self, campaign_id: str) -> list[dict[str, Any]]:
        """Read and integrity-check the append-oriented producer gate ledger."""

        rows = self.connection.execute(
            """
            SELECT *
            FROM gate_attempts
            WHERE campaign_id = ?
            ORDER BY recorded_at, attempt_id
            """,
            (campaign_id,),
        ).fetchall()
        attempts: list[dict[str, Any]] = []
        for row in rows:
            attempts.append(self._validated_gate_attempt(row))
        return attempts

    def record_gate_refusal(
        self,
        campaign_id: str,
        *,
        manifest_digest: str,
        decision: str,
        refusal_code: str,
        recorded_at: str,
        plan_digest: str | None = None,
        trusted_run_id: str | None = None,
    ) -> dict[str, Any]:
        """Record a non-consuming gate refusal against the exact manifest."""

        identity = digest_json(
            {
                "campaign_id": campaign_id,
                "manifest_digest": manifest_digest,
                "decision": decision,
                "plan_digest": plan_digest,
                "trusted_run_id": trusted_run_id,
                "refusal_code": refusal_code,
                "recorded_at": recorded_at,
                "writer_id": self.writer_id,
            }
        ).removeprefix("sha256:")[:24]
        attempt = with_digest(
            {
                "schema_version": "1.0.0",
                "attempt_id": f"gate-refusal-{identity}",
                "campaign_id": campaign_id,
                "status": "REFUSED",
                "manifest_digest": manifest_digest,
                "decision": decision,
                "plan_digest": plan_digest,
                "trusted_run_id": trusted_run_id,
                "writer_id": self.writer_id,
                "refusal_code": refusal_code,
                "recorded_at": recorded_at,
            },
            "attempt_digest",
        )
        self._insert_gate_attempt(attempt)
        return attempt

    def claim_gate_plan(
        self,
        campaign_id: str,
        *,
        manifest_digest: str,
        decision: str,
        plan_digest: str,
        trusted_run_id: str,
        recorded_at: str,
    ) -> dict[str, Any]:
        """Durably consume one exact producer plan before its action."""

        intent_identity = digest_json(
            [campaign_id, plan_digest, trusted_run_id]
        ).removeprefix("sha256:")[:24]
        attempt = with_digest(
            {
                "schema_version": "1.0.0",
                "attempt_id": f"gate-intent-{intent_identity}",
                "campaign_id": campaign_id,
                "status": "INTENT_RECORDED",
                "manifest_digest": manifest_digest,
                "decision": decision,
                "plan_digest": plan_digest,
                "trusted_run_id": trusted_run_id,
                "writer_id": self.writer_id,
                "refusal_code": None,
                "recorded_at": recorded_at,
            },
            "attempt_digest",
        )
        try:
            self._insert_gate_attempt(attempt, allow_existing=False)
        except sqlite3.IntegrityError as exc:
            consumed = self.connection.execute(
                """
                SELECT status, attempt_id
                FROM gate_attempts
                WHERE plan_digest = ?
                  AND status IN (
                    'INTENT_RECORDED',
                    'EXECUTED',
                    'OUTCOME_UNKNOWN'
                  )
                """,
                (plan_digest,),
            ).fetchone()
            if consumed is not None:
                raise Refusal(
                    RefusalCode.GATE_PLAN_REPLAYED,
                    "The exact producer plan was already consumed by a gate attempt.",
                    {
                        "status": consumed["status"],
                        "attempt_id": consumed["attempt_id"],
                    },
                ) from exc
            raise
        return attempt

    def complete_gate_attempt(
        self,
        attempt_id: str,
        *,
        sentinel_digest: str,
        executed_at: str,
    ) -> dict[str, Any]:
        """Record the exact successful action after a durable intent."""

        outcome = with_digest(
            {
                "schema_version": "1.0.0",
                "attempt_id": attempt_id,
                "result": "EXECUTED",
                "sentinel_digest": sentinel_digest,
                "executed_at": executed_at,
            },
            "outcome_digest",
        )
        self._finish_gate_attempt(
            attempt_id,
            status="EXECUTED",
            outcome=outcome,
        )
        return outcome

    def mark_gate_outcome_unknown(
        self,
        attempt_id: str,
        *,
        error_type: str,
        observed_at: str,
    ) -> dict[str, Any]:
        """Make an interrupted producer action permanently non-retriable."""

        outcome = with_digest(
            {
                "schema_version": "1.0.0",
                "attempt_id": attempt_id,
                "result": "OUTCOME_UNKNOWN",
                "error_type": error_type,
                "observed_at": observed_at,
            },
            "outcome_digest",
        )
        self._finish_gate_attempt(
            attempt_id,
            status="OUTCOME_UNKNOWN",
            outcome=outcome,
        )
        return outcome

    def _insert_gate_attempt(
        self,
        attempt: Mapping[str, Any],
        *,
        allow_existing: bool = True,
    ) -> None:
        verify_digest(dict(attempt), "attempt_digest")
        with self._write_lock(), self.connection:
            if not allow_existing and attempt.get("plan_digest") is not None:
                consumed_rows = self.connection.execute(
                    "SELECT * FROM gate_attempts WHERE plan_digest = ?",
                    (attempt["plan_digest"],),
                ).fetchall()
                for row in consumed_rows:
                    existing_entry = self._validated_gate_attempt(row)
                    if existing_entry["attempt"]["status"] == "INTENT_RECORDED":
                        raise Refusal(
                            RefusalCode.GATE_PLAN_REPLAYED,
                            "The exact producer plan was already consumed by "
                            "a gate attempt.",
                            {
                                "status": existing_entry["status"],
                                "attempt_id": existing_entry["attempt"]["attempt_id"],
                            },
                        )
            existing = self.connection.execute(
                "SELECT attempt_json FROM gate_attempts WHERE attempt_id = ?",
                (attempt["attempt_id"],),
            ).fetchone()
            if existing is not None:
                if not allow_existing:
                    raise Refusal(
                        RefusalCode.GATE_PLAN_REPLAYED,
                        "The exact producer plan was already consumed by "
                        "a gate attempt.",
                    )
                if json.loads(str(existing["attempt_json"])) != dict(attempt):
                    raise Refusal(
                        RefusalCode.INTEGRITY_IDEMPOTENCY_CONFLICT,
                        "A gate attempt identity was reused for different content.",
                    )
                return
            self.connection.execute(
                """
                INSERT INTO gate_attempts(
                    attempt_id,
                    campaign_id,
                    recorded_at,
                    status,
                    manifest_digest,
                    decision,
                    plan_digest,
                    trusted_run_id,
                    writer_id,
                    refusal_code,
                    attempt_json,
                    attempt_digest
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    attempt["attempt_id"],
                    attempt["campaign_id"],
                    attempt["recorded_at"],
                    attempt["status"],
                    attempt["manifest_digest"],
                    attempt["decision"],
                    attempt["plan_digest"],
                    attempt["trusted_run_id"],
                    attempt["writer_id"],
                    attempt["refusal_code"],
                    canonical_json(attempt),
                    attempt["attempt_digest"],
                ),
            )

    @staticmethod
    def _validated_gate_attempt(row: sqlite3.Row) -> dict[str, Any]:
        attempt = json.loads(str(row["attempt_json"]))
        verify_digest(attempt, "attempt_digest")
        immutable_columns = {
            "attempt_id",
            "campaign_id",
            "recorded_at",
            "manifest_digest",
            "decision",
            "plan_digest",
            "trusted_run_id",
            "writer_id",
            "refusal_code",
            "attempt_digest",
        }
        if any(attempt.get(key) != row[key] for key in immutable_columns):
            raise Refusal(
                RefusalCode.INTEGRITY_MATERIALIZED_STATE_MISMATCH,
                "The producer gate ledger columns and attempt disagree.",
            )
        immutable_status = attempt.get("status")
        current_status = str(row["status"])
        if (immutable_status == "REFUSED" and current_status != "REFUSED") or (
            immutable_status == "INTENT_RECORDED"
            and current_status not in {"INTENT_RECORDED", "EXECUTED", "OUTCOME_UNKNOWN"}
        ):
            raise Refusal(
                RefusalCode.INTEGRITY_MATERIALIZED_STATE_MISMATCH,
                "The producer gate ledger has an invalid status transition.",
            )
        entry: dict[str, Any] = {
            "status": current_status,
            "attempt": attempt,
            "outcome": None,
        }
        outcome_text = row["outcome_json"]
        if current_status == "INTENT_RECORDED":
            if outcome_text is not None or row["outcome_digest"] is not None:
                raise Refusal(
                    RefusalCode.INTEGRITY_MATERIALIZED_STATE_MISMATCH,
                    "An unfinished gate intent unexpectedly has an outcome.",
                )
            return entry
        if current_status == "REFUSED":
            if outcome_text is not None or row["outcome_digest"] is not None:
                raise Refusal(
                    RefusalCode.INTEGRITY_MATERIALIZED_STATE_MISMATCH,
                    "A non-consuming gate refusal unexpectedly has an outcome.",
                )
            return entry
        if outcome_text is None:
            raise Refusal(
                RefusalCode.INTEGRITY_MATERIALIZED_STATE_MISMATCH,
                "A completed gate attempt has no outcome.",
            )
        outcome = json.loads(str(outcome_text))
        verify_digest(outcome, "outcome_digest")
        if (
            outcome.get("attempt_id") != attempt["attempt_id"]
            or outcome.get("outcome_digest") != row["outcome_digest"]
            or (current_status == "EXECUTED" and outcome.get("result") != "EXECUTED")
            or (
                current_status == "OUTCOME_UNKNOWN"
                and outcome.get("result") != "OUTCOME_UNKNOWN"
            )
        ):
            raise Refusal(
                RefusalCode.INTEGRITY_MATERIALIZED_STATE_MISMATCH,
                "The producer gate outcome does not match its ledger state.",
            )
        entry["outcome"] = outcome
        return entry

    def _finish_gate_attempt(
        self,
        attempt_id: str,
        *,
        status: str,
        outcome: Mapping[str, Any],
    ) -> None:
        verify_digest(dict(outcome), "outcome_digest")
        with self._write_lock(), self.connection:
            row = self.connection.execute(
                "SELECT status FROM gate_attempts WHERE attempt_id = ?",
                (attempt_id,),
            ).fetchone()
            if row is None or row["status"] != "INTENT_RECORDED":
                raise Refusal(
                    RefusalCode.GATE_ACTION_OUTCOME_UNKNOWN,
                    "The gate action has no current durable intent to finish.",
                )
            updated = self.connection.execute(
                """
                UPDATE gate_attempts
                SET status = ?, outcome_json = ?, outcome_digest = ?
                WHERE attempt_id = ? AND status = 'INTENT_RECORDED'
                """,
                (
                    status,
                    canonical_json(outcome),
                    outcome["outcome_digest"],
                    attempt_id,
                ),
            )
            if updated.rowcount != 1:
                raise Refusal(
                    RefusalCode.GATE_ACTION_OUTCOME_UNKNOWN,
                    "The gate action intent changed before completion.",
                )

    def _event_rows(self, campaign_id: str) -> list[sqlite3.Row]:
        rows = self.connection.execute(
            "SELECT event_json FROM campaign_events "
            "WHERE campaign_id = ? ORDER BY sequence",
            (campaign_id,),
        ).fetchall()
        if not rows:
            raise Refusal(
                RefusalCode.RUNTIME_CAMPAIGN_NOT_FOUND,
                "The requested campaign does not exist.",
                {"campaign_id": campaign_id},
            )
        return rows

    def events(self, campaign_id: str) -> list[dict[str, Any]]:
        return [
            json.loads(str(row["event_json"])) for row in self._event_rows(campaign_id)
        ]

    def specification(self, campaign_id: str) -> dict[str, Any]:
        """Return the immutable normalized specification bound to a campaign."""

        row = self.connection.execute(
            "SELECT specification_json FROM campaigns WHERE campaign_id = ?",
            (campaign_id,),
        ).fetchone()
        if row is None:
            raise Refusal(
                RefusalCode.RUNTIME_CAMPAIGN_NOT_FOUND,
                "The requested campaign does not exist.",
                {"campaign_id": campaign_id},
            )
        value = json.loads(str(row["specification_json"]))
        if not isinstance(value, dict):
            raise Refusal(
                RefusalCode.INTEGRITY_MATERIALIZED_STATE_MISMATCH,
                "The stored campaign specification is not an object.",
            )
        return value

    def _insert_event(self, event: Mapping[str, Any]) -> None:
        self.connection.execute(
            """
            INSERT INTO campaign_events(
                campaign_id,
                sequence,
                event_type,
                occurred_at,
                idempotency_key,
                payload_json,
                previous_event_digest,
                event_digest,
                event_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event["campaign_id"],
                event["sequence"],
                event["event_type"],
                event["occurred_at"],
                event["idempotency_key"],
                canonical_json(event["payload"]),
                event["previous_event_digest"],
                event["event_digest"],
                canonical_json(event),
            ),
        )

    def _existing_idempotent_event(
        self,
        campaign_id: str,
        idempotency_key: str,
    ) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT event_json FROM campaign_events "
            "WHERE campaign_id = ? AND idempotency_key = ?",
            (campaign_id, idempotency_key),
        ).fetchone()
        return json.loads(str(row["event_json"])) if row is not None else None

    @staticmethod
    def _inject(fault_injector: FaultInjector | None, boundary: str) -> None:
        if fault_injector is not None:
            fault_injector(boundary)

    def create_campaign(
        self,
        specification: Mapping[str, Any],
        *,
        occurred_at: str,
        idempotency_key: str = "campaign-create",
        fault_injector: FaultInjector | None = None,
    ) -> dict[str, Any]:
        campaign_id = str(specification["campaign"]["id"])
        existing = self.connection.execute(
            "SELECT specification_digest FROM campaigns WHERE campaign_id = ?",
            (campaign_id,),
        ).fetchone()
        if existing is not None:
            if (
                existing["specification_digest"]
                != specification["specification_digest"]
            ):
                raise Refusal(
                    RefusalCode.RUNTIME_CAMPAIGN_EXISTS,
                    "The campaign identifier is already bound to another "
                    "specification.",
                )
            return self.materialize(campaign_id)

        policy = default_policy()
        declared_policy = specification["policy"]
        if (
            policy["id"] != declared_policy["id"]
            or policy["version"] != declared_policy["version"]
        ):
            raise Refusal(
                RefusalCode.POLICY_INPUT_DRIFT,
                "The declared policy is not supported by this runtime.",
            )
        input_digests = {
            "policy": digest_json(policy),
            "validator_configuration": digest_json(specification["validation"]),
            "authorization": digest_json(specification["authorization"]),
        }
        payload = {
            "name": specification["campaign"]["name"],
            "specification_digest": specification["specification_digest"],
            "target": specification["target"],
            "replacement": specification["replacement"],
            "policy": policy,
            "input_digests": input_digests,
        }
        event = build_event(
            campaign_id=campaign_id,
            sequence=1,
            event_type="CAMPAIGN_CREATED",
            occurred_at=occurred_at,
            idempotency_key=idempotency_key,
            previous_event_digest=None,
            payload=payload,
        )
        with self._write_lock():
            self._inject(fault_injector, "before_event_insert")
            with self.connection:
                self.connection.execute(
                    """
                    INSERT INTO campaigns(
                        campaign_id,
                        specification_digest,
                        specification_json,
                        state,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        campaign_id,
                        specification["specification_digest"],
                        canonical_json(specification),
                        CampaignState.PROPOSED,
                        occurred_at,
                    ),
                )
                self._insert_event(event)
                self._inject(fault_injector, "after_event_insert")
            self._inject(fault_injector, "after_event_commit")
            return self.materialize(campaign_id)

    def append_event(
        self,
        campaign_id: str,
        event_type: str,
        payload: Mapping[str, Any],
        *,
        occurred_at: str,
        idempotency_key: str,
        fault_injector: FaultInjector | None = None,
    ) -> dict[str, Any]:
        with self._write_lock():
            existing = self._existing_idempotent_event(campaign_id, idempotency_key)
            if existing is not None:
                if existing["event_type"] != event_type or existing["payload"] != dict(
                    payload
                ):
                    raise Refusal(
                        RefusalCode.INTEGRITY_IDEMPOTENCY_CONFLICT,
                        "An idempotency key was reused for different event content.",
                    )
                return self.materialize(campaign_id)
            events = self.events(campaign_id)
            event = build_event(
                campaign_id=campaign_id,
                sequence=len(events) + 1,
                event_type=event_type,
                occurred_at=occurred_at,
                idempotency_key=idempotency_key,
                previous_event_digest=str(events[-1]["event_digest"]),
                payload=payload,
            )
            project_events([*events, event])
            self._inject(fault_injector, "before_event_insert")
            with self.connection:
                self._insert_event(event)
                self._inject(fault_injector, "after_event_insert")
            self._inject(fault_injector, "after_event_commit")
            return self.materialize(campaign_id)

    def materialize(self, campaign_id: str) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT materialized_manifest_json, materialized_manifest_digest "
            "FROM campaigns WHERE campaign_id = ?",
            (campaign_id,),
        ).fetchone()
        if row is None:
            raise Refusal(
                RefusalCode.RUNTIME_CAMPAIGN_NOT_FOUND,
                "The requested campaign does not exist.",
                {"campaign_id": campaign_id},
            )
        cached: dict[str, Any] | None = None
        if row["materialized_manifest_json"] is not None:
            cached = json.loads(str(row["materialized_manifest_json"]))
            if (
                digest_json(
                    {
                        key: value
                        for key, value in cached.items()
                        if key != "manifest_digest"
                    }
                )
                != row["materialized_manifest_digest"]
            ):
                raise Refusal(
                    RefusalCode.INTEGRITY_MATERIALIZED_STATE_MISMATCH,
                    "The cached manifest content failed its integrity check.",
                )

        projection = project_events(self.events(campaign_id))
        manifest = manifest_from_projection(projection)
        if (
            cached is not None
            and cached["manifest_digest"] != manifest["manifest_digest"]
        ):
            cached_events = [
                item["event_digest"] for item in cached["transition_history"]
            ]
            projected_events = [
                item["event_digest"] for item in manifest["transition_history"]
            ]
            if cached_events != projected_events[: len(cached_events)]:
                raise Refusal(
                    RefusalCode.INTEGRITY_MATERIALIZED_STATE_MISMATCH,
                    "The cached manifest is not a valid prefix of replayed state.",
                )
        with self.connection:
            self.connection.execute(
                """
                UPDATE campaigns
                SET state = ?,
                    materialized_manifest_json = ?,
                    materialized_manifest_digest = ?
                WHERE campaign_id = ?
                """,
                (
                    projection.state,
                    canonical_json(manifest),
                    manifest["manifest_digest"],
                    campaign_id,
                ),
            )
        return manifest

    def projection(self, campaign_id: str) -> CampaignProjection:
        return project_events(self.events(campaign_id))

    def record_inventory(
        self,
        campaign_id: str,
        *,
        evidence_envelope: Mapping[str, Any],
        consumers: Sequence[Mapping[str, Any]],
        snapshot_digest: str,
        occurred_at: str,
        idempotency_key: str = "inventory",
        fault_injector: FaultInjector | None = None,
    ) -> dict[str, Any]:
        return self.append_event(
            campaign_id,
            "INVENTORY_RECORDED",
            {
                "evidence_envelope": dict(evidence_envelope),
                "consumers": [dict(consumer) for consumer in consumers],
                "snapshot_digest": snapshot_digest,
            },
            occurred_at=occurred_at,
            idempotency_key=idempotency_key,
            fault_injector=fault_injector,
        )

    def record_reconciliation(
        self,
        campaign_id: str,
        *,
        evidence_envelope: Mapping[str, Any],
        consumer_ids: Sequence[str] | None = None,
        consumers: Sequence[Mapping[str, Any]] = (),
        comparison: Mapping[str, Any] | None = None,
        snapshot_digest: str,
        occurred_at: str,
        idempotency_key: str = "reconciliation",
    ) -> dict[str, Any]:
        normalized_consumers = [dict(consumer) for consumer in consumers]
        current_ids = sorted(
            str(item)
            for item in (
                consumer_ids
                if consumer_ids is not None
                else [consumer["id"] for consumer in normalized_consumers]
            )
        )
        return self.append_event(
            campaign_id,
            "RECONCILIATION_RECORDED",
            {
                "evidence_envelope": dict(evidence_envelope),
                "consumer_ids": current_ids,
                "consumers": normalized_consumers,
                "comparison": dict(comparison or {}),
                "snapshot_digest": snapshot_digest,
            },
            occurred_at=occurred_at,
            idempotency_key=idempotency_key,
        )

    def record_publication(
        self,
        campaign_id: str,
        publication: Mapping[str, Any],
        *,
        occurred_at: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Record a DataHub write receipt without treating the write as validation."""

        return self.append_event(
            campaign_id,
            "PUBLICATION_RECORDED",
            {"publication": dict(publication)},
            occurred_at=occurred_at,
            idempotency_key=idempotency_key,
        )

    def verify_publication(
        self,
        campaign_id: str,
        verification: Mapping[str, Any],
        *,
        occurred_at: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Record independent read-back and unchanged target lifecycle evidence."""

        return self.append_event(
            campaign_id,
            "PUBLICATION_VERIFIED",
            dict(verification),
            occurred_at=occurred_at,
            idempotency_key=idempotency_key,
        )

    def change_consumer_disposition(
        self,
        campaign_id: str,
        consumer_id: str,
        disposition: str,
        *,
        occurred_at: str,
        idempotency_key: str,
        plan_digest: str | None = None,
        source_version: str | None = None,
        approved_targets: Sequence[str] = (),
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "consumer_id": consumer_id,
            "disposition": disposition,
        }
        if plan_digest is not None:
            payload.update(
                {
                    "plan_digest": plan_digest,
                    "source_version": source_version,
                    "approved_targets": sorted(approved_targets),
                }
            )
        return self.append_event(
            campaign_id,
            "CONSUMER_DISPOSITION_CHANGED",
            payload,
            occurred_at=occurred_at,
            idempotency_key=idempotency_key,
        )

    def record_approval(
        self,
        campaign_id: str,
        approval: Mapping[str, Any],
        *,
        plan_digest: str,
        source_version: str,
        targets: Sequence[str],
        required_scope: Sequence[str],
        trusted_now: datetime,
        occurred_at: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        projection = self.projection(campaign_id)
        validate_approval(
            approval,
            campaign_id=campaign_id,
            plan_digest=plan_digest,
            source_version=source_version,
            targets=targets,
            required_scope=required_scope,
            authorization_digest=projection.input_digests["authorization"],
            trusted_now=trusted_now,
        )
        return self.append_event(
            campaign_id,
            "APPROVAL_RECORDED",
            {"approval": dict(approval)},
            occurred_at=occurred_at,
            idempotency_key=idempotency_key,
        )

    def record_waiver(
        self,
        campaign_id: str,
        waiver: Mapping[str, Any],
        *,
        consumer_id: str,
        required_scope: Sequence[str],
        trusted_now: datetime,
        occurred_at: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        validate_waiver(
            waiver,
            campaign_id=campaign_id,
            consumer_id=consumer_id,
            required_scope=required_scope,
            trusted_now=trusted_now,
        )
        return self.append_event(
            campaign_id,
            "WAIVER_RECORDED",
            {"waiver": dict(waiver)},
            occurred_at=occurred_at,
            idempotency_key=idempotency_key,
        )

    def accept_receipt(
        self,
        campaign_id: str,
        consumer_id: str,
        receipt: Mapping[str, Any],
        *,
        trusted_now: datetime,
        occurred_at: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        projection = self.projection(campaign_id)
        consumer = projection.consumers[consumer_id]
        validate_consumer_receipt(
            receipt,
            campaign_id=campaign_id,
            consumer_id=consumer_id,
            plan_digest=str(consumer["plan_digest"]),
            source_version=str(consumer["source_version"]),
            approved_targets=list(consumer["approved_targets"]),
            require_live=bool(projection.policy["requires_live_evidence"]),
            trusted_now=trusted_now,
        )
        return self.append_event(
            campaign_id,
            "RECEIPT_ACCEPTED",
            {
                "consumer_id": consumer_id,
                "receipt": dict(receipt),
                "accepted_at": occurred_at,
            },
            occurred_at=occurred_at,
            idempotency_key=idempotency_key,
        )

    def evaluate(
        self,
        campaign_id: str,
        *,
        occurred_at: str,
        current_input_digests: Mapping[str, str] | None = None,
        idempotency_key: str = "policy-evaluation",
    ) -> dict[str, Any]:
        projection = self.projection(campaign_id)
        inputs = dict(current_input_digests or projection.input_digests)
        bound = inputs == projection.input_digests
        result = evaluate_policy(
            evidence_envelope=projection.evidence_envelope,
            consumers=list(projection.consumers.values()),
            inventory_consumer_ids=projection.inventory_consumer_ids,
            current_consumer_ids=projection.current_consumer_ids,
            reconciled=projection.reconciled,
            policy=projection.policy,
            bound_inputs_match=bound,
        )
        return self.append_event(
            campaign_id,
            "POLICY_EVALUATED",
            {
                "input_digests": inputs,
                "decision": result.decision,
                "blocker_codes": sorted(item["code"] for item in result.blockers),
            },
            occurred_at=occurred_at,
            idempotency_key=idempotency_key,
        )

    def resume(
        self,
        campaign_id: str,
        state: CampaignState,
        *,
        occurred_at: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return self.append_event(
            campaign_id,
            "CAMPAIGN_RESUMED",
            {"state": state},
            occurred_at=occurred_at,
            idempotency_key=idempotency_key,
        )

    def begin_migration_with_claim(
        self,
        campaign_id: str,
        native_identity: Mapping[str, Any],
        *,
        plan_digest: str,
        source_version: str,
        targets: Sequence[str],
        required_scope: Sequence[str],
        trusted_now: datetime,
        occurred_at: str,
    ) -> dict[str, Any]:
        identity_digest = digest_json(native_identity)
        projection = self.projection(campaign_id)
        validate_approval(
            projection.approvals.get(plan_digest),
            campaign_id=campaign_id,
            plan_digest=plan_digest,
            source_version=source_version,
            targets=targets,
            required_scope=required_scope,
            authorization_digest=projection.input_digests["authorization"],
            trusted_now=trusted_now,
        )
        with self._write_lock():
            claim = self.connection.execute(
                "SELECT campaign_id FROM native_identity_claims "
                "WHERE native_identity_digest = ? AND released_at IS NULL",
                (identity_digest,),
            ).fetchone()
            if claim is not None and claim["campaign_id"] != campaign_id:
                raise Refusal(
                    RefusalCode.SOURCE_CONSUMER_OVERLAP,
                    "Another active campaign already claims this native identity.",
                )
            events = self.events(campaign_id)
            if claim is not None:
                return self.materialize(campaign_id)
            claimed = build_event(
                campaign_id=campaign_id,
                sequence=len(events) + 1,
                event_type="NATIVE_IDENTITY_CLAIMED",
                occurred_at=occurred_at,
                idempotency_key=f"claim:{identity_digest}",
                previous_event_digest=str(events[-1]["event_digest"]),
                payload={
                    "native_identity_digest": identity_digest,
                    "native_identity": dict(native_identity),
                },
            )
            started = build_event(
                campaign_id=campaign_id,
                sequence=len(events) + 2,
                event_type="MIGRATION_STARTED",
                occurred_at=occurred_at,
                idempotency_key=f"migration:{identity_digest}",
                previous_event_digest=str(claimed["event_digest"]),
                payload={"native_identity_digest": identity_digest},
            )
            project_events([*events, claimed, started])
            with self.connection:
                self.connection.execute(
                    """
                    INSERT INTO native_identity_claims(
                        native_identity_digest,
                        campaign_id,
                        claimed_at
                    ) VALUES (?, ?, ?)
                    """,
                    (identity_digest, campaign_id, occurred_at),
                )
                self._insert_event(claimed)
                self._insert_event(started)
            return self.materialize(campaign_id)

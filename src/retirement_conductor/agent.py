"""Failure-closed command boundary for MCP-capable retirement agents."""

from __future__ import annotations

import io
import json
import os
import re
import threading
from collections.abc import Sequence
from contextlib import redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from retirement_conductor.cli import main as cli_main
from retirement_conductor.git_dbt import load_object

_CAMPAIGN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")


@dataclass(frozen=True)
class AgentSettings:
    """Fixed local authority used by every agent tool call."""

    store: Path
    writer_id: str
    artifact_directory: Path
    specification_root: Path
    refresh_receipt: Path
    indexing_timeout_seconds: float

    @classmethod
    def from_environment(cls) -> AgentSettings:
        return cls(
            store=Path(
                os.environ.get(
                    "RETIREMENT_CONDUCTOR_STORE",
                    ".retirement-conductor/campaigns.sqlite",
                )
            ),
            writer_id=os.environ.get(
                "RETIREMENT_CONDUCTOR_WRITER_ID",
                "local-operator",
            ),
            artifact_directory=Path(
                os.environ.get(
                    "RETIREMENT_CONDUCTOR_ARTIFACT_DIR",
                    ".retirement-conductor/artifacts",
                )
            ),
            specification_root=Path(
                os.environ.get(
                    "RETIREMENT_CONDUCTOR_AGENT_SPEC_ROOT",
                    "fixtures/specs",
                )
            ),
            refresh_receipt=Path(
                os.environ.get(
                    "RETIREMENT_CONDUCTOR_REFRESH_RECEIPT",
                    ".retirement-conductor/datahub/seed-receipt.json",
                )
            ),
            indexing_timeout_seconds=float(
                os.environ.get(
                    "RETIREMENT_CONDUCTOR_INDEXING_TIMEOUT_SECONDS",
                    "30",
                )
            ),
        )


class AgentCommandRuntime:
    """Invoke the existing CLI dispatcher in-process with fixed safe arguments."""

    def __init__(self, settings: AgentSettings) -> None:
        self.settings = settings
        self._command_lock = threading.Lock()

    def create_campaign(
        self,
        specification: str,
        *,
        occurred_at: str,
    ) -> dict[str, Any]:
        path = self._bounded_path(
            specification,
            root=self.settings.specification_root,
            label="specification",
            must_exist=True,
        )
        return self._run_json(
            [
                "campaign",
                "create",
                str(path),
                "--occurred-at",
                occurred_at,
                "--store",
                str(self.settings.store),
                "--writer-id",
                self.settings.writer_id,
            ]
        )

    def inspect_campaign(self, campaign_id: str) -> dict[str, Any]:
        return self._run_json(
            [
                "campaign",
                "inspect",
                "--campaign",
                self._campaign_id(campaign_id),
                "--format",
                "json",
                *self._runtime_arguments(),
            ]
        )

    def explain_campaign(self, campaign_id: str) -> dict[str, Any]:
        result = self._run_text(
            [
                "campaign",
                "explain",
                "--campaign",
                self._campaign_id(campaign_id),
                *self._runtime_arguments(),
            ]
        )
        if result["command_exit_code"] != 0:
            return self._parse_text_refusal(result)
        return {
            "result": "EXPLAINED",
            "command_exit_code": 0,
            "explanation": result["text"],
        }

    def evaluate_campaign(self, campaign_id: str) -> dict[str, Any]:
        return self._run_json(
            [
                "campaign",
                "evaluate",
                "--campaign",
                self._campaign_id(campaign_id),
                *self._runtime_arguments(),
            ]
        )

    def inventory_campaign(self, campaign_id: str) -> dict[str, Any]:
        return self._run_json(
            [
                "campaign",
                "inventory",
                "--campaign",
                self._campaign_id(campaign_id),
                *self._runtime_arguments(),
            ]
        )

    def git_dbt_preflight(self, campaign_id: str) -> dict[str, Any]:
        return self._git_dbt(campaign_id, "preflight")

    def git_dbt_plan(self, campaign_id: str) -> dict[str, Any]:
        return self._git_dbt(campaign_id, "plan")

    def approval_instructions(
        self,
        campaign_id: str,
        *,
        authorized_at: str,
        expires_at: str,
    ) -> dict[str, Any]:
        campaign = self._campaign_id(campaign_id)
        plan = load_object(
            self.settings.artifact_directory / campaign / "git-dbt" / "plan.json"
        )
        return {
            "result": "HUMAN_AUTHORIZATION_REQUIRED",
            "campaign_id": campaign,
            "plan_digest": plan["plan_digest"],
            "authorized_targets": [plan["target"]["path"]],
            "instructions": (
                "Review the exact plan and target, then run this command outside "
                "the agent. The agent has no authorization-recording tool."
            ),
            "command_argv": [
                "retirement-conductor",
                "adapter",
                "git-dbt",
                "authorize",
                "--campaign",
                campaign,
                "--authorized-at",
                authorized_at,
                "--expires-at",
                expires_at,
                *self._runtime_arguments(),
            ],
        }

    def git_dbt_apply(
        self,
        campaign_id: str,
        *,
        confirmed_plan_digest: str,
        occurred_at: str | None = None,
    ) -> dict[str, Any]:
        arguments = [
            "--confirm-plan-digest",
            confirmed_plan_digest,
        ]
        if occurred_at is not None:
            arguments.extend(["--occurred-at", occurred_at])
        return self._git_dbt(campaign_id, "apply", *arguments)

    def git_dbt_validate(
        self,
        campaign_id: str,
        *,
        expires_at: str | None = None,
    ) -> dict[str, Any]:
        arguments: list[str] = []
        if expires_at is not None:
            arguments.extend(["--expires-at", expires_at])
        return self._git_dbt(campaign_id, "validate", *arguments)

    def reconcile_campaign(self, campaign_id: str) -> dict[str, Any]:
        return self._run_json(
            [
                "campaign",
                "reconcile",
                "--campaign",
                self._campaign_id(campaign_id),
                "--refresh-receipt",
                str(self.settings.refresh_receipt),
                "--indexing-timeout-seconds",
                str(self.settings.indexing_timeout_seconds),
                *self._runtime_arguments(),
            ]
        )

    def publish_campaign(self, campaign_id: str) -> dict[str, Any]:
        return self._campaign_publication(campaign_id, "publish")

    def verify_publication(self, campaign_id: str) -> dict[str, Any]:
        return self._campaign_publication(campaign_id, "verify-publication")

    def prepare_producer_plan(
        self,
        campaign_id: str,
        *,
        expires_at: str,
    ) -> dict[str, Any]:
        return self._run_json(
            [
                "producer",
                "plan",
                "--campaign",
                self._campaign_id(campaign_id),
                "--expires-at",
                expires_at,
                *self._runtime_arguments(),
            ]
        )

    def execute_gate(
        self,
        campaign_id: str,
        *,
        plan: str | None = None,
    ) -> dict[str, Any]:
        arguments = [
            "gate",
            "--campaign",
            self._campaign_id(campaign_id),
            *self._runtime_arguments(),
        ]
        if plan is not None:
            plan_path = self._bounded_path(
                plan,
                root=self.settings.artifact_directory,
                label="producer plan",
                must_exist=True,
            )
            arguments.extend(["--plan", str(plan_path)])
        return self._run_json(arguments)

    def _campaign_publication(
        self,
        campaign_id: str,
        command: str,
    ) -> dict[str, Any]:
        return self._run_json(
            [
                "campaign",
                command,
                "--campaign",
                self._campaign_id(campaign_id),
                *self._runtime_arguments(),
            ]
        )

    def _git_dbt(
        self,
        campaign_id: str,
        command: str,
        *arguments: str,
    ) -> dict[str, Any]:
        return self._run_json(
            [
                "adapter",
                "git-dbt",
                command,
                "--campaign",
                self._campaign_id(campaign_id),
                *arguments,
                *self._runtime_arguments(),
            ]
        )

    def _runtime_arguments(self) -> list[str]:
        return [
            "--store",
            str(self.settings.store),
            "--writer-id",
            self.settings.writer_id,
            "--artifact-dir",
            str(self.settings.artifact_directory),
        ]

    def _run_json(self, arguments: Sequence[str]) -> dict[str, Any]:
        result = self._run_text(arguments)
        text = str(result["text"])
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "The existing command boundary returned non-JSON output."
            ) from exc
        if not isinstance(value, dict):
            raise RuntimeError("The existing command boundary returned a non-object.")
        value["command_exit_code"] = result["command_exit_code"]
        return value

    def _run_text(self, arguments: Sequence[str]) -> dict[str, Any]:
        output = io.StringIO()
        with self._command_lock, redirect_stdout(output):
            exit_code = cli_main(list(arguments))
        return {
            "command_exit_code": exit_code,
            "text": output.getvalue().strip(),
        }

    @staticmethod
    def _parse_text_refusal(result: dict[str, Any]) -> dict[str, Any]:
        try:
            value = json.loads(str(result["text"]))
        except json.JSONDecodeError:
            return {
                "result": "ERROR",
                "refusal_code": "RUNTIME_COMMAND_OUTPUT_INVALID",
                **result,
            }
        if not isinstance(value, dict):
            return {
                "result": "ERROR",
                "refusal_code": "RUNTIME_COMMAND_OUTPUT_INVALID",
                **result,
            }
        value["command_exit_code"] = result["command_exit_code"]
        return value

    @staticmethod
    def _campaign_id(value: str) -> str:
        if not _CAMPAIGN_ID.fullmatch(value):
            raise ValueError(
                "campaign_id must contain only letters, digits, dots, underscores, "
                "or hyphens and be at most 128 characters"
            )
        return value

    @staticmethod
    def _bounded_path(
        value: str,
        *,
        root: Path,
        label: str,
        must_exist: bool,
    ) -> Path:
        resolved_root = root.resolve()
        candidate = Path(value)
        if not candidate.is_absolute():
            candidate = resolved_root / candidate
        resolved = candidate.resolve(strict=must_exist)
        try:
            resolved.relative_to(resolved_root)
        except ValueError as exc:
            raise ValueError(f"{label} must remain inside {resolved_root}") from exc
        if must_exist and not resolved.is_file():
            raise ValueError(f"{label} must name one regular file")
        return resolved

"""Authorization-bound orchestration for the concrete Superset executor."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from retirement_conductor.canonical import verify_digest
from retirement_conductor.records import validate_approval
from retirement_conductor.superset import SupersetAdapter


class SupersetWorkflow:
    """Keep native planning, approved apply, validation, and recovery distinct."""

    def __init__(self, adapter: SupersetAdapter, artifact_directory: Path) -> None:
        self.adapter = adapter
        self.artifact_directory = artifact_directory

    def apply(
        self,
        plan: Mapping[str, Any],
        *,
        approval: Mapping[str, Any] | None,
        authorization_digest: str,
        confirmed_plan_digest: str,
        trusted_now: datetime,
    ) -> dict[str, Any]:
        """Require external exact approval before issuing the native update."""

        verify_digest(dict(plan), "plan_digest")
        validate_approval(
            approval,
            campaign_id=str(plan["campaign_id"]),
            plan_digest=str(plan["plan_digest"]),
            source_version=str(plan["source_version"]),
            targets=[str(item) for item in plan["proposed_targets"]],
            required_scope=["apply"],
            authorization_digest=authorization_digest,
            trusted_now=trusted_now,
        )
        return self.adapter.apply(
            plan,
            confirmed_plan_digest=confirmed_plan_digest,
            artifact_root=self._root(str(plan["campaign_id"])),
        )

    def validate_and_emit_receipt(
        self,
        plan: Mapping[str, Any],
        apply_record: Mapping[str, Any],
        *,
        expires_at: str | None = None,
    ) -> dict[str, Any]:
        root = self._root(str(plan["campaign_id"]))
        validation = self.adapter.validate(
            plan,
            apply_record,
            artifact_root=root / "native-validation",
        )
        receipt = self.adapter.emit_receipt(
            plan,
            apply_record,
            validation,
            compensation=None,
            expires_at=expires_at,
            artifact_root=root,
        )
        return {"result": "VALIDATED", "validation": validation, "receipt": receipt}

    def compensate(
        self,
        plan: Mapping[str, Any],
        apply_record: Mapping[str, Any],
        *,
        approval: Mapping[str, Any] | None,
        authorization_digest: str,
        trusted_now: datetime,
    ) -> dict[str, Any]:
        validate_approval(
            approval,
            campaign_id=str(plan["campaign_id"]),
            plan_digest=str(plan["plan_digest"]),
            source_version=str(plan["source_version"]),
            targets=[str(item) for item in plan["proposed_targets"]],
            required_scope=["compensate"],
            authorization_digest=authorization_digest,
            trusted_now=trusted_now,
        )
        return self.adapter.compensate(
            plan,
            apply_record,
            artifact_root=self._root(str(plan["campaign_id"])),
        )

    def reconcile(
        self,
        plan: Mapping[str, Any],
        receipt: Mapping[str, Any],
        datahub_observation: Mapping[str, Any],
    ) -> dict[str, Any]:
        return self.adapter.reconcile_source(
            plan,
            receipt,
            datahub_observation,
            artifact_root=self._root(str(plan["campaign_id"])) / "reconciliation",
        )

    def _root(self, campaign_id: str) -> Path:
        return self.artifact_directory / campaign_id / "superset"

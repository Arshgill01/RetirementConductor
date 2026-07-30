#!/usr/bin/env python3
"""Generate public, explicitly non-live Phase 06 pre-acceptance evidence."""

from __future__ import annotations

import copy
import json
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from retirement_conductor.canonical import (
    digest_bytes,
    verify_digest,
    with_digest,
    write_json,
)
from retirement_conductor.clock import parse_timestamp
from retirement_conductor.datahub import utc_now
from retirement_conductor.errors import Refusal
from retirement_conductor.looker import LookerAdapter
from retirement_conductor.looker_access import (
    CONTROL_VARIABLES,
    DERIVED_EVIDENCE_VARIABLES,
    LOOKER_ACCESS_VARIABLES,
    OPTIONAL_SECRET_VARIABLES,
    build_looker_access_packet,
)
from retirement_conductor.records import validate_consumer_receipt
from retirement_conductor.store import CampaignStore
from tests.integration.test_looker_reconciliation import (
    CAMPAIGN_ID as COMBINED_CAMPAIGN_ID,
)
from tests.integration.test_looker_reconciliation import (
    LOOKER_CONSUMER as COMBINED_LOOKER_CONSUMER,
)
from tests.integration.test_looker_reconciliation import (
    FakeLookerAdapter as CombinedFakeLookerAdapter,
)
from tests.integration.test_looker_reconciliation import (
    FakeStore as CombinedFakeStore,
)
from tests.integration.test_looker_reconciliation import (
    _workflow as combined_workflow,
)
from tests.integration.test_looker_workflow import (
    CAMPAIGN_ID as WORKFLOW_CAMPAIGN_ID,
)
from tests.integration.test_looker_workflow import (
    InterruptingLookerClient,
    _expires_after,
)
from tests.integration.test_looker_workflow import (
    _specification as workflow_specification,
)
from tests.integration.test_looker_workflow import (
    _workflow as durable_workflow,
)
from tests.unit.test_looker import (
    CAMPAIGN_ID,
    CONSUMER_ID,
    NOW,
    FakeLookerClient,
    _edge_snapshot,
    _plan,
    _settings,
    _validated_migration,
)

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "artifacts/public/phase06"
LOOKML_EVIDENCE = PUBLIC / "lookml-ingestion-evidence.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def refusal(action: Callable[[], object]) -> dict[str, Any]:
    try:
        action()
    except Refusal as error:
        return {
            "result": "REFUSED",
            "refusal_code": error.code,
        }
    raise RuntimeError("expected refusal did not occur")


def repository_commit() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return completed.stdout.strip()


def lifecycle_evidence() -> dict[str, Any]:
    fake = FakeLookerClient()
    adapter, first_plan = _plan(fake)
    first_intent = adapter.prepare_apply_intent(first_plan, recorded_at=NOW)
    first_apply = adapter.apply(first_plan, first_intent, occurred_at=NOW)
    first_validation = adapter.validate(first_plan, first_apply)
    replay = adapter.apply(
        first_plan,
        first_intent,
        prior_apply=first_apply,
        occurred_at=NOW,
    )
    compensation = adapter.compensate(first_plan, first_apply, occurred_at=NOW)

    second_plan = adapter.plan(
        campaign_id=CAMPAIGN_ID,
        consumer_id=CONSUMER_ID,
    )
    second_intent = adapter.prepare_apply_intent(second_plan, recorded_at=NOW)
    second_apply = adapter.apply(second_plan, second_intent, occurred_at=NOW)
    second_validation = adapter.validate(second_plan, second_apply)
    stale_compensation = refusal(
        lambda: adapter.emit_receipt(
            second_plan,
            second_apply,
            second_validation,
            compensation=compensation,
            captured_at=NOW,
            expires_at=None,
            artifact_ids=[f"sha256:{'8' * 64}"],
        )
    )
    receipt = adapter.emit_receipt(
        second_plan,
        second_apply,
        second_validation,
        compensation=None,
        captured_at=NOW,
        expires_at=None,
        artifact_ids=[f"sha256:{'8' * 64}"],
    )
    live_rejection = refusal(
        lambda: validate_consumer_receipt(
            receipt,
            campaign_id=CAMPAIGN_ID,
            consumer_id=CONSUMER_ID,
            plan_digest=str(second_plan["plan_digest"]),
            source_version=str(second_plan["source"]["version"]),
            approved_targets=["look:41"],
            require_live=True,
            trusted_now=parse_timestamp(NOW),
        )
    )

    require(first_apply["actual_changed_fields"] == ["query_id"], "apply widened")
    require(first_apply["actual_targets"] == ["look:41"], "target widened")
    require(first_validation["result"] == "PASSED", "validation failed")
    require(
        replay["apply_digest"] == first_apply["apply_digest"],
        "idempotent replay changed apply",
    )
    require(compensation["result"] == "RESTORED", "compensation failed")
    require(second_validation["result"] == "PASSED", "reapply validation failed")
    require(
        stale_compensation["refusal_code"] == "AUTH_APPROVAL_WRONG_PLAN",
        "old compensation attached to a new plan",
    )
    require(
        live_rejection["refusal_code"] == "EVIDENCE_RECEIPT_MODE_NOT_LIVE",
        "fixture receipt was accepted as live",
    )
    require(fake.patch_calls == 3, "unexpected mutation count")

    return {
        "mode": "fixture",
        "target_sets": first_plan["target_sets"],
        "pagination": {
            "complete": first_plan["discovery"]["pagination_complete"],
            "page_count": first_plan["discovery"]["page_count"],
        },
        "relevance": first_plan["relevance"],
        "first_apply": {
            "actual_changed_fields": first_apply["actual_changed_fields"],
            "actual_targets": first_apply["actual_targets"],
            "automatic_mutation_retry": first_apply["automatic_mutation_retry"],
            "result": first_apply["result"],
        },
        "validation": {
            "result": first_validation["result"],
            "content_scope": first_validation["scope"],
            "query_execution": {
                "executed": True,
                "row_count": first_validation["query_execution"]["row_count"],
                "row_limit": first_validation["query_execution"]["row_limit"],
                "raw_result_retained": first_validation["query_execution"][
                    "raw_result_retained"
                ],
            },
        },
        "idempotent_replay": {
            "same_apply_digest": True,
            "patch_calls_after_replay": 1,
        },
        "compensation": {
            "result": compensation["result"],
            "restored_source": (
                compensation["restored_fingerprint"]
                == first_plan["source"]["fingerprint"]
            ),
        },
        "reapply": {
            "new_plan": second_plan["plan_digest"] != first_plan["plan_digest"],
            "result": second_apply["result"],
            "validation": second_validation["result"],
            "receipt_compensation_exercised": receipt["compensation"]["exercised"],
        },
        "stale_compensation": stale_compensation,
        "fixture_receipt_live_acceptance": live_rejection,
        "native_call_counts": {
            "patch": fake.patch_calls,
            "query_post": fake.query_posts,
        },
        "artifact_digests": {
            "first_plan": first_plan["plan_digest"],
            "first_apply": first_apply["apply_digest"],
            "first_validation": first_validation["validation_digest"],
            "compensation": compensation["compensation_digest"],
            "second_plan": second_plan["plan_digest"],
            "second_apply": second_apply["apply_digest"],
            "receipt": receipt["receipt_digest"],
        },
    }


def durable_recovery(client: FakeLookerClient, *, interrupt: bool) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="retirement-conductor-phase06-") as raw:
        root = Path(raw)
        with CampaignStore(root / "campaign.sqlite", writer_id="phase06") as store:
            store.create_campaign(
                workflow_specification(),
                occurred_at="2026-07-30T00:00:00Z",
            )
            workflow = durable_workflow(root, store, client)
            workflow.preflight(WORKFLOW_CAMPAIGN_ID)
            plan = workflow.plan(WORKFLOW_CAMPAIGN_ID)["plan"]
            authorized_at = utc_now()
            workflow.authorize(
                WORKFLOW_CAMPAIGN_ID,
                principal="fixture-operator",
                authorized_at=authorized_at,
                expires_at=_expires_after(authorized_at),
            )
            expected_code = (
                "PROCESS_INTERRUPTED" if interrupt else "APPLY_OUTCOME_UNKNOWN"
            )
            if interrupt:
                try:
                    workflow.apply(
                        WORKFLOW_CAMPAIGN_ID,
                        confirmed_plan_digest=str(plan["plan_digest"]),
                        occurred_at=authorized_at,
                    )
                except KeyboardInterrupt:
                    first_result = expected_code
                else:
                    raise RuntimeError("expected process interruption did not occur")
            else:
                client.drop_patch_response = True
                first_result = refusal(
                    lambda: workflow.apply(
                        WORKFLOW_CAMPAIGN_ID,
                        confirmed_plan_digest=str(plan["plan_digest"]),
                        occurred_at=authorized_at,
                    )
                )["refusal_code"]
            intent_path = (
                root
                / "artifacts"
                / WORKFLOW_CAMPAIGN_ID
                / "looker"
                / "apply-intent.json"
            )
            pending = json.loads(intent_path.read_text(encoding="utf-8"))
            recovered = workflow.apply(
                WORKFLOW_CAMPAIGN_ID,
                confirmed_plan_digest=str(plan["plan_digest"]),
                occurred_at=authorized_at,
            )
            resolved = json.loads(intent_path.read_text(encoding="utf-8"))
            require(client.patch_calls == 1, "recovery retried the mutation")
            require(
                recovered["apply"]["recovery"] == "native_reread",
                "recovery did not reread native state",
            )
            return {
                "first_result": first_result,
                "durable_status_before_recovery": pending["status"],
                "durable_status_after_recovery": resolved["status"],
                "recovery": recovered["apply"]["recovery"],
                "patch_calls": client.patch_calls,
            }


def scope_refusals() -> dict[str, Any]:
    probes: dict[str, Any] = {}

    fake = FakeLookerClient()
    fake.permissions.remove("save_content")
    adapter = LookerAdapter(_settings(), client=fake, clock=lambda: NOW)
    probes["missing_permission"] = {
        **refusal(adapter.preflight),
        "patch_calls": fake.patch_calls,
    }

    mutations: dict[str, Callable[[FakeLookerClient], None]] = {
        "schedule": lambda value: value.schedules.append(
            {
                "id": "s-1",
                "look_id": "41",
                "query_id": "q-before",
                "enabled": True,
                "run_as_recipient": False,
                "filters_string": "",
                "created_at": NOW,
                "updated_at": NOW,
            }
        ),
        "expanded_folder": lambda value: value.extra_looks.append(
            {
                "id": "42",
                "content_metadata_id": "cm-42",
                "created_at": NOW,
                "updated_at": NOW,
                "folder_id": "9",
                "query_id": "q-before",
                "deleted": False,
                "query": copy.deepcopy(value.queries["q-before"]),
            }
        ),
        "calculation": lambda value: value.queries["q-before"].update(
            {
                "dynamic_fields": '[{"expression":"legacy reference"}]',
                "has_table_calculations": True,
            }
        ),
        "merged_result": lambda value: value.look.update({"merge_query_id": "merge-1"}),
        "incompatible_replacement": lambda value: value.fields[-1].update(
            {"type": "number", "is_numeric": True}
        ),
        "content_validation": lambda value: value.content_errors.append(
            {"look_id": "41", "message": "fixture validation error"}
        ),
    }
    expected = {
        "schedule": "SCOPE_TARGET_NOT_ALLOWED",
        "expanded_folder": "SCOPE_TARGET_NOT_ALLOWED",
        "calculation": "SCOPE_TARGET_NOT_ALLOWED",
        "merged_result": "SCOPE_TARGET_NOT_ALLOWED",
        "incompatible_replacement": "SPEC_REPLACEMENT_INCOMPATIBLE",
        "content_validation": "VALIDATION_RECEIPT_FAILED",
    }
    for name, mutate in mutations.items():
        candidate = FakeLookerClient()
        mutate(candidate)
        candidate_adapter = LookerAdapter(
            _settings(),
            client=candidate,
            clock=lambda: NOW,
        )
        result = refusal(
            lambda adapter=candidate_adapter: adapter.plan(
                campaign_id=CAMPAIGN_ID,
                consumer_id=CONSUMER_ID,
            )
        )
        require(result["refusal_code"] == expected[name], f"{name} refusal changed")
        probes[name] = {**result, "patch_calls": candidate.patch_calls}

    stale = FakeLookerClient()
    stale_adapter, stale_plan = _plan(stale)
    stale_intent = stale_adapter.prepare_apply_intent(stale_plan, recorded_at=NOW)
    stale.look["title"] = "intervening edit"
    probes["stale_source"] = {
        **refusal(
            lambda: stale_adapter.apply(
                stale_plan,
                stale_intent,
                occurred_at=NOW,
            )
        ),
        "patch_calls": stale.patch_calls,
        "intervening_edit_preserved": stale.look["title"] == "intervening edit",
    }

    recreated = FakeLookerClient()
    recreated_adapter, recreated_plan = _plan(recreated)
    recreated_intent = recreated_adapter.prepare_apply_intent(
        recreated_plan,
        recorded_at=NOW,
    )
    recreated.look["content_metadata_id"] = "cm-recreated"
    recreated.look["created_at"] = "2026-07-30T12:00:01Z"
    probes["recreated_identity"] = {
        **refusal(
            lambda: recreated_adapter.apply(
                recreated_plan,
                recreated_intent,
                occurred_at=NOW,
            )
        ),
        "patch_calls": recreated.patch_calls,
    }

    conflict = FakeLookerClient()
    conflict_adapter, conflict_plan = _plan(conflict)
    conflict_intent = conflict_adapter.prepare_apply_intent(
        conflict_plan,
        recorded_at=NOW,
    )
    conflict_apply = conflict_adapter.apply(
        conflict_plan,
        conflict_intent,
        occurred_at=NOW,
    )
    conflict.look["title"] = "owner intervention"
    probes["compensation_conflict"] = {
        **refusal(
            lambda: conflict_adapter.compensate(
                conflict_plan,
                conflict_apply,
                occurred_at=NOW,
            )
        ),
        "patch_calls": conflict.patch_calls,
        "intervening_edit_preserved": conflict.look["title"] == "owner intervention",
        "replacement_state_preserved": conflict.query_id == "q-after",
    }
    return probes


def recovery_evidence() -> dict[str, Any]:
    lost_response = durable_recovery(FakeLookerClient(), interrupt=False)
    interruption = durable_recovery(InterruptingLookerClient(), interrupt=True)
    probes = scope_refusals()
    require(
        lost_response
        == {
            "first_result": "APPLY_OUTCOME_UNKNOWN",
            "durable_status_before_recovery": "OUTCOME_UNKNOWN",
            "durable_status_after_recovery": "RESOLVED",
            "recovery": "native_reread",
            "patch_calls": 1,
        },
        "lost-response recovery changed",
    )
    require(
        interruption["durable_status_before_recovery"] == "PENDING"
        and interruption["durable_status_after_recovery"] == "RESOLVED"
        and interruption["patch_calls"] == 1,
        "interruption recovery changed",
    )
    for name, value in probes.items():
        expected_calls = 1 if name == "compensation_conflict" else 0
        require(
            value["patch_calls"] == expected_calls,
            f"{name} used an unexpected number of mutations",
        )
    return {
        "mode": "fixture",
        "lost_response": lost_response,
        "process_interruption": interruption,
        "pre_mutation_refusals": probes,
        "automatic_mutation_retry": False,
    }


def reconciliation_evidence() -> dict[str, Any]:
    fake = FakeLookerClient()
    adapter, plan, applied, receipt = _validated_migration(fake)
    exact = adapter.reconcile_source(
        plan,
        applied,
        receipt,
        legacy_snapshot=_edge_snapshot("legacy_status", state="absent"),
        replacement_snapshot=_edge_snapshot("order_status", state="field"),
        require_live=False,
    )
    table_only = adapter.reconcile_source(
        plan,
        applied,
        receipt,
        legacy_snapshot=_edge_snapshot("legacy_status", state="absent"),
        replacement_snapshot=_edge_snapshot("order_status", state="table"),
        require_live=False,
    )
    persisting_legacy = refusal(
        lambda: adapter.reconcile_source(
            plan,
            applied,
            receipt,
            legacy_snapshot=_edge_snapshot("legacy_status", state="field"),
            replacement_snapshot=_edge_snapshot("order_status", state="field"),
            require_live=False,
        )
    )

    recreated = FakeLookerClient()
    recreated_adapter, recreated_plan, recreated_apply, recreated_receipt = (
        _validated_migration(recreated)
    )
    recreated.look["content_metadata_id"] = "cm-recreated"
    recreated.look["created_at"] = "2026-07-30T12:00:01Z"
    recreated_result = refusal(
        lambda: recreated_adapter.reconcile_source(
            recreated_plan,
            recreated_apply,
            recreated_receipt,
            legacy_snapshot=_edge_snapshot("legacy_status", state="absent"),
            replacement_snapshot=_edge_snapshot("order_status", state="field"),
            require_live=False,
        )
    )

    with tempfile.TemporaryDirectory(prefix="retirement-conductor-phase06-") as raw:
        combined_store = CombinedFakeStore()
        combined = combined_workflow(
            Path(raw) / "success",
            combined_store,
            CombinedFakeLookerAdapter(),
        ).reconcile(COMBINED_CAMPAIGN_ID)
        recreated_store = CombinedFakeStore()
        combined_recreated = combined_workflow(
            Path(raw) / "recreated",
            recreated_store,
            CombinedFakeLookerAdapter(
                refusal=Refusal(
                    "IDENTITY_NATIVE_OBJECT_RECREATED",
                    "fixture identity changed",
                )
            ),
        ).reconcile(COMBINED_CAMPAIGN_ID)

    invalidations = combined_recreated["comparison"]["invalidated_receipts"]
    require(exact["datahub_edges"]["legacy"]["state"] == "NOT_OBSERVED", "legacy")
    require(
        exact["datahub_edges"]["replacement"]["state"] == "FIELD_EDGE_PRESENT",
        "replacement field edge missing",
    )
    require(
        table_only["datahub_edges"]["field_closure"]
        == "NOT_CLAIMED_CONNECTOR_LIMITATION",
        "table-only lineage claimed closure",
    )
    require(
        persisting_legacy["refusal_code"] == "RECONCILIATION_SCOPE_MISMATCH",
        "persisting legacy edge did not refuse",
    )
    require(
        recreated_result["refusal_code"] == "IDENTITY_NATIVE_OBJECT_RECREATED",
        "recreated native identity did not refuse",
    )
    require(combined["result"] == "RECONCILED", "combined reconciliation failed")
    require(
        len(invalidations) == 1
        and invalidations[0]["consumer_id"] == COMBINED_LOOKER_CONSUMER,
        "combined reconciliation invalidated the wrong receipt",
    )

    return {
        "mode": "fixture",
        "exact_field_edges": {
            "legacy": exact["datahub_edges"]["legacy"]["state"],
            "replacement": exact["datahub_edges"]["replacement"]["state"],
            "field_closure": exact["datahub_edges"]["field_closure"],
            "disappearance_alone_is_closure": exact["datahub_edges"][
                "disappearance_alone_is_closure"
            ],
        },
        "table_only_replacement": {
            "state": table_only["datahub_edges"]["replacement"]["state"],
            "field_closure": table_only["datahub_edges"]["field_closure"],
        },
        "persisting_legacy_edge": persisting_legacy,
        "recreated_identity": recreated_result,
        "combined_campaign": {
            "result": combined["result"],
            "git_source_recorded": bool(
                combined["comparison"]["current"]["git_reconciliation_digest"]
            ),
            "looker_source_recorded": bool(
                combined["comparison"]["current"]["looker_reconciliation_digest"]
            ),
            "replacement_snapshot_recorded": bool(
                combined["comparison"]["current"]["replacement_datahub_snapshot_digest"]
            ),
            "invalidated_receipts": combined["comparison"]["invalidated_receipts"],
        },
        "selective_identity_invalidation": {
            "invalidated_consumer_ids": [item["consumer_id"] for item in invalidations],
            "refusal_codes": [item["refusal_code"] for item in invalidations],
            "git_disposition": recreated_store.projection_value.consumers[
                "consumer-git"
            ]["disposition"],
            "looker_disposition": recreated_store.projection_value.consumers[
                COMBINED_LOOKER_CONSUMER
            ]["disposition"],
        },
        "simulated_live_labels_are_not_acceptance_evidence": True,
    }


def access_evidence() -> dict[str, Any]:
    names = (
        *LOOKER_ACCESS_VARIABLES,
        *DERIVED_EVIDENCE_VARIABLES,
        *OPTIONAL_SECRET_VARIABLES,
        *CONTROL_VARIABLES,
    )
    environment = {
        name: f"phase06-sensitive-marker-{index}" for index, name in enumerate(names)
    }
    environment["LOOKER_ALLOW_APPLY"] = "false"
    packet, summary = build_looker_access_packet(
        campaign_id="phase06-access-boundary",
        environment=environment,
    )
    markers = [value for value in environment.values() if value != "false"]
    require(not any(marker in packet for marker in markers), "access value leaked")
    serialized = json.dumps(summary, sort_keys=True)
    require(not any(marker in serialized for marker in markers), "summary leaked")
    require(summary["provisioning_allowed"] is False, "provisioning enabled")
    require(summary["apply_control"] == "DISABLED", "apply was not disabled")
    require(
        summary["resume_command"]
        == "retirement-conductor deployment preflight --profile looker-plan",
        "access packet resume assumed unavailable campaign state",
    )
    require(
        summary["campaign_state_required_before_adapter_preflight"] is True,
        "access packet omitted the exact campaign bootstrap prerequisite",
    )
    return {
        "packet_digest": digest_bytes(packet.encode("utf-8")),
        "provisioning_allowed": summary["provisioning_allowed"],
        "apply_control": summary["apply_control"],
        "resume_command": summary["resume_command"],
        "campaign_state_required_before_adapter_preflight": summary[
            "campaign_state_required_before_adapter_preflight"
        ],
        "configuration_names": len(summary["configuration"]),
        "adapter_permissions": summary["adapter_permissions"],
        "ingestion_permissions": summary["ingestion_permissions"],
        "supplied_values_present": False,
    }


def artifact(name: str, body: dict[str, Any]) -> dict[str, Any]:
    value = with_digest(
        {
            "schema_version": "1.0.0",
            "generated_at": NOW,
            "evidence_mode": "fixture",
            **body,
        },
        "artifact_digest",
    )
    write_json(PUBLIC / name, value)
    return value


def run() -> int:
    lookml = json.loads(LOOKML_EVIDENCE.read_text(encoding="utf-8"))
    require(isinstance(lookml, dict), "LookML evidence is not an object")
    verify_digest(lookml, "artifact_digest")
    require(
        lookml.get("result") == "VERIFIED_LOCAL_LOOKML_INGESTION",
        "local LookML ingestion evidence is not verified",
    )

    lifecycle = artifact(
        "adapter-evidence.json",
        {"result": "VERIFIED_FIXTURE_LIFECYCLE", **lifecycle_evidence()},
    )
    recovery = artifact(
        "recovery-evidence.json",
        {"result": "VERIFIED_FIXTURE_RECOVERY", **recovery_evidence()},
    )
    reconciliation = artifact(
        "reconciliation-evidence.json",
        {
            "result": "VERIFIED_FIXTURE_RECONCILIATION",
            **reconciliation_evidence(),
        },
    )
    access = access_evidence()
    rollup = artifact(
        "phase06-preacceptance-evidence.json",
        {
            "result": "CREDENTIAL_INDEPENDENT_WORK_VERIFIED",
            "repository_commit": repository_commit(),
            "phase_acceptance": "NOT_SATISFIED_LIVE_BOUNDARY",
            "evidence_ledger_entry": "EP-006 remains not-run",
            "artifacts": {
                "adapter": lifecycle["artifact_digest"],
                "recovery": recovery["artifact_digest"],
                "reconciliation": reconciliation["artifact_digest"],
                "local_lookml_ingestion": lookml["artifact_digest"],
            },
            "access_boundary": access,
            "claim_boundary": {
                "fixture_adapter_receipt_is_live": False,
                "local_lookml_input_mode": "fixture",
                "local_datahub_runtime_observed": True,
                "live_looker_api_observed": False,
                "live_saved_look_ingested": False,
                "native_looker_query_executed": False,
                "paid_resource_provisioned": False,
                "bigquery_queried": False,
                "remaining_live_boundary": (
                    "one pre-existing user-approved disposable Looker instance "
                    "with scoped content and least-privileged credentials"
                ),
            },
        },
    )

    rendered = json.dumps(
        {
            "lifecycle": lifecycle,
            "recovery": recovery,
            "reconciliation": reconciliation,
            "rollup": rollup,
        },
        sort_keys=True,
    )
    for forbidden in (
        "customer@example.invalid",
        "Private retirement fixture",
        "fixture-secret",
        "owner intervention",
        "intervening edit",
    ):
        require(
            forbidden not in rendered, f"private fixture marker leaked: {forbidden}"
        )
    print(
        json.dumps(
            {
                "result": rollup["result"],
                "artifact_digest": rollup["artifact_digest"],
                "phase_acceptance": rollup["phase_acceptance"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())

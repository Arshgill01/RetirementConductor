"""Retirement Conductor command-line entry point."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from retirement_conductor.canonical import digest_json, write_json
from retirement_conductor.datahub import (
    DataHubBoundary,
    render_campaign_summary,
    utc_now,
)
from retirement_conductor.datahub_config import DataHubSettings
from retirement_conductor.datahub_http import DataHubGraphClient
from retirement_conductor.errors import Refusal
from retirement_conductor.events import (
    event_stream_digest,
    manifest_from_projection,
    project_events,
)
from retirement_conductor.fixtures import run_fixture
from retirement_conductor.git_dbt import GitDbtAdapter
from retirement_conductor.git_dbt_config import GitDbtSettings
from retirement_conductor.git_dbt_workflow import GitDbtWorkflow
from retirement_conductor.mcp_http import HttpMCPClient
from retirement_conductor.reconciliation import ReconciliationWorkflow
from retirement_conductor.specification import load_specification
from retirement_conductor.store import CampaignStore
from retirement_conductor.vocabulary import CampaignState


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="retirement-conductor")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser(
        "validate-spec",
        help="validate and normalize a retirement specification",
    )
    validate.add_argument("specification", type=Path)

    fixture = subparsers.add_parser(
        "fixture",
        help="run deterministic, explicitly non-live contract fixtures",
    )
    fixture_subparsers = fixture.add_subparsers(dest="fixture_command", required=True)
    fixture_run = fixture_subparsers.add_parser("run")
    fixture_run.add_argument("specification", type=Path)
    fixture_run.add_argument("--scenario", type=Path)
    fixture_run.add_argument("--output-dir", type=Path)

    datahub = subparsers.add_parser(
        "datahub",
        help="inspect the live DataHub evidence boundary",
    )
    datahub_subparsers = datahub.add_subparsers(
        dest="datahub_command",
        required=True,
    )
    preflight = datahub_subparsers.add_parser("preflight")
    preflight.add_argument(
        "--output",
        type=Path,
        default=Path(".retirement-conductor/datahub/capability-fingerprint.json"),
    )

    campaign = subparsers.add_parser(
        "campaign",
        help="create, replay, inspect, evaluate, resume, or export a campaign",
    )
    campaign_subparsers = campaign.add_subparsers(
        dest="campaign_command", required=True
    )
    replay = campaign_subparsers.add_parser("replay")
    replay.add_argument("source", type=Path)
    evaluate = campaign_subparsers.add_parser("evaluate")
    evaluate.add_argument("source", type=Path, nargs="?")
    evaluate.add_argument("--campaign", dest="campaign_id")
    _add_runtime_arguments(evaluate)

    create = campaign_subparsers.add_parser("create")
    create.add_argument("specification", type=Path)
    _add_store_arguments(create)
    create.add_argument("--occurred-at", required=True)

    inspect = campaign_subparsers.add_parser("inspect")
    inspect.add_argument("campaign_id")
    _add_store_arguments(inspect)

    resume = campaign_subparsers.add_parser("resume")
    resume.add_argument("campaign_id")
    resume.add_argument(
        "--state",
        choices=[
            CampaignState.INVENTORIED,
            CampaignState.MIGRATING,
            CampaignState.RECONCILING,
        ],
        required=True,
    )
    resume.add_argument("--occurred-at", required=True)
    resume.add_argument("--idempotency-key", required=True)
    _add_store_arguments(resume)

    export = campaign_subparsers.add_parser("export")
    export.add_argument("campaign_id")
    export.add_argument("--output", type=Path, required=True)
    _add_store_arguments(export)

    inventory = campaign_subparsers.add_parser("inventory")
    _add_live_campaign_arguments(inventory)

    reconcile = campaign_subparsers.add_parser("reconcile")
    _add_live_campaign_arguments(reconcile)
    reconcile.add_argument(
        "--refresh-receipt",
        type=Path,
        default=Path(".retirement-conductor/datahub/seed-receipt.json"),
    )
    reconcile.add_argument(
        "--indexing-timeout-seconds",
        type=float,
        default=30,
    )

    publish = campaign_subparsers.add_parser("publish")
    _add_live_campaign_arguments(publish)

    verify_publication = campaign_subparsers.add_parser("verify-publication")
    _add_live_campaign_arguments(verify_publication)

    adapter = subparsers.add_parser(
        "adapter",
        help="operate a source-native consumer adapter",
    )
    adapter_subparsers = adapter.add_subparsers(
        dest="adapter_name",
        required=True,
    )
    git_dbt = adapter_subparsers.add_parser(
        "git-dbt",
        help="operate the bounded Git/dbt adapter",
    )
    git_dbt_subparsers = git_dbt.add_subparsers(
        dest="adapter_command",
        required=True,
    )
    for command in ("preflight", "plan", "apply", "compensate", "validate"):
        operation = git_dbt_subparsers.add_parser(command)
        _add_live_campaign_arguments(operation)
        if command in {"apply", "compensate"}:
            operation.add_argument("--occurred-at")
        if command == "validate":
            operation.add_argument("--expires-at")
    authorize = git_dbt_subparsers.add_parser("authorize")
    _add_live_campaign_arguments(authorize)
    authorize.add_argument("--principal")
    authorize.add_argument("--authorized-at", required=True)
    authorize.add_argument("--expires-at", required=True)
    return parser


def _add_store_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--writer-id", required=True)


def _add_live_campaign_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--campaign", dest="campaign_id", required=True)
    _add_runtime_arguments(parser)


def _add_runtime_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--store",
        type=Path,
        default=Path(
            os.environ.get(
                "RETIREMENT_CONDUCTOR_STORE",
                ".retirement-conductor/campaigns.sqlite",
            )
        ),
    )
    parser.add_argument(
        "--writer-id",
        default=os.environ.get("RETIREMENT_CONDUCTOR_WRITER_ID", "local-operator"),
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path(
            os.environ.get(
                "RETIREMENT_CONDUCTOR_ARTIFACT_DIR",
                ".retirement-conductor/artifacts",
            )
        ),
    )


def _datahub_boundary() -> DataHubBoundary:
    settings = DataHubSettings.from_environment()
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


def _campaign_artifact_root(args: argparse.Namespace, operation: str) -> Path:
    return Path(args.artifact_dir) / str(args.campaign_id) / "datahub" / operation


def _git_dbt_workflow(
    args: argparse.Namespace,
    store: CampaignStore,
) -> GitDbtWorkflow:
    settings = GitDbtSettings.from_environment()
    return GitDbtWorkflow(
        store=store,
        adapter=GitDbtAdapter(settings),
        artifact_directory=Path(args.artifact_dir),
        boundary=(_datahub_boundary() if args.adapter_command == "preflight" else None),
    )


def _publication_source_manifest(
    store: CampaignStore,
    campaign_id: str,
    content_digest: str,
) -> dict[str, Any]:
    events = store.events(campaign_id)
    for index in range(len(events) - 1, 0, -1):
        event = events[index]
        if (
            event["event_type"] == "PUBLICATION_RECORDED"
            and event["payload"]["publication"]["content_digest"] == content_digest
        ):
            manifest = manifest_from_projection(project_events(events[:index]))
            recorded = event["payload"]["publication"]["published_manifest_digest"]
            if manifest["manifest_digest"] != recorded:
                raise Refusal(
                    "INTEGRITY_MATERIALIZED_STATE_MISMATCH",
                    "The publication source manifest could not be reconstructed.",
                )
            return manifest
    raise Refusal(
        "EVIDENCE_PUBLICATION_MISMATCH",
        "The publication write receipt was not found in campaign history.",
    )


def _load_fixture_events(source: Path) -> list[dict[str, Any]]:
    path = source / "events.json" if source.is_dir() else source
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Refusal(
            "SPEC_PARSE_FAILED",
            "The campaign event fixture could not be parsed.",
            {"file": path.name, "error_type": type(exc).__name__},
        ) from exc
    events = value.get("events") if isinstance(value, dict) else None
    if not isinstance(events, list) or not all(
        isinstance(event, dict) for event in events
    ):
        raise Refusal(
            "SPEC_SCHEMA_INVALID",
            "The campaign fixture must contain an events array.",
            {"file": path.name},
        )
    return events


def _render(value: object) -> None:
    print(
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Execute the command line and map expected refusals to exit code 2."""

    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate-spec":
            specification = load_specification(args.specification)
            _render({"result": "VALID", "specification": specification})
            return 0
        if args.command == "fixture" and args.fixture_command == "run":
            summary = run_fixture(
                args.specification,
                scenario_path=args.scenario,
                output_directory=args.output_dir,
            )
            _render(summary)
            return 0
        if args.command == "datahub" and args.datahub_command == "preflight":
            fingerprint = _datahub_boundary().preflight()
            write_json(args.output, fingerprint)
            _render(
                {
                    "result": "OK",
                    "capability_fingerprint": fingerprint,
                    "output": str(args.output),
                }
            )
            return 0
        if args.command == "adapter" and args.adapter_name == "git-dbt":
            with CampaignStore(args.store, writer_id=args.writer_id) as store:
                workflow = _git_dbt_workflow(args, store)
                if args.adapter_command == "preflight":
                    result = workflow.preflight(args.campaign_id)
                elif args.adapter_command == "plan":
                    result = workflow.plan(args.campaign_id)
                elif args.adapter_command == "authorize":
                    result = workflow.authorize(
                        args.campaign_id,
                        principal=args.principal or workflow.adapter.settings.principal,
                        authorized_at=args.authorized_at,
                        expires_at=args.expires_at,
                    )
                elif args.adapter_command == "apply":
                    result = workflow.apply(
                        args.campaign_id,
                        occurred_at=args.occurred_at,
                    )
                elif args.adapter_command == "compensate":
                    result = workflow.compensate(
                        args.campaign_id,
                        occurred_at=args.occurred_at,
                    )
                else:
                    result = workflow.validate(
                        args.campaign_id,
                        expires_at=args.expires_at,
                    )
            _render(result)
            return 0
        if args.command == "campaign":
            if args.campaign_command == "replay" or (
                args.campaign_command == "evaluate" and args.source is not None
            ):
                events = _load_fixture_events(args.source)
                projection = project_events(events)
                manifest = manifest_from_projection(projection)
                if args.campaign_command == "replay":
                    _render(
                        {
                            "result": "REPLAYED",
                            "event_count": len(events),
                            "event_stream_digest": event_stream_digest(events),
                            "manifest": manifest,
                        }
                    )
                else:
                    _render(
                        {
                            "result": "EVALUATED",
                            "decision": manifest["decision"],
                            "blockers": manifest["blockers"],
                            "manifest_digest": manifest["manifest_digest"],
                        }
                    )
                return 0
            if args.campaign_command == "evaluate":
                if args.campaign_id is None:
                    raise Refusal(
                        "SPEC_SCHEMA_INVALID",
                        "Campaign evaluation requires a fixture source or --campaign.",
                    )
                with CampaignStore(args.store, writer_id=args.writer_id) as store:
                    projection = store.projection(args.campaign_id)
                    if (
                        projection.state in {CampaignState.BLOCKED, CampaignState.READY}
                        and projection.last_policy_result is not None
                    ):
                        manifest = store.materialize(args.campaign_id)
                    else:
                        before = store.materialize(args.campaign_id)
                        manifest = store.evaluate(
                            args.campaign_id,
                            occurred_at=utc_now(),
                            idempotency_key=(
                                "policy-evaluation-"
                                f"{str(before['manifest_digest'])[-16:]}"
                            ),
                        )
                _render(
                    {
                        "result": "EVALUATED",
                        "decision": manifest["decision"],
                        "blockers": manifest["blockers"],
                        "manifest_digest": manifest["manifest_digest"],
                        "manifest": manifest,
                    }
                )
                return 0
            if args.campaign_command == "reconcile":
                with CampaignStore(args.store, writer_id=args.writer_id) as store:
                    reconciliation_workflow = ReconciliationWorkflow(
                        store=store,
                        boundary=_datahub_boundary(),
                        git_dbt=GitDbtAdapter(GitDbtSettings.from_environment()),
                        artifact_directory=Path(args.artifact_dir),
                        refresh_receipt=args.refresh_receipt,
                        indexing_timeout_seconds=args.indexing_timeout_seconds,
                    )
                    result = reconciliation_workflow.reconcile(args.campaign_id)
                _render(result)
                return 0
            if args.campaign_command in {
                "inventory",
                "publish",
                "verify-publication",
            }:
                boundary = _datahub_boundary()
                with CampaignStore(args.store, writer_id=args.writer_id) as store:
                    specification = store.specification(args.campaign_id)
                    if args.campaign_command == "inventory":
                        snapshot = boundary.inventory(
                            specification,
                            artifact_root=_campaign_artifact_root(
                                args,
                                "baseline",
                            ),
                        )
                        manifest = store.record_inventory(
                            args.campaign_id,
                            evidence_envelope=snapshot["evidence_envelope"],
                            consumers=[
                                {
                                    "id": consumer["id"],
                                    "disposition": consumer["disposition"],
                                    "receipt_digest": None,
                                }
                                for consumer in snapshot["consumers"]
                            ],
                            snapshot_digest=snapshot["snapshot_digest"],
                            occurred_at=snapshot["captured_at"],
                            idempotency_key=(
                                f"inventory-{snapshot['snapshot_digest'][-16:]}"
                            ),
                        )
                        _render(
                            {
                                "result": "INVENTORIED",
                                "snapshot": snapshot,
                                "manifest": manifest,
                            }
                        )
                        return 0
                    resolved = boundary.resolve_field_pair(
                        specification["target"],
                        specification["replacement"],
                    )
                    target_urn = str(resolved["dataset"]["urn"])
                    manifest = store.materialize(args.campaign_id)
                    if args.campaign_command == "publish":
                        content = render_campaign_summary(manifest)
                        existing = manifest.get("publication")
                        existing_urn = (
                            str(existing["urn"])
                            if isinstance(existing, dict)
                            and isinstance(existing.get("urn"), str)
                            else None
                        )
                        lifecycle_digest = digest_json(boundary.lifecycle(target_urn))
                        receipt = boundary.save_summary(
                            campaign_id=args.campaign_id,
                            target_urn=target_urn,
                            content=content,
                            existing_urn=existing_urn,
                            artifact_root=_campaign_artifact_root(
                                args,
                                "publication",
                            ),
                        )
                        publication_record = {
                            "logical_key": f"campaign/{args.campaign_id}",
                            "urn": receipt["urn"],
                            "content_digest": receipt["content_digest"],
                            "published_manifest_digest": manifest["manifest_digest"],
                            "lifecycle_digest_before": lifecycle_digest,
                            "readback_verified": False,
                        }
                        updated = store.record_publication(
                            args.campaign_id,
                            publication_record,
                            occurred_at=utc_now(),
                            idempotency_key=(
                                f"publication-{receipt['content_digest'][-16:]}"
                            ),
                        )
                        _render(
                            {
                                "result": "PUBLISHED",
                                "publication": updated["publication"],
                                "write_artifact_ids": receipt["artifact_ids"],
                                "manifest": updated,
                            }
                        )
                        return 0
                    publication_value = manifest.get("publication")
                    if not isinstance(publication_value, dict):
                        raise Refusal(
                            "EVIDENCE_PUBLICATION_MISMATCH",
                            "The campaign has no DataHub publication to verify.",
                        )
                    source_manifest = _publication_source_manifest(
                        store,
                        args.campaign_id,
                        str(publication_value["content_digest"]),
                    )
                    expected_content = render_campaign_summary(source_manifest)
                    verification = boundary.verify_summary(
                        campaign_id=args.campaign_id,
                        urn=str(publication_value["urn"]),
                        expected_content=expected_content,
                        target_urn=target_urn,
                        expected_lifecycle_digest=str(
                            publication_value["lifecycle_digest_before"]
                        ),
                        artifact_root=_campaign_artifact_root(
                            args,
                            "publication",
                        ),
                    )
                    if publication_value.get("readback_verified") is True:
                        _render(
                            {
                                "result": "VERIFIED",
                                "publication": publication_value,
                                "manifest": manifest,
                            }
                        )
                        return 0
                    verified_at = utc_now()
                    updated = store.verify_publication(
                        args.campaign_id,
                        {
                            "urn": publication_value["urn"],
                            "content_digest": publication_value["content_digest"],
                            "lifecycle_digest_after": verification[
                                "lifecycle_digest_after"
                            ],
                            "readback_artifact_id": verification[
                                "readback_artifact_id"
                            ],
                            "verified_at": verified_at,
                        },
                        occurred_at=verified_at,
                        idempotency_key=(
                            f"publication-verify-"
                            f"{str(publication_value['content_digest'])[-16:]}"
                        ),
                    )
                    _render(
                        {
                            "result": "VERIFIED",
                            "publication": updated["publication"],
                            "manifest": updated,
                        }
                    )
                    return 0
            with CampaignStore(args.store, writer_id=args.writer_id) as store:
                if args.campaign_command == "create":
                    specification = load_specification(args.specification)
                    manifest = store.create_campaign(
                        specification,
                        occurred_at=args.occurred_at,
                    )
                elif args.campaign_command == "resume":
                    manifest = store.resume(
                        args.campaign_id,
                        CampaignState(args.state),
                        occurred_at=args.occurred_at,
                        idempotency_key=args.idempotency_key,
                    )
                else:
                    manifest = store.materialize(args.campaign_id)
                if args.campaign_command == "export":
                    write_json(args.output, manifest)
                    _render(
                        {
                            "result": "EXPORTED",
                            "campaign_id": args.campaign_id,
                            "manifest_digest": manifest["manifest_digest"],
                            "output": args.output.name,
                        }
                    )
                else:
                    _render({"result": "OK", "manifest": manifest})
                return 0
    except Refusal as refusal:
        _render(refusal.as_dict())
        return 2

    _render(
        {
            "result": "ERROR",
            "refusal_code": "RUNTIME_COMMAND_UNREACHABLE",
            "message": "The requested command could not be dispatched.",
        }
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())

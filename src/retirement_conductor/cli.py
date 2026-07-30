"""Retirement Conductor command-line entry point."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping, Sequence
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
from retirement_conductor.gate import ProducerGateWorkflow, TrustedProducerContext
from retirement_conductor.git_dbt import GitDbtAdapter
from retirement_conductor.git_dbt_config import GitDbtSettings
from retirement_conductor.git_dbt_workflow import GitDbtWorkflow
from retirement_conductor.looker import LookerAdapter
from retirement_conductor.looker_config import LookerSettings
from retirement_conductor.looker_workflow import LookerWorkflow
from retirement_conductor.mcp_http import HttpMCPClient
from retirement_conductor.operator import (
    build_campaign_view,
    render_campaign_explain,
    render_campaign_inspect,
    safe_report_filename,
    write_campaign_report,
)
from retirement_conductor.publication import publication_source_manifest
from retirement_conductor.reconciliation import ReconciliationWorkflow
from retirement_conductor.specification import load_specification
from retirement_conductor.store import CampaignStore
from retirement_conductor.vocabulary import CampaignState, Decision


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
        help="create, replay, inspect, explain, evaluate, resume, or export a campaign",
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
    _add_campaign_selection(inspect)
    _add_runtime_arguments(inspect)
    inspect.add_argument("--manifest", type=Path)
    _add_output_format(inspect, default="text")

    explain = campaign_subparsers.add_parser("explain")
    _add_campaign_selection(explain)
    _add_runtime_arguments(explain)
    explain.add_argument("--manifest", type=Path)
    _add_output_format(explain, default="text")

    resume = campaign_subparsers.add_parser("resume")
    _add_campaign_selection(resume)
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
    _add_runtime_arguments(resume)
    _add_output_format(resume, default="text")

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
        if command == "apply":
            operation.add_argument("--confirm-plan-digest")
        if command == "validate":
            operation.add_argument("--expires-at")
    authorize = git_dbt_subparsers.add_parser("authorize")
    _add_live_campaign_arguments(authorize)
    authorize.add_argument("--principal")
    authorize.add_argument("--authorized-at", required=True)
    authorize.add_argument("--expires-at", required=True)

    looker = adapter_subparsers.add_parser(
        "looker",
        help="operate the bounded saved-Look adapter",
    )
    looker_subparsers = looker.add_subparsers(
        dest="adapter_command",
        required=True,
    )
    for command in ("preflight", "plan", "apply", "compensate", "validate"):
        operation = looker_subparsers.add_parser(command)
        _add_live_campaign_arguments(operation)
        if command in {"apply", "compensate"}:
            operation.add_argument("--occurred-at")
        if command == "apply":
            operation.add_argument("--confirm-plan-digest")
        if command == "validate":
            operation.add_argument("--expires-at")
    looker_authorize = looker_subparsers.add_parser("authorize")
    _add_live_campaign_arguments(looker_authorize)
    looker_authorize.add_argument("--principal", required=True)
    looker_authorize.add_argument("--authorized-at", required=True)
    looker_authorize.add_argument("--expires-at", required=True)

    producer = subparsers.add_parser(
        "producer",
        help="prepare an exact short-lived producer retirement plan",
    )
    producer_subparsers = producer.add_subparsers(
        dest="producer_command",
        required=True,
    )
    producer_plan = producer_subparsers.add_parser("plan")
    _add_live_campaign_arguments(producer_plan)
    _add_producer_path_arguments(producer_plan)
    producer_plan.add_argument("--expires-at", required=True)

    gate = subparsers.add_parser(
        "gate",
        help="verify and consume one exact producer retirement plan",
    )
    _add_live_campaign_arguments(gate)
    _add_producer_path_arguments(gate)
    gate.add_argument("--plan", type=Path)

    report = subparsers.add_parser(
        "report",
        help="build a deterministic report from canonical campaign state",
    )
    report_subparsers = report.add_subparsers(
        dest="report_command",
        required=True,
    )
    report_build = report_subparsers.add_parser("build")
    _add_live_campaign_arguments(report_build)
    report_build.add_argument("--manifest", type=Path)
    report_build.add_argument("--output", type=Path)
    report_build.add_argument(
        "--public",
        action="store_true",
        help="redact identities and sensitive source details for public export",
    )
    _add_output_format(report_build, default="text")
    return parser


def _add_store_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--writer-id", required=True)


def _add_campaign_selection(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("campaign_id", nargs="?")
    parser.add_argument("--campaign", dest="selected_campaign_id")


def _add_output_format(
    parser: argparse.ArgumentParser,
    *,
    default: str,
) -> None:
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default=default,
    )


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


def _add_producer_path_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--producer-repository",
        type=Path,
        default=Path(os.environ.get("RETIREMENT_CONDUCTOR_PRODUCER_REPOSITORY", ".")),
    )
    parser.add_argument(
        "--producer-source-marker",
        type=Path,
        default=Path(
            os.environ.get(
                "RETIREMENT_CONDUCTOR_PRODUCER_SOURCE_MARKER",
                "fixtures/producer/retire-order-status.json",
            )
        ),
    )
    parser.add_argument(
        "--sentinel-root",
        type=Path,
        default=Path(
            os.environ.get(
                "RETIREMENT_CONDUCTOR_SENTINEL_ROOT",
                ".retirement-conductor/producer-sentinels",
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


def _looker_workflow(
    args: argparse.Namespace,
    store: CampaignStore,
) -> LookerWorkflow:
    return LookerWorkflow(
        store=store,
        adapter=LookerAdapter(LookerSettings.from_environment()),
        artifact_directory=Path(args.artifact_dir),
        boundary=(_datahub_boundary() if args.adapter_command == "preflight" else None),
    )


def _git_dbt_adapter_for_campaign(
    store: CampaignStore,
    campaign_id: str,
) -> GitDbtAdapter:
    environment = dict(os.environ)
    if not environment.get("GIT_DBT_REPOSITORY_ROOT", "").strip():
        repositories = store.specification(campaign_id)["evidence"]["repositories"]
        if len(repositories) != 1:
            raise Refusal(
                "SOURCE_GIT_UNAVAILABLE",
                "The gate requires one exact configured Git/dbt repository.",
            )
        environment["GIT_DBT_REPOSITORY_ROOT"] = str(repositories[0]["path"])
    return GitDbtAdapter(GitDbtSettings.from_environment(environment))


def _producer_gate_workflow(
    args: argparse.Namespace,
    store: CampaignStore,
    *,
    with_datahub: bool,
    with_git_dbt: bool,
) -> ProducerGateWorkflow:
    return ProducerGateWorkflow(
        store=store,
        artifact_directory=Path(args.artifact_dir),
        producer_repository_root=args.producer_repository,
        producer_source_marker=args.producer_source_marker,
        sentinel_root=args.sentinel_root,
        boundary=(_datahub_boundary() if with_datahub else None),
        git_dbt=(
            _git_dbt_adapter_for_campaign(store, args.campaign_id)
            if with_git_dbt
            else None
        ),
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


def _selected_campaign_id(args: argparse.Namespace) -> str:
    positional = getattr(args, "campaign_id", None)
    selected = getattr(args, "selected_campaign_id", None)
    if positional and selected and positional != selected:
        raise Refusal(
            "SPEC_SCHEMA_INVALID",
            "The positional and --campaign identifiers do not match.",
        )
    campaign_id = selected or positional
    if not isinstance(campaign_id, str) or not campaign_id.strip():
        raise Refusal(
            "SPEC_SCHEMA_INVALID",
            "The command requires one campaign identifier.",
        )
    return campaign_id


def _load_manifest_artifact(path: Path, campaign_id: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Refusal(
            "INTEGRITY_DIGEST_MISMATCH",
            "The canonical manifest artifact could not be read.",
            {"error_type": type(exc).__name__},
        ) from exc
    if not isinstance(value, dict):
        raise Refusal(
            "INTEGRITY_DIGEST_MISMATCH",
            "The canonical manifest artifact must be a JSON object.",
        )
    view = build_campaign_view(value)
    manifest_campaign = str(_mapping(view["campaign"])["id"])
    if manifest_campaign != campaign_id:
        raise Refusal(
            "INTEGRITY_DIGEST_MISMATCH",
            "The canonical manifest belongs to another campaign.",
        )
    return value


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


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


def _render_report_result(value: Mapping[str, Any]) -> None:
    print(
        "\n".join(
            [
                f"Report built: {value['output']}",
                f"Decision: {value['decision']}",
                f"Export mode: {value['export_mode']}",
                f"Manifest digest: {value['manifest_digest']}",
            ]
        )
    )


def _render_campaign_command(
    args: argparse.Namespace,
    manifest: Mapping[str, Any],
) -> None:
    view = build_campaign_view(manifest)
    if args.format == "json":
        _render(
            {
                "result": "OK",
                "view": view,
                "manifest": manifest,
            }
        )
    elif args.campaign_command == "explain":
        print(render_campaign_explain(view))
    else:
        print(render_campaign_inspect(view))


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
                    if not args.confirm_plan_digest:
                        raise Refusal(
                            "AUTH_APPROVAL_MISSING",
                            "Apply requires explicit confirmation of the exact "
                            "plan digest. Review the plan and pass "
                            "--confirm-plan-digest.",
                        )
                    result = workflow.apply(
                        args.campaign_id,
                        confirmed_plan_digest=args.confirm_plan_digest,
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
        if args.command == "adapter" and args.adapter_name == "looker":
            with CampaignStore(args.store, writer_id=args.writer_id) as store:
                looker_workflow = _looker_workflow(args, store)
                if args.adapter_command == "preflight":
                    result = looker_workflow.preflight(args.campaign_id)
                elif args.adapter_command == "plan":
                    result = looker_workflow.plan(args.campaign_id)
                elif args.adapter_command == "authorize":
                    result = looker_workflow.authorize(
                        args.campaign_id,
                        principal=args.principal,
                        authorized_at=args.authorized_at,
                        expires_at=args.expires_at,
                    )
                elif args.adapter_command == "apply":
                    if not args.confirm_plan_digest:
                        raise Refusal(
                            "AUTH_APPROVAL_MISSING",
                            "Apply requires explicit confirmation of the exact "
                            "Looker plan digest. Review the plan and pass "
                            "--confirm-plan-digest.",
                        )
                    result = looker_workflow.apply(
                        args.campaign_id,
                        confirmed_plan_digest=args.confirm_plan_digest,
                        occurred_at=args.occurred_at,
                    )
                elif args.adapter_command == "compensate":
                    result = looker_workflow.compensate(
                        args.campaign_id,
                        occurred_at=args.occurred_at,
                    )
                else:
                    result = looker_workflow.validate(
                        args.campaign_id,
                        expires_at=args.expires_at,
                    )
            _render(result)
            return 0
        if args.command == "report" and args.report_command == "build":
            if args.manifest:
                manifest = _load_manifest_artifact(
                    args.manifest,
                    args.campaign_id,
                )
            else:
                with CampaignStore(args.store, writer_id=args.writer_id) as store:
                    manifest = store.materialize(args.campaign_id)
            report_filename = safe_report_filename(args.campaign_id)
            report_directory = report_filename.removesuffix(".html")
            output = args.output or (
                Path(args.artifact_dir) / report_directory / "report" / report_filename
            )
            result = write_campaign_report(
                manifest,
                output,
                public=args.public,
            )
            if args.format == "json":
                _render(result)
            else:
                _render_report_result(result)
            return 0
        if (
            args.command == "campaign"
            and args.campaign_command in {"inspect", "explain"}
            and args.manifest
        ):
            campaign_id = _selected_campaign_id(args)
            manifest = _load_manifest_artifact(args.manifest, campaign_id)
            _render_campaign_command(args, manifest)
            return 0
        if args.command == "producer" and args.producer_command == "plan":
            with CampaignStore(args.store, writer_id=args.writer_id) as store:
                producer_workflow = _producer_gate_workflow(
                    args,
                    store,
                    with_datahub=False,
                    with_git_dbt=True,
                )
                result = producer_workflow.prepare(
                    args.campaign_id,
                    context=TrustedProducerContext.from_environment(),
                    expires_at=args.expires_at,
                )
            _render(result)
            return 0
        if args.command == "gate":
            with CampaignStore(args.store, writer_id=args.writer_id) as store:
                manifest = store.materialize(args.campaign_id)
                ready = manifest["decision"] == Decision.READY_TO_RETIRE
                gate_workflow = _producer_gate_workflow(
                    args,
                    store,
                    with_datahub=ready,
                    with_git_dbt=ready,
                )
                result = gate_workflow.execute(
                    args.campaign_id,
                    context=TrustedProducerContext.from_environment(),
                    plan_path=args.plan,
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
                    source_manifest = publication_source_manifest(
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
                    campaign_id = _selected_campaign_id(args)
                    manifest = store.resume(
                        campaign_id,
                        CampaignState(args.state),
                        occurred_at=args.occurred_at,
                        idempotency_key=args.idempotency_key,
                    )
                elif args.campaign_command in {"inspect", "explain"}:
                    campaign_id = _selected_campaign_id(args)
                    manifest = store.materialize(campaign_id)
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
                elif args.campaign_command in {"inspect", "explain", "resume"}:
                    _render_campaign_command(args, manifest)
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

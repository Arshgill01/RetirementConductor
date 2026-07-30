"""Retirement Conductor command-line entry point."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from retirement_conductor.canonical import write_json
from retirement_conductor.errors import Refusal
from retirement_conductor.events import (
    event_stream_digest,
    manifest_from_projection,
    project_events,
)
from retirement_conductor.fixtures import run_fixture
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
    evaluate.add_argument("source", type=Path)

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
    return parser


def _add_store_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--writer-id", required=True)


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
        if args.command == "campaign":
            if args.campaign_command in {"replay", "evaluate"}:
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

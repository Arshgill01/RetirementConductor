"""Retirement Conductor command-line entry point."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from retirement_conductor.errors import Refusal
from retirement_conductor.fixtures import run_fixture
from retirement_conductor.specification import load_specification


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
    return parser


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

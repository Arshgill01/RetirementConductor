#!/usr/bin/env python3
"""Export one verified campaign as an explicitly recorded Workbench view."""

from __future__ import annotations

import argparse
from pathlib import Path

from retirement_conductor.canonical import write_json
from retirement_conductor.store import CampaignStore
from retirement_conductor.workbench import build_workbench_view


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--writer-id", required=True)
    parser.add_argument("--campaign", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    with CampaignStore(args.store, writer_id=args.writer_id) as store:
        view = build_workbench_view(
            store.materialize(args.campaign),
            store.events(args.campaign),
            actions_enabled=False,
        )
    view["mode"] = "recorded-evidence"
    write_json(args.output, view)


if __name__ == "__main__":
    main()

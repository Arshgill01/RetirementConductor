from __future__ import annotations

import pytest

from retirement_conductor.cli import build_parser


def test_producer_retire_requires_an_explicit_action() -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["producer", "retire", "--campaign", "campaign-one"])


def test_producer_retire_selects_the_fresh_one_shot_path() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "producer",
            "retire",
            "--campaign",
            "campaign-one",
            "--action",
            "postgres",
        ]
    )

    assert args.command == "producer"
    assert args.producer_command == "retire"
    assert args.action == "postgres"

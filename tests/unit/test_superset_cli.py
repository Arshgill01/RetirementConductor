from __future__ import annotations

from retirement_conductor.cli import build_parser


def test_superset_campaign_commands_are_registered() -> None:
    parser = build_parser()
    common = [
        "--campaign",
        "ret-orders-heterogeneous",
        "--store",
        "campaign.sqlite",
        "--writer-id",
        "operator",
    ]

    plan = parser.parse_args(
        [
            "adapter",
            "superset",
            "plan",
            *common,
            "--consumer",
            "consumer-superset",
            "--datahub-entities",
            "entities.json",
            "--dataset-id",
            "1",
            "--chart-id",
            "1",
            "--legacy-field",
            "legacy_status",
            "--replacement-field",
            "order_status",
        ]
    )
    compensate = parser.parse_args(["adapter", "superset", "compensate", *common])
    reconcile = parser.parse_args(
        [
            "adapter",
            "superset",
            "reconcile",
            *common,
            "--datahub-observation",
            "observation.json",
        ]
    )

    assert plan.adapter_name == "superset"
    assert plan.adapter_command == "plan"
    assert compensate.adapter_command == "compensate"
    assert reconcile.adapter_command == "reconcile"

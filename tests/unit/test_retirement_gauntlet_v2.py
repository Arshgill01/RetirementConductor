from __future__ import annotations

from collections import Counter

from scripts.run_retirement_gauntlet_v2 import (
    comparison_matches,
    verify_frozen_truth,
)


def test_frozen_gauntlet_has_required_balance_and_tiers() -> None:
    corpus, oracle, freeze = verify_frozen_truth()

    assert freeze["frozen_before_product_execution"] is True
    assert len(corpus["cases"]) == 24
    assert Counter(item["family"] for item in corpus["cases"]) == {
        "enum": 8,
        "measure": 8,
        "temporal": 8,
    }
    assert Counter(item["decision"] for item in oracle["cases"]) == {
        "READY_TO_RETIRE": 4,
        "BLOCKED": 6,
        "UNSAFE": 10,
        "REVIEW_REQUIRED": 4,
    }
    assert sum("datahub" in item["tiers"] for item in corpus["cases"]) >= 12
    assert sum("git_dbt" in item["tiers"] for item in corpus["cases"]) >= 8
    assert sum("sequence" in item["tiers"] for item in corpus["cases"]) >= 4
    assert sum(len(item["consumer_ids"]) for item in corpus["cases"]) > 100


def test_comparator_rejects_an_intentionally_corrupt_oracle_result() -> None:
    assert comparison_matches(
        expected_decision="READY_TO_RETIRE",
        expected_codes=[],
        observed_decision="READY_TO_RETIRE",
        observed_codes_value=[],
    )
    assert not comparison_matches(
        expected_decision="UNSAFE",
        expected_codes=[],
        observed_decision="READY_TO_RETIRE",
        observed_codes_value=[],
    )

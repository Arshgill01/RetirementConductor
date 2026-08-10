from __future__ import annotations

import os

import pytest

from scripts.run_postgres_producer_acceptance import run


@pytest.mark.skipif(
    os.environ.get("RC_CP01_RUN_LIVE") != "1",
    reason="set RC_CP01_RUN_LIVE=1 for isolated live PostgreSQL acceptance",
)
def test_live_postgres_producer_acceptance() -> None:
    result = run()

    assert result["recommendation"] == "KEEP"
    assert len(result["refusal_matrix"]) == 16
    assert result["destructive_statements"]["committed"] == 3
    assert result["replay"]["additional_destructive_statements"] == 0
    assert result["service_isolation"]["service_stopped"] is True

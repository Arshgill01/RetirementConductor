from __future__ import annotations

import pytest

from retirement_conductor.errors import Refusal
from retirement_conductor.postgres_producer_config import (
    POSTGRES_CONFIGURATION_INCOMPLETE,
    POSTGRES_ENDPOINT_NOT_LOOPBACK,
    PostgresProducerSettings,
)


def environment(**overrides: str) -> dict[str, str]:
    values = {
        "POSTGRES_PRODUCER_HOST": "127.0.0.1",
        "POSTGRES_PRODUCER_PORT": "25432",
        "POSTGRES_PRODUCER_DATABASE": "rc_cp01_producer",
        "POSTGRES_PRODUCER_OBSERVER_USER": "rc_cp01_observer",
        "POSTGRES_PRODUCER_OBSERVER_PASSWORD": "observer-secret",
        "POSTGRES_PRODUCER_MUTATION_USER": "rc_cp01_mutator",
        "POSTGRES_PRODUCER_MUTATION_PASSWORD": "mutation-secret",
        "POSTGRES_PRODUCER_ALLOWED_TARGET": (
            "rc_cp01_producer/retirement_lab/orders/legacy_status/order_status"
        ),
    }
    values.update(overrides)
    return values


def test_settings_are_apply_off_by_default_and_secret_safe() -> None:
    settings = PostgresProducerSettings.from_environment(environment())

    assert settings.allow_apply is False
    assert settings.allowed_targets[0].table == "orders"
    rendered = str(settings.safe_summary())
    assert "observer-secret" not in rendered
    assert "mutation-secret" not in rendered
    assert settings.safe_summary()["credential_references_present"] == {
        "observer": True,
        "mutation": True,
    }


@pytest.mark.parametrize(
    "host",
    ["db.example.invalid", "10.0.0.3", "0.0.0.0", "localhost.example"],
)
def test_settings_refuse_non_loopback_endpoints(host: str) -> None:
    with pytest.raises(Refusal) as exc_info:
        PostgresProducerSettings.from_environment(
            environment(POSTGRES_PRODUCER_HOST=host)
        )

    assert exc_info.value.code == POSTGRES_ENDPOINT_NOT_LOOPBACK


def test_settings_allow_an_explicitly_empty_allowlist() -> None:
    settings = PostgresProducerSettings.from_environment(
        environment(POSTGRES_PRODUCER_ALLOWED_TARGET="")
    )

    assert settings.allowed_targets == ()


def test_settings_refuse_allowlist_for_another_database() -> None:
    with pytest.raises(Refusal) as exc_info:
        PostgresProducerSettings.from_environment(
            environment(
                POSTGRES_PRODUCER_ALLOWED_TARGET=(
                    "other/retirement_lab/orders/legacy_status/order_status"
                )
            )
        )

    assert exc_info.value.code == POSTGRES_CONFIGURATION_INCOMPLETE

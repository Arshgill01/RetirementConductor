from retirement_conductor.refusals import (
    ALLOWED_FAMILIES,
    REFUSAL_REGISTRY,
    validate_refusal_registry,
)
from retirement_conductor.vocabulary import RefusalCode


def test_every_refusal_code_is_registered_in_a_stable_family() -> None:
    validate_refusal_registry()

    assert set(REFUSAL_REGISTRY) == {code.value for code in RefusalCode}
    assert set(REFUSAL_REGISTRY.values()).issubset(ALLOWED_FAMILIES)

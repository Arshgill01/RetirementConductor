"""Stable fail-closed domain errors."""

from __future__ import annotations

from typing import Any


class Refusal(Exception):
    """An expected refusal that is safe to present to an operator."""

    def __init__(
        self,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.details = details or {}

    def as_dict(self) -> dict[str, Any]:
        """Return a stable JSON-safe representation."""

        return {
            "result": "REFUSED",
            "refusal_code": self.code,
            "message": self.message,
            "details": self.details,
        }

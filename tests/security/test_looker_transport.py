from __future__ import annotations

import json
from email.message import Message
from types import TracebackType
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

import retirement_conductor.looker as looker_module
from retirement_conductor.errors import Refusal
from retirement_conductor.looker import LookerApiClient
from retirement_conductor.looker_config import LookerSettings
from retirement_conductor.vocabulary import EvidenceMode

SECRET = "recognizable-transport-secret"
TOKEN = "recognizable-access-token"


class JsonResponse:
    def __init__(self, value: Any, *, encoded: bool = False) -> None:
        if encoded:
            self.payload = value.encode() if isinstance(value, str) else bytes(value)
        else:
            self.payload = json.dumps(value).encode()

    def __enter__(self) -> JsonResponse:
        return self

    def __exit__(
        self,
        _exception_type: type[BaseException] | None,
        _exception: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


class SequencedOpener:
    def __init__(self, outcomes: list[JsonResponse | BaseException]) -> None:
        self.outcomes = outcomes
        self.requests: list[Request] = []

    def __call__(self, request: Request, **_kwargs: Any) -> JsonResponse:
        self.requests.append(request)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def settings(*, max_retries: int) -> LookerSettings:
    return LookerSettings(
        base_url="http://127.0.0.1:19999",
        client_id="fixture-client",
        client_secret=SECRET,
        platform_instance="retirement-disposable",
        project_id="retirement_project",
        model_id="commerce",
        explore_id="orders",
        folder_id="9",
        content_target="look:41",
        legacy_reference="orders.legacy_status",
        replacement_reference="orders.order_status",
        datahub_urn="urn:li:dashboard:(looker,retirement-disposable.look.41)",
        graph_snapshot_digest=f"sha256:{'7' * 64}",
        mode=EvidenceMode.FIXTURE,
        allow_apply=True,
        max_retries=max_retries,
        timeout_seconds=1,
    )


def client_with_token(
    *,
    max_retries: int,
    sleeps: list[float],
) -> LookerApiClient:
    client = LookerApiClient(settings(max_retries=max_retries), sleep=sleeps.append)
    client._token = TOKEN
    return client


def http_error(code: int, *, retry_after: str | None = None) -> HTTPError:
    headers = Message()
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    return HTTPError(
        f"https://example.invalid/{SECRET}",
        code,
        f"upstream response containing {SECRET}",
        headers,
        None,
    )


def test_reads_retry_rate_limit_connection_loss_and_server_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleeps: list[float] = []
    opener = SequencedOpener(
        [
            http_error(429, retry_after="99"),
            URLError(f"connection failed with {SECRET}"),
            http_error(503),
            JsonResponse({"id": "41"}),
        ]
    )
    monkeypatch.setattr(looker_module, "urlopen", opener)
    client = client_with_token(max_retries=3, sleeps=sleeps)

    result = client.request("GET", "/looks/41")

    assert result == {"id": "41"}
    assert len(opener.requests) == 4
    assert sleeps == [2.0, 0.5, 1.0]


def test_invalid_read_response_is_retried_without_leaking_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleeps: list[float] = []
    opener = SequencedOpener(
        [
            JsonResponse(f'{{"value":"{SECRET}"', encoded=True),
            JsonResponse({"result": "ok"}),
        ]
    )
    monkeypatch.setattr(looker_module, "urlopen", opener)
    client = client_with_token(max_retries=1, sleeps=sleeps)

    assert client.request("GET", "/looks/41") == {"result": "ok"}
    assert len(opener.requests) == 2
    assert sleeps == [0.25]


@pytest.mark.parametrize(
    ("status", "expected_code"),
    [
        (401, "SOURCE_LOOKER_PERMISSION_DENIED"),
        (403, "SOURCE_LOOKER_PERMISSION_DENIED"),
        (404, "IDENTITY_NOT_FOUND"),
        (409, "SOURCE_FINGERPRINT_MISMATCH"),
        (422, "VALIDATION_RECEIPT_FAILED"),
        (429, "SOURCE_LOOKER_UNAVAILABLE"),
        (500, "SOURCE_LOOKER_UNAVAILABLE"),
    ],
)
def test_http_refusals_are_actionable_and_secret_safe(
    monkeypatch: pytest.MonkeyPatch,
    status: int,
    expected_code: str,
) -> None:
    opener = SequencedOpener([http_error(status)])
    monkeypatch.setattr(looker_module, "urlopen", opener)
    client = client_with_token(max_retries=0, sleeps=[])

    with pytest.raises(Refusal) as raised:
        client.request(
            "GET",
            "/looks/41",
            query={"fields": SECRET},
        )

    rendered = json.dumps(raised.value.as_dict())
    assert raised.value.code == expected_code
    assert raised.value.details["status"] == status
    assert raised.value.details["retry_count"] == 0
    assert SECRET not in rendered
    assert TOKEN not in rendered
    assert SECRET not in str(raised.value)


@pytest.mark.parametrize(
    "outcome",
    [
        http_error(408),
        http_error(425),
        http_error(500),
        http_error(503),
        TimeoutError(f"timeout containing {SECRET}"),
        URLError(f"connection failed with {SECRET}"),
        JsonResponse(f'{{"value":"{SECRET}"', encoded=True),
    ],
)
def test_ambiguous_mutation_failures_are_never_retried(
    monkeypatch: pytest.MonkeyPatch,
    outcome: JsonResponse | BaseException,
) -> None:
    sleeps: list[float] = []
    opener = SequencedOpener([outcome])
    monkeypatch.setattr(looker_module, "urlopen", opener)
    client = client_with_token(max_retries=5, sleeps=sleeps)

    with pytest.raises(Refusal) as raised:
        client.request(
            "PATCH",
            "/looks/41",
            body={"query_id": SECRET},
            mutation=True,
        )

    rendered = json.dumps(raised.value.as_dict())
    assert raised.value.code == "APPLY_OUTCOME_UNKNOWN"
    assert len(opener.requests) == 1
    assert sleeps == []
    assert SECRET not in rendered
    assert TOKEN not in rendered


@pytest.mark.parametrize(
    ("status", "expected_code"),
    [
        (401, "SOURCE_LOOKER_PERMISSION_DENIED"),
        (403, "SOURCE_LOOKER_PERMISSION_DENIED"),
        (404, "IDENTITY_NOT_FOUND"),
        (409, "SOURCE_FINGERPRINT_MISMATCH"),
        (422, "VALIDATION_RECEIPT_FAILED"),
        (429, "SOURCE_LOOKER_UNAVAILABLE"),
    ],
)
def test_definitive_mutation_refusals_are_not_retried(
    monkeypatch: pytest.MonkeyPatch,
    status: int,
    expected_code: str,
) -> None:
    opener = SequencedOpener([http_error(status)])
    monkeypatch.setattr(looker_module, "urlopen", opener)
    client = client_with_token(max_retries=5, sleeps=[])

    with pytest.raises(Refusal) as raised:
        client.request(
            "PATCH",
            "/looks/41",
            body={"query_id": "q-after"},
            mutation=True,
        )

    assert raised.value.code == expected_code
    assert len(opener.requests) == 1

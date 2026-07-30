from __future__ import annotations

from email.message import Message
from urllib.error import HTTPError

import pytest

from retirement_conductor import datahub_http
from retirement_conductor.datahub_http import DataHubGraphClient
from retirement_conductor.errors import Refusal
from retirement_conductor.vocabulary import RefusalCode


def test_graph_client_classifies_permission_failure_without_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def deny(*_args: object, **_kwargs: object) -> None:
        raise HTTPError(
            "http://datahub.test/config",
            403,
            "forbidden",
            Message(),
            None,
        )

    monkeypatch.setattr(datahub_http, "urlopen", deny)
    client = DataHubGraphClient(
        "http://datahub.test",
        token="must-not-appear",
        timeout_seconds=1,
    )

    with pytest.raises(Refusal) as caught:
        client.server_config()

    assert caught.value.code == RefusalCode.SOURCE_DATAHUB_PERMISSION_DENIED
    assert "must-not-appear" not in str(caught.value.as_dict())

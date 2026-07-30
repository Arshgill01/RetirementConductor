from __future__ import annotations

import json
from pathlib import Path

from retirement_conductor.cli import main

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "fixtures/campaigns/blocked"


def test_campaign_replay_and_evaluate_share_manifest_digest(capsys: object) -> None:
    replay_exit = main(["campaign", "replay", str(FIXTURE)])
    assert replay_exit == 0
    replay = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]

    evaluate_exit = main(["campaign", "evaluate", str(FIXTURE)])
    assert evaluate_exit == 0
    evaluation = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]

    assert replay["result"] == "REPLAYED"
    assert replay["event_count"] == 3
    assert replay["manifest"]["decision"] == "BLOCKED"
    assert evaluation["decision"] == "BLOCKED"
    assert replay["manifest"]["manifest_digest"] == evaluation["manifest_digest"]


def test_campaign_replay_refuses_tampered_event(
    tmp_path: Path,
    capsys: object,
) -> None:
    fixture = json.loads((FIXTURE / "events.json").read_text(encoding="utf-8"))
    fixture["events"][1]["payload"]["consumers"][0]["disposition"] = "VALIDATED"
    tampered = tmp_path / "events.json"
    tampered.write_text(json.dumps(fixture), encoding="utf-8")

    exit_code = main(["campaign", "replay", str(tampered)])

    assert exit_code == 2
    output = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert output["refusal_code"].startswith("INTEGRITY_")

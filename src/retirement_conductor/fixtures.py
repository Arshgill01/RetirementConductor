"""Deterministic fixture execution for executable contract evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from retirement_conductor import __version__
from retirement_conductor.canonical import (
    digest_json,
    verify_digest,
    with_digest,
    write_json,
)
from retirement_conductor.errors import Refusal
from retirement_conductor.paths import (
    require_allowed_target,
    resolve_scoped_path,
    verify_source_fingerprint,
)
from retirement_conductor.schemas import validate_schema
from retirement_conductor.specification import load_specification
from retirement_conductor.vocabulary import (
    CampaignState,
    ConsumerDisposition,
    Decision,
    EvidenceMode,
    EvidenceStatus,
    RefusalCode,
)


def repository_root() -> Path:
    """Return the source-checkout root when one is available."""

    return Path(__file__).resolve().parents[2]


def fixture_data_root() -> Path:
    """Locate packaged fixture data or fixture data in a source checkout."""

    packaged = Path(__file__).resolve().parent / "fixture_data"
    if packaged.is_dir():
        return packaged
    return repository_root() / "fixtures"


def load_scenario(path: Path) -> dict[str, Any]:
    """Load one strict deterministic scenario."""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Refusal(
            RefusalCode.SPEC_PARSE_FAILED,
            "The fixture scenario could not be parsed.",
            {"file": path.name, "error_type": type(exc).__name__},
        ) from exc
    if not isinstance(value, dict):
        raise Refusal(
            RefusalCode.SPEC_SCHEMA_INVALID,
            "The fixture scenario must be a mapping.",
            {"file": path.name},
        )
    validate_schema("fixture-scenario", value)
    return value


def _identity_refusal(match_count: int) -> None:
    if match_count == 0:
        raise Refusal(
            RefusalCode.IDENTITY_NOT_FOUND,
            "No exact native identity matched the observed consumer.",
            {"match_count": 0},
        )
    if match_count != 1:
        raise Refusal(
            RefusalCode.IDENTITY_AMBIGUOUS,
            "More than one native identity matched the observed consumer.",
            {"match_count": match_count},
        )


def _required_evidence_refusal(specification: dict[str, Any], status: str) -> None:
    if specification["evidence"]["datahub"]["required"] and (
        status != EvidenceStatus.COMPLETE
    ):
        raise Refusal(
            RefusalCode.EVIDENCE_REQUIRED_SOURCE_INCOMPLETE,
            "A required evidence source is not complete and fresh.",
            {"source_id": "datahub", "status": status},
        )


def _event(
    sequence: int,
    campaign_id: str,
    occurred_at: str,
    event_type: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    unsigned = {
        "schema_version": "1.0.0",
        "sequence": sequence,
        "campaign_id": campaign_id,
        "occurred_at": occurred_at,
        "event_type": event_type,
        "payload": payload,
    }
    return with_digest(unsigned, "event_digest")


def _build_envelope(
    specification: dict[str, Any],
    scenario: dict[str, Any],
) -> dict[str, Any]:
    datahub = specification["evidence"]["datahub"]
    raw_claim = {
        "consumer_id": scenario["consumer"]["id"],
        "datahub_urn": scenario["consumer"]["datahub_urn"],
        "match_count": scenario["identity_match_count"],
    }
    envelope = {
        "schema_version": "1.0.0",
        "captured_at": scenario["captured_at"],
        "mode": EvidenceMode.FIXTURE,
        "sources": [
            {
                "id": "datahub",
                "required": datahub["required"],
                "status": scenario["evidence_status"],
                "source_version": "fixture-datahub/1.0",
                "identity": "public-fixture",
                "scope": {
                    "direction": datahub["direction"],
                    "max_hops": datahub["max_hops"],
                    "filters": datahub["platform_filters"],
                    "pages": 1,
                    "reported_total": 1,
                    "returned_total": 1,
                },
                "freshness": {
                    "observed_at": scenario["captured_at"],
                    "source_updated_at": scenario["captured_at"],
                    "maximum_age_seconds": datahub["maximum_age_seconds"],
                },
                "permissions": {
                    "principal": "fixture-principal",
                    "effective_scope": "controlled public fixture only",
                },
                "limitations": [
                    "Controlled fixture evidence is not a live DataHub observation."
                ],
                "artifact_ids": [digest_json(raw_claim)],
            }
        ],
    }
    finalized = with_digest(envelope, "envelope_digest")
    validate_schema("evidence-envelope", finalized)
    verify_digest(finalized, "envelope_digest")
    return finalized


def _build_receipt(
    specification: dict[str, Any],
    scenario: dict[str, Any],
    source_fingerprint: str,
) -> dict[str, Any]:
    target = scenario["source_path"]
    plan_content = {
        "legacy_field": specification["target"]["field"],
        "replacement_field": specification["replacement"]["field"],
        "proposed_targets": [target],
        "approved_targets": [target],
        "source_fingerprint": source_fingerprint,
    }
    plan_digest = digest_json(plan_content)
    validation_artifact = digest_json(
        {
            "mode": "fixture",
            "result": "PASSED",
            "source_fingerprint": source_fingerprint,
            "target": target,
        }
    )
    receipt = {
        "schema_version": "1.0.0",
        "receipt_id": f"receipt-{plan_digest.removeprefix('sha256:')[:16]}",
        "campaign_id": specification["campaign"]["id"],
        "consumer_id": scenario["consumer"]["id"],
        "datahub_urn": scenario["consumer"]["datahub_urn"],
        "native_identity": scenario["consumer"]["native_identity"],
        "adapter": {
            "name": "fixture-git-dbt",
            "version": __version__,
            "mode": EvidenceMode.FIXTURE,
        },
        "source_before": {
            "version": scenario["source_version"],
            "fingerprint": source_fingerprint,
        },
        "plan": {
            "digest": plan_digest,
            "proposed_targets": [target],
            "approved_targets": [target],
        },
        "apply": {
            "result": "SIMULATED",
            "actual_targets": [],
            "before_fingerprint": source_fingerprint,
            "after_fingerprint": source_fingerprint,
            "native_change_ids": [],
        },
        "validation": {
            "result": "PASSED",
            "validator": "deterministic fixture validator",
            "validator_version": __version__,
            "artifact_ids": [validation_artifact],
        },
        "compensation": {
            "available": True,
            "exercised": False,
            "result": "NOT_NEEDED",
        },
        "captured_at": scenario["captured_at"],
        "expires_at": None,
        "limitations": ["No native mutation or live validator ran in fixture mode."],
        "terminal_disposition": ConsumerDisposition.VALIDATED,
    }
    finalized = with_digest(receipt, "receipt_digest")
    validate_schema("consumer-receipt", finalized)
    verify_digest(finalized, "receipt_digest")
    return finalized


def run_fixture(
    specification_path: Path,
    *,
    scenario_path: Path | None = None,
    output_directory: Path | None = None,
    fixture_repository: Path | None = None,
) -> dict[str, Any]:
    """Run one deterministic, non-live campaign fixture."""

    data_root = fixture_data_root()
    scenario_path = scenario_path or data_root / "scenarios/valid.json"
    output_directory = output_directory or Path.cwd() / "artifacts/public/phase00"
    fixture_repository = fixture_repository or data_root / "repository"

    specification = load_specification(specification_path)
    scenario = load_scenario(scenario_path)

    _required_evidence_refusal(specification, scenario["evidence_status"])
    _identity_refusal(scenario["identity_match_count"])
    if not scenario["replacement_compatible"]:
        raise Refusal(
            RefusalCode.SPEC_REPLACEMENT_INCOMPATIBLE,
            "The fixture replacement is not declared compatible.",
        )

    source_path = resolve_scoped_path(scenario["source_path"], fixture_repository)
    require_allowed_target(
        scenario["source_path"],
        specification["authorization"]["allowed_paths"],
    )
    source_fingerprint = verify_source_fingerprint(
        source_path,
        scenario["expected_source_fingerprint"],
    )

    envelope = _build_envelope(specification, scenario)
    receipt = _build_receipt(specification, scenario, source_fingerprint)
    campaign_id = specification["campaign"]["id"]
    occurred_at = scenario["captured_at"]
    events = [
        _event(
            1,
            campaign_id,
            occurred_at,
            "SPECIFICATION_VALIDATED",
            {"specification_digest": specification["specification_digest"]},
        ),
        _event(
            2,
            campaign_id,
            occurred_at,
            "EVIDENCE_CAPTURED",
            {
                "envelope_digest": envelope["envelope_digest"],
                "mode": EvidenceMode.FIXTURE,
            },
        ),
        _event(
            3,
            campaign_id,
            occurred_at,
            "CONSUMER_IDENTIFIED",
            {
                "consumer_id": scenario["consumer"]["id"],
                "identity_match_count": 1,
            },
        ),
        _event(
            4,
            campaign_id,
            occurred_at,
            "RECEIPT_RECORDED",
            {"receipt_digest": receipt["receipt_digest"]},
        ),
        _event(
            5,
            campaign_id,
            occurred_at,
            "POLICY_EVALUATED",
            {
                "decision": Decision.BLOCKED,
                "refusal_code": RefusalCode.EVIDENCE_MODE_NOT_LIVE,
            },
        ),
    ]
    event_log = with_digest(
        {
            "schema_version": "1.0.0",
            "mode": EvidenceMode.FIXTURE,
            "events": events,
        },
        "event_log_digest",
    )
    blocker = {
        "code": RefusalCode.EVIDENCE_MODE_NOT_LIVE,
        "message": "Fixture evidence cannot satisfy a live-evidence policy.",
    }
    manifest = with_digest(
        {
            "schema_version": "1.0.0",
            "campaign": {
                "id": campaign_id,
                "name": specification["campaign"]["name"],
                "state": CampaignState.BLOCKED,
            },
            "specification_digest": specification["specification_digest"],
            "policy": {
                "id": specification["policy"]["id"],
                "version": specification["policy"]["version"],
                "requires_live_evidence": True,
            },
            "target": specification["target"],
            "replacement": specification["replacement"],
            "evidence_envelope": envelope,
            "snapshot_digests": [envelope["envelope_digest"]],
            "consumers": [
                {
                    "id": scenario["consumer"]["id"],
                    "disposition": ConsumerDisposition.VALIDATED,
                    "receipt_digest": receipt["receipt_digest"],
                }
            ],
            "receipt_digests": [receipt["receipt_digest"]],
            "blockers": [blocker],
            "transition_history": [
                {
                    "sequence": event["sequence"],
                    "event_type": event["event_type"],
                    "event_digest": event["event_digest"],
                }
                for event in events
            ],
            "publication": None,
            "decision": Decision.BLOCKED,
            "generated_at": occurred_at,
        },
        "manifest_digest",
    )
    validate_schema("campaign-manifest", manifest)
    verify_digest(manifest, "manifest_digest")

    artifacts = {
        "normalized-spec.json": specification,
        "evidence-envelope.json": envelope,
        "events.json": event_log,
        "receipt.json": receipt,
        "manifest.json": manifest,
    }
    for filename, value in artifacts.items():
        write_json(output_directory / filename, value)

    summary = {
        "result": "FIXTURE_COMPLETE",
        "mode": EvidenceMode.FIXTURE,
        "decision": Decision.BLOCKED,
        "refusal_code": RefusalCode.EVIDENCE_MODE_NOT_LIVE,
        "manifest_digest": manifest["manifest_digest"],
        "event_log_digest": event_log["event_log_digest"],
        "artifacts": {
            filename: digest_json(value)
            for filename, value in sorted(artifacts.items())
        },
    }
    write_json(output_directory / "summary.json", summary)
    return summary

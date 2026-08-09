"""Failure-closed semantic validation planning for one Git/dbt migration."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, NoReturn

from retirement_conductor.canonical import (
    digest_bytes,
    digest_json,
    verify_digest,
    with_digest,
)
from retirement_conductor.clock import parse_timestamp
from retirement_conductor.errors import Refusal
from retirement_conductor.records import validate_approval
from retirement_conductor.schemas import validate_schema
from retirement_conductor.vocabulary import RefusalCode

SEMANTIC_TEMPLATE_VERSION = "semantic-dbt-v1"
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
CHECK_ID = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
SAFE_CAMPAIGN = re.compile(r"[^a-z0-9_-]+")
SAFE_EVIDENCE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")

PRIMITIVE_PARAMETER_KEYS: dict[str, frozenset[str]] = {
    "type_compatibility": frozenset(),
    "null_rate_bound": frozenset(
        {"max_increase_fraction", "max_replacement_null_rate"}
    ),
    "accepted_values_coverage": frozenset({"accepted_values", "minimum_coverage"}),
    "category_mapping_completeness": frozenset({"mapping", "required_coverage"}),
    "row_count_coverage": frozenset({"minimum_coverage"}),
    "keyed_row_coverage": frozenset({"key_columns", "minimum_coverage"}),
    "aggregate_parity": frozenset(
        {"measure", "group_by", "time_grain", "tolerance_fraction"}
    ),
    "exact_model_output_parity": frozenset(),
    "freshness_window": frozenset({"maximum_age_seconds"}),
}

NON_MATERIALIZED_PRIMITIVES = {"type_compatibility", "freshness_window"}


@dataclass(frozen=True)
class SemanticPolicy:
    """Deterministic bounds for model-proposed semantic checks."""

    maximum_tolerance_fraction: float = 0.05
    minimum_coverage: float = 0.95
    maximum_freshness_seconds: int = 3600
    allowed_key_columns: tuple[str, ...] = ()
    allowed_group_columns: tuple[str, ...] = ()
    allowed_measures: tuple[str, ...] = ()


def freeze_semantic_plan(
    proposal: Mapping[str, Any],
    *,
    git_plan: Mapping[str, Any],
    evidence_snapshot: Mapping[str, Any],
    trusted_now: datetime,
    policy: SemanticPolicy | None = None,
) -> dict[str, Any]:
    """Validate a model proposal against current evidence and freeze its digest."""

    policy_value = policy or SemanticPolicy()
    git_value = dict(git_plan)
    verify_digest(git_value, "plan_digest")
    _require_exact_keys(
        proposal,
        {
            "schema_version",
            "campaign_id",
            "git_plan_digest",
            "repository",
            "target",
            "replacement",
            "consumer",
            "evidence_snapshot_digest",
            "checks",
        },
        label="semantic proposal",
    )
    if proposal.get("schema_version") != "1.0.0":
        _refuse("The semantic proposal schema version is unsupported.")

    expected = _expected_proposal_identity(git_value)
    for key in (
        "campaign_id",
        "git_plan_digest",
        "repository",
        "target",
        "replacement",
        "consumer",
    ):
        if proposal.get(key) != expected[key]:
            raise Refusal(
                RefusalCode.AUTH_APPROVAL_WRONG_PLAN,
                "The semantic proposal differs from the current campaign plan.",
                {"mismatched_field": key},
            )

    snapshot = _validate_evidence_snapshot(evidence_snapshot, trusted_now=trusted_now)
    if proposal.get("evidence_snapshot_digest") != snapshot["digest"]:
        raise Refusal(
            RefusalCode.SOURCE_FINGERPRINT_MISMATCH,
            "The proposal was created for another evidence snapshot.",
        )
    checks = _validate_checks(
        proposal.get("checks"),
        snapshot=snapshot,
        expected=expected,
        policy=policy_value,
    )
    proposal_value = {
        "schema_version": "1.0.0",
        **{key: expected[key] for key in expected},
        "evidence_snapshot_digest": snapshot["digest"],
        "checks": checks,
    }
    proposal_digest = digest_json(proposal_value)
    materializations = _materialization_records(
        str(expected["campaign_id"]),
        checks,
        repository=expected["repository"],
        target=expected["target"],
        replacement=expected["replacement"],
    )
    plan = with_digest(
        {
            "schema_version": "1.0.0",
            **{key: expected[key] for key in expected},
            "evidence_snapshot": snapshot,
            "checks": checks,
            "materializations": materializations,
            "generated_targets": [item["path"] for item in materializations],
            "proposal_digest": proposal_digest,
        },
        "plan_digest",
    )
    validate_schema(
        "semantic-validation-plan",
        plan,
        refusal_code=RefusalCode.INTEGRITY_DIGEST_MISMATCH,
    )
    return plan


def create_semantic_approval(
    plan: Mapping[str, Any],
    *,
    principal: str,
    authorization_digest: str,
    authorized_at: str,
    expires_at: str,
) -> dict[str, Any]:
    """Create one external-human approval bound to the plan and exact file set."""

    value = dict(plan)
    _validate_plan(value)
    return with_digest(
        {
            "schema_version": "1.0.0",
            "approval_id": (
                f"semantic-{value['campaign_id']}-{str(value['plan_digest'])[-12:]}"
            ),
            "campaign_id": value["campaign_id"],
            "plan_digest": value["plan_digest"],
            "source_version": value["repository"]["source_version"],
            "targets": approved_targets(value),
            "principal": principal,
            "scope": ["materialize", "push", "create-pr"],
            "authorization_digest": authorization_digest,
            "authorized_at": authorized_at,
            "expires_at": expires_at,
        },
        "approval_digest",
    )


def approved_targets(plan: Mapping[str, Any]) -> list[str]:
    """Return the exact model and generated test targets under approval."""

    return sorted(
        {
            str(plan["consumer"]["native_target"]),
            *(str(path) for path in plan["generated_targets"]),
        }
    )


def materialize_semantic_tests(
    plan: Mapping[str, Any],
    approval: Mapping[str, Any] | None,
    *,
    repository_root: Path,
    authorization_digest: str,
    trusted_now: datetime,
) -> list[Path]:
    """Write only deterministic, digest-bound dbt singular tests after approval."""

    value = dict(plan)
    _validate_plan(value)
    validate_approval(
        approval,
        campaign_id=str(value["campaign_id"]),
        plan_digest=str(value["plan_digest"]),
        source_version=str(value["repository"]["source_version"]),
        targets=approved_targets(value),
        required_scope=["materialize"],
        authorization_digest=authorization_digest,
        trusted_now=trusted_now,
    )
    root = repository_root.resolve()
    if not root.is_dir() or not (root / ".git").exists():
        raise Refusal(
            RefusalCode.SOURCE_GIT_UNAVAILABLE,
            "Semantic test materialization requires the exact Git repository.",
        )
    materializations = {
        str(item["check_id"]): item for item in value["materializations"]
    }
    written: list[Path] = []
    for check in value["checks"]:
        check_id = str(check["check_id"])
        record = materializations.get(check_id)
        if record is None:
            if check["primitive"] in NON_MATERIALIZED_PRIMITIVES:
                continue
            raise Refusal(
                RefusalCode.INTEGRITY_DIGEST_MISMATCH,
                "A materialized semantic check is absent from the frozen plan.",
            )
        content = render_semantic_test(
            check,
            repository=value["repository"],
            target=value["target"],
            replacement=value["replacement"],
        )
        if digest_bytes(content.encode("utf-8")) != record["content_digest"]:
            raise Refusal(
                RefusalCode.INTEGRITY_DIGEST_MISMATCH,
                "The reviewed semantic test template no longer matches its digest.",
            )
        destination = (root / str(record["path"])).resolve()
        try:
            destination.relative_to(root)
        except ValueError as exc:
            raise Refusal(
                RefusalCode.SCOPE_PATH_OUTSIDE_ROOT,
                "A semantic test target escaped the repository.",
            ) from exc
        if destination.exists() or destination.is_symlink():
            raise Refusal(
                RefusalCode.SOURCE_GIT_FILE_CHANGED,
                "A generated semantic test target already exists.",
                {"path": record["path"]},
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.parent.resolve() != destination.parent:
            raise Refusal(
                RefusalCode.SCOPE_PATH_OUTSIDE_ROOT,
                "A semantic test directory resolves through a symlink.",
            )
        destination.write_text(content, encoding="utf-8")
        written.append(destination)
    return written


def render_semantic_test(
    check: Mapping[str, Any],
    *,
    repository: Mapping[str, Any],
    target: Mapping[str, Any],
    replacement: Mapping[str, Any],
) -> str:
    """Render one reviewed dbt singular-test template without model-authored SQL."""

    primitive = str(check["primitive"])
    parameters = check["parameters"]
    comparison = _dbt_ref(str(repository["comparison_relation"]))
    consumer = _dbt_ref(str(repository["consumer_relation"]))
    target_field = _quoted_identifier(str(target["field"]))
    replacement_field = _quoted_identifier(str(replacement["field"]))
    header = f"-- generated by {SEMANTIC_TEMPLATE_VERSION}; check={check['check_id']}\n"

    if primitive == "null_rate_bound":
        max_increase = _number(parameters["max_increase_fraction"])
        max_rate = _number(parameters["max_replacement_null_rate"])
        return (
            header
            + f"""with rates as (
  select
    avg(case when {target_field} is null then 1.0 else 0.0 end) as target_rate,
    avg(case when {replacement_field} is null then 1.0 else 0.0 end) as replacement_rate
  from {comparison}
)
select * from rates
where replacement_rate > {max_rate}
   or replacement_rate - target_rate > {max_increase}
"""
        )
    if primitive == "accepted_values_coverage":
        values = ", ".join(
            _sql_literal(str(item)) for item in parameters["accepted_values"]
        )
        minimum = _number(parameters["minimum_coverage"])
        return (
            header
            + f"""with coverage as (
  select avg(case when {replacement_field} in ({values}) then 1.0 else 0.0 end) as ratio
  from {comparison}
)
select * from coverage where coalesce(ratio, 0.0) < {minimum}
"""
        )
    if primitive == "category_mapping_completeness":
        pairs = "\n    union all\n".join(
            "select "
            f"{_sql_literal(str(item['target_value']))} as target_value, "
            f"{_sql_literal(str(item['replacement_value']))} as replacement_value"
            for item in parameters["mapping"]
        )
        return (
            header
            + f"""with expected as (
    {pairs}
), mismatches as (
  select source.{target_field}, source.{replacement_field}
  from {comparison} as source
  left join expected
    on source.{target_field} = expected.target_value
   and source.{replacement_field} = expected.replacement_value
  where expected.target_value is null
)
select * from mismatches
"""
        )
    if primitive == "row_count_coverage":
        minimum = _number(parameters["minimum_coverage"])
        return (
            header
            + f"""with counts as (
  select
    (select count(*) from {comparison}) as expected_count,
    (select count(*) from {consumer}) as actual_count
)
select * from counts
where expected_count > 0 and actual_count * 1.0 / expected_count < {minimum}
"""
        )
    if primitive == "keyed_row_coverage":
        keys = [_quoted_identifier(str(item)) for item in parameters["key_columns"]]
        predicate = " and ".join(f"actual.{key} = expected.{key}" for key in keys)
        missing = f"actual.{keys[0]} is null"
        minimum = _number(parameters["minimum_coverage"])
        return (
            header
            + f"""with coverage as (
  select avg(case when {missing} then 0.0 else 1.0 end) as ratio
  from {comparison} as expected
  left join {consumer} as actual on {predicate}
)
select * from coverage where coalesce(ratio, 0.0) < {minimum}
"""
        )
    if primitive == "aggregate_parity":
        measure = _quoted_identifier(str(parameters["measure"]))
        groups = [_quoted_identifier(str(item)) for item in parameters["group_by"]]
        group_list = ", ".join(groups)
        join = " and ".join(f"expected.{item} = actual.{item}" for item in groups)
        tolerance = _number(parameters["tolerance_fraction"])
        return (
            header
            + f"""with expected as (
  select {group_list}, sum({measure}) as value from {comparison} group by {group_list}
), actual as (
  select {group_list}, sum({measure}) as value from {consumer} group by {group_list}
)
select expected.*, actual.value as actual_value
from expected left join actual on {join}
where actual.value is null
   or abs(actual.value - expected.value) > abs(expected.value) * {tolerance}
"""
        )
    if primitive == "exact_model_output_parity":
        return (
            header
            + f"""select {target_field}, {replacement_field}
from {comparison}
where {target_field} is distinct from {replacement_field}
"""
        )
    raise Refusal(
        RefusalCode.SPEC_SCHEMA_INVALID,
        "The semantic primitive has no reviewed dbt materialization.",
        {"primitive": primitive},
    )


def _expected_proposal_identity(git_plan: Mapping[str, Any]) -> dict[str, Any]:
    replacement = git_plan["replacement"]
    return {
        "campaign_id": git_plan["campaign_id"],
        "git_plan_digest": git_plan["plan_digest"],
        "repository": {
            "identity": git_plan["repository"]["identity"],
            "base_branch": git_plan["repository"]["source_branch"],
            "source_version": git_plan["repository"]["source_version"],
            "target_branch": git_plan["repository"]["target_branch"],
            "comparison_relation": _node_name(
                str(replacement["target"].get("dbt_unique_id", "seed.project.orders"))
            ),
            "consumer_relation": _node_name(
                str(git_plan["native_identity"]["dbt_unique_id"])
            ),
        },
        "target": {
            "datahub_urn": replacement["target"].get(
                "datahub_urn", git_plan["datahub_urn"]
            ),
            "field": replacement["target"]["field"],
            "native_type": replacement["target"]["datahub_native_type"],
        },
        "replacement": {
            "datahub_urn": replacement["replacement"].get(
                "datahub_urn", git_plan["datahub_urn"]
            ),
            "field": replacement["replacement"]["field"],
            "native_type": replacement["replacement"]["datahub_native_type"],
        },
        "consumer": {
            "id": git_plan["consumer_id"],
            "datahub_urn": git_plan["datahub_urn"],
            "repository_id": git_plan["repository"]["id"],
            "dbt_unique_id": git_plan["native_identity"]["dbt_unique_id"],
            "native_target": git_plan["target"]["path"],
        },
    }


def _validate_evidence_snapshot(
    evidence_snapshot: Mapping[str, Any], *, trusted_now: datetime
) -> dict[str, Any]:
    _require_exact_keys(
        evidence_snapshot,
        {"digest", "captured_at", "expires_at", "references"},
        label="evidence snapshot",
    )
    value = {
        "digest": evidence_snapshot["digest"],
        "captured_at": evidence_snapshot["captured_at"],
        "expires_at": evidence_snapshot["expires_at"],
        "references": [dict(item) for item in evidence_snapshot["references"]],
    }
    unsigned = {key: item for key, item in value.items() if key != "digest"}
    if value["digest"] != digest_json(unsigned):
        raise Refusal(
            RefusalCode.SOURCE_FINGERPRINT_MISMATCH,
            "The current observation set does not match its digest.",
        )
    captured_at = parse_timestamp(str(value["captured_at"]))
    expires_at = parse_timestamp(str(value["expires_at"]))
    if captured_at > trusted_now or expires_at <= trusted_now:
        raise Refusal(
            RefusalCode.EVIDENCE_REQUIRED_SOURCE_INCOMPLETE,
            "Fresh semantic planning evidence is required.",
        )
    seen: set[str] = set()
    for reference in value["references"]:
        _require_exact_keys(
            reference,
            {
                "evidence_id",
                "kind",
                "subject",
                "source_version",
                "observed_at",
                "artifact_id",
            },
            label="evidence reference",
        )
        evidence_id = str(reference["evidence_id"])
        if not SAFE_EVIDENCE_ID.fullmatch(evidence_id) or evidence_id in seen:
            _refuse("Evidence reference identities must be unique and bounded.")
        seen.add(evidence_id)
        if not str(reference["artifact_id"]).startswith("sha256:"):
            _refuse("Every evidence reference must name a content digest.")
        observed_at = parse_timestamp(str(reference["observed_at"]))
        if observed_at > trusted_now or observed_at > expires_at:
            raise Refusal(
                RefusalCode.EVIDENCE_REQUIRED_SOURCE_INCOMPLETE,
                "An evidence reference is not current for this proposal.",
            )
    return value


def _validate_checks(
    raw_checks: object,
    *,
    snapshot: Mapping[str, Any],
    expected: Mapping[str, Any],
    policy: SemanticPolicy,
) -> list[dict[str, Any]]:
    if not isinstance(raw_checks, list) or not raw_checks or len(raw_checks) > 16:
        _refuse("A semantic proposal requires between one and sixteen checks.")
    evidence = {str(item["evidence_id"]): item for item in snapshot["references"]}
    allowed_subjects = {
        str(expected["target"]["datahub_urn"]),
        str(expected["replacement"]["datahub_urn"]),
        str(expected["consumer"]["datahub_urn"]),
        str(expected["consumer"]["dbt_unique_id"]),
    }
    checks: list[dict[str, Any]] = []
    ids: set[str] = set()
    primitives: set[str] = set()
    for raw in raw_checks:
        if not isinstance(raw, Mapping):
            _refuse("Each semantic check must be a typed object.")
        _require_exact_keys(
            raw,
            {
                "check_id",
                "primitive",
                "parameters",
                "evidence_references",
                "rationale",
                "expected_validator",
                "limitations",
            },
            label="semantic check",
        )
        check_id = str(raw["check_id"])
        primitive = str(raw["primitive"])
        if not CHECK_ID.fullmatch(check_id) or check_id in ids:
            _refuse("Semantic check identifiers must be unique and bounded.")
        if primitive not in PRIMITIVE_PARAMETER_KEYS:
            _refuse("The proposal named an unsupported validation primitive.")
        if primitive in primitives:
            raise Refusal(
                RefusalCode.SPEC_SCHEMA_INVALID,
                "Duplicate or contradictory semantic primitives are refused.",
                {"primitive": primitive},
            )
        ids.add(check_id)
        primitives.add(primitive)
        parameters = raw["parameters"]
        if not isinstance(parameters, Mapping):
            _refuse("Semantic check parameters must be a typed object.")
        _require_exact_keys(
            parameters,
            set(PRIMITIVE_PARAMETER_KEYS[primitive]),
            label=f"{primitive} parameters",
        )
        references = raw["evidence_references"]
        if not isinstance(references, list) or not references:
            _refuse("Every semantic check must cite current DataHub evidence.")
        if len(set(str(item) for item in references)) != len(references):
            _refuse("Semantic evidence references cannot be duplicated.")
        for evidence_id in references:
            observed = evidence.get(str(evidence_id))
            if observed is None:
                raise Refusal(
                    RefusalCode.EVIDENCE_REQUIRED_SOURCE_INCOMPLETE,
                    (
                        "A proposed evidence reference is absent from current "
                        "observations."
                    ),
                    {"evidence_id": evidence_id},
                )
            if str(observed["subject"]) not in allowed_subjects:
                raise Refusal(
                    RefusalCode.IDENTITY_NOT_FOUND,
                    "An evidence reference belongs to another campaign subject.",
                )
        validator = raw["expected_validator"]
        if validator != {"name": "dbt-core", "version_family": "1.x"}:
            raise Refusal(
                RefusalCode.VALIDATION_SCOPE_VIOLATION,
                "Only the reviewed dbt-core validator family is supported.",
            )
        _validate_parameters(primitive, parameters, expected=expected, policy=policy)
        rationale = raw["rationale"]
        limitations = raw["limitations"]
        if not isinstance(rationale, str) or not 1 <= len(rationale) <= 1000:
            _refuse("A bounded rationale is required for every semantic check.")
        if (
            not isinstance(limitations, list)
            or len(limitations) > 16
            or not all(
                isinstance(item, str) and 1 <= len(item) <= 500 for item in limitations
            )
        ):
            _refuse("Semantic limitations must be a bounded string list.")
        checks.append(
            {
                "check_id": check_id,
                "primitive": primitive,
                "parameters": dict(parameters),
                "evidence_references": [str(item) for item in references],
                "rationale": rationale,
                "expected_validator": dict(validator),
                "limitations": list(limitations),
            }
        )
    return checks


def _validate_parameters(
    primitive: str,
    parameters: Mapping[str, Any],
    *,
    expected: Mapping[str, Any],
    policy: SemanticPolicy,
) -> None:
    def fraction(name: str, *, minimum: float = 0.0) -> float:
        value = parameters.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            _refuse(f"{name} must be a numeric fraction.")
        result = float(value)
        if result < minimum or result > 1.0:
            _refuse(f"{name} is outside policy.")
        return result

    if primitive == "type_compatibility":
        if _normalized_type(str(expected["target"]["native_type"])) != _normalized_type(
            str(expected["replacement"]["native_type"])
        ):
            raise Refusal(
                RefusalCode.SPEC_REPLACEMENT_INCOMPATIBLE,
                "The declared field types are incompatible with this primitive.",
            )
    elif primitive == "null_rate_bound":
        if (
            fraction("max_increase_fraction") > policy.maximum_tolerance_fraction
            or fraction("max_replacement_null_rate") > policy.maximum_tolerance_fraction
        ):
            _refuse("The proposed null tolerance exceeds campaign policy.")
    elif primitive == "accepted_values_coverage":
        values = parameters.get("accepted_values")
        if (
            not isinstance(values, list)
            or not values
            or len(values) > 64
            or len(set(str(item) for item in values)) != len(values)
            or not all(
                isinstance(item, str) and 1 <= len(item) <= 128 for item in values
            )
        ):
            _refuse("Accepted values must be a bounded unique string list.")
        fraction("minimum_coverage", minimum=policy.minimum_coverage)
    elif primitive == "category_mapping_completeness":
        mapping = parameters.get("mapping")
        if not isinstance(mapping, list) or not mapping or len(mapping) > 64:
            _refuse("Category mapping must be a bounded non-empty list.")
        targets: set[str] = set()
        for item in mapping:
            if not isinstance(item, Mapping):
                _refuse("Every category mapping entry must be typed.")
            _require_exact_keys(
                item,
                {"target_value", "replacement_value"},
                label="category mapping",
            )
            source = str(item["target_value"])
            replacement = str(item["replacement_value"])
            if (
                not source
                or len(source) > 128
                or not replacement
                or len(replacement) > 128
            ):
                _refuse("Category mapping values must be bounded strings.")
            if source in targets:
                _refuse("Contradictory category mappings are refused.")
            targets.add(source)
        if parameters.get("required_coverage") != 1:
            _refuse("Category mappings must require complete coverage.")
    elif primitive in {"row_count_coverage", "keyed_row_coverage"}:
        fraction("minimum_coverage", minimum=policy.minimum_coverage)
        if primitive == "keyed_row_coverage":
            _validate_allowed_identifiers(
                parameters.get("key_columns"), policy.allowed_key_columns, "key"
            )
    elif primitive == "aggregate_parity":
        if fraction("tolerance_fraction") > policy.maximum_tolerance_fraction:
            _refuse("The proposed aggregate tolerance exceeds campaign policy.")
        _validate_allowed_identifiers(
            parameters.get("group_by"), policy.allowed_group_columns, "group"
        )
        measure = str(parameters.get("measure", ""))
        if measure not in set(policy.allowed_measures) or not IDENTIFIER.fullmatch(
            measure
        ):
            _refuse("The aggregate measure is outside the campaign allowlist.")
        if parameters.get("time_grain") not in {"day", "week", "month"}:
            _refuse("The aggregate time grain is unsupported.")
    elif primitive == "freshness_window":
        age = parameters.get("maximum_age_seconds")
        if (
            isinstance(age, bool)
            or not isinstance(age, int)
            or age < 1
            or age > policy.maximum_freshness_seconds
        ):
            _refuse("The proposed freshness window exceeds campaign policy.")


def _materialization_records(
    campaign_id: str,
    checks: Sequence[Mapping[str, Any]],
    *,
    repository: Mapping[str, Any],
    target: Mapping[str, Any],
    replacement: Mapping[str, Any],
) -> list[dict[str, Any]]:
    slug = SAFE_CAMPAIGN.sub("-", campaign_id.casefold()).strip("-") or "campaign"
    records: list[dict[str, Any]] = []
    for index, check in enumerate(checks, start=1):
        if check["primitive"] in NON_MATERIALIZED_PRIMITIVES:
            continue
        content = render_semantic_test(
            check,
            repository=repository,
            target=target,
            replacement=replacement,
        )
        path = f"tests/retirement_conductor/{slug}/{index:02d}_{check['check_id']}.sql"
        records.append(
            {
                "check_id": check["check_id"],
                "path": path,
                "content_digest": digest_bytes(content.encode("utf-8")),
                "template_version": SEMANTIC_TEMPLATE_VERSION,
            }
        )
    return records


def _validate_plan(plan: dict[str, Any]) -> None:
    validate_schema(
        "semantic-validation-plan",
        plan,
        refusal_code=RefusalCode.INTEGRITY_DIGEST_MISMATCH,
    )
    verify_digest(plan, "plan_digest")
    if approved_targets(plan) != sorted(
        {
            str(plan["consumer"]["native_target"]),
            *(str(item["path"]) for item in plan["materializations"]),
        }
    ):
        raise Refusal(
            RefusalCode.INTEGRITY_DIGEST_MISMATCH,
            "The semantic plan target sets disagree.",
        )
    if list(plan["generated_targets"]) != [
        item["path"] for item in plan["materializations"]
    ]:
        raise Refusal(
            RefusalCode.INTEGRITY_DIGEST_MISMATCH,
            "The generated semantic targets are not canonical.",
        )


def _require_exact_keys(
    value: Mapping[str, Any], expected: set[str], *, label: str
) -> None:
    actual = set(value)
    if actual != expected:
        raise Refusal(
            RefusalCode.SPEC_SCHEMA_INVALID,
            f"The {label} has unsupported or missing fields.",
            {
                "missing": sorted(expected - actual),
                "unsupported": sorted(actual - expected),
            },
        )


def _validate_allowed_identifiers(
    value: object, allowed: Sequence[str], label: str
) -> None:
    if not isinstance(value, list) or not value or len(value) > 8:
        _refuse(f"The {label} columns must be a bounded list.")
    allowed_set = set(allowed)
    if len(set(str(item) for item in value)) != len(value) or any(
        not isinstance(item, str)
        or not IDENTIFIER.fullmatch(item)
        or item not in allowed_set
        for item in value
    ):
        _refuse(f"A proposed {label} column is outside the campaign allowlist.")


def _node_name(unique_id: str) -> str:
    value = unique_id.rsplit(".", 1)[-1]
    if not IDENTIFIER.fullmatch(value):
        _refuse("A dbt relation identity is unsafe.")
    return value


def _dbt_ref(name: str) -> str:
    if not IDENTIFIER.fullmatch(name):
        _refuse("A dbt relation identity is unsafe.")
    return "{{ ref('" + name + "') }}"


def _quoted_identifier(value: str) -> str:
    if not IDENTIFIER.fullmatch(value):
        _refuse("A semantic field identity is unsafe.")
    return f'"{value}"'


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _number(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _refuse("A semantic numeric parameter is invalid.")
    return format(float(value), ".12g")


def _normalized_type(value: str) -> str:
    return re.sub(r"\s+", "", value.casefold())


def _refuse(message: str) -> NoReturn:
    raise Refusal(RefusalCode.SPEC_SCHEMA_INVALID, message)

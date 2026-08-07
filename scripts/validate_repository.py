#!/usr/bin/env python3
"""Validate the documentation foundation without third-party dependencies."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = {
    ".agents/skills/retirement-conductor-agent/SKILL.md",
    ".agents/skills/retirement-conductor-agent/agents/openai.yaml",
    ".agents/skills/retirement-conductor-agent/references/tool-sequence.md",
    ".codex/config.toml",
    ".env.example",
    ".editorconfig",
    ".gitignore",
    ".markdownlint-cli2.yaml",
    "AGENTS.md",
    "CONTRIBUTING.md",
    "GOAL.md",
    "LICENSE",
    "Makefile",
    "PLAN.md",
    "PROJECT_CONTEXT.md",
    "README.md",
    "SECURITY.md",
    "STATUS.md",
    "docs/DEPENDENCIES.md",
    "docs/ACCESS.md",
    "docs/ARCHITECTURE.md",
    "docs/CONTRACTS.md",
    "docs/COMPATIBILITY.md",
    "docs/DECISIONS.md",
    "docs/EVALUATION.md",
    "docs/EVIDENCE_BASELINE.md",
    "docs/EVIDENCE_LEDGER.md",
    "docs/MAINTENANCE.md",
    "docs/OPEN_QUESTIONS.md",
    "docs/PRODUCT.md",
    "docs/REQUIREMENTS_TRACEABILITY.md",
    "docs/RISKS.md",
    "docs/SECURITY_MODEL.md",
    "docs/phases/README.md",
    "docs/phases/00-foundation.md",
    "docs/phases/01-campaign-kernel.md",
    "docs/phases/02-datahub-evidence.md",
    "docs/phases/03-git-dbt-execution.md",
    "docs/phases/04-reconciliation-gate.md",
    "docs/phases/05-operator-experience.md",
    "docs/phases/06-data-quality-benchmark.md",
    "docs/phases/07-security-reliability.md",
    "docs/phases/08-deployment-adoption.md",
    "docs/research/README.md",
    "docs/research/CAPABILITY_GAP.md",
    "docs/research/COMPETITIVE_BOUNDARY.md",
    "docs/research/PRODUCT_SUBSTANCE.md",
    "docs/research/SCOPE_PRESSURE.md",
    "docs/research/SOURCE_LEDGER.md",
    "docs/runbooks/GIT_DBT.md",
    "docs/runbooks/AGENT_DEMO.md",
    "docs/runbooks/DATA_QUALITY_BENCHMARK.md",
    "docs/runbooks/OPERATOR.md",
    "docs/runbooks/DEPLOYMENT.md",
    "docs/runbooks/RECOVERY.md",
    "docs/runbooks/RECONCILIATION_GATE.md",
    "docs/templates/OPERATOR_OBSERVATION.md",
    "artifacts/public/phase01/blocked-manifest.json",
    "artifacts/public/phase01/kernel-evidence.json",
    "artifacts/public/phase02/capability-evidence.json",
    "artifacts/public/phase02/inventory-evidence.json",
    "artifacts/public/phase02/phase02-evidence.json",
    "artifacts/public/phase02/publication-evidence.json",
    "artifacts/public/phase03/adversarial-evidence.json",
    "artifacts/public/phase03/execution-evidence.json",
    "artifacts/public/phase03/phase03-evidence.json",
    "artifacts/public/phase04/gate-evidence.json",
    "artifacts/public/phase04/late-manifest.json",
    "artifacts/public/phase04/phase04-evidence.json",
    "artifacts/public/phase04/ready-manifest.json",
    "artifacts/public/phase04/reconciliation-evidence.json",
    "artifacts/public/phase04/refusal-evidence.json",
    "artifacts/public/phase05/accessibility-evidence.json",
    "artifacts/public/phase05/all-closed-fixture-report.html",
    "artifacts/public/phase05/browser-evidence.json",
    "artifacts/public/phase05/cli-blocked.txt",
    "artifacts/public/phase05/cli-ready.txt",
    "artifacts/public/phase05/cli-review-required.txt",
    "artifacts/public/phase05/cli-unsafe-explain.txt",
    "artifacts/public/phase05/cli-unsafe.txt",
    "artifacts/public/phase05/live-refusal-report.html",
    "artifacts/public/phase05/phase05-evidence.json",
    "artifacts/public/phase05/public-export.html",
    "artifacts/public/phase05/review-required-manifest.json",
    "artifacts/public/phase06/campaign-evidence.json",
    "artifacts/public/phase06/corpus-evidence.json",
    "artifacts/public/phase06/datahub-evidence.json",
    "artifacts/public/phase06/dataset-evidence.json",
    "artifacts/public/phase06/native-validation-evidence.json",
    "artifacts/public/phase06/oracle-evidence.json",
    "artifacts/public/phase06/phase06-evidence.json",
    "artifacts/public/phase06/refusal-matrix.json",
    "artifacts/public/phase07/failure-matrix.json",
    "artifacts/public/phase07/phase07-evidence.json",
    "artifacts/public/phase07/recovery-evidence.json",
    "artifacts/public/phase07/scan-evidence.json",
    "artifacts/public/phase07/security-evidence.json",
    "artifacts/public/phase08/compatibility-evidence.json",
    "artifacts/public/phase08/install-evidence.json",
    "artifacts/public/phase08/operator-boundary.json",
    "artifacts/public/phase08/package-evidence.json",
    "artifacts/public/phase08/phase08-preacceptance-evidence.json",
    "artifacts/public/phase08/reference-evidence.json",
    "artifacts/public/phase08/upgrade-evidence.json",
    "docs/assets/phase05/all-closed-mobile.png",
    "docs/assets/phase05/live-refusal-desktop.png",
    "fixtures/campaigns/blocked/events.json",
    "fixtures/benchmark-dbt-project/dbt_project.yml",
    "fixtures/benchmark-dbt-project/models/orders_status_summary.sql",
    "fixtures/benchmark-dbt-project/models/schema.yml",
    "fixtures/benchmark-dbt-project/profiles.yml",
    "fixtures/benchmark-dbt-project/tests/orders_source_status_parity.sql",
    "fixtures/benchmark-dbt-project/tests/orders_status_semantic_equivalence.sql",
    "fixtures/data-quality/datasets.json",
    "fixtures/repository/models/order_summary.sql",
    "fixtures/git-dbt-project/dbt_project.yml",
    "fixtures/git-dbt-project/models/orders_model_00.sql",
    "fixtures/git-dbt-project/tests/orders_model_semantic_equivalence.sql",
    "fixtures/scenarios/valid.json",
    "fixtures/specs/data-quality-benchmark-live.yaml",
    "fixtures/specs/valid.yaml",
    "pyproject.toml",
    "schemas/campaign-event-v1.schema.json",
    "schemas/benchmark-fault-manifest-v1.schema.json",
    "schemas/benchmark-generation-receipt-v1.schema.json",
    "schemas/benchmark-oracle-v1.schema.json",
    "schemas/benchmark-quality-report-v1.schema.json",
    "schemas/campaign-manifest-v1.schema.json",
    "schemas/consumer-receipt-v1.schema.json",
    "schemas/evidence-envelope-v1.schema.json",
    "schemas/dataset-cache-receipt-v1.schema.json",
    "schemas/dataset-registry-v1.schema.json",
    "schemas/git-dbt-plan-v1.schema.json",
    "schemas/retirement-spec-v1alpha1.schema.json",
    "scripts/check_ui_artifacts.py",
    "scripts/datahub_benchmark_seed.py",
    "scripts/generate_phase03_evidence.py",
    "scripts/generate_phase04_evidence.py",
    "scripts/generate_phase05_evidence.py",
    "scripts/generate_phase06_evidence.py",
    "scripts/generate_phase07_evidence.py",
    "scripts/generate_phase08_evidence.py",
    "scripts/package_release.py",
    "scripts/prepare_benchmark_workspace.py",
    "scripts/phase08_support.py",
    "scripts/reference_services.py",
    "scripts/run_phase04_end_to_end.py",
    "scripts/run_phase05_browser_acceptance.py",
    "scripts/run_phase06_benchmark.py",
    "scripts/run_phase08_reference_campaign.py",
    "scripts/run_agent_acceptance.py",
    "scripts/run_security_scan.py",
    "scripts/test_install.py",
    "scripts/test_upgrade.py",
    "site/.openai/hosting.json",
    "site/app/page.tsx",
    "site/package.json",
    "site/public/retirement-conductor.html",
    "src/retirement_conductor/cli.py",
    "src/retirement_conductor/agent.py",
    "src/retirement_conductor/agent_mcp.py",
    "src/retirement_conductor/benchmark_data.py",
    "src/retirement_conductor/benchmark_oracle.py",
    "src/retirement_conductor/dataset_registry.py",
    "src/retirement_conductor/events.py",
    "src/retirement_conductor/git_dbt.py",
    "src/retirement_conductor/git_dbt_workflow.py",
    "src/retirement_conductor/gate.py",
    "src/retirement_conductor/operator.py",
    "src/retirement_conductor/migrations/001_initial.sql",
    "src/retirement_conductor/migrations/002_initial.sql",
    "src/retirement_conductor/migrations/003_initial.sql",
    "src/retirement_conductor/policy.py",
    "src/retirement_conductor/reconciliation.py",
    "src/retirement_conductor/store.py",
    "tests/contracts/test_records.py",
    "tests/contracts/test_specification.py",
    "tests/fixture/test_fixture_run.py",
    "tests/fixture/test_reference.py",
    "tests/integration/test_campaign_store.py",
    "tests/integration/test_gate.py",
    "tests/integration/test_git_dbt_workflow.py",
    "tests/integration/test_operator_cli.py",
    "tests/reliability/test_store_operations.py",
    "tests/unit/test_deployment.py",
    "tests/unit/test_agent.py",
    "tests/unit/test_agent_acceptance.py",
    "tests/unit/test_agent_mcp.py",
    "tests/unit/test_operator.py",
    "tests/unit/test_phase08_reference.py",
}

GOAL_HEADINGS = {
    "## Exact objective",
    "## Current truth",
    "## Instruction order",
    "## Authority and repository boundary",
    "## Required product outcome",
    "## Phase authority",
    "## Continuous execution protocol",
    "## Work available before external access",
    "## Evidence contract",
    "## Failure-closed requirements",
    "## Scope control",
    "## External boundary protocol",
    "## Reframe protocol",
    "## Completion states",
    "## Final handoff",
}

PHASE_HEADINGS = {
    "## Outcome",
    "## Dependencies",
    "## Scope",
    "## Deliverables",
    "## Work breakdown",
    "## Acceptance evidence",
    "## Stop or reframe conditions",
    "## Risks changed",
}

REQUIRED_REQUIREMENT_IDS = {f"RC-{number:03d}" for number in range(1, 20)}
REQUIRED_EVIDENCE_IDS = {f"EP-{number:03d}" for number in range(9)}
ALLOWED_PHASE_STATES = {
    "queued",
    "active",
    "access-dependent",
    "blocked",
    "complete",
    "reframed",
}

LINK_PATTERN = re.compile(r"!?\[[^\]]*]\(([^)]+)\)")
SCHEME_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")
EXCLUDED_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".retirement-conductor",
    ".ruff_cache",
    ".venv",
    ".vinext",
    ".next",
    ".wrangler",
    "__pycache__",
    "dist",
    "node_modules",
    "outputs",
}


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def markdown_files() -> list[Path]:
    return sorted(
        path
        for path in ROOT.rglob("*.md")
        if not any(part in EXCLUDED_PARTS for part in path.relative_to(ROOT).parts)
    )


def validate_required_files(errors: list[str]) -> None:
    for filename in sorted(REQUIRED_FILES):
        if not (ROOT / filename).is_file():
            errors.append(f"missing required file: {filename}")


def validate_markdown_shape(path: Path, errors: list[str]) -> None:
    content = path.read_text(encoding="utf-8")
    name = relative(path)
    if not content.endswith("\n"):
        errors.append(f"{name}: missing final newline")
    body = content
    if path.name == "SKILL.md" and content.startswith("---\n"):
        frontmatter_end = content.find("\n---\n", 4)
        if frontmatter_end == -1:
            errors.append(f"{name}: unclosed skill frontmatter")
            return
        body = content[frontmatter_end + len("\n---\n") :].lstrip("\n")
    if not body.startswith("# "):
        errors.append(f"{name}: first line must be one level-one heading")
    level_one = [line for line in content.splitlines() if line.startswith("# ")]
    if len(level_one) != 1:
        errors.append(f"{name}: expected one level-one heading, found {len(level_one)}")


def clean_link_target(raw_target: str) -> str:
    target = raw_target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    elif " " in target:
        target = target.split(" ", 1)[0]
    target = target.split("#", 1)[0]
    target = target.split("?", 1)[0]
    return unquote(target)


def validate_links(path: Path, errors: list[str]) -> int:
    content = path.read_text(encoding="utf-8")
    checked = 0
    for match in LINK_PATTERN.finditer(content):
        raw_target = match.group(1)
        target = clean_link_target(raw_target)
        if not target or raw_target.lstrip().startswith("#"):
            continue
        if SCHEME_PATTERN.match(target):
            continue
        checked += 1
        if target.startswith("/"):
            errors.append(
                f"{relative(path)}: absolute local link is not portable: {target}"
            )
            continue
        resolved = (path.parent / target).resolve()
        try:
            resolved.relative_to(ROOT)
        except ValueError:
            errors.append(f"{relative(path)}: link escapes repository: {target}")
            continue
        if not resolved.exists():
            errors.append(f"{relative(path)}: broken relative link: {target}")
    return checked


def validate_phase_files(errors: list[str]) -> None:
    for path in sorted((ROOT / "docs" / "phases").glob("[0-9][0-9]-*.md")):
        headings = {
            line
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.startswith("## ")
        }
        missing = sorted(PHASE_HEADINGS - headings)
        if missing:
            errors.append(
                f"{relative(path)}: missing phase headings: {', '.join(missing)}"
            )


def validate_plan_phase_links(errors: list[str]) -> None:
    plan = (ROOT / "PLAN.md").read_text(encoding="utf-8")
    for phase in range(9):
        token = f"docs/phases/{phase:02d}-"
        if token not in plan:
            errors.append(f"PLAN.md: missing phase {phase:02d} link")


def validate_goal_contract(errors: list[str]) -> None:
    path = ROOT / "GOAL.md"
    content = path.read_text(encoding="utf-8")
    headings = {line for line in content.splitlines() if line.startswith("## ")}
    missing = sorted(GOAL_HEADINGS - headings)
    if missing:
        errors.append(f"GOAL.md: missing controlling headings: {', '.join(missing)}")
    for phase in range(9):
        token = f"docs/phases/{phase:02d}-"
        if token not in content:
            errors.append(f"GOAL.md: missing phase {phase:02d} authority link")


def validate_status_phase_ledger(errors: list[str]) -> None:
    content = (ROOT / "STATUS.md").read_text(encoding="utf-8")
    matches = re.findall(
        r"^\|\s*(0[0-8])\s*\|\s*([a-z-]+)\s*\|",
        content,
        flags=re.MULTILINE,
    )
    phases = [phase for phase, _ in matches]
    expected = [f"{phase:02d}" for phase in range(9)]
    if phases != expected:
        errors.append(
            "STATUS.md: phase ledger must contain phases 00 through 08 "
            "exactly once and in order"
        )
    states = [state for _, state in matches]
    unknown = sorted(set(states) - ALLOWED_PHASE_STATES)
    if unknown:
        errors.append(f"STATUS.md: unknown phase states: {', '.join(unknown)}")
    if states.count("active") > 1:
        errors.append("STATUS.md: at most one phase may be active")


def validate_traceability(errors: list[str]) -> None:
    content = (ROOT / "docs" / "REQUIREMENTS_TRACEABILITY.md").read_text(
        encoding="utf-8"
    )
    found = set(re.findall(r"\bRC-\d{3}\b", content))
    missing = sorted(REQUIRED_REQUIREMENT_IDS - found)
    if missing:
        errors.append(
            "docs/REQUIREMENTS_TRACEABILITY.md: missing requirement IDs: "
            f"{', '.join(missing)}"
        )


def validate_evidence_ledger(errors: list[str]) -> None:
    content = (ROOT / "docs" / "EVIDENCE_LEDGER.md").read_text(encoding="utf-8")
    found = set(re.findall(r"\bEP-\d{3}\b", content))
    missing = sorted(REQUIRED_EVIDENCE_IDS - found)
    if missing:
        errors.append(
            f"docs/EVIDENCE_LEDGER.md: missing phase evidence IDs: {', '.join(missing)}"
        )


def validate_risk_coverage(errors: list[str]) -> None:
    register = (ROOT / "docs" / "RISKS.md").read_text(encoding="utf-8")
    registered = set(re.findall(r"\bR-\d{2}\b", register))
    phase_content = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "docs" / "phases").glob("[0-9][0-9]-*.md"))
    )
    referenced = set(re.findall(r"\bR-\d{2}\b", phase_content))
    missing = sorted(registered - referenced)
    unknown = sorted(referenced - registered)
    if missing:
        errors.append(
            "docs/phases: registered risks missing phase ownership: "
            f"{', '.join(missing)}"
        )
    if unknown:
        errors.append(f"docs/phases: unknown risk references: {', '.join(unknown)}")


def run() -> int:
    errors: list[str] = []
    validate_required_files(errors)

    markdown = markdown_files()
    links_checked = 0
    for path in markdown:
        validate_markdown_shape(path, errors)
        links_checked += validate_links(path, errors)

    validate_phase_files(errors)
    validate_plan_phase_links(errors)
    validate_goal_contract(errors)
    validate_status_phase_ledger(errors)
    validate_traceability(errors)
    validate_evidence_ledger(errors)
    validate_risk_coverage(errors)

    if errors:
        print("Repository validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(
        "Repository validation passed: "
        f"{len(REQUIRED_FILES)} required files, "
        f"{len(markdown)} Markdown files, "
        f"{links_checked} relative links."
    )
    return 0


if __name__ == "__main__":
    sys.exit(run())

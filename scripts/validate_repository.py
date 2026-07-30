#!/usr/bin/env python3
"""Validate the documentation foundation without third-party dependencies."""

from __future__ import annotations

from pathlib import Path
import re
import sys
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = {
    ".editorconfig",
    ".gitignore",
    ".markdownlint-cli2.yaml",
    "AGENTS.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "Makefile",
    "PLAN.md",
    "README.md",
    "SECURITY.md",
    "docs/ARCHITECTURE.md",
    "docs/CONTRACTS.md",
    "docs/DECISIONS.md",
    "docs/EVIDENCE_BASELINE.md",
    "docs/OPEN_QUESTIONS.md",
    "docs/PRODUCT.md",
    "docs/RISKS.md",
    "docs/phases/README.md",
    "docs/phases/00-foundation.md",
    "docs/phases/01-campaign-kernel.md",
    "docs/phases/02-datahub-evidence.md",
    "docs/phases/03-git-dbt-execution.md",
    "docs/phases/04-reconciliation-gate.md",
    "docs/phases/05-operator-experience.md",
    "docs/phases/06-looker-adapter.md",
    "docs/phases/07-security-reliability.md",
    "docs/phases/08-deployment-adoption.md",
    "docs/research/README.md",
    "docs/research/CAPABILITY_GAP.md",
    "docs/research/COMPETITIVE_BOUNDARY.md",
    "docs/research/PRODUCT_SUBSTANCE.md",
    "docs/research/SCOPE_PRESSURE.md",
    "docs/research/SOURCE_LEDGER.md",
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

LINK_PATTERN = re.compile(r"!?\[[^\]]*]\(([^)]+)\)")
SCHEME_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def markdown_files() -> list[Path]:
    return sorted(
        path
        for path in ROOT.rglob("*.md")
        if ".git" not in path.parts
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
    if not content.startswith("# "):
        errors.append(f"{name}: first line must be one level-one heading")
    level_one = [
        line for line in content.splitlines() if line.startswith("# ")
    ]
    if len(level_one) != 1:
        errors.append(
            f"{name}: expected one level-one heading, found {len(level_one)}"
        )


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
            errors.append(
                f"{relative(path)}: link escapes repository: {target}"
            )
            continue
        if not resolved.exists():
            errors.append(
                f"{relative(path)}: broken relative link: {target}"
            )
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

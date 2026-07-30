#!/usr/bin/env python3
"""Run deterministic semantic, keyboard, and contrast checks on HTML reports."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORTS = (
    ROOT / "artifacts/public/phase05/live-refusal-report.html",
    ROOT / "artifacts/public/phase05/all-closed-fixture-report.html",
)
COLOR_PATTERN = re.compile(r"--([a-z-]+):\s*(#[0-9a-fA-F]{6})")
PUBLIC_FORBIDDEN = {
    "private home path": re.compile(r"(?:/home/|/Users/)[^/\s]+/"),
    "email address": re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
    "DataHub URN": re.compile(r"\burn:li:", re.IGNORECASE),
    "credential assignment": re.compile(
        r"(?im)\b(?:token|client_secret|password|cookie)\s*[=:]\s*\S+"
    ),
    "SQL statement": re.compile(
        r"(?is)\b(?:select|insert|update|delete|merge)\b.{1,200}"
        r"\b(?:from|into|set)\b"
    ),
}


class ReportAudit(HTMLParser):
    """Collect accessibility-relevant facts without executing report content."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: Counter[str] = Counter()
        self.ids: set[str] = set()
        self.duplicate_ids: set[str] = set()
        self.fragment_refs: set[str] = set()
        self.aria_refs: set[str] = set()
        self.heading_levels: list[int] = []
        self.interactive_controls = 0
        self.errors: list[str] = []
        self.html_lang = ""
        self.has_viewport = False
        self.has_skip_link = False
        self.has_labelled_nav = False
        self.title_text = ""
        self._capture_title = False
        self._details_depth = 0
        self._details_first_child: list[str | None] = []

    def handle_starttag(
        self,
        tag: str,
        attrs_list: list[tuple[str, str | None]],
    ) -> None:
        attrs = {name: value or "" for name, value in attrs_list}
        self.tags[tag] += 1
        element_id = attrs.get("id")
        if element_id:
            if element_id in self.ids:
                self.duplicate_ids.add(element_id)
            self.ids.add(element_id)
        labelled_by = attrs.get("aria-labelledby", "")
        self.aria_refs.update(labelled_by.split())
        href = attrs.get("href", "")
        if href.startswith("#") and len(href) > 1:
            self.fragment_refs.add(href[1:])
        if any(name.lower().startswith("on") for name in attrs):
            self.errors.append(f"<{tag}> uses an inline event handler")
        tabindex = attrs.get("tabindex")
        if tabindex:
            try:
                if int(tabindex) > 0:
                    self.errors.append(f"<{tag}> uses positive tabindex")
            except ValueError:
                self.errors.append(f"<{tag}> has an invalid tabindex")
        if tag == "html":
            self.html_lang = attrs.get("lang", "")
        elif tag == "meta" and attrs.get("name", "").lower() == "viewport":
            self.has_viewport = "width=device-width" in attrs.get("content", "")
        elif tag == "title":
            self._capture_title = True
        elif tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.heading_levels.append(int(tag[1]))
        elif tag == "nav" and (attrs.get("aria-label") or attrs.get("aria-labelledby")):
            self.has_labelled_nav = True
        elif tag == "a":
            self.interactive_controls += 1
            if not href:
                self.errors.append("<a> is missing href")
            if href == "#main" and "skip-link" in attrs.get("class", "").split():
                self.has_skip_link = True
            if attrs.get("target") == "_blank" and "noopener" not in attrs.get(
                "rel", ""
            ):
                self.errors.append('target="_blank" link is missing rel="noopener"')
        elif tag == "button":
            self.interactive_controls += 1
            if attrs.get("type") not in {"button", "submit", "reset"}:
                self.errors.append("<button> is missing an explicit type")
        elif tag in {"input", "select", "textarea"}:
            self.interactive_controls += 1
            if not (
                attrs.get("aria-label")
                or attrs.get("aria-labelledby")
                or attrs.get("id")
            ):
                self.errors.append(f"<{tag}> has no accessible naming hook")
        elif tag == "summary":
            self.interactive_controls += 1
        elif tag == "img" and "alt" not in attrs:
            self.errors.append("<img> is missing alt")
        elif tag in {"audio", "video"} and "autoplay" in attrs:
            self.errors.append(f"<{tag}> must not autoplay")

        if self._details_depth and tag != "details":
            current = self._details_first_child[-1]
            if current is None:
                self._details_first_child[-1] = tag
        if tag == "details":
            self._details_depth += 1
            self._details_first_child.append(None)

    def handle_startendtag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._capture_title = False
        if tag == "details" and self._details_first_child:
            first = self._details_first_child.pop()
            if first != "summary":
                self.errors.append("<details> does not begin with <summary>")
            self._details_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._capture_title:
            self.title_text += data


def _relative(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return path.name


def _linear_channel(value: int) -> float:
    channel = value / 255
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def _luminance(color: str) -> float:
    red = int(color[1:3], 16)
    green = int(color[3:5], 16)
    blue = int(color[5:7], 16)
    return (
        0.2126 * _linear_channel(red)
        + 0.7152 * _linear_channel(green)
        + 0.0722 * _linear_channel(blue)
    )


def _contrast(first: str, second: str) -> float:
    light, dark = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def audit_report(path: Path) -> dict[str, Any]:
    content = path.read_text(encoding="utf-8")
    parser = ReportAudit()
    parser.feed(content)
    errors = list(parser.errors)

    if parser.html_lang != "en":
        errors.append('<html> must declare lang="en"')
    if not parser.has_viewport:
        errors.append("responsive viewport metadata is missing")
    if not parser.title_text.strip():
        errors.append("document title is empty")
    if parser.tags["h1"] != 1:
        errors.append(f"expected one h1, found {parser.tags['h1']}")
    for landmark in ("header", "main", "footer", "nav"):
        if parser.tags[landmark] < 1:
            errors.append(f"<{landmark}> landmark is missing")
    if not parser.has_labelled_nav:
        errors.append("navigation landmark has no accessible name")
    if not parser.has_skip_link:
        errors.append("skip link to #main is missing")
    if parser.duplicate_ids:
        errors.append(f"duplicate ids: {', '.join(sorted(parser.duplicate_ids))}")
    missing_fragments = sorted(parser.fragment_refs - parser.ids)
    if missing_fragments:
        errors.append(f"broken fragment targets: {', '.join(missing_fragments)}")
    missing_labels = sorted(parser.aria_refs - parser.ids)
    if missing_labels:
        errors.append(f"broken aria-labelledby targets: {', '.join(missing_labels)}")
    for previous, current in zip(
        parser.heading_levels,
        parser.heading_levels[1:],
        strict=False,
    ):
        if current > previous + 1:
            errors.append(f"heading level skips from h{previous} to h{current}")
    for marker in (
        ":focus-visible",
        "@media (prefers-reduced-motion: reduce)",
        "@media (max-width: 44rem)",
    ):
        if marker not in content:
            errors.append(f"required responsive/accessibility CSS is missing: {marker}")

    colors = dict(COLOR_PATTERN.findall(content))
    contrast_pairs = (
        ("ink", "paper"),
        ("muted", "paper"),
        ("safe", "paper"),
        ("warning", "paper"),
        ("danger", "paper"),
        ("paper-raised", "ink"),
    )
    contrast_results: dict[str, float] = {}
    for foreground, background in contrast_pairs:
        if foreground not in colors or background not in colors:
            errors.append(f"color token is missing: {foreground} or {background}")
            continue
        ratio = _contrast(colors[foreground], colors[background])
        contrast_results[f"{foreground}_on_{background}"] = round(ratio, 2)
        if ratio < 4.5:
            errors.append(
                f"{foreground} on {background} contrast is {ratio:.2f}, below 4.5"
            )

    if 'data-export="public"' in content:
        for label, pattern in PUBLIC_FORBIDDEN.items():
            if pattern.search(content):
                errors.append(f"public report contains {label}")

    return {
        "file": _relative(path),
        "result": "PASSED" if not errors else "FAILED",
        "checks": {
            "landmarks": sum(
                parser.tags[tag] for tag in ("header", "main", "footer", "nav")
            ),
            "headings": len(parser.heading_levels),
            "interactive_controls": parser.interactive_controls,
            "fragment_targets": len(parser.fragment_refs),
            "aria_references": len(parser.aria_refs),
            "contrast_ratios": contrast_results,
        },
        "violations": errors,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("reports", nargs="*", type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def run() -> int:
    args = parse_args()
    reports = tuple(args.reports) or DEFAULT_REPORTS
    missing = [path for path in reports if not path.is_file()]
    if missing:
        for path in missing:
            print(f"UI artifact is missing: {_relative(path)}", file=sys.stderr)
        return 1

    audited = [audit_report(path) for path in reports]
    result = {
        "schema_version": "1.0.0",
        "result": (
            "PASSED"
            if all(item["result"] == "PASSED" for item in audited)
            else "FAILED"
        ),
        "standard": "WCAG 2.2 AA deterministic structural subset",
        "reports": audited,
    }
    serialized = json.dumps(
        result,
        allow_nan=False,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{serialized}\n", encoding="utf-8")
    print(serialized)
    return 0 if result["result"] == "PASSED" else 1


if __name__ == "__main__":
    sys.exit(run())

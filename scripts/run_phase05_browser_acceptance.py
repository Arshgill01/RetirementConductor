#!/usr/bin/env python3
"""Exercise generated reports with Playwright CLI, keyboard input, and axe."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import threading
from contextlib import suppress
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = ROOT / "artifacts/public/phase05"
RAW_ROOT = ROOT / "output/playwright/phase05"
TRACKED_SCREENSHOTS = ROOT / "docs/assets/phase05"
RUNTIME_ROOT = ROOT / ".retirement-conductor/phase05"
PLAYWRIGHT_VERSION = "0.1.17"
AXE_CLI_VERSION = "4.10.2"
CHROME_VERSION = "150"
LIVE_MANIFEST = ROOT / "artifacts/public/phase04/late-manifest.json"
FIXTURE_MANIFEST = ROOT / "artifacts/public/phase00/manifest.json"


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        """Suppress request paths from acceptance output."""


def digest_file(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def png_dimensions(path: Path) -> tuple[int, int]:
    content = path.read_bytes()
    if content[:8] != b"\x89PNG\r\n\x1a\n" or content[12:16] != b"IHDR":
        raise RuntimeError(f"{path.name} is not a PNG screenshot")
    return struct.unpack(">II", content[16:24])


def command_prefix() -> list[str]:
    wrapper = os.environ.get("PLAYWRIGHT_CLI_WRAPPER", "").strip()
    if wrapper:
        path = Path(wrapper)
        if not path.is_file():
            raise RuntimeError("PLAYWRIGHT_CLI_WRAPPER is not a file")
        return ["bash", str(path)]
    return [
        "npx",
        "--yes",
        "--package",
        f"@playwright/cli@{PLAYWRIGHT_VERSION}",
        "playwright-cli",
    ]


def run_command(
    arguments: list[str],
    *,
    cwd: Path = ROOT,
    timeout: int = 120,
) -> str:
    completed = subprocess.run(
        arguments,
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"{arguments[0]} failed with exit {completed.returncode}: "
            f"{completed.stderr.strip() or 'no safe error text'}"
        )
    return completed.stdout


def manifest_campaign_id(path: Path) -> str:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("campaign"), dict):
        raise RuntimeError(f"{path.name} is not a canonical campaign manifest")
    campaign_id = value["campaign"].get("id")
    if not isinstance(campaign_id, str) or not campaign_id:
        raise RuntimeError(f"{path.name} has no campaign identifier")
    return campaign_id


def prepare_reports() -> None:
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    inputs = (
        (
            LIVE_MANIFEST,
            REPORT_ROOT / "live-refusal-report.html",
            False,
        ),
        (
            FIXTURE_MANIFEST,
            REPORT_ROOT / "all-closed-fixture-report.html",
            False,
        ),
        (
            LIVE_MANIFEST,
            REPORT_ROOT / "public-export.html",
            True,
        ),
    )
    for manifest, output, public in inputs:
        command = [
            "uv",
            "run",
            "retirement-conductor",
            "report",
            "build",
            "--campaign",
            manifest_campaign_id(manifest),
            "--manifest",
            str(manifest.relative_to(ROOT)),
            "--output",
            str(output.relative_to(ROOT)),
        ]
        if public:
            command.append("--public")
        run_command(command)


def playwright(
    prefix: list[str],
    session: str,
    command: list[str],
) -> dict[str, Any]:
    output = run_command(
        [*prefix, "--session", session, "--json", *command],
        cwd=RAW_ROOT,
    )
    try:
        value = json.loads(output)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Playwright CLI did not return JSON") from exc
    if not isinstance(value, dict):
        raise RuntimeError("Playwright CLI response is not an object")
    result = value.get("result")
    if isinstance(result, dict) and result.get("isError"):
        raise RuntimeError("Playwright CLI reported an in-browser error")
    return value


def evaluated(
    prefix: list[str],
    session: str,
    expression: str,
) -> Any:
    value = playwright(prefix, session, ["eval", expression])
    result = value.get("result")
    if not isinstance(result, str):
        raise RuntimeError("Playwright evaluation did not return serialized JSON")
    try:
        return json.loads(result)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Playwright evaluation result is not JSON") from exc


def focus_descriptor(prefix: list[str], session: str) -> dict[str, Any]:
    result = evaluated(
        prefix,
        session,
        "() => ({"
        "tag: document.activeElement.tagName,"
        "text: document.activeElement.textContent.trim(),"
        "href: document.activeElement.getAttribute('href')"
        "})",
    )
    if not isinstance(result, dict):
        raise RuntimeError("focused element descriptor is not an object")
    return result


def keyboard_flow(
    prefix: list[str],
    session: str,
) -> dict[str, Any]:
    expected = evaluated(
        prefix,
        session,
        "() => Array.from(document.querySelectorAll("
        "'a[href], summary, button, input, select, textarea'"
        ")).filter((element) => !element.disabled && "
        "element.getClientRects().length).map((element) => ({"
        "tag: element.tagName,"
        "text: element.textContent.trim(),"
        "href: element.getAttribute('href')"
        "}))",
    )
    if not isinstance(expected, list) or not expected:
        raise RuntimeError("report exposed no keyboard controls")
    observed: list[dict[str, Any]] = []
    summary_toggled = False
    for expected_control in expected:
        playwright(prefix, session, ["press", "Tab"])
        focused = focus_descriptor(prefix, session)
        observed.append(focused)
        if focused != expected_control:
            raise RuntimeError("keyboard focus order differed from document order")
        if focused.get("tag") == "SUMMARY" and not summary_toggled:
            playwright(prefix, session, ["press", "Enter"])
            state = evaluated(
                prefix,
                session,
                "() => document.activeElement.closest('details').open",
            )
            if state is not True:
                raise RuntimeError("keyboard activation did not open report details")
            summary_toggled = True
    if not summary_toggled:
        raise RuntimeError("no report details control was keyboard activated")
    return {
        "control_count": len(expected),
        "focus_order": [
            {
                "tag": str(item.get("tag")),
                "text": str(item.get("text")),
                "href": item.get("href"),
            }
            for item in observed
        ],
        "details_toggled": summary_toggled,
    }


def page_flow(
    prefix: list[str],
    *,
    session: str,
    url: str,
    label: str,
    screenshot_name: str,
    mobile: bool,
) -> dict[str, Any]:
    open_command = ["open", url, "--browser", "chrome"]
    if mobile:
        open_command.append("--mobile")
    playwright(prefix, session, open_command)
    if not mobile:
        playwright(prefix, session, ["resize", "1440", "1000"])
    snapshot = playwright(prefix, session, ["snapshot"])
    if "snapshot" not in snapshot.get("result", snapshot):
        raise RuntimeError("Playwright did not capture an accessibility snapshot")

    page = evaluated(
        prefix,
        session,
        "() => ({"
        "title: document.title,"
        "decision: document.querySelector('.decision-code').textContent.trim(),"
        "manifestDigest: document.querySelector('footer code').textContent.trim(),"
        "viewportWidth: document.documentElement.clientWidth,"
        "contentWidth: document.documentElement.scrollWidth,"
        "resourceRequests: performance.getEntriesByType('resource').length"
        "})",
    )
    if not isinstance(page, dict):
        raise RuntimeError("browser page facts are not an object")
    if int(page["contentWidth"]) > int(page["viewportWidth"]):
        raise RuntimeError(f"{label} has horizontal overflow")
    if int(page["resourceRequests"]) != 0:
        raise RuntimeError(f"{label} loaded an unexpected external resource")

    keyboard = keyboard_flow(prefix, session)
    raw_screenshot = RAW_ROOT / screenshot_name
    tracked_screenshot = TRACKED_SCREENSHOTS / screenshot_name
    playwright(
        prefix,
        session,
        [
            "screenshot",
            "--filename",
            str(raw_screenshot),
            "--full-page",
        ],
    )
    TRACKED_SCREENSHOTS.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(raw_screenshot, tracked_screenshot)
    width, height = png_dimensions(tracked_screenshot)
    return {
        "label": label,
        "title": str(page["title"]),
        "decision": str(page["decision"]),
        "manifest_digest": str(page["manifestDigest"]),
        "viewport_width": int(page["viewportWidth"]),
        "content_width": int(page["contentWidth"]),
        "horizontal_overflow": False,
        "external_resource_requests": int(page["resourceRequests"]),
        "accessibility_snapshot": True,
        "keyboard": keyboard,
        "screenshot": {
            "file": tracked_screenshot.relative_to(ROOT).as_posix(),
            "digest": digest_file(tracked_screenshot),
            "width": width,
            "height": height,
        },
    }


def browser_paths() -> tuple[str, str]:
    chrome = os.environ.get("PHASE05_CHROME_PATH", "").strip()
    driver = os.environ.get("PHASE05_CHROMEDRIVER_PATH", "").strip()
    if chrome and driver:
        return chrome, driver
    output = run_command(
        [
            "npx",
            "--yes",
            "browser-driver-manager",
            "install",
            f"chrome@{CHROME_VERSION}",
        ],
        timeout=300,
    )
    chrome_match = re.search(r'CHROME_TEST_PATH="([^"]+)"', output)
    driver_match = re.search(r'CHROMEDRIVER_TEST_PATH="([^"]+)"', output)
    if not chrome_match or not driver_match:
        raise RuntimeError("browser-driver-manager did not report synchronized paths")
    return chrome_match.group(1), driver_match.group(1)


def axe_flow(urls: list[str]) -> list[dict[str, Any]]:
    chrome, driver = browser_paths()
    raw_output = RUNTIME_ROOT / "axe-raw.json"
    run_command(
        [
            "npx",
            "--yes",
            f"@axe-core/cli@{AXE_CLI_VERSION}",
            *urls,
            "--tags",
            "wcag2a,wcag2aa,wcag21a,wcag21aa,wcag22aa,best-practice",
            "--exit",
            "--save",
            str(raw_output),
            "--no-reporter",
            "--chrome-path",
            chrome,
            "--chromedriver-path",
            driver,
        ],
        timeout=300,
    )
    value = json.loads(raw_output.read_text(encoding="utf-8"))
    if not isinstance(value, list) or len(value) != len(urls):
        raise RuntimeError("axe output did not contain every report")
    results: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            raise RuntimeError("axe page result is not an object")
        violations = item.get("violations")
        incomplete = item.get("incomplete")
        if not isinstance(violations, list) or not isinstance(incomplete, list):
            raise RuntimeError("axe result omitted violation categories")
        if violations or incomplete:
            raise RuntimeError("axe reported a violation or incomplete check")
        engine = item.get("testEngine")
        passes = item.get("passes")
        results.append(
            {
                "page": Path(str(item.get("url"))).name,
                "engine": (
                    dict(engine)
                    if isinstance(engine, dict)
                    else {"name": "axe-core", "version": "unknown"}
                ),
                "violations": len(violations),
                "incomplete": len(incomplete),
                "passes": len(passes) if isinstance(passes, list) else 0,
            }
        )
    return results


def run() -> int:
    prepare_reports()
    reports = {
        "live-refusal": REPORT_ROOT / "live-refusal-report.html",
        "all-closed-fixture": REPORT_ROOT / "all-closed-fixture-report.html",
    }
    missing = [path.name for path in reports.values() if not path.is_file()]
    if missing:
        raise RuntimeError(f"generate reports before browser acceptance: {missing}")
    RAW_ROOT.mkdir(parents=True, exist_ok=True)
    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    prefix = command_prefix()
    version = run_command([*prefix, "--version"], cwd=RAW_ROOT).strip()

    handler = partial(QuietHandler, directory=str(REPORT_ROOT))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    sessions = ("phase05-desktop", "phase05-mobile")
    try:
        live_url = f"http://127.0.0.1:{port}/{reports['live-refusal'].name}"
        fixture_url = f"http://127.0.0.1:{port}/{reports['all-closed-fixture'].name}"
        pages = [
            page_flow(
                prefix,
                session=sessions[0],
                url=live_url,
                label="live-refusal-desktop",
                screenshot_name="live-refusal-desktop.png",
                mobile=False,
            ),
            page_flow(
                prefix,
                session=sessions[1],
                url=fixture_url,
                label="all-closed-fixture-mobile",
                screenshot_name="all-closed-mobile.png",
                mobile=True,
            ),
        ]
        axe = axe_flow([live_url, fixture_url])
    finally:
        for session in sessions:
            with suppress(RuntimeError, subprocess.SubprocessError):
                playwright(prefix, session, ["close"])
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    evidence = {
        "schema_version": "1.0.0",
        "result": "PASSED",
        "playwright_cli_version": version,
        "reports": {
            label: {
                "file": path.relative_to(ROOT).as_posix(),
                "digest": digest_file(path),
            }
            for label, path in reports.items()
        },
        "pages": pages,
        "axe": axe,
    }
    output = RUNTIME_ROOT / "browser-evidence.json"
    serialized = json.dumps(
        evidence,
        allow_nan=False,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    output.write_text(
        f"{serialized}\n",
        encoding="utf-8",
    )
    print(
        "Phase 05 browser acceptance passed: "
        f"{sum(page['keyboard']['control_count'] for page in pages)} "
        "keyboard controls, 2 responsive screenshots, 0 axe violations."
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(run())
    except (OSError, RuntimeError, subprocess.SubprocessError, ValueError) as exc:
        print(
            f"Phase 05 browser acceptance failed: {type(exc).__name__}",
            file=sys.stderr,
        )
        sys.exit(1)

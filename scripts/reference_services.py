"""Provision only the disposable local services used by the reference run."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from retirement_conductor.canonical import digest_bytes
from scripts.phase08_support import PHASE08_RUNTIME, ROOT, checked

DATAHUB_GMS_URL = "http://127.0.0.1:18080"
DATAHUB_MCP_URL = "http://127.0.0.1:8000/mcp"
MCP_HEALTH_URL = "http://127.0.0.1:8000/health"
MCP_SOURCE = "https://github.com/acryldata/mcp-server-datahub.git"
MCP_COMMIT = "9a6946daa7d30eb481c82dd8ee5e15ae6526a3c9"
MCP_PORT = 8000
MCP_TOOL_ROOT = (
    ROOT / ".retirement-conductor" / "tools" / f"mcp-server-datahub-{MCP_COMMIT[:12]}"
)
COMPOSE_FILE = ROOT / "deploy/datahub/docker-compose.core.yml"
COMPOSE_ENV = ROOT / ".retirement-conductor/datahub/core.env"


@dataclass
class ReferenceServices:
    gms_started: bool
    mcp_started: bool
    mcp_process: subprocess.Popen[str] | None
    mcp_identity: dict[str, Any]

    def evidence(self) -> dict[str, Any]:
        return {
            "datahub_core": {
                "health": http_health(f"{DATAHUB_GMS_URL}/health"),
                "started_for_run": self.gms_started,
                "scope": "loopback disposable Core",
                **datahub_core_identity(),
            },
            "mcp_server": {
                "health": http_json(MCP_HEALTH_URL),
                "started_for_run": self.mcp_started,
                "scope": "loopback disposable Core",
                **self.mcp_identity,
            },
        }


def http_json(url: str) -> dict[str, Any]:
    _, body = http_response(url)
    try:
        value = json.loads(body.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("a local reference endpoint returned invalid JSON") from exc
    if not isinstance(value, dict):
        raise RuntimeError("a local reference endpoint returned non-object JSON")
    return value


def http_response(url: str) -> tuple[int, bytes]:
    request = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=3) as response:
            status = response.status
            body = response.read()
    except (OSError, URLError) as exc:
        raise RuntimeError("a required local reference service is unavailable") from exc
    if status < 200 or status >= 300:
        raise RuntimeError("a local reference service returned an unhealthy status")
    return status, body


def http_health(url: str) -> dict[str, Any]:
    status, body = http_response(url)
    return {
        "http_status": status,
        "response_body_digest": digest_bytes(body),
        "response_body_bytes": len(body),
    }


def healthy(url: str, *, json_required: bool = False) -> bool:
    try:
        if json_required:
            http_json(url)
        else:
            http_health(url)
    except RuntimeError:
        return False
    return True


def ensure_datahub_core() -> bool:
    if healthy(f"{DATAHUB_GMS_URL}/health"):
        return False
    checked(["uv", "run", "python", "scripts/datahub_core_env.py"])
    checked(
        [
            "docker",
            "compose",
            "--env-file",
            str(COMPOSE_ENV),
            "-f",
            str(COMPOSE_FILE),
            "up",
            "-d",
            "--wait",
            "datahub-gms",
        ],
        timeout=600,
    )
    if not healthy(f"{DATAHUB_GMS_URL}/health"):
        raise RuntimeError("disposable DataHub Core did not become healthy")
    return True


def datahub_core_identity() -> dict[str, str]:
    compose = [
        "docker",
        "compose",
        "--env-file",
        str(COMPOSE_ENV),
        "-f",
        str(COMPOSE_FILE),
    ]
    identifiers = [
        value
        for value in checked(
            [*compose, "ps", "--quiet", "datahub-gms"]
        ).stdout.splitlines()
        if value
    ]
    if len(identifiers) != 1:
        raise RuntimeError("expected one disposable DataHub Core container")
    identifier = identifiers[0]

    def inspect_value(template: str) -> str:
        return checked(
            ["docker", "inspect", "--format", template, identifier]
        ).stdout.strip()

    configured_image = json.loads(inspect_value("{{json .Config.Image}}"))
    image_id = json.loads(inspect_value("{{json .Image}}"))
    state = json.loads(inspect_value("{{json .State.Status}}"))
    health = json.loads(inspect_value("{{json .State.Health.Status}}"))
    port = checked(["docker", "port", identifier, "8080/tcp"]).stdout.strip()
    if not all(
        isinstance(value, str) for value in (configured_image, image_id, state, health)
    ):
        raise RuntimeError("DataHub Core container identity was invalid")
    if state != "running" or health != "healthy":
        raise RuntimeError("the disposable DataHub Core container is not healthy")
    if port != "127.0.0.1:18080":
        raise RuntimeError("DataHub Core is not confined to its loopback port")
    return {
        "configured_image": configured_image,
        "image_id": image_id,
        "container_state": state,
        "container_health": health,
        "published_port": port,
    }


def prepare_mcp_tool() -> Path:
    executable = MCP_TOOL_ROOT / ".venv/bin/mcp-server-datahub"
    if executable.is_file():
        commit = checked(
            ["git", "-C", str(MCP_TOOL_ROOT), "rev-parse", "HEAD"]
        ).stdout.strip()
        if commit != MCP_COMMIT:
            raise RuntimeError("the retained MCP tool is not the pinned commit")
        return executable
    if MCP_TOOL_ROOT.exists():
        raise RuntimeError("the retained MCP tool directory is incomplete")

    MCP_TOOL_ROOT.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(
            prefix=".mcp-server-datahub-",
            dir=MCP_TOOL_ROOT.parent,
        )
    )
    try:
        checked(["git", "init", str(temporary)])
        checked(["git", "-C", str(temporary), "remote", "add", "origin", MCP_SOURCE])
        checked(
            [
                "git",
                "-C",
                str(temporary),
                "fetch",
                "--depth=1",
                "origin",
                MCP_COMMIT,
            ],
            timeout=600,
        )
        checked(["git", "-C", str(temporary), "checkout", "--detach", "FETCH_HEAD"])
        commit = checked(
            ["git", "-C", str(temporary), "rev-parse", "HEAD"]
        ).stdout.strip()
        if commit != MCP_COMMIT:
            raise RuntimeError("MCP source checkout did not match the pin")
        os.replace(temporary, MCP_TOOL_ROOT)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    try:
        checked(
            ["uv", "sync", "--frozen", "--no-dev"],
            cwd=MCP_TOOL_ROOT,
            timeout=900,
        )
    except Exception:
        shutil.rmtree(MCP_TOOL_ROOT)
        raise
    if not executable.is_file():
        raise RuntimeError("the pinned MCP executable was not installed")
    return executable


def listening_socket_inodes(port: int) -> set[str]:
    inodes: set[str] = set()
    for table in (Path("/proc/net/tcp"), Path("/proc/net/tcp6")):
        if not table.is_file():
            continue
        for line in table.read_text(encoding="ascii").splitlines()[1:]:
            fields = line.split()
            if len(fields) < 10:
                continue
            local_endpoint = fields[1]
            state = fields[3]
            try:
                local_port = int(local_endpoint.rsplit(":", 1)[1], 16)
            except (IndexError, ValueError):
                continue
            if local_port == port and state == "0A":
                inodes.add(fields[9])
    return inodes


def listener_process_ids(port: int) -> set[int]:
    sockets = {f"socket:[{inode}]" for inode in listening_socket_inodes(port)}
    process_ids: set[int] = set()
    if not sockets:
        return process_ids
    for process in Path("/proc").iterdir():
        if not process.name.isdigit():
            continue
        try:
            descriptors = list((process / "fd").iterdir())
        except (FileNotFoundError, PermissionError):
            continue
        for descriptor in descriptors:
            try:
                target = os.readlink(descriptor)
            except (FileNotFoundError, PermissionError):
                continue
            if target in sockets:
                process_ids.add(int(process.name))
                break
    return process_ids


def mcp_listener_identity(*, expected_pid: int | None = None) -> dict[str, Any]:
    process_ids = listener_process_ids(MCP_PORT)
    if len(process_ids) != 1:
        raise RuntimeError("expected one process on the reference MCP port")
    process_id = next(iter(process_ids))
    if expected_pid is not None and process_id != expected_pid:
        raise RuntimeError("a different process claimed the reference MCP port")

    process_root = Path("/proc") / str(process_id)
    try:
        source_root = Path(os.readlink(process_root / "cwd")).resolve()
        command = [
            value.decode("utf-8")
            for value in (process_root / "cmdline").read_bytes().split(b"\0")
            if value
        ]
    except (FileNotFoundError, PermissionError, UnicodeDecodeError) as exc:
        raise RuntimeError("the reference MCP process could not be identified") from exc
    entry_points = [
        (
            source_root / value if not Path(value).is_absolute() else Path(value)
        ).resolve()
        for value in command
        if Path(value).name == "mcp-server-datahub"
    ]
    expected_entry_point = (source_root / ".venv/bin/mcp-server-datahub").resolve()
    if entry_points != [expected_entry_point]:
        raise RuntimeError("the reference MCP process uses an unknown entry point")
    commit = checked(
        ["git", "-C", str(source_root), "rev-parse", "HEAD"]
    ).stdout.strip()
    if commit != MCP_COMMIT:
        raise RuntimeError("the running MCP server is not the pinned source commit")
    tracked_changes = checked(
        [
            "git",
            "-C",
            str(source_root),
            "status",
            "--porcelain=v1",
            "--untracked-files=no",
        ]
    ).stdout.strip()
    if tracked_changes:
        raise RuntimeError("the running MCP source checkout has tracked changes")
    version_output = checked(
        [str(expected_entry_point), "--version"],
        cwd=source_root,
    ).stdout.strip()
    match = re.search(r"\bversion ([^\s]+)$", version_output)
    if match is None:
        raise RuntimeError("the running MCP package version was not observable")
    return {
        "listener": f"127.0.0.1:{MCP_PORT}",
        "source_commit": commit,
        "source_clean": True,
        "package_version": match.group(1),
    }


def start_mcp() -> tuple[subprocess.Popen[str] | None, dict[str, Any]]:
    if healthy(MCP_HEALTH_URL, json_required=True):
        return None, mcp_listener_identity()
    executable = prepare_mcp_tool()
    log_path = PHASE08_RUNTIME / "mcp-server.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = log_path.open("w", encoding="utf-8")
    environment = dict(os.environ)
    environment.update(
        {
            "DATAHUB_GMS_URL": DATAHUB_GMS_URL,
            "DATAHUB_SKIP_CONFIG": "true",
            "DATAHUB_MCP_DISABLE_DEFAULT_VIEW": "true",
            "TOOLS_IS_MUTATION_ENABLED": "true",
            "SAVE_DOCUMENT_TOOL_ENABLED": "true",
            "DATAHUB_TELEMETRY_ENABLED": "false",
            "DO_NOT_TRACK": "1",
        }
    )
    process = subprocess.Popen(
        [str(executable), "--transport", "http"],
        cwd=MCP_TOOL_ROOT,
        env=environment,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    log_file.close()
    for _ in range(90):
        if healthy(MCP_HEALTH_URL, json_required=True):
            return process, mcp_listener_identity(expected_pid=process.pid)
        if process.poll() is not None:
            raise RuntimeError("the pinned MCP server exited before health")
        time.sleep(1)
    process.terminate()
    process.wait(timeout=15)
    raise RuntimeError("the pinned MCP server did not become healthy")


def stop_datahub_core() -> None:
    checked(
        [
            "docker",
            "compose",
            "--env-file",
            str(COMPOSE_ENV),
            "-f",
            str(COMPOSE_FILE),
            "down",
        ],
        timeout=300,
    )


@contextmanager
def reference_services() -> Iterator[ReferenceServices]:
    gms_started = False
    process: subprocess.Popen[str] | None = None
    try:
        gms_started = ensure_datahub_core()
        process, identity = start_mcp()
        services = ReferenceServices(
            gms_started=gms_started,
            mcp_started=process is not None,
            mcp_process=process,
            mcp_identity=identity,
        )
        yield services
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=15)
        if gms_started:
            stop_datahub_core()

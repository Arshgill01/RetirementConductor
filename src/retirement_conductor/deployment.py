"""Secret-safe deployment preflight and confirmed local-state removal."""

from __future__ import annotations

import fcntl
import json
import os
import platform
import shutil
import stat
import sys
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from retirement_conductor import __version__
from retirement_conductor.canonical import (
    digest_file,
    digest_json,
    verify_digest,
    with_digest,
)
from retirement_conductor.clock import parse_timestamp
from retirement_conductor.errors import Refusal
from retirement_conductor.store import CampaignStore
from retirement_conductor.vocabulary import RefusalCode

DEPLOYMENT_PROFILES = (
    "local",
    "core-git-dbt",
)

_SECRET_REFERENCES = {
    "DATAHUB_GMS_TOKEN",
}

_PROFILE_REQUIREMENTS: dict[str, tuple[tuple[str, ...], ...]] = {
    "local": (),
    "core-git-dbt": (
        ("DATAHUB_GMS_URL",),
        ("DATAHUB_MCP_URL",),
        ("GIT_DBT_REPOSITORY_ROOT",),
        ("GIT_DBT_DBT_EXECUTABLE",),
        ("GIT_DBT_PRINCIPAL",),
    ),
}

_PROFILE_TOOLS = {
    "local": (),
    "core-git-dbt": ("git", "bwrap", "docker"),
}


def deployment_preflight(
    *,
    profile: str,
    store_path: Path,
    writer_id: str,
    artifact_directory: Path,
    environment: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Inspect one deployment without exposing configuration values."""

    if profile not in DEPLOYMENT_PROFILES:
        raise Refusal(
            RefusalCode.SPEC_SCHEMA_INVALID,
            "The deployment profile is unsupported.",
            {"allowed_profiles": list(DEPLOYMENT_PROFILES)},
        )
    if not writer_id.strip():
        raise Refusal(
            RefusalCode.SPEC_SCHEMA_INVALID,
            "RETIREMENT_CONDUCTOR_WRITER_ID cannot be empty.",
            {"required_reference": "RETIREMENT_CONDUCTOR_WRITER_ID"},
        )

    values = os.environ if environment is None else environment
    resolved_store = _require_product_state_path(store_path, "campaign store")
    resolved_artifacts = _require_product_state_path(
        artifact_directory,
        "artifact directory",
    )
    _require_distinct_state_targets(resolved_store, resolved_artifacts)

    configuration: list[dict[str, Any]] = []
    missing: list[str] = []
    for aliases in _PROFILE_REQUIREMENTS[profile]:
        configured = [name for name in aliases if values.get(name, "").strip()]
        reference = "|".join(aliases)
        if not configured:
            missing.append(reference)
        configuration.append(
            {
                "reference": reference,
                "present": bool(configured),
                "secret": any(name in _SECRET_REFERENCES for name in aliases),
            }
        )

    tools = [
        {
            "name": name,
            "available": shutil.which(name) is not None,
        }
        for name in _PROFILE_TOOLS[profile]
    ]
    missing.extend(f"tool:{tool['name']}" for tool in tools if not tool["available"])

    if profile == "core-git-dbt":
        dbt_reference = values.get("GIT_DBT_DBT_EXECUTABLE", "").strip()
        if dbt_reference:
            dbt_path = Path(dbt_reference).expanduser()
            dbt_available = (
                dbt_path.is_file()
                and not dbt_path.is_symlink()
                and os.access(dbt_path, os.X_OK)
            )
            tools.append({"name": "dbt", "available": dbt_available})
            if not dbt_available:
                missing.append("capability:executable-dbt")

    state = _state_preflight(
        resolved_store,
        writer_id=writer_id,
        artifact_directory=resolved_artifacts,
    )
    runtime_supported = sys.version_info >= (3, 11)
    if not runtime_supported:
        missing.append("runtime:python>=3.11")

    telemetry_setting = (
        values.get(
            "RETIREMENT_CONDUCTOR_LOCAL_METRICS",
            "false",
        )
        .strip()
        .lower()
    )
    if telemetry_setting not in {"true", "false"}:
        missing.append("RETIREMENT_CONDUCTOR_LOCAL_METRICS=true|false")

    missing = sorted(set(missing))
    ready = not missing
    return with_digest(
        {
            "schema_version": "1.0.0",
            "result": "READY" if ready else "REFUSED",
            "refusal_code": (
                None if ready else RefusalCode.RUNTIME_CONFIGURATION_INCOMPLETE
            ),
            "profile": profile,
            "ready": ready,
            "runtime": {
                "package_version": __version__,
                "python_version": platform.python_version(),
                "python_supported": runtime_supported,
                "implementation": platform.python_implementation(),
            },
            "state": state,
            "configuration": configuration,
            "tools": tools,
            "missing": missing,
            "telemetry": {
                "mode": "local-only",
                "enabled": telemetry_setting == "true",
                "remote_export": False,
                "activation": "explicit environment opt-in and command invocation",
            },
            "next_commands": [
                "retirement-conductor campaign diagnostics",
                "retirement-conductor datahub preflight",
                "retirement-conductor adapter git-dbt preflight",
            ],
            "limitations": [
                "Deployment preflight validates local configuration and tool "
                "presence; source commands establish effective remote permissions.",
                "A ready local profile does not satisfy live integration acceptance.",
            ],
        },
        "preflight_digest",
    )


def create_removal_plan(
    *,
    store_path: Path,
    writer_id: str,
    artifact_directory: Path,
    generated_at: str,
) -> dict[str, Any]:
    """Freeze the exact product-owned local files proposed for deletion."""

    parse_timestamp(generated_at)
    resolved_store = _require_product_state_path(store_path, "campaign store")
    resolved_artifacts = _require_product_state_path(
        artifact_directory,
        "artifact directory",
    )
    _require_distinct_state_targets(resolved_store, resolved_artifacts)
    if not resolved_store.is_file():
        raise Refusal(
            RefusalCode.SOURCE_NOT_FOUND,
            "The campaign store required for a removal plan was not found.",
        )
    with CampaignStore(resolved_store, writer_id=writer_id) as store:
        schema_versions = store.schema_versions()
    lock_path = _lock_path(resolved_store)
    with _exclusive_state_lock(lock_path):
        snapshot = _state_snapshot(resolved_store, resolved_artifacts)
    return with_digest(
        {
            "schema_version": "1.0.0",
            "generated_at": generated_at,
            "store_path": str(resolved_store),
            "store_path_identity": digest_json(str(resolved_store)),
            "artifact_directory": str(resolved_artifacts),
            "artifact_path_identity": digest_json(str(resolved_artifacts)),
            "writer_identity": digest_json(writer_id),
            "schema_versions": schema_versions,
            "state_snapshot": snapshot,
            "confirmation": {
                "required": True,
                "argument": "--confirm-plan-digest",
            },
            "excluded": [
                "retained backups outside the active artifact directory",
                "operator configuration and secret-provider values",
                "the installed Python package",
            ],
            "limitations": [
                "All Retirement Conductor processes must be stopped before removal.",
                "Deletion is not recoverable unless the operator retained a "
                "verified backup.",
            ],
        },
        "removal_plan_digest",
    )


def remove_deployment_state(
    plan: Mapping[str, Any],
    *,
    confirmed_plan_digest: str | None,
    store_path: Path,
    writer_id: str,
    artifact_directory: Path,
) -> dict[str, Any]:
    """Delete only the exact confirmed, unchanged product state."""

    value = dict(plan)
    verify_digest(value, "removal_plan_digest")
    expected_digest = str(value["removal_plan_digest"])
    if not confirmed_plan_digest:
        raise Refusal(
            RefusalCode.AUTH_APPROVAL_MISSING,
            "State removal requires confirmation of the exact removal plan digest.",
        )
    if confirmed_plan_digest != expected_digest:
        raise Refusal(
            RefusalCode.AUTH_APPROVAL_WRONG_PLAN,
            "The confirmed digest does not match the current removal plan.",
        )

    resolved_store = _require_product_state_path(store_path, "campaign store")
    resolved_artifacts = _require_product_state_path(
        artifact_directory,
        "artifact directory",
    )
    _require_distinct_state_targets(resolved_store, resolved_artifacts)
    if (
        str(value.get("store_path")) != str(resolved_store)
        or str(value.get("artifact_directory")) != str(resolved_artifacts)
        or value.get("writer_identity") != digest_json(writer_id)
    ):
        raise Refusal(
            RefusalCode.AUTH_APPROVAL_WRONG_SCOPE,
            "The removal plan belongs to another deployment scope.",
        )

    lock_path = _lock_path(resolved_store)
    with _exclusive_state_lock(lock_path):
        current = _state_snapshot(resolved_store, resolved_artifacts)
        planned = value.get("state_snapshot")
        if not isinstance(planned, Mapping):
            raise Refusal(
                RefusalCode.INTEGRITY_DIGEST_MISMATCH,
                "The removal plan has no valid state snapshot.",
            )
        if current.get("state_snapshot_digest") != planned.get("state_snapshot_digest"):
            raise Refusal(
                RefusalCode.RUNTIME_STATE_DRIFT,
                "Product state changed after the removal plan was generated.",
                {
                    "expected_snapshot_digest": planned.get("state_snapshot_digest"),
                    "actual_snapshot_digest": current.get("state_snapshot_digest"),
                },
            )
        removed_files = int(current["file_count"])
        removed_bytes = int(current["total_bytes"])
        if resolved_artifacts.exists():
            shutil.rmtree(resolved_artifacts)
        for candidate in _store_files(resolved_store):
            if candidate != lock_path:
                candidate.unlink(missing_ok=True)
        _fsync_directory(resolved_store.parent)
        if resolved_artifacts.parent != resolved_store.parent:
            _fsync_directory(resolved_artifacts.parent)
    lock_path.unlink(missing_ok=True)
    _fsync_directory(lock_path.parent)

    return with_digest(
        {
            "schema_version": "1.0.0",
            "result": "STATE_REMOVED",
            "removal_plan_digest": expected_digest,
            "removed_file_count": removed_files,
            "removed_bytes": removed_bytes,
            "store_path_identity": digest_json(str(resolved_store)),
            "artifact_path_identity": digest_json(str(resolved_artifacts)),
            "retained": list(value.get("excluded", [])),
            "limitations": [
                "Python package removal remains an explicit package-manager step."
            ],
        },
        "removal_receipt_digest",
    )


def load_removal_plan(path: Path) -> dict[str, Any]:
    """Read and validate one ignored local removal plan."""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Refusal(
            RefusalCode.INTEGRITY_DIGEST_MISMATCH,
            "The removal plan could not be read.",
            {"error_type": type(exc).__name__},
        ) from exc
    if not isinstance(value, dict):
        raise Refusal(
            RefusalCode.INTEGRITY_DIGEST_MISMATCH,
            "The removal plan must be a JSON object.",
        )
    verify_digest(value, "removal_plan_digest")
    return value


def _state_preflight(
    store_path: Path,
    *,
    writer_id: str,
    artifact_directory: Path,
) -> dict[str, Any]:
    store_exists = store_path.is_file()
    schema_versions: list[int] = []
    filesystem_type = "not-created"
    if store_exists:
        with CampaignStore(store_path, writer_id=writer_id) as store:
            schema_versions = store.schema_versions()
            filesystem_type = store.filesystem_type or "unknown"
        store_mode = f"{stat.S_IMODE(store_path.stat().st_mode):04o}"
    else:
        store_mode = None
    parent = _nearest_existing_parent(store_path.parent)
    artifact_parent = _nearest_existing_parent(artifact_directory)
    return {
        "store_exists": store_exists,
        "store_path_identity": digest_json(str(store_path)),
        "store_mode": store_mode,
        "schema_versions": schema_versions,
        "filesystem_type": filesystem_type,
        "store_parent_writable": os.access(parent, os.W_OK | os.X_OK),
        "artifact_directory_exists": artifact_directory.is_dir(),
        "artifact_path_identity": digest_json(str(artifact_directory)),
        "artifact_parent_writable": os.access(
            artifact_parent,
            os.W_OK | os.X_OK,
        ),
        "writer_identity": digest_json(writer_id),
        "single_writer": True,
    }


def _state_snapshot(store_path: Path, artifact_directory: Path) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for candidate in _store_files(store_path):
        if not candidate.exists():
            continue
        if candidate.is_symlink() or not candidate.is_file():
            raise Refusal(
                RefusalCode.SCOPE_TARGET_NOT_ALLOWED,
                "Product state contains an unsupported store entry.",
            )
        entries.append(_file_entry(candidate, "store", candidate.name))

    if artifact_directory.exists():
        if artifact_directory.is_symlink() or not artifact_directory.is_dir():
            raise Refusal(
                RefusalCode.SCOPE_TARGET_NOT_ALLOWED,
                "The artifact state target must be one real directory.",
            )
        for candidate in sorted(artifact_directory.rglob("*")):
            if candidate.is_symlink():
                raise Refusal(
                    RefusalCode.SCOPE_TARGET_NOT_ALLOWED,
                    "Product state contains a symbolic link and cannot be removed.",
                )
            if candidate.is_file():
                entries.append(
                    _file_entry(
                        candidate,
                        "artifacts",
                        candidate.relative_to(artifact_directory).as_posix(),
                    )
                )
            elif not candidate.is_dir():
                raise Refusal(
                    RefusalCode.SCOPE_TARGET_NOT_ALLOWED,
                    "Product state contains an unsupported filesystem entry.",
                )
    entries.sort(key=lambda item: (str(item["component"]), str(item["path"])))
    return with_digest(
        {
            "schema_version": "1.0.0",
            "files": entries,
            "file_count": len(entries),
            "total_bytes": sum(int(item["size"]) for item in entries),
        },
        "state_snapshot_digest",
    )


def _file_entry(path: Path, component: str, relative_path: str) -> dict[str, Any]:
    return {
        "component": component,
        "path": relative_path,
        "size": path.stat().st_size,
        "mode": f"{stat.S_IMODE(path.stat().st_mode):04o}",
        "digest": digest_file(path),
    }


def _store_files(store_path: Path) -> Sequence[Path]:
    return (
        store_path,
        store_path.with_name(f"{store_path.name}-wal"),
        store_path.with_name(f"{store_path.name}-shm"),
        _lock_path(store_path),
    )


def _lock_path(store_path: Path) -> Path:
    return store_path.with_name(f"{store_path.name}.lock")


@contextmanager
def _exclusive_state_lock(lock_path: Path) -> Iterator[None]:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        os.fchmod(lock_file.fileno(), 0o600)
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise Refusal(
                RefusalCode.RUNTIME_STORE_LOCKED,
                "Another local writer currently owns the campaign store.",
            ) from exc
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _require_product_state_path(path: Path, label: str) -> Path:
    if path.is_symlink() or _has_symlink_component(path):
        raise Refusal(
            RefusalCode.SCOPE_TARGET_NOT_ALLOWED,
            f"The {label} cannot use a symbolic-link path.",
        )
    resolved = path.expanduser().resolve()
    forbidden = {
        Path("/"),
        Path.home().resolve(),
        Path.cwd().resolve(),
    }
    if resolved in forbidden or ".retirement-conductor" not in resolved.parts:
        raise Refusal(
            RefusalCode.SCOPE_TARGET_NOT_ALLOWED,
            f"The {label} must be inside one .retirement-conductor directory.",
        )
    return resolved


def _require_distinct_state_targets(
    store_path: Path,
    artifact_directory: Path,
) -> None:
    if (
        store_path == artifact_directory
        or artifact_directory in store_path.parents
        or store_path in artifact_directory.parents
    ):
        raise Refusal(
            RefusalCode.SCOPE_TARGET_NOT_ALLOWED,
            "The campaign store and artifact directory must not contain each other.",
        )


def _has_symlink_component(path: Path) -> bool:
    candidate = path.expanduser().absolute()
    while True:
        if candidate.is_symlink():
            return True
        if candidate.parent == candidate:
            return False
        candidate = candidate.parent


def _nearest_existing_parent(path: Path) -> Path:
    candidate = path
    while not candidate.exists() and candidate.parent != candidate:
        candidate = candidate.parent
    return candidate


def _fsync_directory(path: Path) -> None:
    if not path.exists():
        return
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)

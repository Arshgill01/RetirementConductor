"""Pinned acquisition and offline verification for benchmark datasets."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import zipfile
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from retirement_conductor.canonical import digest_json, with_digest, write_json
from retirement_conductor.errors import Refusal
from retirement_conductor.schemas import validate_schema
from retirement_conductor.vocabulary import RefusalCode

_APPROVED_LICENSES = frozenset(
    {
        "CC0-1.0",
        "LicenseRef-NYC-Public-Domain",
    }
)
_PINNED_RAW_PREFIX = "https://raw.githubusercontent.com/datahub-project/static-assets"
_REVISION_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_SQLITE_HEADER = b"SQLite format 3\x00"


def default_registry_path() -> Path:
    """Locate the source-checkout or installed dataset registry."""

    candidates = (
        Path(__file__).resolve().parent / "data_quality_data" / "datasets.json",
        Path(__file__).resolve().parents[2]
        / "fixtures"
        / "data-quality"
        / "datasets.json",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise RuntimeError("the packaged dataset registry is unavailable")


def load_dataset_registry(path: Path) -> dict[str, Any]:
    """Load and semantically verify one versioned dataset registry."""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Refusal(
            RefusalCode.DATASET_REGISTRY_INVALID,
            "The dataset registry could not be parsed.",
            {"error_type": type(exc).__name__},
        ) from exc
    if not isinstance(value, dict):
        raise Refusal(
            RefusalCode.DATASET_REGISTRY_INVALID,
            "The dataset registry must be a JSON object.",
        )
    validate_schema(
        "dataset-registry",
        value,
        refusal_code=RefusalCode.DATASET_REGISTRY_INVALID,
    )
    revision = str(_mapping(value["upstream"])["revision"])
    if not _REVISION_PATTERN.fullmatch(revision):
        raise Refusal(
            RefusalCode.DATASET_SOURCE_UNPINNED,
            "The upstream dataset revision must be one full Git commit.",
        )

    seen_asset_ids: set[str] = set()
    for asset_value in _assets(value):
        asset_id = str(asset_value["asset_id"])
        if asset_id in seen_asset_ids:
            raise Refusal(
                RefusalCode.DATASET_REGISTRY_INVALID,
                "Dataset asset identifiers must be unique.",
                {"asset_id": asset_id},
            )
        seen_asset_ids.add(asset_id)
        _validate_asset(asset_value, revision)
    return value


def acquire_datasets(
    registry_path: Path,
    cache_root: Path,
    *,
    offline: bool,
    receipt_path: Path | None = None,
) -> dict[str, Any]:
    """Acquire or offline-verify every asset without exposing local paths."""

    registry = load_dataset_registry(registry_path)
    cache = _prepare_cache_root(cache_root)
    verified_assets: list[dict[str, Any]] = []
    for asset in _assets(registry):
        target = cached_asset_path(cache, asset)
        if not target.is_file():
            if offline:
                raise Refusal(
                    RefusalCode.DATASET_CACHE_MISSING,
                    "A required dataset asset is absent from the offline cache.",
                    {"asset_id": asset["asset_id"]},
                )
            _download_asset(asset, target)
        archive_members = _verify_asset_file(asset, target)
        verified_assets.append(
            {
                "archive_members": archive_members,
                "asset_id": asset["asset_id"],
                "cache_key": target.relative_to(cache).as_posix(),
                "dataset_id": asset["dataset_id"],
                "license_id": asset["license_id"],
                "sha256": asset["sha256"],
                "size_bytes": asset["size_bytes"],
                "variant": asset["variant"],
                "verified": True,
            }
        )

    receipt = with_digest(
        {
            "all_verified": True,
            "assets": verified_assets,
            "mode": "offline-verify" if offline else "acquire",
            "registry_digest": digest_json(registry),
            "schema_version": "dataset-cache-receipt/v1",
            "upstream_revision": _mapping(registry["upstream"])["revision"],
        },
        "receipt_digest",
    )
    validate_schema(
        "dataset-cache-receipt",
        receipt,
        refusal_code=RefusalCode.DATASET_REGISTRY_INVALID,
    )
    write_json(receipt_path or cache / "registry-receipt.json", receipt)
    return receipt


def cached_asset_path(cache_root: Path, asset: Mapping[str, Any]) -> Path:
    """Return one bounded content-addressed cache path."""

    digest = str(asset["sha256"])
    digest_hex = digest.removeprefix("sha256:")
    filename = PurePosixPath(str(asset["source_path"])).name
    if not filename or filename in {".", ".."} or "/" in filename:
        raise Refusal(
            RefusalCode.DATASET_REGISTRY_INVALID,
            "A dataset source path does not have a safe file name.",
            {"asset_id": asset.get("asset_id")},
        )
    content_root = cache_root / "sha256"
    _refuse_symlink(content_root)
    content_root.mkdir(parents=True, exist_ok=True)
    entry_root = content_root / digest_hex
    _refuse_symlink(entry_root)
    entry_root.mkdir(parents=True, exist_ok=True)
    root = cache_root.resolve(strict=True)
    target = entry_root / filename
    resolved = target.resolve(strict=False)
    if root not in resolved.parents:
        raise Refusal(
            RefusalCode.SCOPE_PATH_OUTSIDE_ROOT,
            "The dataset cache entry resolves outside the configured cache.",
            {"asset_id": asset.get("asset_id")},
        )
    if target.is_symlink():
        raise Refusal(
            RefusalCode.SCOPE_PATH_OUTSIDE_ROOT,
            "A dataset cache entry cannot be a symbolic link.",
            {"asset_id": asset.get("asset_id")},
        )
    return target


def _validate_asset(asset: Mapping[str, Any], revision: str) -> None:
    license_id = str(asset["license_id"])
    if license_id not in _APPROVED_LICENSES:
        raise Refusal(
            RefusalCode.DATASET_LICENSE_UNAPPROVED,
            "The dataset license is not in the reviewed allowlist.",
            {"asset_id": asset["asset_id"], "license_id": license_id},
        )
    source_path = str(asset["source_path"])
    source_url = str(asset["source_url"])
    expected_source_url = f"{_PINNED_RAW_PREFIX}/{revision}/{source_path}"
    if source_url != expected_source_url:
        raise Refusal(
            RefusalCode.DATASET_SOURCE_UNPINNED,
            "The dataset source URL is not bound to its declared revision and path.",
            {"asset_id": asset["asset_id"]},
        )
    evidence_url = str(asset["license_evidence_url"])
    _require_pinned_raw_url(evidence_url, revision, asset_id=str(asset["asset_id"]))
    archive_members = [str(item) for item in asset["allowed_archive_members"]]
    if asset["format"] == "zip" and not archive_members:
        raise Refusal(
            RefusalCode.DATASET_REGISTRY_INVALID,
            "A ZIP dataset must declare its complete member allowlist.",
            {"asset_id": asset["asset_id"]},
        )
    if asset["format"] != "zip" and archive_members:
        raise Refusal(
            RefusalCode.DATASET_REGISTRY_INVALID,
            "A non-archive dataset cannot declare archive members.",
            {"asset_id": asset["asset_id"]},
        )
    for member in archive_members:
        _validate_archive_member(member, asset_id=str(asset["asset_id"]))


def _require_pinned_raw_url(url: str, revision: str, *, asset_id: str) -> None:
    parsed = urlparse(url)
    expected_prefix = f"/datahub-project/static-assets/{revision}/"
    if (
        parsed.scheme != "https"
        or parsed.netloc != "raw.githubusercontent.com"
        or not parsed.path.startswith(expected_prefix)
        or parsed.params
        or parsed.query
        or parsed.fragment
    ):
        raise Refusal(
            RefusalCode.DATASET_SOURCE_UNPINNED,
            "A dataset evidence URL is not bound to the reviewed upstream commit.",
            {"asset_id": asset_id},
        )


def _prepare_cache_root(cache_root: Path) -> Path:
    _refuse_symlink(cache_root)
    cache_root.mkdir(parents=True, exist_ok=True)
    return cache_root.resolve(strict=True)


def _refuse_symlink(path: Path) -> None:
    if path.is_symlink():
        raise Refusal(
            RefusalCode.SCOPE_PATH_OUTSIDE_ROOT,
            "The dataset cache cannot traverse a symbolic link.",
        )


def _download_asset(asset: Mapping[str, Any], target: Path) -> None:
    expected_size = int(asset["size_bytes"])
    request = Request(
        str(asset["source_url"]),
        headers={
            "Accept": "application/octet-stream",
            "User-Agent": "retirement-conductor",
        },
        method="GET",
    )
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "wb",
            dir=target.parent,
            prefix=f".{target.name}.",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            with urlopen(request, timeout=60) as response:
                final_url = response.geturl()
                if final_url != asset["source_url"]:
                    raise Refusal(
                        RefusalCode.DATASET_SOURCE_UNPINNED,
                        "The dataset download redirected away from the pinned URL.",
                        {"asset_id": asset["asset_id"]},
                    )
                received = 0
                while chunk := response.read(1024 * 1024):
                    received += len(chunk)
                    if received > expected_size:
                        raise Refusal(
                            RefusalCode.DATASET_SIZE_MISMATCH,
                            "The downloaded dataset exceeded its pinned size.",
                            {
                                "asset_id": asset["asset_id"],
                                "expected_size": expected_size,
                                "actual_size": received,
                            },
                        )
                    temporary.write(chunk)
            temporary.flush()
            os.fsync(temporary.fileno())
        _verify_asset_file(asset, temporary_path)
        os.replace(temporary_path, target)
        temporary_path = None
    except Refusal:
        raise
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise Refusal(
            RefusalCode.DATASET_DOWNLOAD_FAILED,
            "The pinned dataset asset could not be downloaded.",
            {"asset_id": asset["asset_id"], "error_type": type(exc).__name__},
        ) from exc
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _verify_asset_file(asset: Mapping[str, Any], path: Path) -> list[str]:
    actual_size = path.stat().st_size
    expected_size = int(asset["size_bytes"])
    if actual_size != expected_size:
        raise Refusal(
            RefusalCode.DATASET_SIZE_MISMATCH,
            "The dataset asset size does not match the registry.",
            {
                "asset_id": asset["asset_id"],
                "expected_size": expected_size,
                "actual_size": actual_size,
            },
        )
    hasher = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            hasher.update(chunk)
    actual_digest = f"sha256:{hasher.hexdigest()}"
    if actual_digest != asset["sha256"]:
        raise Refusal(
            RefusalCode.DATASET_CHECKSUM_MISMATCH,
            "The dataset asset checksum does not match the registry.",
            {
                "asset_id": asset["asset_id"],
                "expected": asset["sha256"],
                "actual": actual_digest,
            },
        )
    if asset["format"] == "sqlite":
        with path.open("rb") as source:
            header = source.read(len(_SQLITE_HEADER))
        if header != _SQLITE_HEADER:
            raise Refusal(
                RefusalCode.DATASET_REGISTRY_INVALID,
                "A pinned SQLite asset does not have a SQLite file header.",
                {"asset_id": asset["asset_id"]},
            )
        return []
    return _verify_archive(asset, path)


def _verify_archive(asset: Mapping[str, Any], path: Path) -> list[str]:
    expected = sorted(str(item) for item in asset["allowed_archive_members"])
    try:
        with zipfile.ZipFile(path) as archive:
            actual = sorted(info.filename for info in archive.infolist())
    except zipfile.BadZipFile as exc:
        raise Refusal(
            RefusalCode.DATASET_ARCHIVE_UNEXPECTED_MEMBER,
            "The pinned dataset archive is not a valid ZIP file.",
            {"asset_id": asset["asset_id"]},
        ) from exc
    for member in actual:
        _validate_archive_member(member, asset_id=str(asset["asset_id"]))
    if actual != expected:
        raise Refusal(
            RefusalCode.DATASET_ARCHIVE_UNEXPECTED_MEMBER,
            "The dataset archive members do not match the explicit allowlist.",
            {
                "asset_id": asset["asset_id"],
                "expected_members": expected,
                "actual_members": actual,
            },
        )
    return actual


def _validate_archive_member(member: str, *, asset_id: str) -> None:
    path = PurePosixPath(member)
    if path.is_absolute() or ".." in path.parts or member.endswith("/"):
        raise Refusal(
            RefusalCode.DATASET_ARCHIVE_UNEXPECTED_MEMBER,
            "A dataset archive contains an unsafe or unexpected member.",
            {"asset_id": asset_id, "member": member},
        )


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _assets(registry: Mapping[str, Any]) -> list[dict[str, Any]]:
    value = registry.get("assets")
    if not isinstance(value, list):
        return []
    return [dict(asset) for asset in value if isinstance(asset, Mapping)]

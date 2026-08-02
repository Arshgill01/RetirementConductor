from __future__ import annotations

import io
import json
import sqlite3
import zipfile
from pathlib import Path
from typing import Any
from urllib.request import Request

import pytest

from retirement_conductor import dataset_registry
from retirement_conductor.canonical import digest_bytes, verify_digest, write_json
from retirement_conductor.dataset_registry import (
    acquire_datasets,
    cached_asset_path,
    load_dataset_registry,
)
from retirement_conductor.errors import Refusal
from retirement_conductor.vocabulary import RefusalCode

REVISION = "a6479c691dd2a40dd89563396d9c8b2b28bee83c"
ROOT = Path(__file__).resolve().parents[2]


class DownloadResponse(io.BytesIO):
    def __init__(self, content: bytes, url: str) -> None:
        super().__init__(content)
        self._url = url

    def geturl(self) -> str:
        return self._url


def sqlite_content(path: Path) -> bytes:
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE orders (order_id TEXT PRIMARY KEY)")
        connection.execute("INSERT INTO orders VALUES ('order-1')")
    return path.read_bytes()


def registry_value(
    content: bytes,
    *,
    source_path: str = "datasets/fiction-retail/fixture.db",
    format_name: str = "sqlite",
    archive_members: list[str] | None = None,
) -> dict[str, Any]:
    source_url = (
        "https://raw.githubusercontent.com/datahub-project/static-assets/"
        f"{REVISION}/{source_path}"
    )
    return {
        "assets": [
            {
                "allowed_archive_members": archive_members or [],
                "asset_id": "fiction-retail-test",
                "dataset_id": "fiction-retail",
                "format": format_name,
                "license_evidence_url": (
                    "https://raw.githubusercontent.com/datahub-project/"
                    f"static-assets/{REVISION}/datasets/fiction-retail/README.md"
                ),
                "license_id": "CC0-1.0",
                "quality_role": "relational-control",
                "sha256": digest_bytes(content),
                "size_bytes": len(content),
                "source_path": source_path,
                "source_url": source_url,
                "variant": "clean",
            }
        ],
        "resources_page": "https://datahub.devpost.com/resources",
        "schema_version": "dataset-registry/v1",
        "upstream": {
            "repository": "https://github.com/datahub-project/static-assets",
            "revision": REVISION,
        },
    }


def write_registry(path: Path, value: dict[str, Any]) -> None:
    write_json(path, value)


def install_download(
    monkeypatch: pytest.MonkeyPatch,
    content: bytes,
    expected_url: str,
) -> None:
    def open_source(request: Request, *, timeout: int) -> DownloadResponse:
        assert request.full_url == expected_url
        assert timeout == 60
        return DownloadResponse(content, expected_url)

    monkeypatch.setattr(dataset_registry, "urlopen", open_source)


def test_acquire_and_offline_verify_content_addressed_asset(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    content = sqlite_content(tmp_path / "source.db")
    registry = registry_value(content)
    registry_path = tmp_path / "datasets.json"
    cache = tmp_path / "cache"
    write_registry(registry_path, registry)
    source_url = str(registry["assets"][0]["source_url"])
    install_download(monkeypatch, content, source_url)

    acquired = acquire_datasets(registry_path, cache, offline=False)
    verified = acquire_datasets(
        registry_path,
        cache,
        offline=True,
        receipt_path=tmp_path / "verify-receipt.json",
    )

    verify_digest(acquired, "receipt_digest")
    verify_digest(verified, "receipt_digest")
    assert acquired["mode"] == "acquire"
    assert verified["mode"] == "offline-verify"
    asset = load_dataset_registry(registry_path)["assets"][0]
    target = cached_asset_path(cache, asset)
    assert target.read_bytes() == content
    assert acquired["assets"][0]["cache_key"].startswith("sha256/")
    assert str(tmp_path) not in json.dumps(acquired)


def test_offline_verification_refuses_missing_cache(tmp_path: Path) -> None:
    content = sqlite_content(tmp_path / "source.db")
    registry_path = tmp_path / "datasets.json"
    write_registry(registry_path, registry_value(content))

    with pytest.raises(Refusal) as caught:
        acquire_datasets(registry_path, tmp_path / "cache", offline=True)

    assert caught.value.code == RefusalCode.DATASET_CACHE_MISSING


def test_acquisition_refuses_checksum_mismatch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    content = sqlite_content(tmp_path / "source.db")
    registry = registry_value(content)
    registry["assets"][0]["sha256"] = f"sha256:{'0' * 64}"
    registry_path = tmp_path / "datasets.json"
    write_registry(registry_path, registry)
    source_url = str(registry["assets"][0]["source_url"])
    install_download(monkeypatch, content, source_url)

    with pytest.raises(Refusal) as caught:
        acquire_datasets(registry_path, tmp_path / "cache", offline=False)

    assert caught.value.code == RefusalCode.DATASET_CHECKSUM_MISMATCH


def test_acquisition_refuses_size_mismatch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    content = sqlite_content(tmp_path / "source.db")
    registry = registry_value(content)
    registry["assets"][0]["size_bytes"] = len(content) + 1
    registry_path = tmp_path / "datasets.json"
    write_registry(registry_path, registry)
    source_url = str(registry["assets"][0]["source_url"])
    install_download(monkeypatch, content, source_url)

    with pytest.raises(Refusal) as caught:
        acquire_datasets(registry_path, tmp_path / "cache", offline=False)

    assert caught.value.code == RefusalCode.DATASET_SIZE_MISMATCH


def test_registry_refuses_unreviewed_license(tmp_path: Path) -> None:
    content = sqlite_content(tmp_path / "source.db")
    registry = registry_value(content)
    registry["assets"][0]["license_id"] = "LicenseRef-Unknown"
    registry_path = tmp_path / "datasets.json"
    write_registry(registry_path, registry)

    with pytest.raises(Refusal) as caught:
        load_dataset_registry(registry_path)

    assert caught.value.code == RefusalCode.DATASET_LICENSE_UNAPPROVED


def test_registry_refuses_moving_source_url(tmp_path: Path) -> None:
    content = sqlite_content(tmp_path / "source.db")
    registry = registry_value(content)
    registry["assets"][0]["source_url"] = (
        "https://raw.githubusercontent.com/datahub-project/static-assets/"
        "main/datasets/fiction-retail/fixture.db"
    )
    registry_path = tmp_path / "datasets.json"
    write_registry(registry_path, registry)

    with pytest.raises(Refusal) as caught:
        load_dataset_registry(registry_path)

    assert caught.value.code == RefusalCode.DATASET_SOURCE_UNPINNED


def test_acquisition_refuses_unexpected_archive_member(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    archive_path = tmp_path / "asset.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("expected.db", b"expected")
        archive.writestr("unexpected.txt", b"unexpected")
    content = archive_path.read_bytes()
    registry = registry_value(
        content,
        source_path="datasets/fiction-retail/fixture.zip",
        format_name="zip",
        archive_members=["expected.db"],
    )
    registry_path = tmp_path / "datasets.json"
    write_registry(registry_path, registry)
    source_url = str(registry["assets"][0]["source_url"])
    install_download(monkeypatch, content, source_url)

    with pytest.raises(Refusal) as caught:
        acquire_datasets(registry_path, tmp_path / "cache", offline=False)

    assert caught.value.code == RefusalCode.DATASET_ARCHIVE_UNEXPECTED_MEMBER


def test_tracked_registry_pins_the_reviewed_official_assets() -> None:
    registry = load_dataset_registry(ROOT / "fixtures/data-quality/datasets.json")

    assert registry["upstream"]["revision"] == REVISION
    assert {asset["asset_id"] for asset in registry["assets"]} == {
        "fiction-retail-database",
        "healthcare-database",
        "nyc-taxi-clean-database",
        "nyc-taxi-stale-database",
    }

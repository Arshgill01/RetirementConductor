from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from retirement_conductor.benchmark_data import (
    compare_generation_outputs,
    generate_benchmark_corpus,
    verify_generation_output,
)
from retirement_conductor.canonical import digest_file, write_json
from retirement_conductor.dataset_registry import cached_asset_path
from retirement_conductor.errors import Refusal
from retirement_conductor.vocabulary import RefusalCode

REVISION = "a6479c691dd2a40dd89563396d9c8b2b28bee83c"


def create_fiction_database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE customers (
              customer_id TEXT, signup_date TEXT, country TEXT, state TEXT,
              city TEXT, customer_segment TEXT
            );
            CREATE TABLE orders (
              order_id TEXT, customer_id TEXT, order_date TEXT,
              order_status TEXT, total_amount REAL, payment_method TEXT,
              shipping_country TEXT, promo_id TEXT
            );
            CREATE TABLE order_items (
              order_item_id TEXT, order_id TEXT, product_id TEXT,
              quantity INTEGER, unit_price REAL, discount_pct REAL
            );
            CREATE TABLE products (
              product_id TEXT, category TEXT, brand TEXT, price REAL,
              weight_kg REAL, supplier_id TEXT
            );
            CREATE TABLE suppliers (
              supplier_id TEXT, country TEXT, contract_start_date TEXT,
              status TEXT
            );
            CREATE TABLE inventory (
              inventory_id TEXT, product_id TEXT, warehouse_id TEXT,
              quantity_on_hand INTEGER, reserved_quantity INTEGER,
              reorder_threshold INTEGER, last_restocked_date TEXT
            );
            CREATE TABLE warehouses (
              warehouse_id TEXT, city TEXT, state TEXT, country TEXT,
              capacity_units INTEGER, opened_date TEXT
            );
            CREATE TABLE shipments (
              shipment_id TEXT, order_id TEXT, warehouse_id TEXT,
              carrier TEXT, shipped_date TEXT, delivered_date TEXT,
              shipment_state TEXT
            );
            CREATE TABLE returns (
              return_id TEXT, order_id TEXT, product_id TEXT, return_date TEXT,
              refund_amount REAL, return_reason_code TEXT
            );
            CREATE TABLE promotions (
              promo_id TEXT, discount_pct REAL, valid_from TEXT,
              valid_until TEXT, applies_to_category TEXT, max_uses INTEGER,
              status TEXT
            );
            INSERT INTO customers VALUES
              ('c1','2023-01-01','US','CA','Oakland','Retail'),
              ('c2','2023-01-02','US','NY','Albany','Wholesale');
            INSERT INTO suppliers VALUES ('s1','US','2022-01-01','Active');
            INSERT INTO warehouses VALUES
              ('w1','Oakland','CA','US',1000,'2020-01-01');
            INSERT INTO products VALUES
              ('p1','Tools','North','10.0','1.0','s1'),
              ('p2','Home','South','20.0','2.0','s1');
            INSERT INTO promotions VALUES
              ('promo1',10,'2023-01-01','2024-12-31',NULL,100,'Active');
            INSERT INTO orders VALUES
              ('o1','c1','2024-01-01','delivered',20,'card','US','promo1'),
              ('o2','c2','2024-01-02','returned',40,'cash','US',NULL);
            INSERT INTO order_items VALUES
              ('i1','o1','p1',2,10,0),
              ('i2','o2','p2',2,20,0);
            INSERT INTO inventory VALUES
              ('inv1','p1','w1',20,2,5,'2024-01-01'),
              ('inv2','p2','w1',30,3,5,'2024-01-01');
            INSERT INTO shipments VALUES
              ('sh1','o1','w1','A','2024-01-02','2024-01-03','Delivered'),
              ('sh2','o2','w1','B','2024-01-03','2024-01-04','Delivered');
            INSERT INTO returns VALUES
              ('r1','o2','p2','2024-01-05',40,'Defective');
            """
        )


def create_healthcare_database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE raw_patients (
              billing_amount TEXT, name TEXT, age TEXT,
              discharge_date TEXT, date_of_admission TEXT
            );
            CREATE TABLE mart_billing (
              billing_amount REAL, name TEXT, length_of_stay_days INTEGER
            );
            CREATE TABLE mart_demographics (name TEXT, age INTEGER);
            INSERT INTO raw_patients VALUES
              ('-10',NULL,'130','2024-01-01','2024-01-03');
            INSERT INTO mart_billing VALUES (-10,NULL,-2);
            INSERT INTO mart_demographics VALUES (NULL,130);
            """
        )


def create_taxi_database(path: Path, *, stale: bool) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE raw_trips (tpep_pickup_datetime TEXT);
            CREATE TABLE staging_trips (trip_date TEXT);
            CREATE TABLE mart_daily_summary (trip_date TEXT, trip_count INTEGER);
            INSERT INTO raw_trips VALUES ('2024-01-10 12:00:00');
            """
        )
        stage_date = "2024-01-01" if stale else "2024-01-10"
        connection.execute("INSERT INTO staging_trips VALUES (?)", (stage_date,))
        connection.execute(
            "INSERT INTO mart_daily_summary VALUES (?, 1)", (stage_date,)
        )


def prepare_registry(tmp_path: Path) -> tuple[Path, Path]:
    sources = tmp_path / "sources"
    sources.mkdir()
    files = {
        "fiction-retail-database": sources / "fiction-retail.db",
        "healthcare-database": sources / "healthcare.db",
        "nyc-taxi-clean-database": sources / "nyc_taxi.db",
        "nyc-taxi-stale-database": sources / "nyc_taxi_pipeline.db",
    }
    create_fiction_database(files["fiction-retail-database"])
    create_healthcare_database(files["healthcare-database"])
    create_taxi_database(files["nyc-taxi-clean-database"], stale=False)
    create_taxi_database(files["nyc-taxi-stale-database"], stale=True)
    definitions = (
        (
            "fiction-retail-database",
            "fiction-retail",
            "clean",
            "relational-control",
            "datasets/fiction-retail/fiction-retail.db",
            "CC0-1.0",
        ),
        (
            "healthcare-database",
            "healthcare",
            "planted-quality-faults",
            "branch-selective-quality",
            "datasets/healthcare/healthcare.db",
            "CC0-1.0",
        ),
        (
            "nyc-taxi-clean-database",
            "nyc-taxi",
            "clean",
            "freshness-control",
            "datasets/nyc-taxi/nyc_taxi.db",
            "LicenseRef-NYC-Public-Domain",
        ),
        (
            "nyc-taxi-stale-database",
            "nyc-taxi",
            "stale",
            "freshness-fault",
            "datasets/nyc-taxi/nyc_taxi_pipeline.db",
            "LicenseRef-NYC-Public-Domain",
        ),
    )
    assets: list[dict[str, Any]] = []
    for asset_id, dataset_id, variant, role, source_path, license_id in definitions:
        path = files[asset_id]
        assets.append(
            {
                "allowed_archive_members": [],
                "asset_id": asset_id,
                "dataset_id": dataset_id,
                "format": "sqlite",
                "license_evidence_url": (
                    "https://raw.githubusercontent.com/datahub-project/"
                    f"static-assets/{REVISION}/datasets/{dataset_id}/README.md"
                ),
                "license_id": license_id,
                "quality_role": role,
                "sha256": digest_file(path),
                "size_bytes": path.stat().st_size,
                "source_path": source_path,
                "source_url": (
                    "https://raw.githubusercontent.com/datahub-project/"
                    f"static-assets/{REVISION}/{source_path}"
                ),
                "variant": variant,
            }
        )
    registry = {
        "assets": assets,
        "resources_page": "https://datahub.devpost.com/resources",
        "schema_version": "dataset-registry/v1",
        "upstream": {
            "repository": "https://github.com/datahub-project/static-assets",
            "revision": REVISION,
        },
    }
    registry_path = tmp_path / "datasets.json"
    write_json(registry_path, registry)
    cache = tmp_path / "cache"
    cache.mkdir()
    for asset in assets:
        shutil.copyfile(files[str(asset["asset_id"])], cached_asset_path(cache, asset))
    return registry_path, cache


def test_generation_is_relationship_closed_and_byte_deterministic(
    tmp_path: Path,
) -> None:
    registry_path, cache = prepare_registry(tmp_path)

    first = generate_benchmark_corpus(
        registry_path,
        cache,
        tmp_path / "first",
        seed=42,
        scale="small",
    )
    second = generate_benchmark_corpus(
        registry_path,
        cache,
        tmp_path / "second",
        seed=42,
        scale="small",
    )
    comparison = compare_generation_outputs(tmp_path / "first", tmp_path / "second")
    report = json.loads((tmp_path / "first/quality-report.json").read_text())
    oracle = json.loads((tmp_path / "first/oracle.json").read_text())

    assert first == second
    assert comparison["byte_equivalent"] is True
    assert report["generated"]["total_quality_violations"] == 0
    assert report["generated"]["tables"]["orders"]["row_count"] == 2
    assert len(oracle["scenarios"]) == 14
    assert str(tmp_path) not in json.dumps(first)


def test_generation_refuses_tampered_artifact(tmp_path: Path) -> None:
    registry_path, cache = prepare_registry(tmp_path)
    output = tmp_path / "output"
    generate_benchmark_corpus(
        registry_path,
        cache,
        output,
        seed=42,
        scale="small",
    )
    with (output / "data/clean/orders.csv").open("a", encoding="utf-8") as target:
        target.write("tampered\n")

    with pytest.raises(Refusal) as caught:
        verify_generation_output(output)

    assert caught.value.code == RefusalCode.INTEGRITY_DIGEST_MISMATCH

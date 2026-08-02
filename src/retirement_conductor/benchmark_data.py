"""Deterministic benchmark corpus generation and official-data probes."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any

from retirement_conductor.benchmark_oracle import build_oracle
from retirement_conductor.canonical import (
    digest_file,
    digest_json,
    verify_digest,
    with_digest,
    write_json,
)
from retirement_conductor.dataset_registry import (
    acquire_datasets,
    cached_asset_path,
    load_dataset_registry,
)
from retirement_conductor.errors import Refusal
from retirement_conductor.schemas import validate_schema
from retirement_conductor.vocabulary import RefusalCode

GENERATOR_VERSION = "1.1.0"
SCALE_ORDER_LIMITS = {"small": 250, "medium": 2_500, "full": None}
TARGET_DATASET_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:sqlite,"
    "retirement_benchmark.analytics.fiction_retail.orders,PROD)"
)
DBT_CONSUMER = "dbt:retirement_benchmark.orders_status_summary"

_TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "customers": (
        "customer_id",
        "signup_date",
        "country",
        "state",
        "city",
        "customer_segment",
    ),
    "orders": (
        "order_id",
        "customer_id",
        "order_date",
        "legacy_status",
        "order_status",
        "total_amount",
        "payment_method",
        "shipping_country",
        "promo_id",
    ),
    "order_items": (
        "order_item_id",
        "order_id",
        "product_id",
        "quantity",
        "unit_price",
        "discount_pct",
    ),
    "products": (
        "product_id",
        "category",
        "brand",
        "price",
        "weight_kg",
        "supplier_id",
    ),
    "suppliers": ("supplier_id", "country", "contract_start_date", "status"),
    "inventory": (
        "inventory_id",
        "product_id",
        "warehouse_id",
        "quantity_on_hand",
        "reserved_quantity",
        "reorder_threshold",
        "last_restocked_date",
    ),
    "warehouses": (
        "warehouse_id",
        "city",
        "state",
        "country",
        "capacity_units",
        "opened_date",
    ),
    "shipments": (
        "shipment_id",
        "order_id",
        "warehouse_id",
        "carrier",
        "shipped_date",
        "delivered_date",
        "shipment_state",
    ),
    "returns": (
        "return_id",
        "order_id",
        "product_id",
        "return_date",
        "refund_amount",
        "return_reason_code",
    ),
    "promotions": (
        "promo_id",
        "discount_pct",
        "valid_from",
        "valid_until",
        "applies_to_category",
        "max_uses",
        "status",
    ),
}
_PRIMARY_KEYS = {
    "customers": "customer_id",
    "orders": "order_id",
    "order_items": "order_item_id",
    "products": "product_id",
    "suppliers": "supplier_id",
    "inventory": "inventory_id",
    "warehouses": "warehouse_id",
    "shipments": "shipment_id",
    "returns": "return_id",
    "promotions": "promo_id",
}


def generate_benchmark_corpus(
    registry_path: Path,
    cache_root: Path,
    output_directory: Path,
    *,
    seed: int,
    scale: str,
) -> dict[str, Any]:
    """Generate one relationship-closed corpus and independent oracle."""

    if scale not in SCALE_ORDER_LIMITS or seed < 0:
        raise Refusal(
            RefusalCode.SPEC_SCHEMA_INVALID,
            "Benchmark generation requires a known scale and non-negative seed.",
            {"scale": scale, "seed": seed},
        )
    registry = load_dataset_registry(registry_path)
    registry_digest = digest_json(registry)
    if output_directory.exists() or output_directory.is_symlink():
        return verify_generation_output(
            output_directory,
            expected_seed=seed,
            expected_scale=scale,
            expected_registry_digest=registry_digest,
        )

    input_receipt = acquire_datasets(
        registry_path,
        cache_root,
        offline=True,
        receipt_path=cache_root / "generation-input-receipt.json",
    )
    assets = {
        str(asset["asset_id"]): cached_asset_path(cache_root.resolve(), asset)
        for asset in _registry_assets(registry)
    }
    output_directory.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{output_directory.name}.",
            dir=output_directory.parent,
        )
    )
    try:
        receipt = _generate_into(
            staging,
            assets=assets,
            seed=seed,
            scale=scale,
            registry=registry,
            registry_digest=registry_digest,
            input_receipt=input_receipt,
        )
        os.replace(staging, output_directory)
        return receipt
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def verify_generation_output(
    output_directory: Path,
    *,
    expected_seed: int | None = None,
    expected_scale: str | None = None,
    expected_registry_digest: str | None = None,
) -> dict[str, Any]:
    """Verify every generated artifact before idempotent reuse."""

    if output_directory.is_symlink() or not output_directory.is_dir():
        raise Refusal(
            RefusalCode.SCOPE_TARGET_NOT_ALLOWED,
            "The benchmark output must be one real directory.",
        )
    receipt_path = output_directory / "generation-receipt.json"
    try:
        value = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Refusal(
            RefusalCode.INTEGRITY_DIGEST_MISMATCH,
            "The benchmark generation receipt is unavailable or invalid.",
            {"error_type": type(exc).__name__},
        ) from exc
    if not isinstance(value, dict):
        raise Refusal(
            RefusalCode.INTEGRITY_DIGEST_MISMATCH,
            "The benchmark generation receipt must be an object.",
        )
    validate_schema("benchmark-generation-receipt", value)
    verify_digest(value, "receipt_digest")
    expectations = {
        "seed": expected_seed,
        "scale": expected_scale,
        "registry_digest": expected_registry_digest,
    }
    for key, expected in expectations.items():
        if expected is not None and value.get(key) != expected:
            raise Refusal(
                RefusalCode.INTEGRITY_DIGEST_MISMATCH,
                "Existing benchmark output was generated from different inputs.",
                {"input": key},
            )
    artifact_digests = value.get("artifact_digests")
    if not isinstance(artifact_digests, Mapping):
        raise Refusal(
            RefusalCode.INTEGRITY_DIGEST_MISMATCH,
            "The benchmark receipt has no artifact digest map.",
        )
    root = output_directory.resolve(strict=True)
    for relative_name, expected_digest in sorted(artifact_digests.items()):
        relative = PurePosixPath(str(relative_name))
        if relative.is_absolute() or ".." in relative.parts:
            raise Refusal(
                RefusalCode.SCOPE_PATH_OUTSIDE_ROOT,
                "A generated artifact path escapes the benchmark output.",
            )
        path = output_directory.joinpath(*relative.parts)
        resolved = path.resolve(strict=False)
        if root not in resolved.parents or not resolved.is_file():
            raise Refusal(
                RefusalCode.INTEGRITY_DIGEST_MISMATCH,
                "A generated benchmark artifact is missing.",
                {"artifact": str(relative_name)},
            )
        if digest_file(resolved) != expected_digest:
            raise Refusal(
                RefusalCode.INTEGRITY_DIGEST_MISMATCH,
                "A generated benchmark artifact changed after generation.",
                {"artifact": str(relative_name)},
            )
    _verify_structured_outputs(output_directory, value)
    return value


def compare_generation_outputs(left: Path, right: Path) -> dict[str, Any]:
    """Require two independently generated directories to be byte-equivalent."""

    left_receipt = verify_generation_output(left)
    right_receipt = verify_generation_output(right)
    if left_receipt != right_receipt:
        raise Refusal(
            RefusalCode.INTEGRITY_DIGEST_MISMATCH,
            "Twin benchmark generations are not byte-equivalent.",
            {
                "left_receipt_digest": left_receipt["receipt_digest"],
                "right_receipt_digest": right_receipt["receipt_digest"],
            },
        )
    return {
        "artifact_count": len(left_receipt["artifact_digests"]),
        "byte_equivalent": True,
        "receipt_digest": left_receipt["receipt_digest"],
        "result": "VERIFIED",
    }


def _generate_into(
    output: Path,
    *,
    assets: Mapping[str, Path],
    seed: int,
    scale: str,
    registry: Mapping[str, Any],
    registry_digest: str,
    input_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    tables = _relationship_closed_fiction_slice(
        assets["fiction-retail-database"],
        seed=seed,
        scale=scale,
    )
    data_directory = output / "data" / "clean"
    table_digests = _write_tables(data_directory, tables)
    generated_quality = _generated_quality(tables, table_digests)
    if generated_quality["total_quality_violations"] != 0:
        raise Refusal(
            RefusalCode.VALIDATION_RECEIPT_FAILED,
            "The clean generated corpus violates its quality contract.",
            {"violations": generated_quality["total_quality_violations"]},
        )

    fault_manifest = _write_fault_variants(output, tables["orders"], seed=seed)
    oracle = build_oracle(
        seed=seed,
        scale=scale,
        target_dataset_urn=TARGET_DATASET_URN,
        expected_graph=_expected_graph(),
        scenarios=_scenario_facts(),
    )
    write_json(output / "oracle.json", oracle)
    quality_report = with_digest(
        {
            "artifact_classification": "public-safe-aggregate",
            "generated": generated_quality,
            "official_probes": _official_probes(assets),
            "registry_digest": registry_digest,
            "scale": scale,
            "schema_version": "benchmark-quality-report/v1",
            "seed": seed,
            "upstream_revision": _mapping(registry["upstream"])["revision"],
        },
        "quality_report_digest",
    )
    validate_schema("benchmark-quality-report", quality_report)
    write_json(output / "quality-report.json", quality_report)

    artifact_digests = {
        path.relative_to(output).as_posix(): digest_file(path)
        for path in sorted(output.rglob("*"))
        if path.is_file()
    }
    receipt = with_digest(
        {
            "artifact_digests": artifact_digests,
            "fault_manifest_digest": fault_manifest["fault_manifest_digest"],
            "generator_version": GENERATOR_VERSION,
            "oracle_digest": oracle["oracle_digest"],
            "quality_report_digest": quality_report["quality_report_digest"],
            "registry_digest": input_receipt["registry_digest"],
            "scale": scale,
            "schema_version": "benchmark-generation-receipt/v1",
            "seed": seed,
        },
        "receipt_digest",
    )
    validate_schema("benchmark-generation-receipt", receipt)
    write_json(output / "generation-receipt.json", receipt)
    return receipt


def _relationship_closed_fiction_slice(
    database: Path,
    *,
    seed: int,
    scale: str,
) -> dict[str, dict[str, Any]]:
    with _connect_read_only(database) as connection:
        all_order_ids = [
            str(row[0]) for row in connection.execute("SELECT order_id FROM orders")
        ]
        limit = SCALE_ORDER_LIMITS[scale]
        selected_order_ids = _stable_select(all_order_ids, seed=seed, limit=limit)

        source_order_columns = tuple(
            column for column in _TABLE_COLUMNS["orders"] if column != "legacy_status"
        )
        source_orders = _fetch_by_values(
            connection,
            "orders",
            source_order_columns,
            "order_id",
            selected_order_ids,
            primary_key="order_id",
        )
        order_status_index = source_order_columns.index("order_status")
        orders = [
            (
                *row[:order_status_index],
                row[order_status_index],
                *row[order_status_index:],
            )
            for row in source_orders
        ]
        order_id_index = _TABLE_COLUMNS["orders"].index("order_id")
        customer_id_index = _TABLE_COLUMNS["orders"].index("customer_id")
        promo_id_index = _TABLE_COLUMNS["orders"].index("promo_id")
        order_ids = {str(row[order_id_index]) for row in orders}
        customer_ids = {str(row[customer_id_index]) for row in orders}
        promo_ids = {
            str(row[promo_id_index])
            for row in orders
            if row[promo_id_index] is not None
        }

        order_items = _fetch_by_values(
            connection,
            "order_items",
            _TABLE_COLUMNS["order_items"],
            "order_id",
            order_ids,
            primary_key="order_item_id",
        )
        returns = _fetch_by_values(
            connection,
            "returns",
            _TABLE_COLUMNS["returns"],
            "order_id",
            order_ids,
            primary_key="return_id",
        )
        shipments = _fetch_by_values(
            connection,
            "shipments",
            _TABLE_COLUMNS["shipments"],
            "order_id",
            order_ids,
            primary_key="shipment_id",
        )
        item_product_index = _TABLE_COLUMNS["order_items"].index("product_id")
        return_product_index = _TABLE_COLUMNS["returns"].index("product_id")
        product_ids = {str(row[item_product_index]) for row in order_items}
        product_ids.update(str(row[return_product_index]) for row in returns)
        products = _fetch_by_values(
            connection,
            "products",
            _TABLE_COLUMNS["products"],
            "product_id",
            product_ids,
            primary_key="product_id",
        )
        supplier_index = _TABLE_COLUMNS["products"].index("supplier_id")
        supplier_ids = {str(row[supplier_index]) for row in products}
        inventory = _fetch_by_values(
            connection,
            "inventory",
            _TABLE_COLUMNS["inventory"],
            "product_id",
            product_ids,
            primary_key="inventory_id",
        )
        inventory_warehouse_index = _TABLE_COLUMNS["inventory"].index("warehouse_id")
        shipment_warehouse_index = _TABLE_COLUMNS["shipments"].index("warehouse_id")
        warehouse_ids = {str(row[inventory_warehouse_index]) for row in inventory}
        warehouse_ids.update(str(row[shipment_warehouse_index]) for row in shipments)

        selected: dict[str, list[tuple[Any, ...]]] = {
            "customers": _fetch_by_values(
                connection,
                "customers",
                _TABLE_COLUMNS["customers"],
                "customer_id",
                customer_ids,
                primary_key="customer_id",
            ),
            "orders": orders,
            "order_items": order_items,
            "products": products,
            "suppliers": _fetch_by_values(
                connection,
                "suppliers",
                _TABLE_COLUMNS["suppliers"],
                "supplier_id",
                supplier_ids,
                primary_key="supplier_id",
            ),
            "inventory": inventory,
            "warehouses": _fetch_by_values(
                connection,
                "warehouses",
                _TABLE_COLUMNS["warehouses"],
                "warehouse_id",
                warehouse_ids,
                primary_key="warehouse_id",
            ),
            "shipments": shipments,
            "returns": returns,
            "promotions": _fetch_by_values(
                connection,
                "promotions",
                _TABLE_COLUMNS["promotions"],
                "promo_id",
                promo_ids,
                primary_key="promo_id",
            ),
        }
    return {
        table: {"columns": _TABLE_COLUMNS[table], "rows": selected[table]}
        for table in _TABLE_COLUMNS
    }


def _fetch_by_values(
    connection: sqlite3.Connection,
    table: str,
    columns: Sequence[str],
    filter_column: str,
    values: Sequence[str] | set[str],
    *,
    primary_key: str,
) -> list[tuple[Any, ...]]:
    selected = sorted(set(values))
    if not selected:
        return []
    rendered_columns = ", ".join(columns)
    rows: list[tuple[Any, ...]] = []
    for offset in range(0, len(selected), 500):
        chunk = selected[offset : offset + 500]
        placeholders = ",".join("?" for _ in chunk)
        query = (
            f"SELECT {rendered_columns} FROM {table} "
            f"WHERE {filter_column} IN ({placeholders})"
        )
        rows.extend(tuple(row) for row in connection.execute(query, chunk))
    primary_index = columns.index(primary_key)
    return sorted(rows, key=lambda row: str(row[primary_index]))


def _stable_select(values: Sequence[str], *, seed: int, limit: int | None) -> list[str]:
    ordered = sorted(
        set(values),
        key=lambda value: (
            hashlib.sha256(f"{seed}:{value}".encode()).hexdigest(),
            value,
        ),
    )
    return ordered if limit is None else ordered[:limit]


def _write_tables(
    directory: Path,
    tables: Mapping[str, Mapping[str, Any]],
) -> dict[str, str]:
    directory.mkdir(parents=True, exist_ok=True)
    digests: dict[str, str] = {}
    for table in _TABLE_COLUMNS:
        path = directory / f"{table}.csv"
        _write_csv(path, tables[table]["columns"], tables[table]["rows"])
        digests[table] = digest_file(path)
    return digests


def _write_csv(
    path: Path, columns: Sequence[str], rows: Sequence[Sequence[Any]]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(columns)
        writer.writerows(rows)


def _generated_quality(
    tables: Mapping[str, Mapping[str, Any]],
    table_digests: Mapping[str, str],
) -> dict[str, Any]:
    table_stats: dict[str, Any] = {}
    primary_key_violations = 0
    for table, content in tables.items():
        columns = tuple(str(column) for column in content["columns"])
        rows = list(content["rows"])
        primary_index = columns.index(_PRIMARY_KEYS[table])
        primary_values = [row[primary_index] for row in rows]
        null_count = sum(value is None or value == "" for value in primary_values)
        duplicate_count = len(primary_values) - len(set(primary_values))
        primary_key_violations += null_count + duplicate_count
        table_stats[table] = {
            "content_digest": table_digests[table],
            "duplicate_primary_keys": duplicate_count,
            "null_primary_keys": null_count,
            "row_count": len(rows),
        }

    foreign_keys = {
        "orders.customer_id": _foreign_key_violations(
            tables, "orders", "customer_id", "customers", "customer_id"
        ),
        "orders.promo_id": _foreign_key_violations(
            tables,
            "orders",
            "promo_id",
            "promotions",
            "promo_id",
            nullable=True,
        ),
        "order_items.order_id": _foreign_key_violations(
            tables, "order_items", "order_id", "orders", "order_id"
        ),
        "order_items.product_id": _foreign_key_violations(
            tables, "order_items", "product_id", "products", "product_id"
        ),
        "products.supplier_id": _foreign_key_violations(
            tables, "products", "supplier_id", "suppliers", "supplier_id"
        ),
        "inventory.product_id": _foreign_key_violations(
            tables, "inventory", "product_id", "products", "product_id"
        ),
        "inventory.warehouse_id": _foreign_key_violations(
            tables, "inventory", "warehouse_id", "warehouses", "warehouse_id"
        ),
        "shipments.order_id": _foreign_key_violations(
            tables, "shipments", "order_id", "orders", "order_id"
        ),
        "shipments.warehouse_id": _foreign_key_violations(
            tables, "shipments", "warehouse_id", "warehouses", "warehouse_id"
        ),
        "returns.order_id": _foreign_key_violations(
            tables, "returns", "order_id", "orders", "order_id"
        ),
        "returns.product_id": _foreign_key_violations(
            tables, "returns", "product_id", "products", "product_id"
        ),
    }
    orders = tables["orders"]
    order_columns = tuple(orders["columns"])
    legacy_index = order_columns.index("legacy_status")
    replacement_index = order_columns.index("order_status")
    amount_index = order_columns.index("total_amount")
    date_index = order_columns.index("order_date")
    mismatch_count = sum(
        row[legacy_index] != row[replacement_index] for row in orders["rows"]
    )
    replacement_null_count = sum(
        row[replacement_index] is None for row in orders["rows"]
    )
    status_counts: dict[str, int] = {}
    for row in orders["rows"]:
        status = str(row[replacement_index])
        status_counts[status] = status_counts.get(status, 0) + 1
    temporal_violations = _temporal_violations(tables)
    numeric_violations = sum(float(row[amount_index]) < 0 for row in orders["rows"])
    total_violations = (
        primary_key_violations
        + sum(foreign_keys.values())
        + mismatch_count
        + replacement_null_count
        + temporal_violations
        + numeric_violations
    )
    amounts = [float(row[amount_index]) for row in orders["rows"]]
    dates = [str(row[date_index]) for row in orders["rows"]]
    return {
        "distribution_bounds": {
            "order_date_max": max(dates),
            "order_date_min": min(dates),
            "order_status_counts": dict(sorted(status_counts.items())),
            "total_amount_max": max(amounts),
            "total_amount_min": min(amounts),
        },
        "foreign_key_violations": dict(sorted(foreign_keys.items())),
        "numeric_bound_violations": numeric_violations,
        "primary_key_violations": primary_key_violations,
        "semantic_pair": {
            "legacy_replacement_mismatches": mismatch_count,
            "replacement_nulls": replacement_null_count,
        },
        "tables": table_stats,
        "temporal_violations": temporal_violations,
        "total_quality_violations": total_violations,
    }


def _foreign_key_violations(
    tables: Mapping[str, Mapping[str, Any]],
    child_table: str,
    child_column: str,
    parent_table: str,
    parent_column: str,
    *,
    nullable: bool = False,
) -> int:
    child_columns = tuple(tables[child_table]["columns"])
    parent_columns = tuple(tables[parent_table]["columns"])
    child_index = child_columns.index(child_column)
    parent_index = parent_columns.index(parent_column)
    parent_values = {row[parent_index] for row in tables[parent_table]["rows"]}
    return sum(
        value not in parent_values
        for value in (row[child_index] for row in tables[child_table]["rows"])
        if not (nullable and value is None)
    )


def _temporal_violations(tables: Mapping[str, Mapping[str, Any]]) -> int:
    order_columns = tuple(tables["orders"]["columns"])
    order_id_index = order_columns.index("order_id")
    order_date_index = order_columns.index("order_date")
    order_dates = {
        row[order_id_index]: str(row[order_date_index])
        for row in tables["orders"]["rows"]
    }
    shipment_columns = tuple(tables["shipments"]["columns"])
    shipment_order_index = shipment_columns.index("order_id")
    shipped_index = shipment_columns.index("shipped_date")
    delivered_index = shipment_columns.index("delivered_date")
    violations = 0
    for row in tables["shipments"]["rows"]:
        shipped = str(row[shipped_index])
        delivered = row[delivered_index]
        if shipped < order_dates[row[shipment_order_index]]:
            violations += 1
        if delivered is not None and str(delivered) < shipped:
            violations += 1
    return_columns = tuple(tables["returns"]["columns"])
    return_order_index = return_columns.index("order_id")
    return_date_index = return_columns.index("return_date")
    for row in tables["returns"]["rows"]:
        if str(row[return_date_index]) < order_dates[row[return_order_index]]:
            violations += 1
    return violations


def _write_fault_variants(
    output: Path,
    orders: Mapping[str, Any],
    *,
    seed: int,
) -> dict[str, Any]:
    columns = tuple(str(column) for column in orders["columns"])
    clean_rows = [tuple(row) for row in orders["rows"]]
    order_id_index = columns.index("order_id")
    replacement_index = columns.index("order_status")
    row_ids = [str(row[order_id_index]) for row in clean_rows]
    statuses = sorted({str(row[replacement_index]) for row in clean_rows})
    definitions = (
        ("null-inflated", 101, "set-to-null"),
        ("semantic-drift", 202, "replace-with-different-valid-status"),
        ("unmapped-value", 303, "set-to-unmapped-category"),
    )
    manifest_entries: list[dict[str, Any]] = []
    affected_count = max(1, len(row_ids) // 100)
    for variant_id, salt, mutation in definitions:
        affected_ids = set(
            _stable_select(row_ids, seed=seed + salt, limit=affected_count)
        )
        variant_rows: list[tuple[Any, ...]] = []
        for clean in clean_rows:
            row = list(clean)
            if str(row[order_id_index]) in affected_ids:
                if variant_id == "null-inflated":
                    row[replacement_index] = None
                elif variant_id == "unmapped-value":
                    row[replacement_index] = "__unmapped__"
                else:
                    current = str(row[replacement_index])
                    row[replacement_index] = statuses[
                        (statuses.index(current) + 1) % len(statuses)
                    ]
            variant_rows.append(tuple(row))
        _write_csv(
            output / "data" / "variants" / variant_id / "orders.csv",
            columns,
            variant_rows,
        )
        manifest_entries.append(
            {
                "affected_count": len(affected_ids),
                "affected_rate": round(len(affected_ids) / len(row_ids), 8),
                "field": "order_status",
                "impact": [DBT_CONSUMER],
                "mutation": mutation,
                "row_ids": sorted(affected_ids),
                "variant_id": variant_id,
            }
        )
    manifest = with_digest(
        {
            "artifact_classification": "private-exact-fault-provenance",
            "schema_version": "benchmark-fault-manifest/v1",
            "seed": seed,
            "variants": manifest_entries,
        },
        "fault_manifest_digest",
    )
    validate_schema("benchmark-fault-manifest", manifest)
    write_json(output / "fault-manifest.json", manifest)
    return manifest


def _scenario_facts() -> list[dict[str, Any]]:
    tableau = "tableau:retirement_benchmark.executive_orders"
    spark = "spark:retirement_benchmark.late_order_export"
    table_only = "external:retirement_benchmark.table_only_consumer"
    billing = "sqlite:healthcare.mart_billing"
    demographics = "sqlite:healthcare.mart_demographics"
    inventory = "sqlite:fiction_retail.inventory"

    def facts(
        consumers: list[dict[str, str]],
        *,
        evidence_status: str = "COMPLETE",
        pagination_complete: bool = True,
        native_data_fresh: bool = True,
        identity_match_count: int = 1,
        replacement_compatible: bool = True,
        reconciled: bool = True,
        inventory_ids: list[str] | None = None,
        current_ids: list[str] | None = None,
        quality_failures: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        ids = [consumer["id"] for consumer in consumers]
        return {
            "consumers": consumers,
            "current_consumer_ids": current_ids if current_ids is not None else ids,
            "evidence_status": evidence_status,
            "identity_match_count": identity_match_count,
            "inventory_consumer_ids": inventory_ids
            if inventory_ids is not None
            else ids,
            "native_data_fresh": native_data_fresh,
            "pagination_complete": pagination_complete,
            "quality_failures": quality_failures or [],
            "reconciled": reconciled,
            "replacement_compatible": replacement_compatible,
        }

    validated = {"disposition": "VALIDATED", "id": DBT_CONSUMER}
    scenarios = [
        {
            "description": "One exact Git/dbt consumer is natively validated.",
            "facts": facts([validated]),
            "id": "clean-isolated-ready",
        },
        {
            "description": "An opaque dashboard remains in the richer graph.",
            "facts": facts([validated, {"disposition": "OPAQUE", "id": tableau}]),
            "id": "rich-graph-unsafe",
        },
        {
            "description": "Fresh reconciliation discovers a late Spark consumer.",
            "facts": facts(
                [validated, {"disposition": "DISCOVERED", "id": spark}],
                inventory_ids=[DBT_CONSUMER],
                current_ids=[DBT_CONSUMER, spark],
            ),
            "id": "late-consumer-unsafe",
        },
        {
            "description": "One required inventory page is incomplete.",
            "facts": facts(
                [validated], evidence_status="PARTIAL", pagination_complete=False
            ),
            "id": "incomplete-pagination-blocked",
        },
        {
            "description": "Metadata is fresh while native taxi timestamps are stale.",
            "facts": facts([validated], native_data_fresh=False),
            "id": "stale-native-data-blocked",
        },
        {
            "description": "Table-only lineage cannot identify field closure.",
            "facts": facts([validated, {"disposition": "OPAQUE", "id": table_only}]),
            "id": "table-only-lineage-unsafe",
        },
        {
            "description": "Two native identities match one graph consumer.",
            "facts": facts([validated], identity_match_count=2),
            "id": "ambiguous-identity-blocked",
        },
        {
            "description": "Replacement type compatibility fails before apply.",
            "facts": facts([validated], replacement_compatible=False),
            "id": "incompatible-type-unsafe",
        },
        {
            "description": "Replacement data contains unmapped categories.",
            "facts": facts(
                [{"disposition": "FAILED", "id": DBT_CONSUMER}],
                quality_failures=[{"id": "unmapped-value", "impact": [DBT_CONSUMER]}],
            ),
            "id": "unmapped-value-unsafe",
        },
        {
            "description": "Replacement null rate exceeds the clean control.",
            "facts": facts(
                [{"disposition": "FAILED", "id": DBT_CONSUMER}],
                quality_failures=[{"id": "null-inflated", "impact": [DBT_CONSUMER]}],
            ),
            "id": "null-inflation-unsafe",
        },
        {
            "description": "Valid replacement categories diverge from legacy meaning.",
            "facts": facts(
                [{"disposition": "FAILED", "id": DBT_CONSUMER}],
                quality_failures=[{"id": "semantic-drift", "impact": [DBT_CONSUMER]}],
            ),
            "id": "semantic-drift-unsafe",
        },
        {
            "description": "Healthcare faults halt only their declared branches.",
            "facts": facts(
                [
                    {"disposition": "FAILED", "id": billing},
                    {"disposition": "FAILED", "id": demographics},
                    {"disposition": "VALIDATED", "id": inventory},
                ],
                quality_failures=[
                    {"id": "negative-billing", "impact": [billing]},
                    {"id": "invalid-age", "impact": [demographics]},
                ],
            ),
            "id": "healthcare-selective-impact-unsafe",
        },
        {
            "description": (
                "Ownership, tags, and glossary context do not prove closure."
            ),
            "facts": facts([validated, {"disposition": "OPAQUE", "id": tableau}]),
            "id": "ownership-context-no-closure",
        },
        {
            "description": "A disappearing edge without native proof remains stale.",
            "facts": facts([validated, {"disposition": "STALE", "id": tableau}]),
            "id": "disappearing-edge-no-closure",
        },
    ]
    return scenarios


def _expected_graph() -> dict[str, Any]:
    dbt_urn = (
        "urn:li:dataset:(urn:li:dataPlatform:dbt,"
        "retirement_benchmark.analytics.consumers.orders_status_summary,PROD)"
    )
    tableau_urn = (
        "urn:li:dataset:(urn:li:dataPlatform:tableau,"
        "retirement_benchmark.analytics.consumers.executive_orders,PROD)"
    )
    spark_urn = (
        "urn:li:dataset:(urn:li:dataPlatform:spark,"
        "retirement_benchmark.analytics.consumers.late_order_export,PROD)"
    )
    return {
        "edges": [
            {
                "downstream": dbt_urn,
                "precision": "field",
                "upstream": TARGET_DATASET_URN,
            },
            {
                "downstream": tableau_urn,
                "precision": "table",
                "upstream": TARGET_DATASET_URN,
            },
            {"downstream": spark_urn, "precision": "field", "upstream": dbt_urn},
        ],
        "entities": sorted([TARGET_DATASET_URN, dbt_urn, tableau_urn, spark_urn]),
    }


def _official_probes(assets: Mapping[str, Path]) -> dict[str, Any]:
    return {
        "fiction_retail": _fiction_probe(assets["fiction-retail-database"]),
        "healthcare": _healthcare_probe(assets["healthcare-database"]),
        "nyc_taxi": _taxi_probe(
            assets["nyc-taxi-clean-database"],
            assets["nyc-taxi-stale-database"],
        ),
    }


def _fiction_probe(database: Path) -> dict[str, Any]:
    with _connect_read_only(database) as connection:
        _require_quick_check(connection, "fiction-retail")
        row_counts = {
            table: int(
                connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            )
            for table in _TABLE_COLUMNS
        }
        status_counts = {
            str(status): int(count)
            for status, count in connection.execute(
                "SELECT order_status, COUNT(*) FROM orders "
                "GROUP BY order_status ORDER BY order_status"
            )
        }
        orphan_count = int(
            connection.execute(
                "SELECT "
                "(SELECT COUNT(*) FROM orders o LEFT JOIN customers c "
                " USING(customer_id) WHERE c.customer_id IS NULL) + "
                "(SELECT COUNT(*) FROM order_items i LEFT JOIN orders o "
                " USING(order_id) LEFT JOIN products p USING(product_id) "
                " WHERE o.order_id IS NULL OR p.product_id IS NULL) + "
                "(SELECT COUNT(*) FROM products p LEFT JOIN suppliers s "
                " USING(supplier_id) WHERE s.supplier_id IS NULL) + "
                "(SELECT COUNT(*) FROM inventory i LEFT JOIN products p "
                " USING(product_id) LEFT JOIN warehouses w USING(warehouse_id) "
                " WHERE p.product_id IS NULL OR w.warehouse_id IS NULL) + "
                "(SELECT COUNT(*) FROM shipments s LEFT JOIN orders o "
                " USING(order_id) LEFT JOIN warehouses w USING(warehouse_id) "
                " WHERE o.order_id IS NULL OR w.warehouse_id IS NULL) + "
                "(SELECT COUNT(*) FROM returns r LEFT JOIN orders o "
                " USING(order_id) LEFT JOIN products p USING(product_id) "
                " WHERE o.order_id IS NULL OR p.product_id IS NULL)"
            ).fetchone()[0]
        )
    return {
        "documented_role": "relational-control",
        "foreign_key_orphans": orphan_count,
        "quick_check": "ok",
        "row_counts": row_counts,
        "status_counts": status_counts,
    }


def _healthcare_probe(database: Path) -> dict[str, Any]:
    with _connect_read_only(database) as connection:
        _require_quick_check(connection, "healthcare")
        raw = connection.execute(
            "SELECT COUNT(*), "
            "SUM(CAST(billing_amount AS REAL) < 0), "
            "SUM(name IS NULL), "
            "SUM(CAST(age AS INTEGER) < 0 OR CAST(age AS INTEGER) > 120), "
            "SUM(date(discharge_date) < date(date_of_admission)) "
            "FROM raw_patients"
        ).fetchone()
        billing = connection.execute(
            "SELECT COUNT(*), SUM(CAST(billing_amount AS REAL) < 0), "
            "SUM(name IS NULL), SUM(length_of_stay_days < 0) FROM mart_billing"
        ).fetchone()
        demographics = connection.execute(
            "SELECT COUNT(*), SUM(name IS NULL), "
            "SUM(CAST(age AS INTEGER) < 0 OR CAST(age AS INTEGER) > 120) "
            "FROM mart_demographics"
        ).fetchone()
        billing_columns = _table_columns(connection, "mart_billing")
        demographic_columns = _table_columns(connection, "mart_demographics")
    return {
        "branch_observations": {
            "billing": {
                "date_swap_rows": int(billing[3]),
                "negative_billing_rows": int(billing[1]),
                "null_name_rows": int(billing[2]),
                "row_count": int(billing[0]),
            },
            "demographics": {
                "invalid_age_rows": int(demographics[2]),
                "null_name_rows": int(demographics[1]),
                "row_count": int(demographics[0]),
            },
        },
        "branch_selectivity": {
            "age_absent_from_billing": "age" not in billing_columns,
            "billing_amount_absent_from_demographics": (
                "billing_amount" not in demographic_columns
            ),
            "null_name_physically_propagates_to_both": (
                int(billing[2]) == int(demographics[1]) == int(raw[2])
            ),
        },
        "documented_role": "branch-selective-quality",
        "quick_check": "ok",
        "raw_fault_counts": {
            "date_swap_rows": int(raw[4]),
            "invalid_age_rows": int(raw[3]),
            "negative_billing_rows": int(raw[1]),
            "null_name_rows": int(raw[2]),
            "row_count": int(raw[0]),
        },
    }


def _taxi_probe(clean_database: Path, stale_database: Path) -> dict[str, Any]:
    clean = _taxi_variant_probe(clean_database)
    stale = _taxi_variant_probe(stale_database)
    raw_date = date.fromisoformat(str(stale["raw_max_date"]))
    staging_date = date.fromisoformat(str(stale["staging_max_date"]))
    observed_gap = (raw_date - staging_date).days
    return {
        "clean": clean,
        "documented_expectations": {
            "empty_load_row": True,
            "staleness_gap_days": 3,
        },
        "documented_role": "native-freshness-control",
        "observed_documentation_discrepancies": {
            "empty_load_row_absent": int(stale["zero_trip_days"]) == 0,
            "staleness_gap_days": observed_gap,
        },
        "stale": stale,
    }


def _taxi_variant_probe(database: Path) -> dict[str, Any]:
    with _connect_read_only(database) as connection:
        _require_quick_check(connection, database.name)
        raw = connection.execute(
            "SELECT MAX(date(tpep_pickup_datetime)), COUNT(*) FROM raw_trips"
        ).fetchone()
        staging = connection.execute(
            "SELECT MAX(trip_date), COUNT(*) FROM staging_trips"
        ).fetchone()
        mart = connection.execute(
            "SELECT MAX(trip_date), SUM(trip_count), SUM(trip_count = 0) "
            "FROM mart_daily_summary"
        ).fetchone()
    return {
        "mart_max_date": str(mart[0]),
        "mart_trip_count": int(mart[1]),
        "quick_check": "ok",
        "raw_max_date": str(raw[0]),
        "raw_row_count": int(raw[1]),
        "staging_max_date": str(staging[0]),
        "staging_row_count": int(staging[1]),
        "zero_trip_days": int(mart[2] or 0),
    }


def _require_quick_check(connection: sqlite3.Connection, asset_id: str) -> None:
    result = [str(row[0]) for row in connection.execute("PRAGMA quick_check")]
    if result != ["ok"]:
        raise Refusal(
            RefusalCode.DATASET_CHECKSUM_MISMATCH,
            "A verified dataset failed SQLite integrity checking.",
            {"asset_id": asset_id, "result_count": len(result)},
        )


def _table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")}


def _connect_read_only(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(
        f"file:{path.resolve().as_posix()}?mode=ro&immutable=1", uri=True
    )


def _verify_structured_outputs(output: Path, receipt: Mapping[str, Any]) -> None:
    named = (
        ("oracle.json", "benchmark-oracle", "oracle_digest"),
        ("fault-manifest.json", "benchmark-fault-manifest", "fault_manifest_digest"),
        ("quality-report.json", "benchmark-quality-report", "quality_report_digest"),
    )
    for filename, schema_name, digest_field in named:
        value = json.loads((output / filename).read_text(encoding="utf-8"))
        validate_schema(schema_name, value)
        verify_digest(value, digest_field)
        if value[digest_field] != receipt[digest_field]:
            raise Refusal(
                RefusalCode.INTEGRITY_DIGEST_MISMATCH,
                "A structured benchmark digest does not match its receipt.",
                {"artifact": filename},
            )


def _registry_assets(registry: Mapping[str, Any]) -> list[dict[str, Any]]:
    assets = registry.get("assets")
    if not isinstance(assets, list):
        return []
    return [dict(asset) for asset in assets if isinstance(asset, Mapping)]


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}

#!/usr/bin/env python3
"""Run one safe-digest Spark/JDBC workload over the disposable producer."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from typing import Any

from py4j.protocol import Py4JJavaError
from pyspark.sql import SparkSession

RESULT_PREFIX = "NATIVE_BREAKAGE_RESULT="
ALLOWED_FIELDS = {"legacy_status", "order_status"}


def emit(value: dict[str, Any]) -> None:
    print(f"{RESULT_PREFIX}{json.dumps(value, sort_keys=True)}", flush=True)


def native_error(error: Py4JJavaError) -> tuple[str, str | None, str]:
    current = error.java_exception
    messages: list[str] = []
    class_name = str(current.getClass().getName())
    sqlstate: str | None = None
    for _ in range(12):
        messages.append(str(current.getMessage() or ""))
        try:
            candidate = current.getSQLState()
            if candidate:
                sqlstate = str(candidate)
        except Exception:  # noqa: BLE001 - not every Java throwable has SQL state
            pass
        cause = current.getCause()
        if cause is None or cause == current:
            break
        current = cause
        class_name = str(current.getClass().getName())
    return class_name, sqlstate, "\n".join(messages)


def main() -> int:
    field = os.environ.get("WORKLOAD_FIELD", "")
    if field not in ALLOWED_FIELDS:
        emit({"outcome": "INVALID_WORKLOAD_FIELD"})
        return 2

    spark = (
        SparkSession.builder.appName(f"native-breakage-{field}")
        .config("spark.jars", "/opt/lab/postgresql-42.7.4.jar")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")
    try:
        query = (
            "(SELECT id, "
            f"{field} AS selected_status, amount_cents "
            "FROM retirement_lab.orders) AS workload_source"
        )
        rows = (
            spark.read.format("jdbc")
            .option("url", os.environ["DB_URL"])
            .option("dbtable", query)
            .option("user", os.environ["DB_USER"])
            .option("password", os.environ["DB_PASSWORD"])
            .option("driver", "org.postgresql.Driver")
            .load()
            .orderBy("id")
            .collect()
        )
        safe_lines = [
            f"{int(row.id)}|{str(row.selected_status).upper()}|{int(row.amount_cents)}"
            for row in rows
        ]
        emit(
            {
                "outcome": "SUCCEEDED",
                "row_count": len(rows),
                "safe_output_digest": (
                    "sha256:"
                    + hashlib.sha256("\n".join(safe_lines).encode()).hexdigest()
                ),
                "spark_version": spark.version,
            }
        )
        return 0
    except Py4JJavaError as error:
        class_name, sqlstate, message = native_error(error)
        normalized = (
            "LEGACY_COLUMN_MISSING"
            if field == "legacy_status"
            and 'column "legacy_status" does not exist' in message
            else "NATIVE_WORKLOAD_FAILED"
        )
        emit(
            {
                "missing_field": "legacy_status" if normalized == "LEGACY_COLUMN_MISSING" else None,
                "native_error_class": class_name,
                "outcome": normalized,
                "sqlstate": sqlstate,
            }
        )
        return 42 if normalized == "LEGACY_COLUMN_MISSING" else 1
    finally:
        spark.stop()


if __name__ == "__main__":
    sys.exit(main())

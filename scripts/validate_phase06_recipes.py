#!/usr/bin/env python3
"""Validate phase 06 recipes with the pinned official DataHub config models."""

from __future__ import annotations

import importlib
import importlib.metadata
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
RECIPES = {
    "looker-saved-look.yml": (
        "looker",
        "datahub.ingestion.source.looker.looker_config",
        "LookerDashboardSourceConfig",
    ),
    "looker-lookml.yml": (
        "lookml",
        "datahub.ingestion.source.looker.lookml_source",
        "LookMLSourceConfig",
    ),
}
SYNTHETIC_VALUES = {
    "DATAHUB_GMS_TOKEN": "phase06-synthetic-datahub-token",
    "DATAHUB_GMS_URL": "http://127.0.0.1:18080",
    "LOOKER_BASE_URL": "https://looker.example.invalid",
    "LOOKER_CLIENT_ID": "phase06-synthetic-client",
    "LOOKER_CLIENT_SECRET": "phase06-synthetic-client-secret",
    "LOOKER_CONNECTION_NAME": "retirement_disposable",
    "LOOKER_CONTENT_ID_PATTERN": "^41$",
    "LOOKER_FOLDER_PATH_PATTERN": "^/Shared/Retirement Conductor$",
    "LOOKER_PLATFORM_INSTANCE": "retirement-disposable",
    "LOOKER_PROJECT_ID": "retirement_conductor",
    "LOOKER_WAREHOUSE_DATABASE": "retirement",
    "LOOKER_WAREHOUSE_INSTANCE": "retirement-disposable",
    "LOOKER_WAREHOUSE_PLATFORM": "bigquery",
    "LOOKER_WAREHOUSE_SCHEMA": "disposable",
    "LOOKML_BASE_FOLDER": str(ROOT / "fixtures/looker-lookml-project"),
}
VARIABLE = re.compile(r"\$\{([A-Z][A-Z0-9_]*)\}")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _expand_synthetic(content: str) -> str:
    referenced = set(VARIABLE.findall(content))
    missing = referenced - SYNTHETIC_VALUES.keys()
    _require(not missing, f"recipe has unknown variable names: {sorted(missing)}")
    return VARIABLE.sub(lambda match: SYNTHETIC_VALUES[match.group(1)], content)


def _mapping(value: object, label: str) -> dict[str, Any]:
    _require(isinstance(value, dict), f"{label} must be a mapping")
    return value


def _load_model(module_name: str, class_name: str) -> type[Any]:
    module = importlib.import_module(module_name)
    model = getattr(module, class_name)
    _require(isinstance(model, type), f"{module_name}.{class_name} is not a class")
    return model


def _validate_saved_look(config: dict[str, Any]) -> None:
    _require(config["extract_independent_looks"] is True, "independent Looks disabled")
    _require(config["extract_column_level_lineage"] is True, "lineage disabled")
    _require(config["extract_usage_history"] is False, "usage queries must be disabled")
    _require(config["extract_embed_urls"] is False, "embed URL extraction must be off")
    _require(config["include_platform_instance_in_urns"] is True, "URN scope missing")
    _require(config["max_threads"] == 1, "saved-Look ingestion must use one thread")
    _require(
        config["dashboard_pattern"] == {"allow": [], "deny": [".*"]},
        "dashboards must be excluded",
    )
    _require(
        config["chart_pattern"]["allow"] == ["^41$"],
        "saved-Look scope must be one anchored numeric ID",
    )
    _require(
        config["folder_path_pattern"]["allow"] == ["^/Shared/Retirement Conductor$"],
        "folder scope must be one anchored disposable path",
    )
    stateful = _mapping(config["stateful_ingestion"], "saved-Look stateful config")
    _require(stateful["enabled"] is True, "stateful ingestion disabled")
    _require(stateful["remove_stale_metadata"] is True, "stale removal disabled")
    _require(stateful["fail_safe_threshold"] == 100, "delete/recreate probe blocked")


def _validate_lookml(config: dict[str, Any]) -> None:
    _require(config["parse_table_names_from_sql"] is True, "SQL parsing disabled")
    _require(config["extract_column_level_lineage"] is True, "lineage disabled")
    _require(
        config["allow_partial_lineage_results"] is False,
        "partial LookML lineage must fail closed",
    )
    _require(
        config["use_api_for_view_lineage"] is False,
        "LookML recipe must not require an admin API credential",
    )
    connection_map = _mapping(
        config["connection_to_platform_map"],
        "LookML connection map",
    )
    _require(
        set(connection_map) == {"retirement_disposable"},
        "LookML recipe must map one exact connection",
    )
    stateful = _mapping(config["stateful_ingestion"], "LookML stateful config")
    _require(stateful["enabled"] is True, "stateful ingestion disabled")
    _require(stateful["remove_stale_metadata"] is True, "stale removal disabled")


def run() -> int:
    results: list[dict[str, str]] = []
    sink_model = _load_model(
        "datahub.ingestion.sink.datahub_rest",
        "DatahubRestSinkConfig",
    )
    for filename, (source_type, module_name, class_name) in RECIPES.items():
        path = ROOT / "deploy/datahub/recipes" / filename
        raw = path.read_text(encoding="utf-8")
        _require(
            "${LOOKER_CLIENT_SECRET}" in raw or source_type == "lookml",
            "saved-Look recipe must use a runtime secret reference",
        )
        document = _mapping(
            yaml.safe_load(_expand_synthetic(raw)),
            f"{filename} recipe",
        )
        source = _mapping(document.get("source"), f"{filename} source")
        sink = _mapping(document.get("sink"), f"{filename} sink")
        _require(source.get("type") == source_type, f"{filename} source type changed")
        _require(sink.get("type") == "datahub-rest", f"{filename} sink type changed")
        source_config = _mapping(source.get("config"), f"{filename} source config")
        sink_config = _mapping(sink.get("config"), f"{filename} sink config")
        _load_model(module_name, class_name).model_validate(source_config)
        sink_model.model_validate(sink_config)
        if source_type == "looker":
            _validate_saved_look(source_config)
        else:
            _validate_lookml(source_config)
        results.append(
            {
                "recipe": filename,
                "source_type": source_type,
                "status": "VALID",
            }
        )
    print(
        json.dumps(
            {
                "datahub_version": importlib.metadata.version("acryl-datahub"),
                "result": "VALID",
                "recipes": results,
                "validation_mode": "official-config-models-with-synthetic-values",
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(run())
    except (ImportError, KeyError, OSError, TypeError, ValueError) as error:
        print(
            json.dumps(
                {
                    "error_type": type(error).__name__,
                    "result": "INVALID",
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        sys.exit(1)

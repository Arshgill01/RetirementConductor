from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
RECIPE_DIRECTORY = ROOT / "deploy/datahub/recipes"


def _recipe(name: str) -> dict[str, object]:
    loaded = yaml.safe_load((RECIPE_DIRECTORY / name).read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def test_saved_look_recipe_is_secret_referenced_and_exactly_scoped() -> None:
    recipe = _recipe("looker-saved-look.yml")
    source = recipe["source"]
    sink = recipe["sink"]
    assert isinstance(source, dict)
    assert isinstance(sink, dict)
    config = source["config"]
    assert isinstance(config, dict)

    assert source["type"] == "looker"
    assert config["client_id"] == "${LOOKER_CLIENT_ID}"
    assert config["client_secret"] == "${LOOKER_CLIENT_SECRET}"
    assert config["extract_independent_looks"] is True
    assert config["extract_column_level_lineage"] is True
    assert config["extract_usage_history"] is False
    assert config["extract_embed_urls"] is False
    assert config["dashboard_pattern"] == {"allow": [], "deny": [".*"]}
    assert config["chart_pattern"] == {
        "allow": ["${LOOKER_CONTENT_ID_PATTERN}"],
        "deny": [],
        "ignoreCase": False,
    }
    assert config["folder_path_pattern"] == {
        "allow": ["${LOOKER_FOLDER_PATH_PATTERN}"],
        "deny": [],
        "ignoreCase": False,
    }
    assert config["max_threads"] == 1
    assert sink == {
        "type": "datahub-rest",
        "config": {
            "server": "${DATAHUB_GMS_URL}",
            "token": "${DATAHUB_GMS_TOKEN}",
        },
    }


def test_lookml_recipe_is_local_exact_and_fails_closed_on_partial_lineage() -> None:
    recipe = _recipe("looker-lookml.yml")
    source = recipe["source"]
    assert isinstance(source, dict)
    config = source["config"]
    assert isinstance(config, dict)

    assert source["type"] == "lookml"
    assert config["base_folder"] == "${LOOKML_BASE_FOLDER}"
    assert config["project_name"] == "${LOOKER_PROJECT_ID}"
    assert config["parse_table_names_from_sql"] is True
    assert config["extract_column_level_lineage"] is True
    assert config["allow_partial_lineage_results"] is False
    assert config["use_api_for_view_lineage"] is False
    assert config["connection_to_platform_map"] == {
        "${LOOKER_CONNECTION_NAME}": {
            "platform": "${LOOKER_WAREHOUSE_PLATFORM}",
            "default_db": "${LOOKER_WAREHOUSE_DATABASE}",
            "default_schema": "${LOOKER_WAREHOUSE_SCHEMA}",
            "platform_instance": "${LOOKER_WAREHOUSE_INSTANCE}",
            "platform_env": "PROD",
        }
    }

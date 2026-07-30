.PHONY: check datahub-core-env datahub-core-up datahub-core-down datahub-seed \
	format git-dbt-tool git-dbt-workspace git-dbt-isolated-workspace \
	phase00-evidence phase01-evidence phase02-evidence phase03-evidence \
	phase04-evidence phase05-browser phase05-evidence phase06-recipes \
	phase06-evidence phase07-evidence scan \
	test test-ui test-end-to-end test-faults test-recovery test-security

check:
	uv run ruff check src tests scripts
	uv run ruff format --check src tests scripts
	uv run mypy
	uv run pytest
	uv run python scripts/validate_repository.py
	uv run python scripts/check_secrets.py
	uv run python scripts/check_public_artifacts.py
	uv build
	git diff --check

format:
	uv run ruff check --fix src tests scripts
	uv run ruff format src tests scripts

datahub-core-env:
	uv run python scripts/datahub_core_env.py

datahub-core-up: datahub-core-env
	docker compose \
		--env-file .retirement-conductor/datahub/core.env \
		-f deploy/datahub/docker-compose.core.yml \
		up -d --wait datahub-gms

datahub-core-down:
	docker compose \
		--env-file .retirement-conductor/datahub/core.env \
		-f deploy/datahub/docker-compose.core.yml \
		down

datahub-seed:
	DATAHUB_GMS_URL=http://127.0.0.1:18080 \
	uv run --python 3.11 --with 'acryl-datahub==1.6.0' \
		python scripts/datahub_seed.py

git-dbt-tool:
	uv venv --python 3.11 .retirement-conductor/tools/dbt-duckdb-1.10.1
	uv pip install \
		--python .retirement-conductor/tools/dbt-duckdb-1.10.1/bin/python \
		'dbt-duckdb==1.10.1'

git-dbt-workspace:
	uv run python scripts/prepare_git_dbt_workspace.py

git-dbt-isolated-workspace:
	uv run python scripts/prepare_git_dbt_workspace.py \
		--template fixtures/git-dbt-isolated-project \
		--destination \
			.retirement-conductor/workspaces/ret-orders-isolated/repository

phase00-evidence:
	uv run python scripts/generate_phase00_evidence.py

phase01-evidence:
	uv run python scripts/generate_phase01_evidence.py

phase02-evidence:
	uv run python scripts/generate_phase02_evidence.py

phase03-evidence:
	uv run python scripts/generate_phase03_evidence.py

phase04-evidence:
	uv run python scripts/generate_phase04_evidence.py

phase05-browser:
	uv run python scripts/run_phase05_browser_acceptance.py

phase05-evidence:
	uv run python scripts/generate_phase05_evidence.py

phase06-recipes:
	uv run --python 3.11 \
		--with 'acryl-datahub[looker,lookml,datahub-rest]==1.6.0' \
		python scripts/validate_phase06_recipes.py

phase06-evidence:
	uv run python -m scripts.generate_phase06_evidence

phase07-evidence:
	uv run python scripts/generate_phase07_evidence.py

scan:
	uv run python scripts/run_security_scan.py

test:
	uv run pytest

test-ui:
	uv run pytest -q \
		tests/unit/test_operator.py \
		tests/unit/test_events.py \
		tests/integration/test_operator_cli.py
	uv run python scripts/check_ui_artifacts.py

test-end-to-end:
	uv run python scripts/run_phase04_end_to_end.py
	uv run pytest -q \
		tests/unit/test_policy.py \
		tests/integration/test_gate.py \
		tests/integration/test_campaign_store.py

test-security:
	uv run pytest -q \
		tests/contracts/test_records.py \
		tests/contracts/test_specification.py \
		tests/security \
		tests/unit/test_git_dbt.py \
		tests/unit/test_looker.py \
		tests/unit/test_operator.py \
		tests/integration/test_gate.py

test-faults:
	uv run pytest -q \
		tests/security/test_looker_transport.py \
		tests/unit/test_datahub_http.py \
		tests/unit/test_mcp_http.py \
		tests/unit/test_git_dbt.py \
		tests/integration/test_campaign_store.py \
		tests/integration/test_gate.py \
		tests/integration/test_looker_workflow.py

test-recovery:
	uv run pytest -q \
		tests/reliability/test_store_operations.py \
		tests/integration/test_campaign_store.py \
		tests/integration/test_gate.py \
		tests/integration/test_git_dbt_workflow.py \
		tests/integration/test_looker_workflow.py

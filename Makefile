.PHONY: benchmark-workspace check datahub-core-env datahub-core-up datahub-core-down datahub-seed \
	format git-dbt-tool git-dbt-workspace git-dbt-isolated-workspace \
	phase00-evidence phase01-evidence phase02-evidence phase03-evidence \
	phase04-evidence phase05-browser phase05-evidence \
	phase06-benchmark phase06-data phase06-evidence phase07-evidence phase08-evidence package scan \
	test test-install test-reference-campaign test-ui test-upgrade \
	test-end-to-end test-faults test-recovery test-security

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

benchmark-workspace:
	uv run python scripts/prepare_benchmark_workspace.py

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

phase06-data:
	uv run retirement-conductor benchmark data acquire \
		--registry fixtures/data-quality/datasets.json \
		--cache .retirement-conductor/datasets \
		--receipt .retirement-conductor/benchmark/data-acquire-receipt.json
	uv run retirement-conductor benchmark data verify \
		--registry fixtures/data-quality/datasets.json \
		--cache .retirement-conductor/datasets \
		--offline \
		--receipt .retirement-conductor/benchmark/data-verify-receipt.json
	uv run retirement-conductor benchmark data generate \
		--registry fixtures/data-quality/datasets.json \
		--cache .retirement-conductor/datasets \
		--seed 20260802 \
		--scale medium \
		--output .retirement-conductor/benchmark/generation-a
	uv run retirement-conductor benchmark data generate \
		--registry fixtures/data-quality/datasets.json \
		--cache .retirement-conductor/datasets \
		--seed 20260802 \
		--scale medium \
		--output .retirement-conductor/benchmark/generation-b
	uv run retirement-conductor benchmark data compare \
		--left .retirement-conductor/benchmark/generation-a \
		--right .retirement-conductor/benchmark/generation-b

phase06-benchmark: benchmark-workspace
	uv run python -m scripts.run_phase06_benchmark

phase06-evidence:
	uv run python -m scripts.generate_phase06_evidence

phase07-evidence:
	uv run python -m scripts.generate_phase07_evidence

phase08-evidence:
	uv run python -m scripts.generate_phase08_evidence

package:
	uv run python -m scripts.package_release

scan:
	uv run python scripts/run_security_scan.py

test:
	uv run pytest

test-install: package
	uv run python -m scripts.test_install

test-reference-campaign: package
	uv run python -m scripts.run_phase08_reference_campaign

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
		tests/unit/test_operator.py \
		tests/integration/test_gate.py

test-faults:
	uv run pytest -q \
		tests/unit/test_datahub_http.py \
		tests/unit/test_mcp_http.py \
		tests/unit/test_git_dbt.py \
		tests/integration/test_campaign_store.py \
		tests/integration/test_gate.py

test-recovery:
	uv run pytest -q \
		tests/reliability/test_store_operations.py \
		tests/integration/test_campaign_store.py \
		tests/integration/test_gate.py \
		tests/integration/test_git_dbt_workflow.py

test-upgrade: package
	uv run python -m scripts.test_upgrade

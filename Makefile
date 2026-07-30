.PHONY: check datahub-core-env datahub-core-up datahub-core-down datahub-seed \
	format git-dbt-tool git-dbt-workspace git-dbt-isolated-workspace \
	phase00-evidence phase01-evidence phase02-evidence phase03-evidence test

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

test:
	uv run pytest

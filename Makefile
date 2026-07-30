.PHONY: check format phase00-evidence test

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

phase00-evidence:
	uv run python scripts/generate_phase00_evidence.py

test:
	uv run pytest

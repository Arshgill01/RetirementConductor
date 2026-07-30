.PHONY: check

check:
	python3 scripts/validate_repository.py
	git diff --check

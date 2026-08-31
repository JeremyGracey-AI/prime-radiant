# Target names follow house convention (nexus-neuromirror); commands are uv-based
# per the newer governance-drift-researcher pattern.

.PHONY: install-dev test lint typecheck check

install-dev:
	uv sync --all-groups

test:
	uv run pytest -q --cov=prime_radiant --cov-fail-under=85

lint:
	uv run ruff check .
	uv run ruff format --check .

typecheck:
	uv run pyright

check: lint typecheck test

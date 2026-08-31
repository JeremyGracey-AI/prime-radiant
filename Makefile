# Target names follow house convention (nexus-neuromirror); commands are uv-based
# per the newer governance-drift-researcher pattern.

.PHONY: install-dev test lint typecheck check

install-dev:
	uv sync --all-groups

# Offline by design: integration tests need network/the hub clone — run them
# explicitly with `make test-integration`.
test:
	uv run pytest -q -m "not integration" --cov=prime_radiant --cov-fail-under=85

test-integration:
	uv run pytest tests/integration -q -m integration

lint:
	uv run ruff check .
	uv run ruff format --check .

typecheck:
	uv run pyright

check: lint typecheck test

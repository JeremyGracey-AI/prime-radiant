# Target names follow house convention (nexus-neuromirror); commands are uv-based
# per the newer governance-drift-researcher pattern.

.PHONY: install-dev test lint typecheck check bundle

install-dev:
	uv sync --all-groups

# Offline by design: integration tests need network/the hub clone — run them
# explicitly with `make test-integration`.
test:
	uv run pytest -q -m "not integration" --cov=prime_radiant --cov-fail-under=100

test-integration:
	uv run pytest tests/integration -q -m integration

lint:
	uv run ruff check .
	uv run ruff format --check .

# gradio writes its component .pyi stubs into site-packages at FIRST IMPORT;
# a fresh venv that has never imported it fails pyright on Dropdown.change
# (adversarial finding: `make check` was not reproducible from a clean clone).
typecheck:
	uv run python -c "import gradio"
	uv run pyright

check: lint typecheck test

# Offline by construction: assembles serve_data/ from local backtest parquets,
# the pinned truth vintage, and the local benchmark cache — never the network.
bundle:
	uv run prime-radiant epi bundle

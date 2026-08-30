# Prime Radiant

Calibrated LLM forecasting bot for Metaculus binary questions: retrieval → ensemble →
aggregation, with every forecast logged and scored (Brier + reliability diagram).

**Status: Phase A (scaffold).** Metaculus client + config + tests. Full methodology,
calibration curve, and limitations land with Phase E.

## Setup

```sh
uv sync
cp .env.example .env   # fill in tokens
uv run pytest
```

## Verify

```sh
uv run ruff check . && uv run pyright && uv run pytest
```

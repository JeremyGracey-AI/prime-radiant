# Current task

Phase 2 (FluSight epi forecaster) — Phase A: Data + contracts. Brief: `HANDOFF_PHASE2.md`.

## Goal

Loaders for hub target-data (current + git vintages), locations, epiweek math; pandera
schemas; VCR cassettes for Socrata. Done: 53 locations × every season since 2022-23;
`as_of(date)` strictly ≤ date; contract tests green; all gates pass.

## Current state

- done: house-style retool — hatchling backend, ruff line-length 100 + format, pyright
  basic, markers `unit|integration|contract|e2e`, coverage gate 85 (actual: 96%),
  Makefile (`install-dev test lint typecheck check`), `requires-python >=3.11`
- done: `epi/data/epiweek.py` (reference_date/target_end_date math),
  `epi/data/locations.py` (53-code universe + NHSN jurisdiction bridge),
  `epi/data/hub.py` (blobless+sparse clone → 169 MB vs ~620 MB full; loader),
  `epi/data/vintages.py` (git-history as_of + parquet cache by sha),
  `epi/data/nhsn.py` (Socrata anonymous, 67→53 jurisdiction filter),
  `epi/schemas.py` (RawTarget/Submission/Feature; submission enforces int values +
  quantile monotonicity — tasks.json only enforces double≥0)
- done: 54 tests (52 offline: unit+contract incl. hypothesis leakage property on a
  synthetic git repo; 2 integration vs the real clone — the done condition passes)
- done: real-data discovery — the hub target file carries NA cells; RawTargetSchema
  value is nullable on purpose (submission layer stays strict int)
- done: fixtures recorded from real sources (locations.csv, target-data slice,
  NHSN cassettes ~564K)

## Next step

Phase B (scorer + baselines): `eval/wis.py` with a hand-computed WIS example test;
FluSight-baseline replica; validate scorer + replica together against official
FluSight-baseline output from S3 (bucket `cdcepi-flusight-forecast-hub`, anonymous
pyarrow) on 2024-25. Golden submission file committed.

## Verify

`make check` (= ruff check + format --check + pyright + pytest-cov≥85, offline)
`uv run pytest tests/integration -m integration` (needs network/clone)

## Blockers

- None for Phase A.
- Season 2026-27 guidance lands ~Oct 2026 — re-verify tasks.json + registration then.

## Notes / gaps

- **Metaculus thread (Phase 1) parked** at its Phase B (retrieval); its client + tests
  remain green in `tests/unit/`. `NEWS_API_KEY` still intentionally empty.
- `eval/` package does not exist yet — Phase B creates it (`wis.py` first; the brief's
  `brier.py`/`calibration.py` belong to the parked Metaculus phases).
- ai-use check action has NO tags (verified) — when CI lands (Phase G), pin
  `JeremyGracey-AI/ai-use/check@eadf1067e62c2e209b926df8e4115a702ef13ee8`.
- No "clean-code" skill exists on this machine (Phase 1 note stands); stand-in:
  superpowers TDD + ruff/pyright/coverage gates.
- data/hub clone is gitignored and disposable; delete + rerun integration suite to
  rebuild. Vintage parquet cache in data/vintage_cache keyed by commit sha.

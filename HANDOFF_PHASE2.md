# HANDOFF — Prime Radiant, Phase 2: FluSight Epidemic Forecaster

You are Claude Code on Jeremys-Mac-Studio, working in `~/src/github.com/JeremyGracey-AI/prime-radiant` (Phase 1 bot already lives here — read `CLAUDE.md`, `NOTES/restart.md`, and `README.md` first). Plan mode first: propose Phase A in ≤10 lines, wait for confirmation, build one phase at a time.

## Goal
Add `prime_radiant.epi`: a CDC FluSight-format quantile forecaster for weekly confirmed-influenza hospital admissions (US + 52 jurisdictions), backtested honestly on prior seasons, benchmarked against FluSight-baseline and FluSight-ensemble, automated for weekly submission, and shipped with a professional test + deploy package. Everything is public-domain CDC data. No keys for data. CPU only. Cost ≈ $0.

## Why this domain (don't re-litigate)
- Open data, no licensing or sensitivity exposure (the reason ACLED/conflict was dropped).
- Public scored benchmark with a real credential: a model on the CDC hub.
- Same thesis as Phase 1 — calibrated aggregate forecasting — upgraded from Brier to full quantile calibration (WIS).

## Verified FluSight facts (as of 2026-08-30; hub README still describes 2025–26 — re-verify 2026–27 guidance in October)
- Hub: `github.com/cdcepi/FluSight-forecast-hub`. Dirs: `hub-config/` (tasks.json = the schema), `model-metadata/`, `model-output/<team>-<model>/`, `target-data/`, `auxiliary-data/locations.csv` (FIPS + population).
- Primary target `wk inc flu hosp`: quantile output, **23 levels** (0.01, 0.025, 0.05, 0.10, 0.15, …, 0.95, 0.975, 0.99), **integer values required**, horizons **−1, 0, 1, 2, 3** (−1 is submitted but not scored). Optional targets: `wk inc flu prop ed visits` (0–1), `wk flu hosp rate change` (5 categories), peak week, peak incidence, 100 sample trajectories. Ship the primary target first; rate-change second.
- Cadence: submit by **Wednesday 11 PM ET**; `reference_date` = the Saturday ending that epiweek; `target_end_date = reference_date + 7·horizon`. File: `model-output/<team>-<model>/<reference_date>-<team>-<model>.csv`. Columns: `reference_date, target, horizon, location, target_end_date, output_type, output_type_id, value`. Locations are 2-digit FIPS strings + `US`.
- Ground truth: NHSN Weekly Hospital Respiratory Data, data.cdc.gov `ua7e-t2fy` (also `mpgq-jmmr` referenced for evaluation). Simplest canonical source: the hub's own `target-data/target-hospital-admissions.csv` — and its **git history gives weekly vintages** for as-of-honest backtests.
- All hub dirs are mirrored on public S3 bucket `cdcepi-flusight-forecast-hub` (anonymous `pyarrow.fs.S3FileSystem(anonymous=True)`). Pull FluSight-baseline, FluSight-ensemble, UMass-flusion outputs from there for benchmarking.
- FluSight-baseline definition: median = last observed value; spread from empirical positive/negative week-over-week differences, symmetrized, truncated at 0. FluSight-ensemble = per-quantile median of eligible models.
- Season 2025–26 ran Nov 19 – May 20 (Wed deadlines). Expect 2026–27 to open ~Nov 2026; registration is by PR adding `model-metadata/<team>-<model>.yml` (copy the field set from an existing file, e.g. FluSight-baseline's). Contact: flusight@cdc.gov.

## Constraints (non-negotiable — inherited from Phase 1, tightened)
1. Same repo, same package. New code under `src/prime_radiant/epi/`; shared scoring under `src/prime_radiant/eval/`.
2. uv + Ruff + Pyright + pytest. `uv.lock` committed. Python 3.11–3.13 matrix.
3. Never train or score on data dated after the forecast origin. Vintage discipline is a tested invariant, not a comment.
4. No secrets needed for data. GitHub/HF tokens only in Actions secrets or `.env`. `detect-secrets` in pre-commit.
5. Flag destructive actions. Live hub submission (PR to the hub) only when `LIVE=1` **and** Jeremy says go.
6. Follow the clean-code skill. Every dependency cap gets a why-comment (house style).

## House consistency (from the Aug 30 audit of your GitHub — copy these, don't reinvent)
| Keep verbatim | Source |
|---|---|
| `pyproject` shape: hatchling, `[dependency-groups] dev`, ruff line-length 100 + `E F W I UP B SIM`, pyright basic, `testpaths=["tests"]`, classifiers/keywords/urls | governance-drift-researcher/python |
| CI shape: matrix → `astral-sh/setup-uv` → ruff → pyright → pytest, then a **cleanroom job** that installs the built wheel into an empty venv and runs the CLI | governance-drift-researcher `python.yml` |
| Publish: `v*` tag → build → `twine check` → upload-artifact → `environment: pypi`, `id-token: write`, `pypa/gh-action-pypi-publish` | llm-council-mcp `publish.yml` |
| README: title → badges (CI · MIT · AI-USE) → one-paragraph "what it is" → pipeline section → honest-framing paragraph → "Try it" links | llm-council-mcp, triton-kernel-lab |
| CONTRIBUTING.md, CHANGELOG.md, Makefile (`install-dev test lint typecheck check`), `.env.example` | nexus-neuromirror |
| AI-USE.md declaration + badge + CI check (`uses: JeremyGracey-AI/ai-use/check@<tag>` — verify the tag) | ai-use |
| HF Spaces via **Gradio** with README front-matter | calibrated-readiness |

## Gaps the audit found — this build closes all of them
| Gap (true of every Python repo audited) | Phase 2 fix |
|---|---|
| No coverage measurement or gate | `pytest-cov`, `--cov-fail-under=85`, Codecov badge |
| No property tests, no data contracts | `hypothesis` invariants + `pandera` schemas at every stage boundary |
| No pre-commit / secrets scanning | `.pre-commit-config.yaml`: ruff, ruff-format, pyright, detect-secrets, check-added-large-files |
| Actions pinned by tag, no Dependabot, no `permissions:` | SHA-pin every action, `.github/dependabot.yml` (actions + uv), `permissions: contents: read` + `concurrency` on all workflows |
| Manual versions, no changelog automation | `python-semantic-release` (Conventional Commits) → tag, CHANGELOG, GitHub release |
| No CITATION.cff, no docs site | CITATION.cff; MkDocs Material → GitHub Pages |
| No Dockerfile on the Python packages | multi-stage uv Dockerfile (`ghcr.io/astral-sh/uv` copy, `--frozen --no-dev`, non-root) |
| Dependency lists duplicated (provenance) | single source of truth in `[project]` + groups; a test asserts `requirements*.txt` don't exist |

## Architecture
```
target-data (hub git/S3) + NHSN Socrata (live)  ──→ epi/data     (loaders, vintages, locations, epiweeks)
                                                       │
                                               epi/features   (lags, diffs, seasonal week, per-location scaling; as-of enforced)
                                                       │
                       ┌───────────────────────────────┼────────────────────────────────┐
              epi/models/baseline            epi/models/lgbm_quantile           epi/models/seasonal
              (FluSight-baseline replica)    (one LightGBM per quantile,        (seasonal-naive)
                                              monotone post-processing)
                       └───────────────────────────────┼────────────────────────────────┘
                                               epi/models/ensemble  (per-quantile median, weights optional)
                                                       │
                                               epi/submission  (hubverse frame → pandera schema → tasks.json check → CSV)
                                                       │
                                               eval/wis  (WIS + decomposition, coverage, relative WIS)  ←── benchmark models from S3
                                                       │
                                               epi/backtest  (rolling-origin over 2022-23 … 2025-26 using target-data vintages)
                                                       │
                                               epi/serve/app.py  (Gradio: choropleth, fan charts, reliability plots)
```
Storage: DuckDB over Parquet in gitignored `data/`. Reports in `reports/` (committed PNG/CSV summaries only).

## Package layout
```
src/prime_radiant/
  eval/        brier.py calibration.py wis.py scoring.py          # wis.py is new; add tests with a hand-computed WIS example
  epi/
    data/      hub.py nhsn.py locations.py epiweek.py vintages.py
    features/  lags.py seasonal.py assemble.py
    models/    baseline.py seasonal.py lgbm_quantile.py ensemble.py postprocess.py
    submission/ schema.py format.py validate.py write.py metadata.py
    backtest/  rolling.py report.py
    serve/     app.py plots.py
    cli.py     # `prime-radiant epi {fetch,backtest,forecast,submit,validate}`
tests/{unit,integration,contract,e2e}/ + tests/cassettes/ + tests/golden/
docs/  mkdocs.yml  Makefile  Dockerfile  CITATION.cff  AI-USE.md  CHANGELOG.md
.github/workflows/{ci.yml,weekly-forecast.yml,release.yml,space-deploy.yml}  .github/dependabot.yml
```

## Phases (one session each; 15–45 min chunks; done = all gates green)
**A. Data + contracts (5–7h).** Loaders for hub target-data (current + git vintages), locations, epiweek math; pandera schemas `RawTargetSchema`, `FeatureSchema`, `SubmissionSchema`; VCR cassettes for Socrata.
Done: all 53 locations load for every season since 2022-23; `vintages.as_of(date)` returns strictly ≤ date; contract tests green.

**B. Scorer + baselines (4–5h).** `eval/wis.py` (WIS, decomposition, 50/95% coverage, relative WIS); FluSight-baseline replica; seasonal-naive; hubverse formatter + validator against `hub-config/tasks.json`.
Done: your WIS scores the official FluSight-baseline output (from S3) and your replica within a small tolerance of each other on 2024-25 — this validates the scorer and the replica together. Golden submission file committed.

**C. Model + ensemble (5–7h).** LightGBM quantile regression per quantile level with lag/diff/seasonal features; monotone + non-negative + integer post-processing; per-quantile-median ensemble with baseline.
Done: relative WIS < 1.0 vs FluSight-baseline on ≥2 retrospective seasons at horizons 0–3, computed on vintage data. If not, fix features before adding models.

**D. Honest backtest + benchmark report (4–5h).** Rolling-origin across seasons using vintages; WIS decomposition, coverage, reliability diagrams; comparison table vs FluSight-baseline, FluSight-ensemble, UMass-flusion.
Done: `reports/backtest_<season>.csv` + `reports/calibration.png`; README table shows wins and losses plainly.

**E. Submission automation (3–4h).** `weekly-forecast.yml`: cron Tue 22:00 UTC + manual dispatch → fetch → forecast → validate → write file → upload artifact → (LIVE=1) open PR to Jeremy's fork of the hub via `gh`. `metadata.py` renders `model-metadata/<team>-<model>.yml` from `pyproject` + config.
Done: dry-run in CI produces a file that passes `SubmissionSchema` + tasks.json checks; PR step is skipped without LIVE.

**F. Dashboard (3–4h).** Gradio app: US choropleth of predicted 3-week change, per-state fan chart with observed history, reliability plot, model-vs-baseline table; `space-deploy.yml` pushes to HF Space `jeremygracey-ai/prime-radiant`.
Done: Space live on CPU-basic; README front-matter correct; secrets only via Space settings.

**G. Release hardening (3–4h).** Coverage gate, pre-commit, Dependabot, SHA-pinned actions, cleanroom job, trusted publishing, python-semantic-release, Dockerfile, MkDocs, CITATION.cff, AI-USE check, CHANGELOG, model card in `docs/model-card.md`.
Done: every README badge green; `uv build` wheel installs clean; `make check` = ruff + pyright + pytest-cov all pass.

Total ≈ 27–36 hrs. Calendar: build in September; watch the hub for 2026–27 guidance and register in October; first live submission when the season opens (~Nov).

## Quality gates (Claude Code must satisfy before calling any phase done)
1. `uv run ruff check . && uv run ruff format --check .` clean.
2. `uv run pyright` clean (basic mode; no `# type: ignore` without a why-comment).
3. `uv run pytest -q --cov=prime_radiant --cov-fail-under=85` green; markers `unit|integration|contract|e2e` registered and used.
4. Hypothesis invariants pass: quantiles monotone non-decreasing; values ≥ 0 and integer for hosp target; `target_end_date == reference_date + 7·horizon`; no feature at origin t depends on rows > t.
5. Determinism test: two runs, identical submission file (seeded LightGBM, `deterministic=True`).
6. Model-quality gate: committed `tests/golden/wis_baseline.json`; CI fails if relative WIS regresses > 2%.
7. No `requirements*.txt`, no raw data, no notebooks with outputs committed (pre-commit `check-added-large-files`, nbstripout if any notebook exists).

## Restart notes (mandatory)
Update `NOTES/restart.md` at the end of every session using the Phase 1 template (Goal / Current state / Next step / Verify / Blockers). Park scope creep in `NOTES/parking-lot.md` (rate-change target, ED-visit target, sample trajectories, RSV hub, Scenario Modeling Hub intervention demo).

## Do NOT
- Use any data dated after a backtest origin (vintages only; never the latest revision for historical scoring).
- Open a PR against `cdcepi/FluSight-forecast-hub` without `LIVE=1` and explicit go from Jeremy.
- Add LLM calls to this phase — it is a pure statistical/ML pipeline by design.
- Rebuild what the audit says to copy; match the house style tables above.

## First action
Read `CLAUDE.md` and `NOTES/restart.md`, then propose the Phase A plan (files, deps, commands, first test) in ≤10 lines and wait for confirmation.

# HANDOFF — Prime Radiant, Phases F & G: Dashboard + Release Hardening

You are Claude Code on Jeremys-Mac-Studio, working in
`~/src/github.com/JeremyGracey-AI/prime-radiant`. Phases 2A–2E are done, committed,
pushed, and adversarially verified. Read `CLAUDE.md`, `NOTES/restart.md`, and
`NOTES/go-live-runbook.md` first; `HANDOFF_PHASE2.md` remains the parent brief.
One phase per session. Plan mode first: run a fact-verification workflow, then
propose the phase plan in ≤10 lines and wait for confirmation.

## State you inherit (all verified this session, 2026-08-31)

- **Results on the record** (`reports/`, README): lgbm WINS 2025-26 at relative
  WIS 0.609 (vs UMass-flusion 0.625); loses 2023-24/2024-25 to flusion — printed.
  Scorer/replica cross-validated at 0.999989. Known debt: lgbm under-covers
  (50% intervals cover 34–40%) — season-bagging is the sanctioned lever, parked.
- **Submission machinery CI-proven**: runs 33456866973 + 33458426164 (hardened
  YAML) — dry-run green, live-submit SKIPPED, 4,877-line hub-valid artifact.
  Live path = five verified gates ending in `exit 1`; go-live steps live in
  `NOTES/go-live-runbook.md` and are NEVER automated.
- Registration metadata rendered + schema-valid (`JGracey-prime_radiant`,
  CC-BY-4.0, designated_model=true — Jeremy may flip before the PR).
- Backtest parquets (255) under `data/backtest/`; benchmarks + vintages cached;
  goldens in `tests/golden/wis_baseline.json` with a ≤2% regression rule wired
  into the gate test. 186 offline tests (cov ~93.6%) + 8 integration.
- Gate commands: `make check` (offline) · `make test-integration` (network).
  **Never pipe the gate command** (a piped `make check | tail` swallowed a
  failing exit once — recorded in restart.md).

## Process rules that earned their keep (follow them)

1. Per phase: plan-mode fact-verification workflow (3–4 read-only researchers)
   → ≤10-line plan → approval → TDD build → gates → commit/push → 4-agent
   adversarial workflow (refuters + gate runner) → fix findings with
   attack-derived regression tests → advisor → close at the phase boundary.
2. **Kill claims are facts only after the mutant runs.** Twice this session a
   "dies by construction" mutant survived. Run every claimed kill.
3. Read refuter outputs IN FULL (summaries and issue arrays untruncated) before
   triage — truncated reads hid real findings twice.
4. Every dependency cap gets a why-comment; SHA-pin new actions with `# vX.Y.Z`;
   exact-pin anything whose determinism is binary-scoped (lightgbm==4.7.0).
5. Fixtures are recorded from real sources, never hand-built; committed
   artifacts must byte-regenerate via an integration test.
6. Jeremy gets a visual walkthrough page per phase (established design system:
   Spectral/Source Sans 3/IBM Plex Mono; paper+amber+green tokens, dual-theme).

## Phase F — Dashboard (3–4h). Gradio on HF Spaces.

Per parent brief: `epi/serve/app.py` + `plots.py` — US choropleth of predicted
3-week change, per-state fan chart (forecast quantile bands + observed history),
reliability plot (reuse `coverage_curve`), model-vs-baseline table (reuse
`reports/` CSVs); `space-deploy.yml` pushes to HF Space
`jeremygracey-ai/prime-radiant`. House precedent: calibrated-readiness (Gradio +
README front-matter; local copy at `~/src/local/agents-league-hackathon/calibrated-readiness`).
Done: Space live on CPU-basic; README front-matter correct; secrets only via
Space settings.
Verify in plan-mode recon (suggested researchers): (a) HF Spaces mechanics 2026
— Gradio version to pin, README front-matter fields, Space creation via
`huggingface_hub`/CLI, HF_TOKEN handling, CPU-basic limits, whether a private
repo can deploy from Actions (needs HF token as repo secret — outward-facing:
creating the Space + token are go-live-style actions requiring Jeremy's go);
(b) data path for the Space — it cannot clone 169MB per boot: precompute
serve-ready parquet bundles (forecasts + truth + coverage) committed to the
Space repo or built at deploy time; (c) choropleth mechanics in Gradio (plotly
choropleth with FIPS; plotly is already a transitive dep via forecasting-tools —
declare it directly if used, with why-comment).
Watch: lightgbm/libomp does NOT need to run on the Space if the bundle is
precomputed — prefer a data-only Space (no model execution) for CPU-basic.

## Phase G — Release hardening (3–4h). Then the repo goes public.

Per parent brief's gap table, all of: `ci.yml` (matrix 3.11–3.13 →
astral-sh/setup-uv → ruff → pyright → pytest-cov gate 85 + cleanroom wheel job —
copy governance-drift-researcher `python.yml` shape; SHA-pin everything;
`permissions: contents: read` + concurrency everywhere), coverage badge
(Codecov), `.pre-commit-config.yaml` (ruff, ruff-format, pyright, detect-secrets,
check-added-large-files), `.github/dependabot.yml` (actions + uv), release
automation (python-semantic-release, Conventional Commits — note: history uses
`[claude] type(scope):` prefixes; verify psr's tag parsing tolerates the prefix
or configure `commit_parser` accordingly), PyPI Trusted Publishing
(llm-council-mcp `publish.yml` pattern: v* tag → build → twine check →
environment: pypi + id-token: write), multi-stage uv Dockerfile
(ghcr.io/astral-sh/uv copy, --frozen --no-dev, non-root; MUST apt-install
libgomp1? verify — manylinux wheel needs libgomp.so.1, slim base images lack it),
MkDocs Material → GitHub Pages, CITATION.cff, AI-USE.md + badge + CI check
(pin `JeremyGracey-AI/ai-use/check@eadf1067e62c2e209b926df8e4115a702ef13ee8` —
repo has NO tags, verified), CHANGELOG.md, CONTRIBUTING.md, model card
`docs/model-card.md`, and a test asserting no `requirements*.txt` exists.
Done: every README badge green; `uv build` wheel installs clean; `make check`
green; **repo flipped public only on Jeremy's explicit go** (it contains his
email in metadata — already public via git identity, but the flip is his).
Known Phase-G landmines from prior recon: weekly-forecast.yml is already
SHA-pinned/hardened (don't re-pin blindly — versions were live-resolved
2026-08-31); Actions cache for the hub clone is the sanctioned CI optimization;
public-repo crons auto-disable after 60 days of inactivity (note in docs).

## Calendar / go-live (outside build phases)

- ~Oct 2026: hub publishes 2026-27 guidance — re-verify tasks.json (quantile
  set, targets, integer policy), then Jeremy decides on the registration PR
  (runbook steps 1–4).
- ~Nov 2026: season opens; first live submission ONLY on explicit go
  (runbook steps 5–6).

## Do NOT

- Execute any go-live-runbook step (fork, PAT, registration PR, Space/token
  creation, repo-public flip) without Jeremy's explicit go in-session.
- Relax the vintage guard, the goldens' regression rules, or the live gates.
- Roll F and G into one session.
- Park scope creep anywhere but `NOTES/parking-lot.md`.

## First action

Read `CLAUDE.md` + `NOTES/restart.md`, enter plan mode, run the Phase F
fact-verification workflow, then propose the Phase F plan in ≤10 lines and wait.

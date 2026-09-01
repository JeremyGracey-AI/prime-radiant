# Current task

Phase 2 (FluSight epi forecaster) — Phase F: Dashboard (Gradio on HF Spaces).
Brief: `HANDOFF_PHASES_FG.md` (parent: `HANDOFF_PHASE2.md`).

## Goal

Gradio dashboard (choropleth of predicted 3-week change, per-state fan chart,
reliability plots, league table) served from a precomputed bundle on HF Space
jeremygracey-ai/prime-radiant; space-deploy.yml stages always, pushes only
through gates. Done = Space live on CPU-basic (needs Jeremy's go for the
outward steps).

## Current state

- done: recon workflow corrected three handoff premises — calibrated-readiness
  is NOT a Gradio precedent (real ones: FetchMerck-AI-Demo, Remy_v1); dashboard
  code must NOT live in the package (Space never installs prime-radiant, else
  lightgbm/libomp+litellm land on it); bundle builds locally, deploy is
  copy-only (CI rebuild non-deterministic: lightgbm binary-scoped, /data/
  untracked, build_reports hits S3 unconditionally).
- done: `epi/serve/bundle.py` + `prime-radiant epi bundle` + `make bundle` →
  committed `serve_data/` (1.7MB: 3 zstd model parquets h0-3, pinned truth
  vintage 786312d7, league CSVs, locations.csv, coverage CSVs, timestamp-free
  manifest). Offline by construction; origins from filenames; benchmarks from
  cache only (loud on miss). Coverage at nominal 0.5 exactly matches the league
  CSVs' interval_coverage_50 (3/3 seasons).
- done: `dashboard/` flat modules (panel_data, panel_plots, app) — ship to the
  Space root as siblings; pyright executionEnvironments + tests/conftest
  sys.path mirror that. Choropleth anchors on last observed <= reference_date
  (advisor caught: "latest observed" would anchor AFTER the prediction; truth
  runs to 2026-07-04, reference is 2026-05-30). Abbreviation guard makes the
  FIPS-silent-blank-map failure loud. Local boot verified HTTP 200; [startup]
  line prints bundle provenance.
- done: `space-deploy.yml` — stage job always (assembles Space tree, GENERATES
  requirements.txt with locked pins, gradio never listed — sdk_version 6.26.0
  governs; keeps Phase G's no-requirements*.txt test viable); deploy job is a
  REAL `hf upload` (huggingface_hub==1.29.0) but triple-gated (dispatch
  deploy=true + SPACE_LIVE=1 var + HF_TOKEN secret, all absent today) and
  pushes only the validated stage artifact (no checkout in deploy job).
  test_space_deploy_honesty.py asserts the gates as exact conjunctions.
- done: 4-agent adversarial workflow (commit 9059713). Verdicts: vintage
  SURVIVED, gates SURVIVED (live GitHub state: 0 vars, 0 secrets, 0 envs,
  sole admin; SHA pins genuine; no reachability bypass constructed), app
  SURVIVED (all 53 locations x 3 models exercised), mutations PARTIALLY
  REFUTED — 9/9 mutants RAN and were killed. Six findings fixed in 6b6e1f0
  with attack-derived regression tests: fresh-clone make check (gradio .pyi
  stubs generated at first import — typecheck now imports gradio first), NaN
  anchor fallback + loud unanchored-location error, gap-only fan prepend
  (53/53 duplicated x before), PR excluded from choropleth (held the invisible
  z-max in 2/3 models), deploy job repo_info pre-check (hf upload silently
  CREATEs a missing Space with a broad token), US+72 in the synthetic fixture
  (unit-level mutant kill) + tightened honesty tests.
- Gates: `make check` green (238 offline, cov 95.95%) · `make test-integration`
  green pre-hardening (11: byte-regen, vintage-sha pin, cache==S3 enumeration);
  the hardening commit touched no src/prime_radiant path, so that run stands.
- Accepted residuals (stated, not fixed): duplicate (location,date) truth rows
  would give an order-dependent anchor — guarded by absence (0 duplicates in
  the shipped truth), no code guard; deploy job goes green-with-steps-skipped
  when HF_TOKEN is absent (matches the weekly-forecast house pattern);
  re-running an old deploy run post-go-live redeploys its stale artifact
  (recorded in the runbook staleness note); `pip install → hf` on the runner
  PATH is verified locally, untested until the first real dispatch; DC's
  visual rendering on the choropleth is confirmed programmatically (in trace
  locations) but eyeballed only on the walkthrough page, not on a live Space.
- **GONE LIVE 2026-08-31 ~22:45 PDT on Jeremy's explicit "go live on
  everything"** — done condition MET: Space live on CPU-basic at
  https://huggingface.co/spaces/jeremygracey-ai/prime-radiant (deploy run
  33474626675 green end-to-end: stage → artifact → repo_info pre-check →
  hf upload; app HTTP 200; served config verified 4 tabs / 4 plots / 5
  handlers). Space created public via local credential; SPACE_LIVE=1;
  HF_TOKEN secret = Jeremy's cached BROAD token (his explicit call —
  **rotation to fine-grained TODO**, recorded in the runbook).
- **Hub registration PR OPEN**: cdcepi/FluSight-forecast-hub#3696
  (designated_model=true — committed Phase E value, Jeremy's ping answer left
  it default; amendable on fork branch until merge). Metadata re-validated
  against the LIVE hub schema (byte-identical to recorded fixture) before
  opening. Fork created. PAT + LIVE=1 deliberately NOT done (weekly live path
  is a ~Nov item). First-time-contributor CI needs maintainer approval — watch
  the PR.
- Jeremy OVERRODE the one-phase-per-session rule in-session: Phase G is to be
  planned NOW, evaluated by him, then run on his approval. Phase G recon
  workflow launched (4 researchers: tooling SHAs/psr-prefix, house precedents,
  Docker/docs, public-flip audit).

## Next step

Present the Phase G plan (from the recon results) for Jeremy's evaluation;
run it on his approval. The public flip remains its own explicit gate inside
Phase G even under the override.

## Verify

`make check` (offline) · `make test-integration` (network; ~9min cold) ·
`uv run python dashboard/app.py` (local boot, HTTP 200)

## Blockers

- None. Outward steps (Space/token/deploy/weekly-refresh wiring) are gated on
  Jeremy by design — see NOTES/go-live-runbook.md "Dashboard go-live".

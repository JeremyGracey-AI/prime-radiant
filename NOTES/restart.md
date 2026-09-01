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
- Gates: `make check` green (234 offline, cov 95.95%) · `make test-integration`
  green (11, incl. bundle byte-regen, vintage-sha pin, cache==S3 enumeration).
- NOT done (needs Jeremy's explicit go — runbook "Dashboard go-live"): create
  Space (PRO account verified), fine-grained HF_TOKEN secret, SPACE_LIVE=1,
  dispatch deploy, verify live. Adversarial workflow + walkthrough page pending
  this session.

## Next step

4-agent adversarial workflow on the Phase F commit; fix findings with
attack-derived regression tests; walkthrough page; then STOP for the go.

## Verify

`make check` (offline) · `make test-integration` (network; ~9min cold) ·
`uv run python dashboard/app.py` (local boot, HTTP 200)

## Blockers

- None. Outward steps (Space/token/deploy/weekly-refresh wiring) are gated on
  Jeremy by design — see NOTES/go-live-runbook.md "Dashboard go-live".

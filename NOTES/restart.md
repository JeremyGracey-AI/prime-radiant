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

## Phase G (same session, Jeremy's override of the one-phase rule)

- done: plan approved after 4-researcher recon; built + pushed (9c6ad38,
  e35cd68, 8299fc5): LICENSE (was the flip blocker), CITATION.cff, AI-USE.md +
  pinned check workflow, CHANGELOG (psr-managed), CONTRIBUTING, model card,
  ci.yml (matrix 3.11-3.13 + cleanroom wheel + docker w/ lightgbm smoke +
  strict docs; codecov OIDC public-gated AND dependabot-excluded),
  release.yml (dispatch-only uvx psr 10.6.2, noop default; psr_parser.py
  strips the [claude] prefix — 0/28 unparseable, computes 0.1.0, proven in a
  scratch clone end-to-end incl. uv.lock-in-release-commit at 0.1.1),
  publish.yml (Trusted Publishing, public-gated, scoped sdist), docs.yml
  (Pages, deploy public-gated), Dockerfile (digest-pinned, libgomp1 verified
  required, nonroot) + .dockerignore, pre-commit (clean --all-files) +
  .secrets.baseline, dependabot (4 ecosystems, python base-image ignore).
- Repo settings hardened: description/topics fixed, wiki+projects off, ruleset
  protect-master (deletion+non-fast-forward), sha_pinning_required=true, old
  artifacts deleted.
- Adversarial pass (4 refuters): release SURVIVED (psr end-to-end proven);
  gates/docs-docker/mutations PARTIALLY REFUTED — 1 high (dependabot codecov
  failure post-flip) + 5 medium + 6 low, ALL fixed with attack-derived guards
  in 8299fc5; 12 mutants run, kills verified, honesty suite hardened against
  every survivor. Gates: 310 offline, cov 95.95%; ci/docs/ai-use green on
  8299fc5 (runs 33482841761/97/46); release --noop on a real runner printed
  0.1.0 (33480745656); docs deploy verifiably SKIPPED while private.
- Accepted residuals (stated): ruleset has no PR/status-check requirement
  (solo-maintainer posture — direct pushes remain possible, honesty tests are
  advisory against them); allowed_actions=all mitigated by sha_pinning_required;
  uvx psr resolves transitive deps unpinned at run time; publish.yml's first
  run under sha_pinning_required is the proof for pypa's runtime-generated
  local action ref; ci docs-build duplicates docs.yml's build per master push
  (waste, accepted); dependabot PRs #2/#3 (setup-uv v10, upload-artifact v7)
  open — need rebase post-8299fc5 before merging; Metaculus thread still
  parked.
- **FLIPPED PUBLIC 2026-09-01 ~09:25 PDT on Jeremy's word** — MIT detected,
  Pages enabled via API and docs deploy un-skipped (site 200 at
  jeremygracey-ai.github.io/prime-radiant), secret scanning + push protection
  enabled via API, badges resolve anonymously. v0.1.0 RELEASED + ON PYPI
  2026-09-01 (runs 33540519945/33540651371; publisher converted). Codecov LIVE
  (app connected, CODECOV_READY=1, badge 96%). Dependabot PRs #2/#3 merged, ci
  green on bumped pins. EVERYTHING ACTIONABLE IS CLOSED — remaining items are
  calendar/external only: hub PR #3696 maintainer CI, ~Oct tasks.json
  re-verification, ~Nov first live submission (explicit go), 60-day cron watch
  (commit every ~50 days in season).
  HF_TOKEN rotation DONE 2026-09-01 (fine-grained single-Space token; verified
  by redeploy run 33539866635).
- Previously (the gate): THE PUBLIC FLIP — Jeremy's word. Post-flip steps in
  the runbook "Phase G — public flip sequence": Pages enable, push protection,
  PyPI pending publisher, Codecov app if needed, first release + publish
  dispatch --ref on the tag. HF_TOKEN rotation TODO still open from Phase F.

- **The Prime Radiant Record shipped (2026-09-01 ~15:30 PDT)**: all eight
  phase walkthroughs merged into one publication (HTML artifact + PDF),
  committed at docs/prime-radiant-record.pdf, linked from the README and the
  docs site (Pages serves it). Jeremy verified before the link landed. The
  merge caught a real bug: the plotly cdnjs pin (3.7.0) never existed — the
  Phase F walkthrough's live panels had been silently blank; both artifacts
  republished on the verified 3.5.1 pin.
- End-to-end health sweep on 4b18c87: git clean, local==origin; make check
  (310, cov 95.95%) + make test-integration (11) + pre-commit --all-files all
  green; ci/docs/ai-use green; all 7 public URLs 200 (incl. the PDF on GitHub
  and Pages); badges resolve anonymously (passing / 96% / v0.1.0); Space
  RUNNING; hub PR #3696 open awaiting maintainer CI; weekly cron active;
  0 open PRs/issues.

- Coverage push (Jeremy's ask, 2026-09-01 ~16:15 PDT): rolling.py + metadata.py
  70.6%/70.8% -> 100% with REAL tests (to_integer_submission contract incl. the
  loud crossing SchemaError, hub rounding rule, all-NaN guard, cleanroom
  fallback, write round-trip); 5 mutants run and killed; offline total 95.95%
  -> 97.72%. PROCESS SLIP (recorded, again): the gate was piped
  (`make check | tail`) in the commit chain and a pyright error reached commit
  76f7226; caught immediately, fixed next commit, gate re-run UNPIPED. The
  rule stands: never pipe the gate command itself.

- 100% and the ratchet (2026-09-01, three user-pushed rounds): the four lowest
  files (metaculus, validate, report, baseline) then every remaining miss ->
  **100.00% offline coverage, 335 tests, 15 mutants run and killed total**;
  gate ratcheted to `--cov-fail-under=100` in Makefile + ci.yml. Learning
  moment written up as the personal skill `closing-coverage-gaps`
  (~/.claude/skills/), TDD'd per writing-skills: baseline agents 0/2 ran
  mutants, with-skill 2/2 produced mutant tables.
- Notation system (answer to "where do we write up the work"; README rejected
  as a front page, not a work log). Three layers, each in the project's own
  machinery:
  1. **CHANGELOG.md** (what changed) — psr-generated from the actor-prefixed
     conventional commits; v0.1.1 cut deliberately to materialize this
     session's entries (Testing section carries the three coverage commits).
  2. **The Record** (why/how narrative) — Afterword section added
     ("Coverage to 100 — and the gate raised to hold it"), PDF rebuilt and
     committed at docs/prime-radiant-record.pdf (120f5a2).
  3. **restart.md** (session log) — this file.
- v0.1.1 chain complete: release run green -> release commit ede7a51
  (CHANGELOG + version + uv.lock, psr-authored) -> publish dispatched
  `--ref v0.1.1` (house rule) -> build+publish green with attestations ->
  pypi.org shows 0.1.1 latest. ci/docs/ai-use green on master.
- README: codecov sunburst graph embedded (Jeremy's pick), right-aligned
  beside the intro, linked to the codecov dashboard (7d5a0ea).

- Early-live build (2026-09-01 evening, Jeremy: "can we run up before Nov?"):
  4-agent recon workflow settled it — hub enumerates NOTHING after 2026-05-30
  (submission structurally impossible today), 2026-27 config lands in Sep by
  3-season precedent, Oct windows existed 2 of 3 years (earliest realistic
  real submission mid-late Oct), hub truth data dormant since 2026-07-09.
  Built on "build it all now": --shadow CLI mode (current-week forecast,
  vintage guard NEVER relaxed, exit 3 = honest skip; validate --shadow relaxes
  round membership only), shadow job committing weekly CSVs to shadow-output/
  once the hub wakes (self-arming baseline), scripts/open_hub_pr.sh replacing
  the exit-1 stub (fixture-tested vs local bare repos + stubbed gh),
  hub-config-watch.yml daily season trigger (one-open-issue ping).
  Adversarial panel: 4 MEDIUMs demonstrated and fixed with regression tests —
  KeyError-as-skip masquerade (NoUsableVintageError), no freshness gate on the
  live path (stale round could submit; now exit 65), same-week retry dead-end
  (force-push idempotency), watcher silent on hub restructure (zero-parse now
  red); plus missing-PAT green-skip -> red, local self-arming via
  update_hub_clone, watcher pagination/quoting. 15 mutants run-and-killed
  total this build; gates green (379 offline @100%, 11 integration); runner
  proofs: shadow exit-3 path green with step summary + downstream steps
  SKIPPED, watcher "no rounds beyond 2026-05-30", live-submit skipped.
  PROCESS SLIP (new lesson): ran mutants on UNCOMMITTED implementation; the
  restore `git checkout` reverted to HEAD and wiped the implementation —
  commit first, then mutate.

## Next step

Calendar items only: hub PR #3696 maintainer CI approval (watch); ~Oct 2026
tasks.json re-verification for the 2026-27 season; ~Nov 2026 first live
submission on Jeremy's explicit go only (LIVE + PAT deliberately unset);
commit every ~50 days in season so the cron never auto-disables.

## Verify

`make check` (offline) · `make test-integration` (network) ·
`uvx pre-commit run --all-files` · CI runs on master green.

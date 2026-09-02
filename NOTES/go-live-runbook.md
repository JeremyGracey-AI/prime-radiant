# Go-live runbook — FluSight 2026-27

Nothing below happens automatically. Every step is outward-facing and waits for
Jeremy's explicit go. Verified facts as of 2026-08-31.

## Executed 2026-08-31 (Jeremy's "go live on everything")

- [x] Step 1 — fork created: JeremyGracey-AI/FluSight-forecast-hub.
- [x] Step 4 — registration PR OPEN: cdcepi/FluSight-forecast-hub#3696
      (`designated_model: true` — the committed Phase E value; amendable on the
      fork branch `add-jgracey-prime-radiant-metadata` until the hub merges).
      Metadata re-validated against the LIVE hub schema before opening
      (byte-identical to the recorded fixture). First-time contributors need a
      maintainer to approve the hub's CI run — expect a wait.
- [x] Dashboard go-live 1–4 — Space live: https://huggingface.co/spaces/jeremygracey-ai/prime-radiant
      (created public via local credential; SPACE_LIVE=1; deploy run 33474626675
      green end-to-end incl. repo_info pre-check + hf upload; app HTTP 200,
      served config verified: 4 tabs, 4 plots, 5 handlers).
- [x] **HF_TOKEN ROTATED 2026-09-01 ~10:47 PDT**: repo secret now holds a
      fine-grained token scoped to Write on only the one Space (Jeremy minted
      it; secret set in his own terminal, never in a transcript). Verified by
      redeploy run 33539866635 — repo_info pre-check + hf upload green under
      the new token; Space RUNNING, HTTP 200. Broad cached local token
      untouched, per plan.
- NOT done, deliberately: step 2 (PAT — only needed for CI-opened weekly PRs,
  ~Nov) and step 3 (`LIVE=1` — stays unset until the weekly live path is
  implemented; arming it early would muddy the audit trail).

## Preconditions (watch, ~Oct-Nov 2026)

- [ ] Hub adds 2026-27 reference dates to `hub-config/tasks.json` (2025-26
      precedent: v6 tasks.json landed 2025-11-05 for a Nov 19 start; watch
      `cdcepi/FluSight-forecast-hub` commits). Until then, any forecast PR fails
      hub CI ("reference_date not a hub round") — and our own `validate` command
      fails the same way, by design.
- [ ] Re-verify tasks.json for 2026-27 rule changes (quantile set, targets,
      integer policy) — HANDOFF_PHASE2.md requires re-verification in October.

## Steps, in order

1. **Fork**: `gh repo fork cdcepi/FluSight-forecast-hub --clone=false`
   (verified: no fork exists under JeremyGracey-AI today).
2. **PAT**: create a CLASSIC personal access token, scope `public_repo`;
   store as repo secret `FLUSIGHT_HUB_PAT` (fine-grained PATs cannot open PRs
   on unscoped public upstreams; default GITHUB_TOKEN cannot cross repos).
3. **Repo variable**: set `LIVE=1` (`gh variable set LIVE --body 1`).
4. **Registration PR**: render metadata
   (`uv run python -c "from pathlib import Path; from prime_radiant.epi.submission.metadata import write_model_metadata; write_model_metadata(Path('out'))"`),
   push `model-metadata/JGracey-prime_radiant.yml` to a fork branch, open the PR.
   Metadata-only PRs merge off-season (verified: hub PRs #3685/#3687). Decide
   `designated_model` (currently `true` = CDC-ensemble-eligible, max 2/team;
   flip to false for a soft launch) BEFORE opening.
5. **PR step IMPLEMENTED** (2026-09-01): `scripts/open_hub_pr.sh`, called by
   the `live-submit` job after downloading the dry-run's validated artifact
   (CSV + rendered metadata). Pushes `submit-<ref>` to the fork, opens the PR
   against `cdcepi:main`, one forecast file per PR; bundles
   `model-metadata/JGracey-prime_radiant.yml` ONLY if upstream still lacks it
   (hub precedent #2329 — covers PR #3696 still being open). Fixture-tested
   against local bare upstream/fork repos with a stubbed `gh`
   (tests/unit/test_open_hub_pr_script.py). STATED GAP: real execution against
   the live hub is untestable until a season window opens — first dispatch
   with live=true is also the script's first live run; watch it end-to-end.
6. **First live submission**: manual dispatch with `live=true`, inside the
   window (Sun −6 .. Wed −3 before the Saturday reference date, 11 PM ET hard
   deadline — the hub does not accept late forecasts). First-time contributors
   need a maintainer to approve the hub's CI run (GitHub default).

## Off-season shadow baseline + season watcher (added 2026-09-01)

- **Shadow job** (weekly-forecast.yml): every Tuesday cron also attempts a
  CURRENT-week forecast (`epi forecast --shadow`). The vintage guard is never
  relaxed: while the hub's truth data is off-season stale (last update
  2026-07-09) the job exits 3 = green run + "Shadow skip" step summary. The
  week the hub resumes publishing truth (2025 precedent: Sep 5), validated
  shadow CSVs start landing in `shadow-output/` via `[cron] chore(shadow)`
  commits — the season baseline arms itself, no action needed.
- **hub-config-watch.yml**: daily 13:23 UTC check of the hub's live tasks.json
  for reference dates beyond LAST_KNOWN_MAX=2026-05-30. On the 2026-27 config
  landing it opens ONE repo issue with the go-live checklist (metadata schema
  re-check, PAT + LIVE, dry-run dispatch, first-window submission). After
  handling: bump LAST_KNOWN_MAX, close the issue.
- Both crons are subject to the 60-day auto-disable watch below.

## Dashboard go-live (Phase F — separate go from the hub go-live)

The Space, its token, and the first push are outward-facing and wait for
Jeremy's explicit go, exactly like the hub steps above.

1. **Create the Space** (account must be PRO — required for new Gradio Spaces
   since ~Jul 2026; verified PRO 2026-08-31):
   `uv run --with huggingface_hub python -c "from huggingface_hub import create_repo; create_repo('jeremygracey-ai/prime-radiant', repo_type='space', space_sdk='gradio', exist_ok=True)"`
   (space_sdk is mandatory; plain git push does NOT auto-create a Space.)
2. **Token**: fine-grained HF token, write access scoped to that Space only;
   store as repo secret `HF_TOKEN` (`gh secret set HF_TOKEN`). The narrow scope
   also forecloses implicit Space creation: `hf upload` silently create_repo's a
   missing Space with a broad write token (verified in huggingface_hub 1.29.0
   cli/upload.py), and the deploy job's repo_info pre-check plus this scope make
   that structurally impossible. Alternative with zero stored secret: configure
   the repo+workflow as a Trusted Publisher in the Space settings and add
   `id-token: write` to the deploy job.
3. **Repo variable**: `gh variable set SPACE_LIVE --body 1`.
4. **Deploy**: dispatch `space-deploy` with `deploy=true`; verify the Space
   boots on CPU-basic and every panel renders.
5. **Staleness watch**: the bundle is frozen (reference 2026-05-30, truth as-of
   2026-07-09). For a live 2026-27 season the weekly workflow must be chained to
   rebuild/refresh `serve_data/` and re-dispatch the deploy — NOT wired yet, by
   design; decide at hub go-live. CPU-basic Spaces sleep after a fixed 48h idle;
   first visitor wakes them. Caution (refuter-noted): after go-live, RE-RUNNING
   an old `deploy=true` workflow run re-evaluates vars at re-run time and would
   redeploy that run's STALE staged artifact — always dispatch fresh, never
   re-run.

## FLIPPED PUBLIC 2026-09-01 ~09:25 PDT (Jeremy's explicit word)

- [x] Repo public; MIT license detected; description/topics live.
- [x] Pages enabled via API (build_type=workflow) — docs deploy un-skipped and
      the site serves: https://jeremygracey-ai.github.io/prime-radiant/
- [x] Secret scanning + push protection enabled via API.
- [x] Dependabot PRs #2/#3 rebased to green; merge decision is Jeremy's.
- [x] **v0.1.0 RELEASED AND PUBLISHED 2026-09-01 ~10:55 PDT**: Jeremy
      registered the pending publisher; release run 33540519945 (psr commit
      773b97a, tag v0.1.0, GitHub release); publish run 33540651371 on the tag
      ref — Trusted Publishing green, pypi.org/project/prime-radiant live
      (wheel 53KB, scoped sdist 344KB). PyPI badge added.
- [x] **CODECOV LIVE 2026-09-01 ~11:10 PDT**: Jeremy signed up + connected
      GitHub on codecov.io; CODECOV_READY=1 set; upload green on run
      33541724367 and the push after — badge renders 96%. Added to README.
- [x] Dependabot PRs #2/#3 MERGED (Jeremy's "finish this out"): setup-uv →
      v10.0.1, upload-artifact → v7.0.1 across workflows; ci green on the
      bumped pins.
- [x] HF_TOKEN rotation to fine-grained — done 2026-09-01 (see above).

## Phase G — public flip sequence (Jeremy's gate) + post-flip steps

Pre-flip (agent-executable on go): LICENSE committed; repo description/topics
fixed; branch ruleset on master (no force-push/deletion); wiki+projects
disabled; Actions `sha_pinning_required` on; old CI artifacts deleted
(regenerate on next runs). Then **the flip itself is Jeremy's word**
(`gh repo edit --visibility public --accept-visibility-change-consequences`).

Post-flip, in order:
1. Settings → Pages → Source: **GitHub Actions**, then dispatch `docs` (its
   deploy job un-skips once the repo is public).
2. Settings → Code security: enable secret-scanning **push protection**
   (secret scanning itself turns on automatically for public repos).
3. **PyPI pending publisher** (outward, Jeremy's account): pypi.org → account
   → Publishing → add GitHub Actions publisher: project `prime-radiant`
   (verified free), owner `JeremyGracey-AI`, repo `prime-radiant`, workflow
   `publish.yml`, environment `pypi`. Until this exists, publish.yml's publish
   job fails at PyPI — by design. Optional hardening (refuter-noted): the
   `pypi` GitHub environment auto-creates UNPROTECTED on first run — pre-create
   it in Settings → Environments with a deployment protection rule if wanted.
4. Codecov: install/authorize the Codecov GitHub app for the repo if coverage
   uploads don't appear (ci.yml uses OIDC, no stored token; the upload step is
   public-gated and turns on at the flip). Then add the codecov badge.
5. First release: dispatch `release` with noop=true (verify computed version
   0.1.0), then noop=false; then dispatch `publish` **with `--ref v0.1.0`**
   (GITHUB_TOKEN-pushed tags cannot fire the push trigger; dispatching on the
   tag ref, not master, guarantees the built artifact matches the tag). Then
   add the PyPI badge. The first release commit contains only CHANGELOG.md —
   pyproject/uv.lock are already at 0.1.0; the lock-in-release-commit mechanism
   engages from 0.1.1 (refuter-verified, not a failure).

Cautions (refuter-noted): NEVER re-run a pre-flip workflow run after the flip —
re-runs reuse the frozen event payload (private=true) and the public gates stay
skipped; always dispatch fresh. AI-USE.md staleness (max-age-days 180 from
2026-08-31) first fails a push on ~2027-02-28 — bump `updated` when the AI-use
reality changes, or expect the ai-use check to go red then.

## Cron auto-disable watch (public repos)

GitHub disables scheduled workflows after 60 days without repository activity;
scheduled runs themselves do NOT reset the timer, and hub submissions land on
the FORK, so FluSight season activity does not protect the weekly cron either.
During Nov–May: ensure a commit lands at least every ~50 days OR re-enable via
`gh workflow enable weekly-forecast` when the disable email arrives (it goes
to whoever last touched the cron line).

## Standing cautions

- Hub merges are done by human maintainers; unmerged late PRs are abandoned.
- Public-repo crons auto-disable after 60 days of repo inactivity.
- The hub's submission CI runs `hubValidations::validate_pr` with the window
  check ON; our local `validate` mirrors the schema/config checks plus
  `counts_lt_popn`, but the WINDOW check only the hub enforces.

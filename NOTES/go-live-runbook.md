# Go-live runbook — FluSight 2026-27

Nothing below happens automatically. Every step is outward-facing and waits for
Jeremy's explicit go. Verified facts as of 2026-08-31.

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
5. **Implement the PR step** in `.github/workflows/weekly-forecast.yml`
   (`live-submit` job currently exits 1 loudly): push branch to the fork with
   the week's file at `model-output/JGracey-prime_radiant/<ref>-JGracey-prime_radiant.csv`,
   `gh pr create` against `cdcepi:main`. One forecast file per weekly PR
   (observed convention).
6. **First live submission**: manual dispatch with `live=true`, inside the
   window (Sun −6 .. Wed −3 before the Saturday reference date, 11 PM ET hard
   deadline — the hub does not accept late forecasts). First-time contributors
   need a maintainer to approve the hub's CI run (GitHub default).

## Standing cautions

- Hub merges are done by human maintainers; unmerged late PRs are abandoned.
- Public-repo crons auto-disable after 60 days of repo inactivity.
- The hub's submission CI runs `hubValidations::validate_pr` with the window
  check ON; our local `validate` mirrors the schema/config checks plus
  `counts_lt_popn`, but the WINDOW check only the hub enforces.

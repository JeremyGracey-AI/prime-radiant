# Codebase walkthrough

Three passes over the repository: the **map** (where things live), the
**forecast pipeline** (what a run actually computes), and the **automation**
(how it runs itself, and where the gates are). A designed rendition of this
page ships as [a PDF](prime-radiant-codebase.pdf).

## 1. The map — where everything lives

Everything interesting is one Python package plus four surfaces that consume it.

```mermaid
flowchart LR
    subgraph pkg["src/prime_radiant — the package"]
        cli["epi/cli.py<br/>forecast · validate · bundle"]
        data["epi/data/<br/>hub · vintages · epiweek<br/>locations · nhsn · benchmarks"]
        feat["epi/features/<br/>transform · lags · seasonal · assemble"]
        models["epi/models/<br/>lgbm_quantile · baseline<br/>ensemble · seasonal · postprocess"]
        sub["epi/submission/<br/>format · validate · write · metadata"]
        bt["epi/backtest/<br/>rolling · report"]
        ev["eval/<br/>wis · scoring"]
        serve["epi/serve/bundle.py"]
    end

    subgraph surfaces["Surfaces"]
        dash["dashboard/ → HF Space"]
        hub["CDC FluSight hub<br/>(PR per week, gated)"]
        pypi["PyPI prime-radiant"]
        docsp["docs/ → GitHub Pages"]
    end

    cli --> data --> feat --> models --> sub
    bt --> ev
    bt --> serve --> dash
    sub --> hub
    pkg --> pypi
    docsp -.describes.-> pkg
```

Reading order for a newcomer: `src/prime_radiant/epi/cli.py` is the front
door — three subcommands, everything else hangs off them. `epi/data` gets and
time-scopes the data, `features`/`models` do the ML, `submission` speaks the
hub's contract, `backtest` + `eval` prove the model is honest, `serve`
packages results for the dashboard. `metaculus.py` and `replication.py` are
the parked Phase-1 thread. At the top level, `tests/` mirrors all of it at
100% coverage, `scripts/open_hub_pr.sh` is the one shell dependency, and
`NOTES/` is the project's memory.

## 2. The heart — what one weekly forecast run computes

The load-bearing idea is **vintage discipline**: never let the model see data
dated after the forecast origin. That is why the data layer is built on git
archaeology rather than "download latest".

```mermaid
flowchart TD
    clone["data/hub.py<br/>ensure_hub_clone — blobless clone of the CDC hub"]
    asof["data/vintages.py · as_of<br/>check out truth CSV <b>as it existed</b> on a past date<br/>(git history = time machine)"]
    guard["backtest/rolling.py · resolve_usable_vintage<br/>walk back 3→10 days from origin<br/>GUARD: ≥52 wks history, ≤14 days stale<br/>honest miss = NoUsableVintageError"]
    feats["features/<br/>transform: 4th-root admission <b>rates</b><br/>lags + seasonal terms → assemble matrix"]

    lgbm["models/lgbm_quantile<br/>pooled LightGBM, 23 quantiles"]
    base["models/baseline<br/>replica of FluSight-baseline<br/>(cross-validated to rel-WIS 0.999989)"]
    ens["models/ensemble<br/>per-quantile MEDIAN of the two<br/>← this is what gets submitted"]

    integer["rolling.to_integer_submission<br/>sort quantiles, round to ints"]
    frame["submission/format<br/>8-column hub frame, Saturday check"]
    validate["submission/validate<br/>vs the hub's LIVE tasks.json:<br/>round · quantile levels · locations<br/>horizons · counts &lt; population · pandera schema"]
    csv["model-output/&lt;date&gt;-JGracey-prime_radiant.csv"]

    clone --> asof --> guard --> feats
    feats --> lgbm --> ens
    feats --> base --> ens
    ens --> integer --> frame --> validate --> csv
```

The same `run_origin` function drives both live forecasts and the historical
backtests — `backtest/rolling.py` replays it across 55 past origins,
`eval/wis.py` scores each with the hub's own metric (weighted interval score),
`backtest/report.py` writes the league tables, and `serve/bundle.py` snapshots
all of it into the offline bundle the dashboard serves. One code path, so a
backtest win means something about the live path.

## 3. The nervous system — how it runs itself, and where the gates are

```mermaid
flowchart TD
    cron["⏰ Tue 22:17 UTC cron"] --> dry & shadow
    daily["⏰ daily 13:23 UTC"] --> watch

    subgraph wf["weekly-forecast.yml"]
        dry["dry-run job<br/>forecast auto → validate<br/>render metadata → artifact"]
        shadow["shadow job<br/>forecast --shadow (current week)<br/>guard refuses → exit 3, green skip<br/>guard passes → commit to shadow-output/"]
        live["live-submit job<br/>download artifact →<br/>scripts/open_hub_pr.sh<br/>freshness gate · idempotent retry"]
    end

    subgraph watchwf["hub-config-watch.yml"]
        watch["rounds beyond 2026-05-30?<br/>zero parsed = RED, not quiet"]
        issue["ONE open issue:<br/>the go-live checklist"]
    end

    gates{"🔒 ALL required:<br/>manual dispatch · live=true<br/>vars.LIVE=1 · PAT secret"}
    hubpr["PR → cdcepi/FluSight-forecast-hub<br/>(bundles metadata if #3696 unmerged)"]

    dry --> gates --> live --> hubpr
    watch -->|"config drops (~Sep)"| issue
    shadow -.->|"self-arms when hub truth resumes"| shadowout["shadow-output/ baseline"]

    subgraph release["Release machinery (separate workflows)"]
        ci["ci.yml — make check @ 100% cov,<br/>wheel cleanroom, docker, codecov"]
        rel["release.yml → psr → tag → publish.yml → PyPI"]
        pages["docs.yml → Pages · space-deploy.yml → HF Space"]
    end
```

The design rule tying it together: **every gate is structure, not prose**.
Cron cannot reach `live-submit` (its `if:` requires a dispatch event), the
shadow validator relaxes exactly one check and the live path cannot invoke
that relaxation, the PR script refuses stale reference dates with its own
exit code — and each of those claims has a test that a mutant provably fails
(`tests/unit/test_workflow_honesty.py` and friends). The forecast can be
wrong; the plumbing can't quietly lie about what it did.

## 4. The next step — the season starts itself

| When | What fires | Whose action |
| --- | --- | --- |
| Now | Shadow job green-skips weekly; watcher checks the hub config daily | none |
| ~Sep (precedent: Sep 5–30) | 2026-27 config lands → watcher opens its issue; hub truth resumes → shadow CSVs start landing in `shadow-output/` | none |
| The gap | PAT + `LIVE=1` set; dry-run dispatched against a real new-season round | operator |
| First open window (possibly mid-Oct) | First real submission — explicit go only | operator |
| ~Nov 18 | Guaranteed open: mass season start | operator |

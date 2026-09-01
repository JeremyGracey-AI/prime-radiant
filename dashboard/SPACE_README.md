---
title: Prime Radiant
emoji: 🦠
colorFrom: yellow
colorTo: green
sdk: gradio
sdk_version: 6.26.0
python_version: "3.12"
app_file: app.py
pinned: false
license: mit
short_description: CDC FluSight flu-hospitalization forecast dashboard
---

# Prime Radiant — FluSight forecast dashboard

Quantile forecasts of weekly confirmed-influenza hospital admissions in the CDC
[FluSight](https://github.com/cdcepi/FluSight-forecast-hub) format, WIS-scored
against three seasons of backtests (2023-24, 2024-25, 2025-26).

**Panels**

- **Map** — predicted 3-week change per state: horizon-3 median minus the last
  observation at or before the forecast reference date.
- **Fan chart** — per-state forecast intervals (50/80/95%) with observed history.
- **Reliability** — empirical vs nominal interval coverage, per season and by
  horizon for the LightGBM model.
- **League table** — WIS and relative skill vs FluSight-baseline, alongside
  FluSight-ensemble and UMass-flusion on the common task set.

**Data** — a frozen, precomputed bundle (`serve_data/`) built offline by
`prime-radiant epi bundle` in the source repo
([JeremyGracey-AI/prime-radiant](https://github.com/JeremyGracey-AI/prime-radiant))
from vintage-honest backtests; truth is pinned to its stated as-of date. The
Space runs no models and fetches nothing at serve time.

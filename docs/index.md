# Prime Radiant

Calibrated forecasting. Two threads share this repo and a calibration thesis:

- **FluSight epi forecaster** — CDC FluSight quantile forecasts (WIS-scored)
  for weekly confirmed-flu hospital admissions. Pure statistical pipeline, no
  LLM calls, ≈$0 compute. Registered as `JGracey-prime_radiant`.
- **Metaculus LLM bot** — LLM retrieval → ensemble → aggregation on binary
  questions, Brier-scored. Parked at its retrieval phase.

## Start here

- **[Live dashboard](https://huggingface.co/spaces/jeremygracey-ai/prime-radiant)** —
  choropleth of predicted 3-week change, per-state fan charts, reliability
  curves, league tables, all served from a frozen, byte-regenerable bundle.
- **[Model card](model-card.md)** — architecture, data, honest evaluation
  (including the seasons it loses and the under-coverage debt).
- [Repository](https://github.com/JeremyGracey-AI/prime-radiant) —
  README carries the three-season league tables;
  [CONTRIBUTING](https://github.com/JeremyGracey-AI/prime-radiant/blob/master/CONTRIBUTING.md)
  carries the gates;
  [AI-USE](https://github.com/JeremyGracey-AI/prime-radiant/blob/master/AI-USE.md)
  declares how AI built this;
  [CHANGELOG](https://github.com/JeremyGracey-AI/prime-radiant/blob/master/CHANGELOG.md)
  is release-automation-managed.

## The one-paragraph method

NHSN weekly admissions (hub target data, git-vintaged) → per-100k 4th-root
transform with per-location scale/center fitted per origin → pooled LightGBM
quantile regression (23 levels, horizon-as-feature, deterministic,
exact-pinned) → monotone sort, inversion, integer rounding at the hub
boundary → per-quantile-median ensemble with a validated baseline replica →
WIS/coverage scoring on natural and log scales, pinned-truth, common-task
relative skill. Leakage invariants are property-tested, not commented.

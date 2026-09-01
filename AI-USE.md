---
ai_use_version: "0.1"
assisted: [code-scaffolding, tests, research, drafting, refactoring]
human: [architecture, decisions, data, final-edit, go-live-gates]
review: full
accountable: Jeremy Gracey
updated: 2026-08-31
---

This repository was built agent-assisted with Claude Code (Anthropic), phase by
phase, under an explicit governance frame: the agent proposes and builds; every
outward-facing action — hub registration, live submissions, deployments, the
public flip of this repo — waits for my explicit go, enforced structurally in
gated CI workflows rather than by convention. Every phase was adversarially
verified before being declared done: independent refuter agents attacked the
claims, mutants were actually run against the test suite, and findings were
fixed with attack-derived regression tests. The `[claude]`-prefixed commits are
the agent's; the methodology choices, the decision to publish losing seasons
alongside the winning one, and the acceptance of every stated gap are mine. I
read and approved the work this declaration covers. If the forecasts are wrong
or the engineering is unsound, that is on me, not the model.

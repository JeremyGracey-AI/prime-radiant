# Parking lot

Ideas out of Phase 1 scope. Park here, do not build.

- Phase 2/3: ABM, generative agents (per handoff brief — explicitly out of scope)

## Metaculus thread — design constraints from "Are LLMs Prescient?" (arXiv:2411.08324)

Read 2026-09-01 (Daily Oracle, NYU; benchmark + code at
agenticlearning.ai/daily-oracle, updated daily). Not applicable to the FluSight
thread (no LLM in that pipeline, by design). When the Metaculus thread unparks,
these findings bind its design:

1. **Phase B retrieval cutoff must be model-knowledge-aware, not just
   question-date-aware.** Their constrained open-book setting cuts the corpus at
   min(resolution_date − 1, RAG_cutoff) — our planned leakage guard (reject
   post-cutoff articles) should adopt the same two-sided form, and the leakage
   unit test should cover both sides.
2. **Phase D backtests must partition by the model's knowledge cutoff.** Their
   central result: accuracy declines gradually pre-cutoff and rapidly
   post-cutoff, and pooling the two inflates apparent skill. Honest eval =
   report pre- and post-cutoff Brier separately; weight the post-cutoff slice
   (that is the deployed regime).
3. **RAG alone will not carry calibration.** Even with the gold source article
   (~90% answerable ceiling) models decline over time — stale internal
   representations, not missing facts. Makes Phase D's recalibration layer
   (Platt, ≥30 resolved) MORE load-bearing than planned, not less.
4. **Reusable assets:** their 7-principle QA filter (esp. non-answerability-
   before-date, no-leakage, non-obviousness) for question hygiene; the Halawi
   et al. 2024 resolved-market set (21,149 questions) and Daily Oracle itself
   (31,510 QA pairs, daily-updated) as supplementary leakage-clean eval sets
   beside Metaculus's own resolved questions.

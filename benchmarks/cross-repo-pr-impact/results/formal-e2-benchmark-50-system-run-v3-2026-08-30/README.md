# Frozen run for the 2026-08-30 strict-E2 release

This directory records one frozen run against `../formal-e2-benchmark-50-v2-2026-08-30/`. All 50 blind containers completed before the unified label read, with Docker network mode `none`, no label-store mount, and no inference-time label read. `verification.json` independently reparses the isolation records and predictions and recomputes all 50 per-case and aggregate scores.

MRR is 0.0722 on development, 0.2333 on evaluation, and 0.25 on holdout. The ranker proposed no runnable checks, so runnable-check rate is 0 and execution remains `not_assessed`. Non-target candidates are `unjudged`; precision, F1, false-positive rate, and specificity are not reported.

Acceptance commands and claim boundaries are documented in `../formal-e2-benchmark-50-v2-2026-08-30/ACCEPTANCE.md`.

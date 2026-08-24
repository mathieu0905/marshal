# Experiment Tracker

| Run ID | Milestone | Purpose | System / Variant | Split | Metrics | Priority | Status | Notes |
|---|---|---|---|---|---|---|---|---|
| R001 | M0 | schema/oracle sanity | deterministic harness | synthetic | parser agreement | MUST | TODO | no product code |
| R002 | M0 | one-case replay | BUMP pre/candidate | calibration | pass/fail, wall time | MUST | TODO | hidden labels |
| R003 | M1 | positive replay | 3 packs | D0 | replay rate, attrition | MUST | TODO | 3 providers |
| R004 | M1 | green candidate mining | exact update tuples | D0 | greens/pack | MUST | TODO | max 30 candidates/pack |
| R005 | M1 | green 2/2 replay | verified controls | D0 | pass stability, resolution | MUST | TODO | candidate version must resolve |
| R006 | M1 | Maven adapter dry run | proof-bound V0 | D0 | proof validity, time | MUST | TODO | fresh local repo |
| R007 | M2 | single-repo condition | C0 | development | primary metrics | MUST | TODO | 3 repeats |
| R008 | M2 | flat-context condition | C1 | development | primary + cost | MUST | TODO | current-state commands allowed |
| R009 | M2 | directional condition | C2 | development | primary + cost | MUST | TODO | no candidate composition |
| R010 | M2 | proof-bound condition | C3 | development | primary + proof | MUST | TODO | exact composition |
| R011 | M3 | held-out four-way run | C0-C3 | test | all primary metrics | MUST | TODO | settings unchanged |
| R012 | M4 | evidence audit | blind two-rater | test sample | correctness, kappa | MUST | TODO | 20% findings |
| R013 | M4 | paired statistics | C0-C3 | test | CI, effect size | MUST | TODO | pack/component unit |
| R014 | M4 | cost/stability analysis | C0-C3 | test | tokens/time/Jaccard | MUST | TODO | 3 repeats |
| R015 | M5 | wallet/node handoff | product case | external | artifact consumption | LATER | TODO | only after GO |
| R016 | M5 | typed LLM proposer | V1 ablation | external | localization vs cost | CUT | TODO | only if deterministic fails |

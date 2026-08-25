# Acceptance statement

## What is machine-accepted

- `final-index.jsonl` contains exactly 50 unique strict-E2 relations.
- For all 50 cases, the validator parses target-specific JSON fields or selected TSV rows and derives A0 pass, A1 fail, and A2 pass. No case is accepted from the index's declared `arms` field alone.
- The 46 pre-existing executions and four new replays are all covered by structured arm rules. The four new replays additionally check raw `run-results.tsv` values and A1 log signatures.
- Terser to Assetgraph Builder and UI5 Builder are checked against all three formal repetitions; each repetition has process exits `0/1/0`. Terser to Preconstruct remains rejected because its A0 and A2 process exits are nonzero.
- Duplicate module/component observations are collapsed to the causal-relation unit. The Backbone relation has two jointly repaired targets but counts as one case.

Run from the repository root:

```bash
python3 benchmarks/cross-repo-pr-impact/verify_final_e2_dataset.py
```

Acceptance requires command exit 0 and the emitted values `case_count=50`, `strict_e2_count=50`, `machine_arm_verified_case_count=50`, and `declared_only_arm_case_count=0`.

## Result-channel policy

The primary result channel is the declared command-scoped test contract. A reliable process exit is parsed when retained. If the historical runner cannot signal test failure through its exit status, a structured native test failure count may be used and must be disclosed in the case note. E2-030 is the only admitted case using that exception: its Gulp/Jasmine process exits zero in every arm, while the retained Jasmine failure counts are 0/3/0.

E2-009 is a test-expectation adaptation rather than a production-code repair. Its A2 scope is explicitly recorded in the case note; all three repetitions still have process exits `0/1/0`. E2-010 is a production configuration repair with the same repeated exit pattern.

## Not supported

- This is not yet a formal leakage-free benchmark release.
- It does not evaluate open-world repository discovery.
- It does not support precision, F1, false-positive rate, or specificity because the main set lacks complete negative judgments.
- The proposed evaluation and holdout labels are not blind: mechanisms, repairs, and labels remain visible in the index. Every case therefore has `blind_evaluation_eligible=false`.
- Two Crater repairs establish repair efficacy but were unmerged at the observation time; they do not establish maintainer adoption.
- The validator and generated manifests are in the same implementation package. The validator checks independent retained execution summaries/logs, but the generated index is not independent evidence for itself.
- A durable Git revision has not been created by this task. Until the user authorizes staging and commit, acceptance must name the workspace state rather than a commit ID.

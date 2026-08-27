# Acceptance statement

## What is machine-accepted

- `final-index.jsonl` contains exactly 50 strict-E2 cases: real replays with A0 exit 0, A1 exit nonzero, A2 exit 0, an exclusive failure signature, and the exact maintainer patch applied to the opening-cutoff target snapshot.
- All 50 cases carry semantic approval, label-independent candidate-catalog target membership, and cutoff target snapshots; 50 unique `(source_change_family, target)` pairs form 25 directed repository relations grouped into 16 connected components, split 30/10/10.
- The frozen run (v4) is verified end to end: 50/50 blind containers with network mode none, label store unmounted, zero label reads during inference, and every prediction timestamped before the unified label-read boundary.

Acceptance commands, run from the repository root (expected: both exit 0 and print `"verified": true`):

```bash
python3 .agents/skills/marshal-e2-case-builder/scripts/verify_formal_release.py \
  --release-dir benchmarks/cross-repo-pr-impact/results/formal-e2-benchmark-50-2026-08-27
python3 .agents/skills/marshal-e2-case-builder/scripts/verify_frozen_benchmark.py \
  --release-dir benchmarks/cross-repo-pr-impact/results/formal-e2-benchmark-50-2026-08-27 \
  --output-dir benchmarks/cross-repo-pr-impact/results/formal-e2-benchmark-50-system-run-v4-2026-08-27
```

## Verification boundaries

- **Leak check is literal.** The four grouping axes are compared after `casefold()` plus whitespace folding (`release_formal_pool.normalized`). A crossed-split pair of differently worded mechanisms or repair templates would not be caught. The hard axes — directed relation and source change family — do guarantee that no repository pair or source-change family crosses splits.
- **The verifier shares a package with the scorer.** `verify_frozen_benchmark.py` recomputes scores with `run_frozen_benchmark.score_prediction`, so it guards against storage drift, not against scoring-code defects. During acceptance, aggregate MRR/Recall@1/@5 were independently reproduced by a separate implementation directly from `predictions.jsonl` × `final-index.jsonl` (development 0.1056/0.0333/0.2, evaluation 0.2833/0.2/0.4, holdout 0.125/0.1/0.2); `check_position_recall` was not independently reimplemented.
- **Blind isolation is proven by pipeline self-records.** The boundary, per-case isolation, and container settings all originate from the same construction pipeline; the verifier re-checks their consistency. The residual trust root is the pipeline itself, not an external witness.

## Process history

- `formal-e2-benchmark-50-system-run{,-v2,-v3}-2026-08-27/` are ramp-up reruns (1, 2, then 7 cases at 12:06–12:09, after the release was frozen at 12:04) retained as evidence that v4 (12:13–12:28, all 50 cases) is the same system at full scale, not a fourth tuned version.
- `formal-e2-50-release-2026-08-26/` is withdrawn diagnostic history: its 0/1/0 evidence came from post-hoc reference-surface checks, not pre-existing target build or test tasks, and does not satisfy TASK_DEFINITION strict-E2 admission. It is retained solely for auditability.

## Not supported

- One frozen run of one system does not support cross-system ranking claims.
- The main set lacks complete negative judgments, so precision, F1, false-positive rate, and specificity are not reported; non-target candidates remain `unjudged`.
- The system proposed no runnable checks, so `runnable_check_rate` is 0 and all execution results remain `not_assessed`. This reflects system output capability, not label quality.
- Evaluation (MRR 0.2833) exceeds development (0.1056); this reflects split composition (large OpenStack catalogs dominate development), not a tuned split.

## Git anchoring

The dataset, frozen run, ramp-up runs, withdrawn history, skill, and governing documents are committed together; the dataset content anchor is commit `ff97315` ("data: freeze formal candidate-bounded strict-E2 benchmark (50 cases) with frozen run v4"). This acceptance-note edit and any later documentation errata do not alter the machine-verified evidence anchored there.

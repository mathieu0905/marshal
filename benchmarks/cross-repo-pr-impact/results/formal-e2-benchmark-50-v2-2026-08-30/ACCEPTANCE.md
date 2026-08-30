# Acceptance statement

## Machine-accepted result

- The release contains exactly 50 candidate-bounded strict-E2 cases. Each case has a real target command replayed as A0 exit 0, A1 exit nonzero, and A2 exit 0, with an A1-exclusive failure signature and the complete maintainer target patch.
- All 50 cases have semantic approval, label-independent candidate-catalog membership, and an available opening-cutoff target snapshot.
- The 50 cases form 15 connected groups and are assigned 30/10/10 to development, evaluation, and holdout. Directed relation, source-change family, normalized mechanism, and normalized repair template do not cross splits.
- The matching frozen run completed 50 network-disabled blind containers. Label stores were mounted in 0 cases, labels were read during inference in 0 cases, and every prediction preceded the unified label-read boundary.

Run both commands from the marshal repository root. Each must exit 0 and print `"verified": true` with an empty `blockers` list.

```bash
python3 .agents/skills/marshal-e2-case-builder/scripts/verify_formal_release.py \
  --release-dir benchmarks/cross-repo-pr-impact/results/formal-e2-benchmark-50-v2-2026-08-30
python3 .agents/skills/marshal-e2-case-builder/scripts/verify_frozen_benchmark.py \
  --release-dir benchmarks/cross-repo-pr-impact/results/formal-e2-benchmark-50-v2-2026-08-30 \
  --output-dir benchmarks/cross-repo-pr-impact/results/formal-e2-benchmark-50-system-run-v3-2026-08-30
```

## Verification boundaries

- The mechanism and repair-template leakage checks normalize case and whitespace; they do not prove semantic equivalence between differently worded labels. Directed relation and source-change family are the hard grouping axes.
- The frozen verifier recomputes scores with code from the same skill package as the runner. It detects output or storage drift, chronology violations, and aggregate inconsistencies, but it is not an independently implemented scorer.
- Container isolation is established by the runner's Docker boundary and its recorded evidence, then consistency-checked by the verifier. It is not an external attestation.
- Candidate source archives and Git mirrors are project-local storage referenced by the public manifests; they are not duplicated into this 41 MB evidence package. A distribution must either carry those exact-commit stores or rewrite only the storage location while preserving the declared repository and commit mapping.

## Not supported

- Non-target candidates remain `unjudged`; the main set does not support precision, F1, false-positive rate, or specificity.
- One frozen run of one ranker does not support cross-system superiority claims.
- The frozen ranker proposed no runnable checks, so runnable-check rate is 0 and execution results are `not_assessed`. This describes the ranker's output, not the quality of the strict-E2 labels.
- The checked-in release contains labels and frozen predictions. A third-party blind evaluation must distribute a carved public package and withhold `final-index.jsonl`, `expected-locations.json`, `cases/*/private/`, scores, and prior predictions until prediction submission is frozen.

## Version and repository location

The marshal source-of-truth commit for this release and frozen run is `7ebe4624`. The separate private dataset repository is `mathieu0905/cross-repo-breakage-benchmark`; at the time of this note it still contains the superseded 2026-08-27 extraction and must not be described as carrying this release until it is synchronized and reverified in that layout.

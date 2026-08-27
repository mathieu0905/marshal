# WITHDRAWN: reference-contract diagnostic package

This directory is **not a formal strict-E2 benchmark**. It contains 50 post-hoc, dataset-authored reference-surface checks. Those checks mechanically produce A0/A1/A2 directions from source and target edits, but they do not prove that a pre-existing target build or test failed under the source-only change. The earlier formal claim is withdrawn.

## What remains useful

- Candidate catalogs were generated before target-label review from two reusable project sources: the OpenStack global-requirements project list (216 repositories) and the StarlingX manifest (75 repositories). Catalog membership did not read case labels.
- Every source input is Gerrit patch set 1 at change creation time. `source-patches/` contains the code diff only; Gerrit commit messages and `Depends-On` trailers are absent.
- Every case has the catalog repositories resolved to their latest default-branch commit at or before the source opening cutoff. Known targets are available in those pre-cutoff catalogs; other candidates remain `unjudged`.
- Every diagnostic check reads real repository files at four pinned commits. This is useful candidate triage, not strict-E2 admission evidence.
- Source families are not split: 30 development, 10 evaluation, and 10 holdout cases.
- The native Marshal configured-contract track wrote 50 empty predictions before label reveal. It did not read candidate repository code, so it is not the required candidate-code ranking run and has no formal benchmark score.

Strict-E2 admission now requires the same pre-existing target command in all arms: A0 old source + old target passes; A1 new source + old target fails; A2 new source + maintainer target repair passes, with the A1 signature gone. None of the 50 checks in this directory currently meets that standard.

## Contents

- `final-index.jsonl`: authoritative 50 labels and split assignments.
- `inputs.jsonl`, `source-patches/`, `candidate-repositories.json`, `repository-snapshots.jsonl`: public evaluation inputs.
- `evidence/*/contract.json` and `run-results.tsv`: per-case three-arm replay records.
- `predictions.jsonl`, `blind-run-records.jsonl`, `marshal-native-score.json`: the frozen native Marshal run and score.
- `group-manifest.jsonl`: directed relation, source-family, mechanism, repair-template, and split grouping.
- `metrics.json`, `verification.json`, `run-manifest.json`: release and independent verification summaries.

## Verification

From `benchmarks/cross-repo-pr-impact`:

```bash
python verify_formal_e2_release.py results/formal-e2-50-release-2026-08-26
python -m unittest
```

The verifier must reject this directory with `real_target_task_e2_count: 0`. A zero-blocker result would be a verifier defect.

## Claim boundary

This package supports only candidate triage and pipeline development. It does not support formal E2 scoring or system comparison.

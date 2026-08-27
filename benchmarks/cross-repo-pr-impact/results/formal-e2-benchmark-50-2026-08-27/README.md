# Marshal candidate-bounded strict-E2 benchmark

This release contains 50 verifier-clean strict-E2 directed relations. Every case includes a label-independent reusable candidate catalog, a source-opening cutoff snapshot, a network-off blind prediction, and a real target command replayed as A0=0, A1!=0, A2=0 with an exclusive failure signature and an exact maintainer A2 patch.

The grouped split contains 30 development, 10 evaluation, and 10 holdout cases. Directed relation, source change family, normalized mechanism, and normalized repair template do not cross splits. Non-target candidates are unjudged, so precision, F1, false-positive rate, and specificity are not reported.

## Package contents and release carving

This directory bundles the frozen dataset with artifacts of the first frozen system run (v4). `predictions.jsonl`, the `scores` block in `metrics.json`, `case-reports.jsonl`, `cases/*/blind/`, `cases/*/prediction-for-score.jsonl`, `cases/*/score.json`, and `cases/*/case-report.json` are run outputs, not dataset material. When redistributing the benchmark to a third party before their run, ship only:

- top-level `final-index.jsonl` is itself label material and must also be withheld until scoring; organizers need `inputs.jsonl`, `candidate-repositories.json`, `repository-snapshots.jsonl`, and `cases/*/public/`;
- withhold `expected-locations.json` (scoring key), `cases/*/private/`, and every run-output file listed above until the third party's predictions are frozen and timestamped.

The authoritative frozen-run record lives in `../formal-e2-benchmark-50-system-run-v4-2026-08-27/`. See `ACCEPTANCE.md` for acceptance boundaries, the literal-normalization scope of the leak check, and the verifier-independence caveat.

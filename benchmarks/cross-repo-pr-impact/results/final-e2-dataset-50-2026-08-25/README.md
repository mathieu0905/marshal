# Final strict-E2 development dataset: 50 cases

This directory is the authoritative local entry point for the 50 execution-verified strict-E2 cases. Every admitted case has the direction A0 pass, A1 fail after only the source change, and A2 pass after the precise target repair. E1 records are not counted, and A3 is not an admission requirement.

The set contains 46 normalized cases from existing three-arm execution assets and four newly replayed cases: Jackson YAML to SchemaCrawler, nv-i18n to jbanking, ASM to Byte Buddy, and Micrometer to RabbitMQ perf-test. The four new replay directories contain A0/A1/A2 command logs and the observed exit pattern `0/1/0`.

Authoritative files:

- `final-index.jsonl`: exactly 50 admitted E2 cases.
- `evidence-audit.jsonl`: per-case evidence audit results.
- `candidate-inventory.jsonl`: 50 admitted rows plus the retained Terser/Preconstruct rejection.
- `group-manifest.jsonl`: source-change-family grouping.
- `split-proposal.jsonl`: 30 development, 10 evaluation-proposal, and 10 holdout-proposal rows.
- `metrics.json` and `run-manifest.json`: machine-readable verification summary.
- `new-replays/`: raw logs and summaries for the four gap-closing runs.

Run `python3 benchmarks/cross-repo-pr-impact/verify_final_e2_dataset.py` from the repository root to rebuild the manifests. The validator parses target-specific JSON fields and TSV rows for all 50 cases, derives each A0/A1/A2 direction, and separately checks the four new replay signatures. The exact acceptance wording and result-channel policy are in `ACCEPTANCE.md`.

## Claim boundary

This is an exactly 50-case strict-E2 execution dataset for development and diagnosis. It is not yet a formal no-leak benchmark release: the proposed split keeps source-change families together, but candidate-catalog provenance and the broader mechanism/fix-template leakage audit remain separate release work. The proposed evaluation and holdout rows are not blind because the index exposes labels, mechanisms, and repair metadata. The main set has incomplete negative judgments, so no precision, F1, false-positive rate, or specificity is reported.

Two Crater cases use exact, successfully replayed external-contributor fixes that were unmerged at the observation time. They establish repair efficacy, not maintainer adoption. The Backbone case jointly repairs two target repositories and counts as one causal relation, so the 50 cases contain 51 target-repository occurrences.

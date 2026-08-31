# Command-scoped restraint set

This release contains ten E3 cases in three fully executed bounded project packs. Every E3 case has three fixed-target A0/A1 repetitions with both arms passing, source-version evidence, an executed consumer surface, and an explicit claim ceiling.

Run:

```bash
python3 benchmarks/cross-repo-pr-impact/verify_restraint_e3_set.py \
  benchmarks/cross-repo-pr-impact/results/restraint-e3-10-v1-2026-08-31
```

Precision and specificity are supported only inside these three complete project packs and only for evidence-backed final verdicts. These labels do not turn the unjudged non-target candidates in the 50-case E2 main set into negatives.

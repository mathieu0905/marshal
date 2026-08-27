# results/ index

Navigation for this directory. Only the entries below are part of a released chain; everything else is construction-period working material kept locally and not committed.

## Authoritative (committed)

- `formal-e2-benchmark-50-2026-08-27/` — the formal candidate-bounded strict-E2 benchmark (50 cases, split 30/10/10). Content anchor: commit `ff97315`. Acceptance: `ACCEPTANCE.md` inside. Release carving: `README.md` inside.
- `formal-e2-benchmark-50-system-run-v4-2026-08-27/` — the authoritative frozen system run (all 50 blind containers, network none, unified label-read boundary). First-run scores: development MRR 0.1056, evaluation 0.2833, holdout 0.125; runnable-check rate 0.
- `final-e2-dataset-50-2026-08-25/` — the earlier 50-case development/diagnostic set (commit `f6bcb0c`). Later audit found 37 outcome-conditioned catalogs and 34 cases failing the opening-cutoff check; it stays development/history material and is superseded by the formal set above.

## Historical (committed, read with care)

- `formal-e2-50-release-2026-08-26/` — **withdrawn**. Its 0/1/0 evidence came from post-hoc reference-surface checks, not pre-existing target tasks; see `CURRENT_CHECKPOINT.md` and the formal set's `ACCEPTANCE.md`.
- `formal-e2-benchmark-50-system-run{,-v2,-v3}-2026-08-27/` — ramp-up reruns (1/2/7 cases) proving v4 is the same system at full scale, not a fourth tuned version.

## Uncommitted construction-period material (local only)

Roughly 440 directories from 2026-08-25..27 screening and construction waves:

- `formal-e2-strict-{wave4,reverse-wave1b}-*-contract-triage-*` — contract triage waves whose `target-patches/` hold the provenance originals of every accepted A2 patch (content-identical copies live inside the benchmark package at `cases/*/evidence/*/target.patch`);
- `formal-e2-high-confidence-*-target-patches-*`, `formal-e2-*-reconstruction-*` — per-relation reconstruction and patch provenance;
- `single-case-pipeline-*` — per-case pipeline working directories (replays, tox/Maven environments, snapshots);
- assorted `*-screening-*`, `*-fse-*`, and E1 catalog/data-ready directories.

These are regenerable working output or provenance duplicates; they are the disk-footprint heavy part of this directory and are deliberately outside Git.

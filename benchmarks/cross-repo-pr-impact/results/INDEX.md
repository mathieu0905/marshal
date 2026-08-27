# results/ index

Navigation for this directory. Every entry here is committed; construction-period working material was archived off-repo (see the last section).

## Authoritative (committed)

- `formal-e2-benchmark-50-2026-08-27/` — the formal candidate-bounded strict-E2 benchmark (50 cases, split 30/10/10). Content anchor: commit `ff97315`. Acceptance: `ACCEPTANCE.md` inside. Release carving: `README.md` inside.
- `formal-e2-benchmark-50-system-run-v4-2026-08-27/` — the authoritative frozen system run (all 50 blind containers, network none, unified label-read boundary). First-run scores: development MRR 0.1056, evaluation 0.2833, holdout 0.125; runnable-check rate 0.
- `final-e2-dataset-50-2026-08-25/` — the earlier 50-case development/diagnostic set (commit `f6bcb0c`). Later audit found 37 outcome-conditioned catalogs and 34 cases failing the opening-cutoff check; it stays development/history material and is superseded by the formal set above.

## Historical (committed, read with care)

- `formal-e2-50-release-2026-08-26/` — **withdrawn**. Its 0/1/0 evidence came from post-hoc reference-surface checks, not pre-existing target tasks; see `CURRENT_CHECKPOINT.md` and the formal set's `ACCEPTANCE.md`.
- `formal-e2-benchmark-50-system-run{,-v2,-v3}-2026-08-27/` — ramp-up reruns (1/2/7 cases) proving v4 is the same system at full scale, not a fourth tuned version.

## Construction-period material (archived off-repo)

The 448 untracked screening/construction entries (~115 GB) that previously lived here were moved out of the repository on 2026-08-27 to `/home/zhihao/hdd/marshal-results-archive/` (same-disk `mv`, zero data loss). They comprised the `formal-e2-strict-*-contract-triage-*` waves (whose `target-patches/` hold the provenance originals of every accepted A2 patch), `formal-e2-high-confidence-*` / `formal-e2-*-reconstruction-*` patch provenance, `single-case-pipeline-*` working directories (replays, tox/Maven environments, snapshots), and assorted `*-screening-*` / `*-fse-*` / E1 catalog directories.

This is safe for the benchmark package because all 50 external patch references are content-identical to the in-package copies at `cases/*/evidence/*/target.patch` (verified 50/50 by byte comparison before the move). The archive is regenerable working output and provenance duplicates, not release material; see its `README.md`. Everything else in this directory is committed.

The formal chain (both benchmark directories above, plus the ramp-up runs, withdrawn history, dev set, skill, and governing docs) is also mirrored to the private repository `mathieu0905/cross-repo-breakage-benchmark` on GitHub (extracted 2026-08-27, single commit `a1db7b4`, both acceptance verifiers re-run green in that layout). This directory remains the source of truth.

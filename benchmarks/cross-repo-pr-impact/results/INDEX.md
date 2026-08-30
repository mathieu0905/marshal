# results/ index

Navigation for released benchmark chains. The entries listed below are committed; local
construction output may coexist in `results/` but is not part of a release unless it is
listed here.

## Authoritative (committed)

- `formal-e2-benchmark-50-v2-2026-08-30/` — the current formal candidate-bounded strict-E2 benchmark: 50 verifier-clean cases, 15 isolated groups, split 30/10/10, and zero cross-split leakage on the four declared grouping axes. Content anchor: marshal commit `7ebe4624`. Acceptance and distribution boundaries: `ACCEPTANCE.md` inside.
- `formal-e2-benchmark-50-system-run-v3-2026-08-30/` — the matching frozen system run. All 50 blind containers completed with network disabled and no label mount or inference-time label read; the unified-boundary verifier recomputed all 50 scores. MRR is 0.0722 development, 0.2333 evaluation, and 0.25 holdout; runnable-check rate is 0.
- `final-e2-dataset-50-2026-08-25/` — the earlier 50-case development/diagnostic set (commit `f6bcb0c`). Later audit found 37 outcome-conditioned catalogs and 34 cases failing the opening-cutoff check; it stays development/history material and is superseded by the formal set above.

## Historical (committed, read with care)

- `formal-e2-benchmark-50-2026-08-27/` and `formal-e2-benchmark-50-system-run-v4-2026-08-27/` — the first formal chain. It remains valid historical evidence but is superseded by the 2026-08-30 release, which reran the current single-case verifier across all selected cases and then performed a fresh 50-container frozen run.
- `formal-e2-50-release-2026-08-26/` — **withdrawn**. Its 0/1/0 evidence came from post-hoc reference-surface checks, not pre-existing target tasks; see `CURRENT_CHECKPOINT.md` and the formal set's `ACCEPTANCE.md`.
- `formal-e2-benchmark-50-system-run{,-v2,-v3}-2026-08-27/` — ramp-up reruns (1/2/7 cases) proving v4 is the same system at full scale, not a fourth tuned version.

## Construction-period material (archived off-repo)

The 448 untracked screening/construction entries (~115 GB) that previously lived here were moved out of the repository on 2026-08-27 to `/home/zhihao/hdd/marshal-results-archive/` (same-disk `mv`, zero data loss). They comprised the `formal-e2-strict-*-contract-triage-*` waves (whose `target-patches/` hold the provenance originals of every accepted A2 patch), `formal-e2-high-confidence-*` / `formal-e2-*-reconstruction-*` patch provenance, `single-case-pipeline-*` working directories (replays, tox/Maven environments, snapshots), and assorted `*-screening-*` / `*-fse-*` / E1 catalog directories.

This is safe for the 2026-08-27 benchmark package because all 50 external patch references are content-identical to the in-package copies at `cases/*/evidence/*/target.patch` (verified 50/50 by byte comparison before the move). The archive is regenerable working output and provenance duplicates, not release material; see its `README.md`.

The dedicated private dataset repository is `mathieu0905/cross-repo-breakage-benchmark` on GitHub. The 2026-08-30 release, frozen run, skill, and governing documents were synchronized to its `main` branch at commit `75875e4`; both acceptance verifiers and the 50-test skill suite passed in that extracted layout before push. This marshal directory remains the construction source of truth, while the private repository is the distribution copy.

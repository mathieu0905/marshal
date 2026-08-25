# Four gap-closing strict E2 replays

These four cases were replayed on 2026-08-25 with OpenJDK 11 and Maven 3.9.8. Every directory contains the command output for A0, A1, and A2 plus `run-results.tsv`. The observed exit pattern is `0, 1, 0`; each A1 log contains the historical failure signature recorded in its `summary.json`.

The ASM and Micrometer inputs each originated as several component-level FSE records. They are each counted once because the records share one target repository, one aggregate dependency update, one failing test, and one target repair.

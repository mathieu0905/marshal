# Four gap-closing strict E2 replays

These four cases were replayed on 2026-08-25 with OpenJDK 11 and Maven 3.9.8. Every directory contains the command output for A0, A1, and A2 plus `run-results.tsv`. The observed exit pattern is `0, 1, 0`; each A1 log contains the historical failure signature recorded in its `summary.json`.

The bytebuddy and rabbitmq-perf commands run Maven in quiet mode (`mvn -q`, see `summary.json`). A quiet build that succeeds prints nothing, so their `a0.log` and `a2.log` are empty by construction; the success evidence for those arms is the exit code 0 recorded in `run-results.tsv`, which the dataset validator asserts. The jbanking and schemacrawler runners do print output on success, so their logs are non-empty in every arm.

The ASM and Micrometer inputs each originated as several component-level FSE records. They are each counted once because the records share one target repository, one aggregate dependency update, one failing test, and one target repair.

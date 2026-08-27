# WITHDRAWN acceptance record

`formal-e2-50-release-2026-08-26` is not accepted as a formal benchmark.

| Requirement | Observed |
|---|---:|
| Formal cases with a real target build/test task | 0 |
| Unique source-family/target relations | 50 |
| A0/A1/A2 machine direction | 50 × pass/fail/pass |
| Bundled opening code diffs | 50 |
| Opening-time candidate snapshot records | 50 |
| Blind native Marshal predictions | 50 |
| Candidate catalogs | 2 reusable, label-independent catalogs |
| Split | 30 development / 10 evaluation / 10 holdout |
| Source-family split leaks | 0 |
| Required verifier outcome | rejected |
| Unit tests | 114 passed |

The native Marshal configured-contract run produced no candidate targets and did not read candidate code. Its old zero score is diagnostic only and must not be reported as a formal benchmark result.

The 50 exit-code triples came from dataset-authored post-hoc reference checks. They are candidate evidence, not strict-E2 target-task validation.

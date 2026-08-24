# H2 VALUE -> Minimal-J replay

## Verdict

The strict three-arm replay holds on the same target test contract:

| Arm | H2 input | Minimal-J input | Result |
| --- | --- | --- | --- |
| A0 | `1b9ddc11be1d603a3fd98b2f0440fb2537376c2e` | `1e432bda7cdf89eba0136c8f5b641a5ac5e956f9` | PASS, 7/7 |
| A1 | `4c40a20aece767dde1ef8a41c5a7c764bc1d20a8` | `1e432bda7cdf89eba0136c8f5b641a5ac5e956f9` | FAIL, 7/7 unique test methods error; 14 XML error records including teardown failures |
| A2 | same A1 H2 artifact | `9bebccf5d20f7a96c8d7393f4b544b97480f7401` | PASS, 7/7 |

## Contract and failure

All formal arms used Java 11, the same Maven repository, offline dependency
resolution, and these native test classes:

- `org.minimalj.model.backend.TransactionTest`
- `org.minimalj.repository.sql.relation.SqlCrudTest`

A1 fails while creating tables with unquoted `value` columns, for example:

```sql
CREATE TABLE TestEntityA (
 id CHAR(36) NOT NULL,
 value INTEGER DEFAULT NULL,
 PRIMARY KEY (id)
)
```

H2 commit `4c40a20a` promotes `VALUE` to a parser keyword. The historical
Minimal-J fix changes only
`src/main/resources/org/minimalj/util/reservedSqlWords.txt` and adds the H2
keyword list, including `VALUE`; with that fix, the same tests pass under the
unchanged A1 H2 artifact.

Surefire did not rerun the tests. The Maven summary reports 7 unique failed
methods, while the two XML suites contain 14 error records because each method
records both its primary error and its `@After` cleanup error. Every method has
the unquoted `value` `42001` signature in its records; the second records are
cascading cleanup or global-state errors after table creation fails.

## Build protocol

The two H2 source trees were built concurrently with separate Maven caches.
`maven.test.skip=true` was required because the historical H2 test-tools tree
uses the removed legacy Doclet API; the produced main JAR is the only source
artifact consumed by the target replay. Each JAR was placed at the target's
declared `com.h2database:h2:2.1.210` coordinate without changing the target
POM. A0 was repeated offline after the shared cache was warm and passed again.
All three final target runs set `TMPDIR` and `java.io.tmpdir` to
`/home/zhihao/hdd/marshal/.work/fse-h2-2.0.202/tmp/`; no writable replay path
was placed in `/tmp` or directly under `/home/zhihao/`.

## A3 decision

No A3 is claimed. The immediately preceding H2 transition changes only an H2
test script, so it does not provide an independent production compatibility
change. The immediate successor starts from the already-breaking A1 state and
therefore cannot form a compatible before/after pair on the fixed target
baseline. Reusing A0 as A3 would duplicate an arm rather than add negative
space.

## Evidence boundary

This replay proves the parser-keyword impact surface exercised by generated
SQL identifiers. H2 commit `4c40a20a` changes 51 files and also adds domain
value expression behavior; the selected Minimal-J tests do not establish
coverage of those other source-change surfaces.

Primary artifacts in this result directory are the three `minimal-j-A*.log`
files, their six Surefire XML reports, the arm exit files, and the preserved
source and maintainer patches in `workstreams/h2-2.0-fse/`.

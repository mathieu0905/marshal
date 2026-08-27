#!/usr/bin/env python3
"""Materialize schema-v1 inputs for E2 cases with audited catalogs."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
SOURCE_INPUTS = {
    "e2-020": {
        "host": "github.com",
        "repository": "assertj/assertj-core",
        "pull_request_number": None,
        "source_change_kind": "direct_commit_released_later",
        "subject": "Use JUnit ComparisonFailure when available",
        "base_commit": "505d2c4dc86698c44aabafaddffb6b64b296b616",
        "candidate_commit": "66e784987234e9c649e043f631ef984036ee9b30",
        "changed_paths": [
            "src/main/java/org/assertj/core/api/AbstractAssert.java",
            "src/main/java/org/assertj/core/error/AssertionErrorCreator.java",
            "src/main/java/org/assertj/core/internal/Failures.java",
            "src/test/java/org/assertj/core/error/AssertionErrorCreator_assertionError_Test.java"
        ],
        "patch_url": "https://github.com/assertj/assertj-core/compare/505d2c4dc86698c44aabafaddffb6b64b296b616...66e784987234e9c649e043f631ef984036ee9b30.diff"
    },
    "e2-040": {
        "host": "github.com",
        "repository": "apache/derby",
        "pull_request_number": None,
        "source_change_kind": "direct_commit_released_later",
        "subject": "Move org.apache.derby.jdbc into derbytools.jar",
        "base_commit": "8f3b7b2fa2f3e775dc90fb3cfa9f46257ae8df0e",
        "candidate_commit": "5a6efccce73b05ac7a27512563868192303f564d",
        "changed_paths": [
            "build.xml",
            "java/build/org/apache/derbyBuild/lastgoodjarcontents/insane.derby.jar.lastcontents",
            "java/build/org/apache/derbyBuild/lastgoodjarcontents/insane.derbytools.jar.lastcontents",
            "java/build/org/apache/derbyBuild/lastgoodjarcontents/sane.derby.jar.lastcontents",
            "java/build/org/apache/derbyBuild/lastgoodjarcontents/sane.derbytools.jar.lastcontents"
        ],
        "patch_url": "https://github.com/apache/derby/compare/8f3b7b2fa2f3e775dc90fb3cfa9f46257ae8df0e...5a6efccce73b05ac7a27512563868192303f564d.diff"
    },
    "e2-009": {
        "host": "github.com",
        "repository": "terser/terser",
        "pull_request_number": 433,
        "subject": "Add wrap_func_args and make it work with wrap_iife",
        "base_commit": "ce57d63f19edf658bafaa6cdd7d32041a6a601d8",
        "candidate_commit": "b3c6765b958157d0452ddd2099981ac55d14c2ce",
        "changed_paths": ["README.md", "lib/output.js", "test/compress/issue-427.js"],
        "patch_url": "https://github.com/terser/terser/compare/ce57d63f19edf658bafaa6cdd7d32041a6a601d8...b3c6765b958157d0452ddd2099981ac55d14c2ce.diff"
    },
    "e2-010": {
        "host": "github.com",
        "repository": "terser/terser",
        "pull_request_number": 433,
        "subject": "Add wrap_func_args and make it work with wrap_iife",
        "base_commit": "ce57d63f19edf658bafaa6cdd7d32041a6a601d8",
        "candidate_commit": "b3c6765b958157d0452ddd2099981ac55d14c2ce",
        "changed_paths": ["README.md", "lib/output.js", "test/compress/issue-427.js"],
        "patch_url": "https://github.com/terser/terser/compare/ce57d63f19edf658bafaa6cdd7d32041a6a601d8...b3c6765b958157d0452ddd2099981ac55d14c2ce.diff"
    },
    "e2-011": {
        "host": "github.com",
        "repository": "snakeyaml/snakeyaml",
        "pull_request_number": None,
        "source_change_kind": "direct_commit_released_later",
        "subject": "Require LoaderOptions when constructing typed YAML constructors",
        "base_commit": "3f05838828b8df36ab961bf836f373b8c20cb8ff",
        "candidate_commit": "68d199a0ef93fbc02639f891d06ea994b6134a0e",
        "changed_paths": [
            "src/main/java/org/yaml/snakeyaml/LoaderOptions.java",
            "src/main/java/org/yaml/snakeyaml/Yaml.java",
            "src/main/java/org/yaml/snakeyaml/constructor/BaseConstructor.java",
            "src/main/java/org/yaml/snakeyaml/constructor/Constructor.java"
        ],
        "patch_url": "https://github.com/snakeyaml/snakeyaml/compare/3f05838828b8df36ab961bf836f373b8c20cb8ff...68d199a0ef93fbc02639f891d06ea994b6134a0e.diff"
    },
    "e2-012": {
        "host": "github.com",
        "repository": "snakeyaml/snakeyaml",
        "pull_request_number": None,
        "source_change_kind": "direct_commit_released_later",
        "subject": "Require LoaderOptions for SafeConstructor",
        "base_commit": "4e12180fe938e60340199e91b5a6d002b260764e",
        "candidate_commit": "bece92a6094fea702ab94c1dce2dadfd764ae32b",
        "changed_paths": [
            "src/main/java/org/yaml/snakeyaml/constructor/SafeConstructor.java"
        ],
        "patch_url": "https://github.com/snakeyaml/snakeyaml/compare/4e12180fe938e60340199e91b5a6d002b260764e...bece92a6094fea702ab94c1dce2dadfd764ae32b.diff"
    },
    "e2-013": {
        "host": "github.com",
        "repository": "codehaus-plexus/plexus-utils",
        "pull_request_number": None,
        "source_change_kind": "direct_commit_released_later",
        "subject": "Remove the XML package from plexus-utils 4",
        "base_commit": "c99355e295957b3b2ecb81bc2e80feceea2cdbde",
        "candidate_commit": "8bf874bb9563116bd6ecd4e697c59fd0662d0a2f",
        "changed_paths": [
            "pom.xml",
            "src/main/java/org/codehaus/plexus/util/xml/Xpp3Dom.java",
            "src/main/java/org/codehaus/plexus/util/xml/pull/XmlPullParserException.java"
        ],
        "patch_url": "https://github.com/codehaus-plexus/plexus-utils/compare/c99355e295957b3b2ecb81bc2e80feceea2cdbde...8bf874bb9563116bd6ecd4e697c59fd0662d0a2f.diff"
    },
    "e2-014": {
        "host": "github.com",
        "repository": "codehaus-plexus/plexus-utils",
        "pull_request_number": None,
        "source_change_kind": "direct_commit_released_later",
        "subject": "Remove the XML package from plexus-utils 4",
        "base_commit": "c99355e295957b3b2ecb81bc2e80feceea2cdbde",
        "candidate_commit": "8bf874bb9563116bd6ecd4e697c59fd0662d0a2f",
        "changed_paths": [
            "pom.xml",
            "src/main/java/org/codehaus/plexus/util/xml/Xpp3Dom.java",
            "src/main/java/org/codehaus/plexus/util/xml/pull/XmlPullParserException.java"
        ],
        "patch_url": "https://github.com/codehaus-plexus/plexus-utils/compare/c99355e295957b3b2ecb81bc2e80feceea2cdbde...8bf874bb9563116bd6ecd4e697c59fd0662d0a2f.diff"
    },
    "e2-016": {
        "host": "github.com",
        "repository": "FasterXML/jackson-databind",
        "pull_request_number": None,
        "subject": "Cache Object.class bean descriptions in BasicClassIntrospector",
        "base_commit": "a8d8ec0e92b6220381a8eae38d4bf8765c7c9ca1",
        "candidate_commit": "2897aa00e04e3a28aef45f5b485001db161e2e2c",
        "changed_paths": [
            "src/main/java/com/fasterxml/jackson/databind/introspect/BasicClassIntrospector.java"
        ],
        "patch_url": "https://github.com/FasterXML/jackson-databind/compare/a8d8ec0e92b6220381a8eae38d4bf8765c7c9ca1...2897aa00e04e3a28aef45f5b485001db161e2e2c.diff"
    },
    "e2-001": {
        "host": "review.opendev.org",
        "repository": "openstack/requirements",
        "pull_request_number": 1001023,
        "subject": "Bump alembic to latest version",
        "base_commit": "b8de3b00af9dd2ffc1a85bf836cf3c7ee9e8bac7",
        "candidate_commit": "978799539e019141d8b0710d09bf91c956976079",
        "changed_paths": ["upper-constraints.txt"],
        "patch_url": "https://review.opendev.org/changes/1001023/revisions/1/patch",
    },
    "e2-006": {
        "host": "review.opendev.org",
        "repository": "openstack/ironic-python-agent",
        "pull_request_number": 1000668,
        "subject": "Maintain plugin requirements as optional dependencies",
        "base_commit": "ec807558924906ae902dfb14ce880e94b69402e1",
        "candidate_commit": "64c25a49ea0e7a9eba9a08d2c7f8fadba77af5f9",
        "changed_paths": ["plugin-requirements.txt", "pyproject.toml"],
        "patch_url": "https://review.opendev.org/changes/1000668/revisions/1/patch",
    },
    "e2-002": {
        "host": "github.com",
        "repository": "jcabi/jcabi-aspects",
        "pull_request_number": 336,
        "subject": "Integration commit for jcabi/jcabi-aspects#336 removes Tv",
        "base_commit": "b07543be3476c40557421799816607c4c0d81243",
        "candidate_commit": "38360cdf43af84d0531cd2aebc98360c0891cb25",
        "changed_paths": ["src/main/java/com/jcabi/aspects/Tv.java"],
        "patch_url": (
            "https://github.com/jcabi/jcabi-aspects/compare/"
            "b07543be3476c40557421799816607c4c0d81243..."
            "38360cdf43af84d0531cd2aebc98360c0891cb25.diff"
        ),
    },
    "e2-003": {
        "host": "github.com",
        "repository": "jcabi/jcabi-aspects",
        "pull_request_number": 336,
        "subject": "Integration commit for jcabi/jcabi-aspects#336 removes Tv",
        "base_commit": "b07543be3476c40557421799816607c4c0d81243",
        "candidate_commit": "38360cdf43af84d0531cd2aebc98360c0891cb25",
        "changed_paths": ["src/main/java/com/jcabi/aspects/Tv.java"],
        "patch_url": (
            "https://github.com/jcabi/jcabi-aspects/compare/"
            "b07543be3476c40557421799816607c4c0d81243..."
            "38360cdf43af84d0531cd2aebc98360c0891cb25.diff"
        ),
    },
    "e2-018": {
        "host": "github.com",
        "repository": "assertj/assertj-core",
        "pull_request_number": 2477,
        "subject": "Remove Byte Buddy shading",
        "base_commit": "27ef21c4ed3c97eb62129bc88160f56516753606",
        "candidate_commit": "463004be40302f0543e8c3ba5d73515d50527d10",
        "changed_paths": ["pom.xml", "verify.bndrun"],
        "patch_url": (
            "https://github.com/assertj/assertj-core/compare/"
            "27ef21c4ed3c97eb62129bc88160f56516753606..."
            "463004be40302f0543e8c3ba5d73515d50527d10.diff"
        ),
    },
    "e2-019": {
        "host": "github.com",
        "repository": "assertj/assertj-core",
        "pull_request_number": 2477,
        "subject": "Remove Byte Buddy shading",
        "base_commit": "27ef21c4ed3c97eb62129bc88160f56516753606",
        "candidate_commit": "463004be40302f0543e8c3ba5d73515d50527d10",
        "changed_paths": ["pom.xml", "verify.bndrun"],
        "patch_url": (
            "https://github.com/assertj/assertj-core/compare/"
            "27ef21c4ed3c97eb62129bc88160f56516753606..."
            "463004be40302f0543e8c3ba5d73515d50527d10.diff"
        ),
    },
    "e2-034": {
        "host": "github.com",
        "repository": "h2database/h2database",
        "pull_request_number": 2143,
        "subject": "Throw exception on usage of MVCC setting",
        "base_commit": "b10dd6d49dfb1b708ccb529883094b6977ec8985",
        "candidate_commit": "92692e63df10c3f73dd799f122949c705769e7b1",
        "changed_paths": [
            "h2/src/main/org/h2/command/Parser.java",
            "h2/src/main/org/h2/engine/ConnectionInfo.java"
        ],
        "patch_url": (
            "https://github.com/h2database/h2database/compare/"
            "b10dd6d49dfb1b708ccb529883094b6977ec8985..."
            "92692e63df10c3f73dd799f122949c705769e7b1.diff"
        ),
    },
    "e2-035": {
        "host": "github.com",
        "repository": "h2database/h2database",
        "pull_request_number": 2143,
        "subject": "Throw exception on usage of MVCC setting",
        "base_commit": "b10dd6d49dfb1b708ccb529883094b6977ec8985",
        "candidate_commit": "92692e63df10c3f73dd799f122949c705769e7b1",
        "changed_paths": [
            "h2/src/main/org/h2/command/Parser.java",
            "h2/src/main/org/h2/engine/ConnectionInfo.java"
        ],
        "patch_url": (
            "https://github.com/h2database/h2database/compare/"
            "b10dd6d49dfb1b708ccb529883094b6977ec8985..."
            "92692e63df10c3f73dd799f122949c705769e7b1.diff"
        ),
    },
    "e2-038": {
        "host": "github.com",
        "repository": "h2database/h2database",
        "pull_request_number": 2099,
        "subject": "Disallow comma before closing parenthesis",
        "base_commit": "0d01d5faf0a4de3d659f16bc2c4d853e5e79f69c",
        "candidate_commit": "3f24dad2b358b7f0a89cc24b5b3b6dc1d81c11b2",
        "changed_paths": [
            "h2/src/main/org/h2/command/Parser.java",
            "h2/src/test/org/h2/test/scripts/testSimple.sql"
        ],
        "patch_url": (
            "https://github.com/h2database/h2database/compare/"
            "0d01d5faf0a4de3d659f16bc2c4d853e5e79f69c..."
            "3f24dad2b358b7f0a89cc24b5b3b6dc1d81c11b2.diff"
        ),
    },
    "e2-036": {
        "host": "github.com",
        "repository": "h2database/h2database",
        "pull_request_number": 2297,
        "subject": "Add DomainValueExpression",
        "base_commit": "1b9ddc11be1d603a3fd98b2f0440fb2537376c2e",
        "candidate_commit": "4c40a20aece767dde1ef8a41c5a7c764bc1d20a8",
        "changed_paths": [
            "h2/src/docsrc/html/advanced.html",
            "h2/src/main/org/h2/command/Parser.java",
            "h2/src/main/org/h2/constraint/ConstraintDomain.java",
            "h2/src/main/org/h2/constraint/DomainColumnResolver.java",
            "h2/src/main/org/h2/engine/SessionRemote.java",
            "h2/src/main/org/h2/expression/DomainValueExpression.java",
            "h2/src/main/org/h2/expression/ExpressionColumn.java",
            "h2/src/main/org/h2/fulltext/FullText.java",
            "h2/src/main/org/h2/jdbc/JdbcConnection.java",
            "h2/src/main/org/h2/jdbc/JdbcDatabaseMetaData.java",
            "h2/src/main/org/h2/util/ParserUtil.java",
            "h2/src/test/org/h2/samples/optimizations.sql",
            "h2/src/test/org/h2/test/TestBase.java",
            "h2/src/test/org/h2/test/db/TestBigResult.java",
            "h2/src/test/org/h2/test/db/TestCases.java",
            "h2/src/test/org/h2/test/db/TestCluster.java",
            "h2/src/test/org/h2/test/db/TestExclusive.java",
            "h2/src/test/org/h2/test/db/TestFunctions.java",
            "h2/src/test/org/h2/test/db/TestIndex.java",
            "h2/src/test/org/h2/test/db/TestLob.java",
            "h2/src/test/org/h2/test/db/TestOptimizations.java",
            "h2/src/test/org/h2/test/db/TestRunscript.java",
            "h2/src/test/org/h2/test/db/TestSpatial.java",
            "h2/src/test/org/h2/test/db/TestTransaction.java",
            "h2/src/test/org/h2/test/db/TestViewDropView.java",
            "h2/src/test/org/h2/test/jdbc/TestCancel.java",
            "h2/src/test/org/h2/test/jdbc/TestGetGeneratedKeys.java",
            "h2/src/test/org/h2/test/jdbc/TestPreparedStatement.java",
            "h2/src/test/org/h2/test/jdbc/TestResultSet.java",
            "h2/src/test/org/h2/test/jdbc/TestStatement.java",
            "h2/src/test/org/h2/test/jdbc/TestUpdatableResultSet.java",
            "h2/src/test/org/h2/test/jdbcx/TestXA.java",
            "h2/src/test/org/h2/test/mvcc/TestMvccMultiThreaded.java",
            "h2/src/test/org/h2/test/scripts/ddl/truncateTable.sql",
            "h2/src/test/org/h2/test/scripts/dml/insertIgnore.sql",
            "h2/src/test/org/h2/test/scripts/dml/mergeUsing.sql",
            "h2/src/test/org/h2/test/scripts/dml/select.sql",
            "h2/src/test/org/h2/test/scripts/dml/with.sql",
            "h2/src/test/org/h2/test/scripts/functions/aggregate/array-agg.sql",
            "h2/src/test/org/h2/test/scripts/functions/aggregate/percentile.sql",
            "h2/src/test/org/h2/test/scripts/functions/window/lead.sql",
            "h2/src/test/org/h2/test/scripts/functions/window/nth_value.sql",
            "h2/src/test/org/h2/test/scripts/functions/window/row_number.sql",
            "h2/src/test/org/h2/test/scripts/other/sequence.sql",
            "h2/src/test/org/h2/test/scripts/testScript.sql",
            "h2/src/test/org/h2/test/synth/TestConcurrentUpdate.java",
            "h2/src/test/org/h2/test/unit/TestCache.java",
            "h2/src/test/org/h2/test/unit/TestKeywords.java",
            "h2/src/test/org/h2/test/unit/TestPageStore.java",
            "h2/src/test/org/h2/test/unit/TestPgServer.java",
            "h2/src/test/org/h2/test/unit/TestRecovery.java"
        ],
        "patch_url": (
            "https://github.com/h2database/h2database/compare/"
            "1b9ddc11be1d603a3fd98b2f0440fb2537376c2e..."
            "4c40a20aece767dde1ef8a41c5a7c764bc1d20a8.diff"
        ),
    },
    "e2-037": {
        "host": "github.com",
        "repository": "h2database/h2database",
        "pull_request_number": 2297,
        "subject": "Add DomainValueExpression",
        "base_commit": "1b9ddc11be1d603a3fd98b2f0440fb2537376c2e",
        "candidate_commit": "4c40a20aece767dde1ef8a41c5a7c764bc1d20a8",
        "changed_paths": [
            "h2/src/main/org/h2/command/Parser.java",
            "h2/src/main/org/h2/expression/DomainValueExpression.java",
            "h2/src/main/org/h2/util/ParserUtil.java"
        ],
        "patch_url": (
            "https://github.com/h2database/h2database/compare/"
            "1b9ddc11be1d603a3fd98b2f0440fb2537376c2e..."
            "4c40a20aece767dde1ef8a41c5a7c764bc1d20a8.diff"
        ),
    },
    "e2-023": {
        "host": "github.com",
        "repository": "checkstyle/checkstyle",
        "pull_request_number": 12737,
        "subject": "FinalClassCheck should report private classes without constructor",
        "base_commit": "e15fcdb90f7ea7c689500bf655070669a78432f7",
        "candidate_commit": "e286af7405332a59b48189590f0b7d29ab925066",
        "changed_paths": [
            "src/main/java/com/puppycrawl/tools/checkstyle/checks/design/FinalClassCheck.java",
            "src/main/resources/com/puppycrawl/tools/checkstyle/meta/checks/design/FinalClassCheck.xml",
            "src/test/java/com/puppycrawl/tools/checkstyle/checks/design/FinalClassCheckTest.java",
            "src/test/java/com/puppycrawl/tools/checkstyle/utils/CommonUtilTest.java",
            "src/test/resources-noncompilable/com/puppycrawl/tools/checkstyle/checks/design/finalclass/InputFinalClassClassWithPrivateCtorWithNestedExtendingClass.java",
            "src/test/resources-noncompilable/com/puppycrawl/tools/checkstyle/checks/design/finalclass/InputFinalClassClassWithPrivateCtorWithNestedExtendingClassWithoutPackage.java",
            "src/test/resources-noncompilable/com/puppycrawl/tools/checkstyle/checks/design/finalclass/InputFinalClassNestedInRecord.java",
            "src/test/resources/com/puppycrawl/tools/checkstyle/checks/coding/onestatementperline/InputOneStatementPerLineBeginTreeTest.java",
            "src/test/resources/com/puppycrawl/tools/checkstyle/checks/coding/onestatementperline/InputOneStatementPerLineTest.java",
            "src/test/resources/com/puppycrawl/tools/checkstyle/checks/design/finalclass/InputFinalClassInnerAndNestedClass.java",
            "src/test/resources/com/puppycrawl/tools/checkstyle/checks/design/finalclass/InputFinalClassPrivateCtor.java",
            "src/test/resources/com/puppycrawl/tools/checkstyle/checks/design/finalclass/InputFinalClassPrivateCtor2.java",
            "src/test/resources/com/puppycrawl/tools/checkstyle/checks/design/finalclass/InputFinalClassPrivateCtor3.java",
            "src/xdocs/checks.xml",
            "src/xdocs/checks/design/finalclass.xml",
            "src/xdocs/checks/design/index.xml",
        ],
        "patch_url": (
            "https://github.com/checkstyle/checkstyle/compare/"
            "e15fcdb90f7ea7c689500bf655070669a78432f7..."
            "e286af7405332a59b48189590f0b7d29ab925066.diff"
        ),
    },
    "e2-025": {
        "host": "github.com",
        "repository": "mockito/mockito",
        "pull_request_number": 404,
        "subject": "Remove deprecated types and methods",
        "base_commit": "6d431e1115866b1947b637fe50ab630f247a1ab2",
        "candidate_commit": "e5788f86b44893b921dd68a77b3676f8682153d8",
        "changed_paths": [
            "src/main/java/org/mockito/Answers.java",
            "src/main/java/org/mockito/BDDMockito.java",
            "src/main/java/org/mockito/Mockito.java",
            "src/main/java/org/mockito/MockitoAnnotations.java",
            "src/main/java/org/mockito/internal/MockitoCore.java",
            "src/main/java/org/mockito/internal/configuration/DefaultAnnotationEngine.java",
            "src/main/java/org/mockito/internal/configuration/MockitoAnnotationsMockAnnotationProcessor.java",
            "src/main/java/org/mockito/internal/configuration/SpyAnnotationEngine.java",
            "src/main/java/org/mockito/internal/configuration/injection/scanner/InjectMocksScanner.java",
            "src/main/java/org/mockito/internal/configuration/injection/scanner/MockScanner.java",
            "src/main/java/org/mockito/internal/creation/bytebuddy/InterceptedInvocation.java",
            "src/main/java/org/mockito/internal/invocation/InvocationImpl.java",
            "src/main/java/org/mockito/internal/junit/JUnitRule.java",
            "src/main/java/org/mockito/internal/progress/IOngoingStubbing.java",
            "src/main/java/org/mockito/internal/progress/MockingProgress.java",
            "src/main/java/org/mockito/internal/progress/MockingProgressImpl.java",
            "src/main/java/org/mockito/internal/progress/ThreadSafeMockingProgress.java",
            "src/main/java/org/mockito/internal/stubbing/BaseStubbing.java",
            "src/main/java/org/mockito/internal/stubbing/ConsecutiveStubbing.java",
            "src/main/java/org/mockito/internal/stubbing/OngoingStubbingImpl.java",
            "src/main/java/org/mockito/internal/stubbing/defaultanswers/Answers.java",
            "src/main/java/org/mockito/invocation/InvocationOnMock.java",
            "src/main/java/org/mockito/junit/MockitoJUnit.java",
            "src/main/java/org/mockito/junit/MockitoJUnitRule.java",
            "src/main/java/org/mockito/stubbing/DeprecatedOngoingStubbing.java",
            "src/main/java/org/mockito/stubbing/OngoingStubbing.java",
            "src/main/java/org/mockito/verification/VerificationWithTimeout.java",
            "src/test/java/org/concurrentmockito/ThreadsStubSharedMockTest.java",
            "src/test/java/org/mockito/MockitoTest.java",
            "src/test/java/org/mockito/internal/InvalidStateDetectionTest.java",
            "src/test/java/org/mockito/internal/junit/JUnitRuleTest.java",
            "src/test/java/org/mockito/internal/verification/VerificationWithDescriptionTest.java",
            "src/test/java/org/mockitousage/annotation/AnnotationsTest.java",
            "src/test/java/org/mockitousage/annotation/DeprecatedMockAnnotationTest.java",
            "src/test/java/org/mockitousage/basicapi/UsingVarargsTest.java",
            "src/test/java/org/mockitousage/bugs/TimeoutWithAtMostOrNeverShouldBeDisabledTest.java",
            "src/test/java/org/mockitousage/junitrule/InvalidTargetMockitoJUnitRuleTest.java",
            "src/test/java/org/mockitousage/junitrule/RuleTestWithParameterConstructorTest.java",
            "src/test/java/org/mockitousage/matchers/VerificationAndStubbingUsingMatchersTest.java",
            "src/test/java/org/mockitousage/spies/SpyingOnRealObjectsTest.java",
            "src/test/java/org/mockitousage/stubbing/DeprecatedStubbingTest.java",
            "src/test/java/org/mockitousage/stubbing/StubbingConsecutiveAnswersTest.java",
            "src/test/java/org/mockitousage/stubbing/StubbingWithCustomAnswerTest.java",
            "src/test/java/org/mockitousage/stubbing/StubbingWithExtraAnswersTest.java",
            "src/test/java/org/mockitousage/stubbing/StubbingWithThrowablesTest.java",
            "src/test/java/org/mockitoutil/ExtraMatchers.java",
            "subprojects/testng/src/main/java/org/mockito/testng/MockitoAfterTestNGMethod.java"
        ],
        "patch_url": "https://github.com/mockito/mockito/compare/6d431e1115866b1947b637fe50ab630f247a1ab2...e5788f86b44893b921dd68a77b3676f8682153d8.diff"
    },
    "e2-026": {
        "host": "github.com",
        "repository": "mockito/mockito",
        "pull_request_number": 2418,
        "subject": "Remove all deprecated APIs for Mockito 4",
        "base_commit": "481639c96cbeeb16626ff2ecbfce772a4523b11b",
        "candidate_commit": "7ac03d9defe42f54dc1e705cc0253e9c9dd943bb",
        "changed_paths": [
            "settings.gradle.kts",
            "src/main/java/org/mockito/AdditionalMatchers.java",
            "src/main/java/org/mockito/Answers.java",
            "src/main/java/org/mockito/ArgumentMatcher.java",
            "src/main/java/org/mockito/ArgumentMatchers.java",
            "src/main/java/org/mockito/BDDMockito.java",
            "src/main/java/org/mockito/Matchers.java",
            "src/main/java/org/mockito/MockedStatic.java",
            "src/main/java/org/mockito/MockingDetails.java",
            "src/main/java/org/mockito/Mockito.java",
            "src/main/java/org/mockito/MockitoDebugger.java",
            "src/main/java/org/mockito/configuration/AnnotationEngine.java",
            "src/main/java/org/mockito/configuration/DefaultMockitoConfiguration.java",
            "src/main/java/org/mockito/configuration/IMockitoConfiguration.java",
            "src/main/java/org/mockito/exceptions/verification/TooFewActualInvocations.java",
            "src/main/java/org/mockito/exceptions/verification/TooLittleActualInvocations.java",
            "src/main/java/org/mockito/internal/InternalMockHandler.java",
            "src/main/java/org/mockito/internal/MockedStaticImpl.java",
            "src/main/java/org/mockito/internal/configuration/GlobalConfiguration.java",
            "src/main/java/org/mockito/internal/configuration/IndependentAnnotationEngine.java",
            "src/main/java/org/mockito/internal/configuration/InjectingAnnotationEngine.java",
            "src/main/java/org/mockito/internal/configuration/SpyAnnotationEngine.java",
            "src/main/java/org/mockito/internal/configuration/plugins/DefaultMockitoPlugins.java",
            "src/main/java/org/mockito/internal/configuration/plugins/PluginRegistry.java",
            "src/main/java/org/mockito/internal/creation/instance/InstantiationException.java",
            "src/main/java/org/mockito/internal/creation/instance/Instantiator.java",
            "src/main/java/org/mockito/internal/creation/instance/InstantiatorProvider2Adapter.java",
            "src/main/java/org/mockito/internal/creation/instance/InstantiatorProviderAdapter.java",
            "src/main/java/org/mockito/internal/debugging/MockitoDebuggerImpl.java",
            "src/main/java/org/mockito/internal/debugging/WarningsCollector.java",
            "src/main/java/org/mockito/internal/exceptions/Reporter.java",
            "src/main/java/org/mockito/internal/invocation/UnusedStubsFinder.java",
            "src/main/java/org/mockito/internal/junit/util/JUnitFailureHacker.java",
            "src/main/java/org/mockito/internal/verification/VerificationDataImpl.java",
            "src/main/java/org/mockito/internal/verification/api/VerificationData.java",
            "src/main/java/org/mockito/invocation/InvocationFactory.java",
            "src/main/java/org/mockito/plugins/InstantiatorProvider.java",
            "src/main/java/org/mockito/runners/ConsoleSpammingMockitoJUnitRunner.java",
            "src/main/java/org/mockito/runners/MockitoJUnitRunner.java",
            "src/main/java/org/mockito/runners/VerboseMockitoJUnitRunner.java",
            "src/main/java/org/mockito/runners/package-info.java",
            "src/main/java/org/mockito/stubbing/ValidableAnswer.java",
            "src/test/java/org/mockito/InvocationFactoryTest.java",
            "src/test/java/org/mockito/MockitoTest.java",
            "src/test/java/org/mockito/configuration/MockitoConfiguration.java",
            "src/test/java/org/mockito/internal/InvalidStateDetectionTest.java",
            "src/test/java/org/mockito/internal/configuration/GlobalConfigurationTest.java",
            "src/test/java/org/mockito/internal/configuration/plugins/DefaultMockitoPluginsTest.java",
            "src/test/java/org/mockito/internal/configuration/plugins/PluginFinderTest.java",
            "src/test/java/org/mockito/internal/handler/InvocationNotifierHandlerTest.java",
            "src/test/java/org/mockito/internal/handler/MockHandlerImplTest.java",
            "src/test/java/org/mockito/internal/invocation/MatcherApplicationStrategyTest.java",
            "src/test/java/org/mockito/internal/junit/util/JUnitFailureHackerTest.java",
            "src/test/java/org/mockito/internal/util/reflection/FieldInitializerTest.java",
            "src/test/java/org/mockito/internal/util/reflection/LenientCopyToolTest.java",
            "src/test/java/org/mockito/internal/util/reflection/ParameterizedConstructorInstantiatorTest.java",
            "src/test/java/org/mockito/runners/ConsoleSpammingMockitoJUnitRunnerTest.java",
            "src/test/java/org/mockitousage/PlaygroundWithDemoOfUnclonedParametersProblemTest.java",
            "src/test/java/org/mockitousage/annotation/DeprecatedAnnotationEngineApiTest.java",
            "src/test/java/org/mockitousage/basicapi/MocksSerializationForAnnotationTest.java",
            "src/test/java/org/mockitousage/basicapi/MocksSerializationTest.java",
            "src/test/java/org/mockitousage/basicapi/ResetTest.java",
            "src/test/java/org/mockitousage/basicapi/UsingVarargsTest.java",
            "src/test/java/org/mockitousage/bugs/ActualInvocationHasNullArgumentNPEBugTest.java",
            "src/test/java/org/mockitousage/bugs/ClassCastExOnVerifyZeroInteractionsTest.java",
            "src/test/java/org/mockitousage/bugs/CompareMatcherTest.java",
            "src/test/java/org/mockitousage/bugs/IOOBExceptionShouldNotBeThrownWhenNotCodingFluentlyTest.java",
            "src/test/java/org/mockitousage/bugs/NPEWithCertainMatchersTest.java",
            "src/test/java/org/mockitousage/bugs/varargs/VarargsAndAnyPicksUpExtraInvocationsTest.java",
            "src/test/java/org/mockitousage/bugs/varargs/VarargsNotPlayingWithAnyTest.java",
            "src/test/java/org/mockitousage/configuration/CustomizedAnnotationForSmartMockTest.java",
            "src/test/java/org/mockitousage/customization/BDDMockitoTest.java",
            "src/test/java/org/mockitousage/debugging/NewMockito.java",
            "src/test/java/org/mockitousage/debugging/StubbingLookupListenerCallbackTest.java",
            "src/test/java/org/mockitousage/examples/use/ExampleTest.java",
            "src/test/java/org/mockitousage/junitrunner/VerboseMockitoRunnerTest.java",
            "src/test/java/org/mockitousage/matchers/AnyXMatchersAcceptNullsTest.java",
            "src/test/java/org/mockitousage/matchers/CustomMatcherDoesYieldCCETest.java",
            "src/test/java/org/mockitousage/matchers/CustomMatchersTest.java",
            "src/test/java/org/mockitousage/matchers/GenericMatchersTest.java",
            "src/test/java/org/mockitousage/matchers/InvalidUseOfMatchersTest.java",
            "src/test/java/org/mockitousage/matchers/MatchersMixedWithRawArgumentsTest.java",
            "src/test/java/org/mockitousage/matchers/MatchersTest.java",
            "src/test/java/org/mockitousage/matchers/MoreMatchersTest.java",
            "src/test/java/org/mockitousage/matchers/NewMatchersTest.java",
            "src/test/java/org/mockitousage/matchers/ReflectionMatchersTest.java",
            "src/test/java/org/mockitousage/misuse/DescriptiveMessagesOnMisuseTest.java",
            "src/test/java/org/mockitousage/misuse/DetectingMisusedMatchersTest.java",
            "src/test/java/org/mockitousage/misuse/ExplicitFrameworkValidationTest.java",
            "src/test/java/org/mockitousage/misuse/InvalidUsageTest.java",
            "src/test/java/org/mockitousage/plugins/MockitoPluginsTest.java",
            "src/test/java/org/mockitousage/spies/StubbingSpiesDoesNotYieldNPETest.java",
            "src/test/java/org/mockitousage/stacktrace/ModellingDescriptiveMessagesTest.java",
            "src/test/java/org/mockitousage/stacktrace/StackTraceFilteringTest.java",
            "src/test/java/org/mockitousage/stubbing/BasicStubbingTest.java",
            "src/test/java/org/mockitousage/verification/BasicVerificationInOrderTest.java",
            "src/test/java/org/mockitousage/verification/CustomVerificationTest.java",
            "src/test/java/org/mockitousage/verification/DescriptiveMessagesWhenVerificationFailsTest.java",
            "src/test/java/org/mockitousage/verification/NoMoreInteractionsVerificationTest.java",
            "src/test/java/org/mockitousage/verification/OnlyVerificationTest.java",
            "src/test/java/org/mockitousage/verification/PrintingVerboseTypesWithArgumentsTest.java",
            "src/test/java/org/mockitousage/verification/VerificationOnMultipleMocksUsingMatchersTest.java",
            "src/test/java/org/mockitousage/verification/VerificationUsingMatchersTest.java",
            "subprojects/deprecatedPluginsTest/deprecatedPluginsTest.gradle",
            "subprojects/deprecatedPluginsTest/src/test/java/org/mockitousage/plugins/DeprecatedInstantiatorProviderTest.java",
            "subprojects/deprecatedPluginsTest/src/test/java/org/mockitousage/plugins/MyDeprecatedInstantiatorProvider.java",
            "subprojects/deprecatedPluginsTest/src/test/resources/mockito-extensions/org.mockito.plugins.InstantiatorProvider",
            "subprojects/extTest/src/test/java/org/mockitousage/plugins/instantiator/MyInstantiatorProvider.java",
            "subprojects/extTest/src/test/resources/mockito-extensions/org.mockito.plugins.InstantiatorProvider"
        ],
        "patch_url": "https://github.com/mockito/mockito/compare/481639c96cbeeb16626ff2ecbfce772a4523b11b...7ac03d9defe42f54dc1e705cc0253e9c9dd943bb.diff"
    },
    "e2-021": {
        "host": "github.com",
        "repository": "apache/commons-io",
        "pull_request_number": None,
        "source_change_kind": "direct_commit",
        "subject": "FileUtils rejects most illegal inputs with IllegalArgumentException",
        "base_commit": "09bda53aed9728ccb235fa7622e981e47cd943a0",
        "candidate_commit": "0cee29aa4c1818963ed1a55058219282e89d7488",
        "changed_paths": [
            "src/changes/changes.xml",
            "src/main/java/org/apache/commons/io/FileUtils.java",
            "src/test/java/org/apache/commons/io/FileUtilsCopyDirectoryToDirectoryTestCase.java",
            "src/test/java/org/apache/commons/io/FileUtilsTestCase.java"
        ],
        "patch_url": "https://github.com/apache/commons-io/compare/09bda53aed9728ccb235fa7622e981e47cd943a0...0cee29aa4c1818963ed1a55058219282e89d7488.diff"
    },
    "e2-022": {
        "host": "github.com",
        "repository": "apache/commons-io",
        "pull_request_number": None,
        "source_change_kind": "direct_commit",
        "subject": "Add builders and deprecate constructor permutations",
        "base_commit": "b51e41938ea794f67223c1414c9e6de8a04c17b5",
        "candidate_commit": "7ecca22f175c644da3096940a4ce899be5b33740",
        "changed_paths": [
            "src/changes/changes.xml",
            "src/main/java/org/apache/commons/io/build/AbstractOrigin.java",
            "src/main/java/org/apache/commons/io/build/AbstractOriginSupplier.java",
            "src/main/java/org/apache/commons/io/build/AbstractStreamBuilder.java",
            "src/main/java/org/apache/commons/io/build/AbstractSupplier.java",
            "src/main/java/org/apache/commons/io/build/package-info.java",
            "src/main/java/org/apache/commons/io/filefilter/WildcardFileFilter.java",
            "src/main/java/org/apache/commons/io/input/BOMInputStream.java",
            "src/main/java/org/apache/commons/io/input/BufferedFileChannelInputStream.java",
            "src/main/java/org/apache/commons/io/input/MemoryMappedFileInputStream.java",
            "src/main/java/org/apache/commons/io/input/MessageDigestCalculatingInputStream.java",
            "src/main/java/org/apache/commons/io/input/RandomAccessFileInputStream.java",
            "src/main/java/org/apache/commons/io/input/ReadAheadInputStream.java",
            "src/main/java/org/apache/commons/io/input/ReaderInputStream.java",
            "src/main/java/org/apache/commons/io/input/ReversedLinesFileReader.java",
            "src/main/java/org/apache/commons/io/input/Tailer.java",
            "src/main/java/org/apache/commons/io/input/XmlStreamReader.java",
            "src/main/java/org/apache/commons/io/output/DeferredFileOutputStream.java",
            "src/main/java/org/apache/commons/io/output/FileWriterWithEncoding.java",
            "src/main/java/org/apache/commons/io/output/LockableFileWriter.java",
            "src/main/java/org/apache/commons/io/output/WriterOutputStream.java",
            "src/main/java/org/apache/commons/io/output/XmlStreamWriter.java",
            "src/test/java/org/apache/commons/io/FileUtilsTest.java",
            "src/test/java/org/apache/commons/io/filefilter/WildcardFileFilterTest.java",
            "src/test/java/org/apache/commons/io/function/IOBaseStreamTest.java",
            "src/test/java/org/apache/commons/io/function/IOPredicateTest.java",
            "src/test/java/org/apache/commons/io/input/BOMInputStreamTest.java",
            "src/test/java/org/apache/commons/io/input/BufferedFileChannelInputStreamTest.java",
            "src/test/java/org/apache/commons/io/input/MemoryMappedFileInputStreamTest.java",
            "src/test/java/org/apache/commons/io/input/MessageDigestCalculatingInputStreamTest.java",
            "src/test/java/org/apache/commons/io/input/RandomAccessFileInputStreamTest.java",
            "src/test/java/org/apache/commons/io/input/ReadAheadInputStreamTest.java",
            "src/test/java/org/apache/commons/io/input/ReaderInputStreamTest.java",
            "src/test/java/org/apache/commons/io/input/ReversedLinesFileReaderTestParamBlockSize.java",
            "src/test/java/org/apache/commons/io/input/ReversedLinesFileReaderTestParamFile.java",
            "src/test/java/org/apache/commons/io/input/SequenceReaderTest.java",
            "src/test/java/org/apache/commons/io/input/TailerTest.java",
            "src/test/java/org/apache/commons/io/input/XmlStreamReaderTest.java",
            "src/test/java/org/apache/commons/io/output/DeferredFileOutputStreamTest.java",
            "src/test/java/org/apache/commons/io/output/FileWriterWithEncodingTest.java",
            "src/test/java/org/apache/commons/io/output/LockableFileWriterTest.java",
            "src/test/java/org/apache/commons/io/output/UncheckedFilterOutputStreamTest.java",
            "src/test/java/org/apache/commons/io/output/WriterOutputStreamTest.java",
            "src/test/java/org/apache/commons/io/output/XmlStreamWriterTest.java"
        ],
        "patch_url": "https://github.com/apache/commons-io/compare/b51e41938ea794f67223c1414c9e6de8a04c17b5...7ecca22f175c644da3096940a4ce899be5b33740.diff"
    },
    "e2-004": {
        "host": "github.com",
        "repository": "qos-ch/slf4j",
        "pull_request_number": None,
        "source_change_kind": "direct_commit_released_later",
        "subject": "Switch provider discovery from StaticLoggerBinder to ServiceLoader",
        "base_commit": "1232e8529f5844e03e4d528a88185413761853e2",
        "candidate_commit": "ed9b3712a03cb3e6617745616b9afb0a6c646a85",
        "changed_paths": [
            "integration/pom.xml",
            "jcl-over-slf4j/pom.xml",
            "jul-to-slf4j/pom.xml",
            "log4j-over-slf4j/pom.xml",
            "osgi-over-slf4j/pom.xml",
            "pom.xml",
            "slf4j-android/pom.xml",
            "slf4j-api/pom.xml",
            "slf4j-api/src/main/java/org/slf4j/LoggerFactory.java",
            "slf4j-api/src/main/java/org/slf4j/impl/StaticLoggerBinder.java",
            "slf4j-api/src/main/java/org/slf4j/spi/SLF4JServiceProvider.java",
            "slf4j-ext/pom.xml",
            "slf4j-jcl/pom.xml",
            "slf4j-jdk14/pom.xml",
            "slf4j-log4j12/pom.xml",
            "slf4j-migrator/pom.xml",
            "slf4j-nop/pom.xml",
            "slf4j-simple/pom.xml",
            "slf4j-site/pom.xml"
        ],
        "patch_url": "https://github.com/qos-ch/slf4j/compare/1232e8529f5844e03e4d528a88185413761853e2...ed9b3712a03cb3e6617745616b9afb0a6c646a85.diff"
    },
    "e2-042": {
        "host": "github.com",
        "repository": "FasterXML/jackson-core",
        "pull_request_number": None,
        "source_change_kind": "direct_commit_released_later",
        "subject": "Make writeXxxField convenience methods mock-interceptable",
        "base_commit": "faba99505a08a1d62590b571ecea18df4d002b27",
        "candidate_commit": "4ca96e5f7752102cc38d89e2c43eea021a79ada0",
        "changed_paths": [
            "src/main/java/com/fasterxml/jackson/core/JsonGenerator.java"
        ],
        "patch_url": "https://github.com/FasterXML/jackson-core/compare/faba99505a08a1d62590b571ecea18df4d002b27...4ca96e5f7752102cc38d89e2c43eea021a79ada0.diff"
    },
    "e2-047": {
        "host": "github.com",
        "repository": "FasterXML/jackson-dataformats-text",
        "pull_request_number": None,
        "source_change_kind": "direct_commit_released_later",
        "subject": "Sync YAMLFactory with jackson-core ContentReference API",
        "base_commit": "0d3f69bb24913e059f65d40bba4d8e3c83b0756e",
        "candidate_commit": "e5dc40f55321161c94b4d1088a030cf9de936497",
        "changed_paths": [
            "csv/src/main/java/com/fasterxml/jackson/dataformat/csv/CsvFactory.java",
            "properties/src/main/java/com/fasterxml/jackson/dataformat/javaprop/JavaPropsFactory.java",
            "yaml/src/main/java/com/fasterxml/jackson/dataformat/yaml/YAMLFactory.java"
        ],
        "patch_url": "https://github.com/FasterXML/jackson-dataformats-text/compare/0d3f69bb24913e059f65d40bba4d8e3c83b0756e...e5dc40f55321161c94b4d1088a030cf9de936497.diff"
    },
}

SOURCE_INPUTS.update({
    "e2-039": {
        "host": "github.com",
        "repository": "apache/logging-log4j2",
        "pull_request_number": None,
        "source_change_kind": "direct_commit_released_later",
        "subject": "Reuse shared empty-array constants across Log4j API and Core",
        "base_commit": "edbba3e6a7f2ed37afb0674653ace4bb7d5231ae",
        "candidate_commit": "97ec707d69280ef57aed8fd5831dc4f3a75f7715",
        "changed_paths": [
            "log4j-api/src/main/java/org/apache/logging/log4j/util/Constants.java",
            "log4j-core/src/main/java/org/apache/logging/log4j/core/config/ConfigurationSource.java",
        ],
        "patch_url": (
            "https://github.com/apache/logging-log4j2/compare/"
            "edbba3e6a7f2ed37afb0674653ace4bb7d5231ae..."
            "97ec707d69280ef57aed8fd5831dc4f3a75f7715.diff"
        ),
    },
    "e2-041": {
        "host": "github.com",
        "repository": "swagger-api/swagger-core",
        "pull_request_number": 3975,
        "subject": "Track explicitly set examples in Swagger model objects",
        "base_commit": "567bb88c9a789dde79d08df166957bfa9a25a3b5",
        "candidate_commit": "f95621890a7a7160489539336020346c2299d206",
        "changed_paths": [
            "modules/swagger-core/src/main/java/io/swagger/v3/core/jackson/mixin/ExampleMixin.java",
            "modules/swagger-core/src/main/java/io/swagger/v3/core/jackson/mixin/MediaTypeMixin.java",
            "modules/swagger-core/src/main/java/io/swagger/v3/core/util/ObjectMapperFactory.java",
            "modules/swagger-core/src/test/java/io/swagger/v3/core/deserialization/JsonDeserializationTest.java",
            "modules/swagger-core/src/test/resources/specFiles/media-type-null-example.yaml",
            "modules/swagger-models/src/main/java/io/swagger/v3/oas/models/examples/Example.java",
            "modules/swagger-models/src/main/java/io/swagger/v3/oas/models/media/MediaType.java",
        ],
        "patch_url": (
            "https://github.com/swagger-api/swagger-core/compare/"
            "567bb88c9a789dde79d08df166957bfa9a25a3b5..."
            "f95621890a7a7160489539336020346c2299d206.diff"
        ),
    },
    "e2-048": {
        "host": "github.com",
        "repository": "TakahikoKawasaki/nv-i18n",
        "pull_request_number": 78,
        "subject": "Add the XU country code",
        "base_commit": "5cd5e0a5dce4f7912a443c023129f4deedc20a63",
        "candidate_commit": "63d5e8ebc4a02d8e99cf370fdef653ad01da034b",
        "changed_paths": [
            "src/main/java/com/neovisionaries/i18n/CountryCode.java",
        ],
        "patch_url": (
            "https://github.com/TakahikoKawasaki/nv-i18n/compare/"
            "5cd5e0a5dce4f7912a443c023129f4deedc20a63..."
            "63d5e8ebc4a02d8e99cf370fdef653ad01da034b.diff"
        ),
    },
    "e2-049": {
        "host": "gitlab.ow2.org",
        "repository": "ow2/asm",
        "pull_request_number": 328,
        "source_change_kind": "merge_request",
        "subject": "Add Java 19 class-file version support",
        "base_commit": "0dd78422eb156571a54638442a085b938476154e",
        "candidate_commit": "1597a6029c2db8252ed3362fc7c7b8b4c25b8e8e",
        "changed_paths": [
            "asm-util/src/main/java/org/objectweb/asm/util/ASMifier.java",
            "asm/src/main/java/org/objectweb/asm/ClassReader.java",
            "asm/src/main/java/org/objectweb/asm/Opcodes.java",
            "asm/src/test/java/org/objectweb/asm/ConstantsTest.java",
        ],
        "patch_url": (
            "https://gitlab.ow2.org/asm/asm/-/commit/"
            "1597a6029c2db8252ed3362fc7c7b8b4c25b8e8e.diff"
        ),
    },
    "e2-050": {
        "host": "github.com",
        "repository": "micrometer-metrics/micrometer",
        "pull_request_number": None,
        "source_change_kind": "direct_commit_released_later",
        "subject": "Pin Dropwizard 4.x and expose meter type in JMX object names",
        "base_commit": "3fd77438a260f1f376e786a66f06529d577fd739",
        "candidate_commit": "4ecd09f7253467e7f144416797d7f11dab74a753",
        "changed_paths": [
            "dependencies.gradle",
            "implementations/micrometer-registry-jmx/src/test/java/io/micrometer/jmx/JmxMeterRegistryTest.java",
        ],
        "patch_url": (
            "https://github.com/micrometer-metrics/micrometer/compare/"
            "3fd77438a260f1f376e786a66f06529d577fd739..."
            "4ecd09f7253467e7f144416797d7f11dab74a753.diff"
        ),
    },
    "e2-043": {
        "host": "github.com",
        "repository": "rust-lang/rust",
        "pull_request_number": 155193,
        "subject": "Check arguments of attributes where no arguments are expected",
        "base_commit": "540f43a224317d894a9a0710a8d67704f179a33c",
        "candidate_commit": "b98202ad067d72e45cec8be3d5c15d86ef0fd086",
        "changed_paths": [
            "compiler/rustc_attr_parsing/src/attributes/allow_unstable.rs",
            "compiler/rustc_attr_parsing/src/attributes/codegen_attrs.rs",
            "compiler/rustc_attr_parsing/src/attributes/diagnostic/on_const.rs",
            "compiler/rustc_attr_parsing/src/attributes/diagnostic/on_move.rs",
            "compiler/rustc_attr_parsing/src/attributes/diagnostic/on_unknown.rs",
            "compiler/rustc_attr_parsing/src/attributes/doc.rs",
            "compiler/rustc_attr_parsing/src/attributes/dummy.rs",
            "compiler/rustc_attr_parsing/src/attributes/inline.rs",
            "compiler/rustc_attr_parsing/src/attributes/instruction_set.rs",
            "compiler/rustc_attr_parsing/src/attributes/macro_attrs.rs",
            "compiler/rustc_attr_parsing/src/attributes/rustc_dump.rs",
            "compiler/rustc_attr_parsing/src/attributes/rustc_internal.rs",
            "compiler/rustc_attr_parsing/src/attributes/test_attrs.rs",
            "compiler/rustc_attr_parsing/src/context.rs",
            "compiler/rustc_attr_parsing/src/interface.rs",
            "compiler/rustc_attr_parsing/src/parser.rs",
            "tests/ui/attributes/args-checked.rs",
            "tests/ui/attributes/args-checked.stderr",
        ],
        "patch_url": (
            "https://github.com/rust-lang/rust/compare/"
            "540f43a224317d894a9a0710a8d67704f179a33c..."
            "b98202ad067d72e45cec8be3d5c15d86ef0fd086.diff"
        ),
    },
    "e2-044": {
        "host": "github.com",
        "repository": "rust-lang/rust",
        "pull_request_number": 154992,
        "subject": "Reject projections of dyn-incompatible types in the old trait solver",
        "base_commit": "1fe72d35998dea48aeecaf7fc07783b0b553f24f",
        "candidate_commit": "a611f2a14e38407ec6717a86a01424ee6fc80762",
        "changed_paths": [
            "compiler/rustc_trait_selection/src/traits/project.rs",
            "tests/ui/self/dispatch-dyn-incompatible-that-does-not-deref.rs",
            "tests/ui/self/dispatch-dyn-incompatible-that-does-not-deref.stderr",
            "tests/ui/traits/ice-with-dyn-pointee-errors.rs",
            "tests/ui/traits/ice-with-dyn-pointee-errors.stderr",
        ],
        "patch_url": (
            "https://github.com/rust-lang/rust/compare/"
            "1fe72d35998dea48aeecaf7fc07783b0b553f24f..."
            "a611f2a14e38407ec6717a86a01424ee6fc80762.diff"
        ),
    },
    "e2-045": {
        "host": "github.com",
        "repository": "rust-lang/rust",
        "pull_request_number": 156776,
        "subject": "Tighten FnDef lifetime outlives handling",
        "base_commit": "b52edc25bfbaa955b4b83c10f998e5224c3478b2",
        "candidate_commit": "e622d8d7bed4f2668d446e06c6c1436ecae15796",
        "changed_paths": [
            "compiler/rustc_type_ir/src/outlives.rs",
            "tests/ui/function-pointer/the-pointerrrr-84366.rs",
            "tests/ui/function-pointer/the-pointerrrr-84366.stderr",
            "tests/ui/lifetimes/issue-70917-lifetimes-in-fn-def.rs",
            "tests/ui/lifetimes/issue-70917-lifetimes-in-fn-def.stderr",
        ],
        "patch_url": (
            "https://github.com/rust-lang/rust/compare/"
            "b52edc25bfbaa955b4b83c10f998e5224c3478b2..."
            "e622d8d7bed4f2668d446e06c6c1436ecae15796.diff"
        ),
    },
    "e2-007": {
        "host": "github.com",
        "repository": "estools/escope",
        "pull_request_number": None,
        "source_change_kind": "release_diff",
        "subject": "Publish ES2015-compiled internal modules in escope 3.4.0",
        "base_commit": "a3402c3e5c04f4e3dc15c88fd2d7ce8608d26ba7",
        "candidate_commit": "69145ebb4b7ebda6ca87d6235491c26447d5c82a",
        "changed_paths": ["package.json", "src/referencer.js", "src/scope-manager.js"],
        "patch_url": "https://github.com/estools/escope/compare/a3402c3e5c04f4e3dc15c88fd2d7ce8608d26ba7...69145ebb4b7ebda6ca87d6235491c26447d5c82a.diff",
    },
    "e2-008": {
        "host": "github.com",
        "repository": "indexzero/window-stream",
        "pull_request_number": None,
        "source_change_kind": "direct_commit_released_later",
        "subject": "Track TimeWindow eviction time internally",
        "base_commit": "ff16ec7327ecd35bc7f7c366768c243f89bb68ca",
        "candidate_commit": "c0a403fa497acff37c5d16194871001ceb7300bb",
        "changed_paths": ["lib/time-window.js"],
        "patch_url": "https://github.com/indexzero/window-stream/compare/ff16ec7327ecd35bc7f7c366768c243f89bb68ca...c0a403fa497acff37c5d16194871001ceb7300bb.diff",
    },
    "e2-015": {
        "host": "github.com",
        "repository": "FasterXML/jackson-databind",
        "pull_request_number": None,
        "source_change_kind": "direct_commit_released_later",
        "subject": "Expose stream read capabilities through databind contexts",
        "base_commit": "a322447b36fc5010605a8ddd770b6664f434b2e4",
        "candidate_commit": "56af702ed8cfbfe446257d251408a2cb64a4b1f2",
        "changed_paths": [
            "src/main/java/com/fasterxml/jackson/databind/DeserializationContext.java",
            "src/main/java/com/fasterxml/jackson/databind/ObjectMapper.java",
            "src/main/java/com/fasterxml/jackson/databind/ObjectReader.java",
            "src/main/java/com/fasterxml/jackson/databind/deser/DefaultDeserializationContext.java",
            "src/main/java/com/fasterxml/jackson/databind/node/TreeTraversingParser.java",
            "src/main/java/com/fasterxml/jackson/databind/util/TokenBuffer.java",
        ],
        "patch_url": "https://github.com/FasterXML/jackson-databind/compare/a322447b36fc5010605a8ddd770b6664f434b2e4...56af702ed8cfbfe446257d251408a2cb64a4b1f2.diff",
    },
    "e2-017": {
        "host": "github.com",
        "repository": "apache/logging-log4j2",
        "pull_request_number": None,
        "source_change_kind": "direct_commit_released_later",
        "subject": "Replace ServiceLoader calls with the shared ServiceLoaderUtil API",
        "base_commit": "bfc8004c42ea70f370fb7691b8301d65fe1076b5",
        "candidate_commit": "262828b193da7c63dd0b45509faaa0fb6e0bf16e",
        "changed_paths": [
            "log4j-api/src/main/java/org/apache/logging/log4j/util/ServiceLoaderUtil.java",
            "log4j-core/src/main/java/org/apache/logging/log4j/core/impl/ThreadContextDataInjector.java",
            "log4j-core/src/main/java/org/apache/logging/log4j/core/util/WatchManager.java",
        ],
        "patch_url": "https://github.com/apache/logging-log4j2/compare/bfc8004c42ea70f370fb7691b8301d65fe1076b5...262828b193da7c63dd0b45509faaa0fb6e0bf16e.diff",
    },
    "e2-027": {
        "host": "github.com",
        "repository": "qos-ch/logback",
        "pull_request_number": None,
        "source_change_kind": "direct_commit_released_later",
        "subject": "Rename the shared Logback version helper",
        "base_commit": "255af5a68b152e8c99ed166459965afa54d8360e",
        "candidate_commit": "417db916b734a5bebf4badbf99a59a7501ac65aa",
        "changed_paths": [
            "logback-classic/src/main/java/ch/qos/logback/classic/util/ContextInitializer.java",
            "logback-classic/src/test/java/ch/qos/logback/classic/util/EnvUtilTest.java",
            "logback-core/src/main/java/ch/qos/logback/core/util/EnvUtil.java",
        ],
        "patch_url": "https://github.com/qos-ch/logback/compare/255af5a68b152e8c99ed166459965afa54d8360e...417db916b734a5bebf4badbf99a59a7501ac65aa.diff",
    },
    "e2-028": {
        "host": "github.com",
        "repository": "reduxjs/react-redux",
        "pull_request_number": None,
        "source_change_kind": "direct_commit_released_later",
        "subject": "Replace the private isPlainObject module with Lodash",
        "base_commit": "1cba5a4bf68a7f07320b2f1f99bfdbd76ee73aae",
        "candidate_commit": "c4ef6f9417438b887be683d4720ffa6fb4b207f9",
        "changed_paths": ["package.json", "src/components/connect.js", "src/utils/isPlainObject.js", "test/utils/isPlainObject.spec.js", "webpack.config.js"],
        "patch_url": "https://github.com/reduxjs/react-redux/compare/1cba5a4bf68a7f07320b2f1f99bfdbd76ee73aae...c4ef6f9417438b887be683d4720ffa6fb4b207f9.diff",
    },
    "e2-029": {
        "host": "github.com",
        "repository": "babel/babel",
        "pull_request_number": None,
        "source_change_kind": "release_diff",
        "subject": "Change babel-preset-es2015 plugin configuration shape",
        "base_commit": "6ab3e35075286f63ca2aeabca7b0eb11156517cf",
        "candidate_commit": "f3ad8a83926787cec3621c532d13abf059a5e8e4",
        "changed_paths": [
            "packages/babel-preset-es2015/README.md",
            "packages/babel-preset-es2015/package.json",
            "packages/babel-preset-es2015/src/index.js",
            "packages/babel-preset-es2015/test/index.js",
        ],
        "patch_url": "https://github.com/babel/babel/compare/6ab3e35075286f63ca2aeabca7b0eb11156517cf...f3ad8a83926787cec3621c532d13abf059a5e8e4.diff",
    },
    "e2-030": {
        "host": "github.com",
        "repository": "imagemin/imagemin-optipng",
        "pull_request_number": None,
        "source_change_kind": "direct_commit_released_later",
        "subject": "Change OptiPNG command-line arguments and optimization level",
        "base_commit": "b5e62e0ae97256da730fae66ee231a9b1d31a16d",
        "candidate_commit": "1b2c2a54d51098501a5b581a2df4191d12dce15a",
        "changed_paths": ["README.md", "index.js"],
        "patch_url": "https://github.com/imagemin/imagemin-optipng/compare/b5e62e0ae97256da730fae66ee231a9b1d31a16d...1b2c2a54d51098501a5b581a2df4191d12dce15a.diff",
    },
    "e2-031": {
        "host": "github.com",
        "repository": "eslint/eslint",
        "pull_request_number": 10062,
        "subject": "Use regexpp for ES2018 regular-expression rule analysis",
        "base_commit": "935f4e460d83c39f107118c4c4dbb7f6b58684b1",
        "candidate_commit": "8d3814e4ae823e58f40539047bb35bcaf5c76660",
        "changed_paths": ["lib/rules/no-control-regex.js", "package.json", "tests/lib/rules/no-control-regex.js"],
        "patch_url": "https://github.com/eslint/eslint/compare/935f4e460d83c39f107118c4c4dbb7f6b58684b1...8d3814e4ae823e58f40539047bb35bcaf5c76660.diff",
    },
    "e2-032": {
        "host": "github.com",
        "repository": "jashkenas/backbone",
        "pull_request_number": 2878,
        "subject": "Make Model.isNew use has(idAttribute)",
        "base_commit": "d13208afe44fe31cfc38242641e8000f95cbd253",
        "candidate_commit": "6dcec298314b785a16ccc15bc44db1b91f01c367",
        "changed_paths": ["backbone.js"],
        "patch_url": "https://github.com/jashkenas/backbone/compare/d13208afe44fe31cfc38242641e8000f95cbd253...6dcec298314b785a16ccc15bc44db1b91f01c367.diff",
    },
    "e2-033": {
        "host": "github.com",
        "repository": "socketio/socket.io",
        "pull_request_number": None,
        "source_change_kind": "direct_commit_released_later",
        "subject": "Convert Socket.IO socket collections from arrays to objects",
        "base_commit": "d4fb6a590408c426a2464a412436b7f93f0641e3",
        "candidate_commit": "b73d9bea4efb48277eee685763026ff2df5a79ab",
        "changed_paths": ["lib/client.js", "lib/index.js", "lib/namespace.js", "lib/socket.js", "test/socket.io.js"],
        "patch_url": "https://github.com/socketio/socket.io/compare/d4fb6a590408c426a2464a412436b7f93f0641e3...b73d9bea4efb48277eee685763026ff2df5a79ab.diff",
    },
})

SOURCE_INPUTS["e2-046"] = dict(SOURCE_INPUTS["e2-045"])

# e2-036 and e2-037 intentionally expose the same complete source commit diff;
# only their hidden downstream labels differ.
SOURCE_INPUTS["e2-037"]["changed_paths"] = list(
    SOURCE_INPUTS["e2-036"]["changed_paths"]
)
SOURCE_INPUTS["e2-024"] = dict(SOURCE_INPUTS["e2-023"])
SOURCE_INPUTS["e2-005"] = dict(SOURCE_INPUTS["e2-004"])


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def materialize(assignments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for assignment in sorted(assignments, key=lambda item: item["case_id"]):
        case_id = assignment["case_id"]
        if case_id not in SOURCE_INPUTS:
            raise ValueError(f"missing source-input metadata for {case_id}")
        rows.append({
            "case_id": case_id,
            "observation_cutoff": assignment["observation_cutoff"],
            "source": SOURCE_INPUTS[case_id],
            "candidate_repository_catalog": assignment["candidate_repository_catalog"],
            "candidate_repository_snapshots": f"repository-snapshots.jsonl#{case_id}",
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--assignments", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--catalogs", type=Path)
    parser.add_argument("--snapshots", type=Path)
    args = parser.parse_args()
    rows = materialize(read_jsonl(args.assignments))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.output, rows)
    if args.catalogs:
        shutil.copyfile(
            args.catalogs, args.output.parent / "candidate-repositories.json"
        )
    if args.snapshots:
        shutil.copyfile(
            args.snapshots, args.output.parent / "repository-snapshots.jsonl"
        )
    print(json.dumps({
        "inputs_materialized": len(rows),
        "output": str(args.output.resolve()),
        "source_patch_visibility": "code_diff_only_during_prepare",
        "catalogs_bundled": bool(args.catalogs),
        "snapshots_bundled": bool(args.snapshots),
    }, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Materialize and verify the 50-case strict-E2 development dataset."""

from __future__ import annotations

import argparse
import csv
import json
import platform
import sys
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = ROOT / "results" / "final-e2-dataset-50-2026-08-25"


def C(case_id, family, source, change, targets, mechanism, evidence, needles, *, repair="maintainer", note=None):
    return {
        "schema_version": "1.0",
        "case_id": case_id,
        "evidence_layer": "E2",
        "dataset_status": "development_diagnostic",
        "source_change_family": family,
        "source_repository": source,
        "source_change": change,
        "target_repositories": targets if isinstance(targets, list) else [targets],
        "mechanism": mechanism,
        "repair_origin": repair,
        "arms": {"A0": "pass", "A1": "fail", "A2": "pass"},
        "evidence_paths": [evidence] if isinstance(evidence, str) else evidence,
        "evidence_needles": needles,
        "scope_note": note,
    }


CASES = [
    C("e2-001", "alembic-1.18.5-1.19.1", "openstack/requirements", "Alembic 1.18.5 -> 1.19.1", "openstack/cinder", "migration constraint reflection changed", "results/requirements-cinder-active-pilot-2026-08-24/summary.json", ["openstack/cinder", '"a0"', '"a1"', '"a2"', '"exit_status": 1']),
    C("e2-002", "jcabi-aspects-0.24.1-0.25.1", "jcabi/jcabi-aspects", "0.24.1 -> 0.25.1", "jcabi/jcabi-s3", "Tv test utility removed", "results/jcabi-formal-repetitions-2026-08-24/summary.json", ["jcabi-s3", "expected_target_failures", "Tv"]),
    C("e2-003", "jcabi-aspects-0.24.1-0.25.1", "jcabi/jcabi-aspects", "0.24.1 -> 0.25.1", "jcabi/jcabi-simpledb", "Tv test utility removed", "results/jcabi-formal-repetitions-2026-08-24/summary.json", ["jcabi-simpledb", "expected_target_failures", "Tv"]),
    C("e2-004", "slf4j-1.7.36-2.0.0", "qos-ch/slf4j", "slf4j-api 1.7.36 -> 2.0.0", "jadler-mocking/jadler", "provider discovery rejects Logback 1.2", "results/slf4j-formal-repetitions-2026-08-24/summary.json", ["jadler-mocking/jadler", "NOPLoggerFactory", "Logback 1.2.11 to 1.3.4"]),
    C("e2-005", "slf4j-1.7.36-2.0.0", "qos-ch/slf4j", "slf4j-api 1.7.36 -> 2.0.0", "rabbitmq/rabbitmq-jms-client", "provider discovery rejects Logback 1.2", "results/slf4j-rabbit-contract-formal-repetitions-2026-08-25/summary.json", ["pass_in_all_runs", "expected_unique_failure_in_all_runs", "recovered_in_all_runs"]),
    C("e2-006", "ipa-hardware-requirement", "openstack/ironic-python-agent", "new hardware>=0.24.0 requirement", "openstack/requirements", "new dependency absent from governance constraints", "results/ipa-requirements-local-three-arm-2026-08-24/summary.json", ["hardware>=0.24.0 not in openstack/requirements", '"result": "pass"', '"result": "fail"']),
    C("e2-007", "escope-3.3.0-3.4.0", "estools/escope", "3.3.0 -> 3.4.0", "babel/babel-eslint", "internal modules became default exports", "results/escope-babel-eslint-screening-2026-08-24.json", ["babel/babel-eslint", "visitClass", '"arm": "A2"']),
    C("e2-008", "window-stream-0.5.2-0.5.3", "indexzero/window-stream", "0.5.2 -> 0.5.3", "nodejitsu/godot", "window eviction time semantics changed", "results/window-stream-godot-screening-2026-08-24.json", ["nodejitsu/godot", "20 honored, 1 broken", "21 honored, 0 broken"]),
    C("e2-009", "terser-4.2.1-4.3.0", "terser/terser", "4.2.1 -> 4.3.0", "assetgraph/assetgraph-builder", "function arguments receive added parentheses", "results/terser-unified-430-repetitions-2026-08-24/summary.json", ["assetgraph/assetgraph-builder", "精确输出断言", "1 项通过"], note="All three repetitions have process exits 0/1/0. A2 is a maintainer-authored test-expectation adaptation that relaxes the exact-output regular expression; it is not a production-code repair."),
    C("e2-010", "terser-4.2.1-4.3.0", "terser/terser", "4.2.1 -> 4.3.0", "SAP/ui5-builder", "function arguments receive added parentheses", "results/terser-unified-430-repetitions-2026-08-24/summary.json", ["SAP/ui5-builder", "6 项精确输出断言失败", "17 项通过"], note="All three repetitions have process exits 0/1/0; A2 is the maintainer production configuration repair."),
    C("e2-011", "snakeyaml-1.32-2.0", "snakeyaml/snakeyaml", "1.32 -> 2.0", "apache/jclouds", "constructor now requires LoaderOptions", "results/snakeyaml-project-package-screening-2026-08-24/summary.json", ["apache/jclouds", "Class 不能转换为 LoaderOptions", '"exit_code": 0']),
    C("e2-012", "snakeyaml-1.32-2.0", "snakeyaml/snakeyaml", "1.32 -> 2.0", "zio/zio-json", "constructor now requires LoaderOptions", "results/snakeyaml-project-package-screening-2026-08-24/summary.json", ["zio/zio-json", "缺少 LoaderOptions 参数", '"exit_code": 1']),
    C("e2-013", "plexus-utils-3.5.1-4.0.0", "codehaus-plexus/plexus-utils", "3.5.1 -> 4.0.0", "s4u/pgpverify-maven-plugin", "XML classes moved to plexus-xml", "results/plexus-utils-project-package-screening-2026-08-24/summary.json", ["s4u/pgpverify-maven-plugin", "Xpp3Dom", '"tests": 300']),
    C("e2-014", "plexus-utils-3.5.1-4.0.0", "codehaus-plexus/plexus-utils", "3.5.1 -> 4.0.0", "mathieucarbou/license-maven-plugin", "XML classes moved to plexus-xml", "results/plexus-utils-project-package-screening-2026-08-24/summary.json", ["mathieucarbou/license-maven-plugin", "NoClassDefFoundError", '"tests": 343']),
    C("e2-015", "jackson-databind-2.10-2.12", "FasterXML/jackson-databind", "2.10.5.1 -> 2.12.6.1", "splunk/kafka-connect-splunk", "Jackson component versions became inconsistent", "results/jackson-initial-screening-2026-08-24/run-results.tsv", ["a0\tsplunk/kafka-connect-splunk", "a1\tsplunk/kafka-connect-splunk", "a2\tsplunk/kafka-connect-splunk"]),
    C("e2-016", "jackson-databind-object-cache", "FasterXML/jackson-databind", "a8d8ec0e -> 2897aa00", "RWS/dxa-web-application-java", "Object.class metadata cache bypassed mapper mix-ins", "results/jackson-second-positive-dxa-2026-08-25/summary.json", ["RWS/dxa-web-application-java", '"A0"', '"A1"', '"A2"'], note="Strict direction is measured on the maintainer product ObjectMapper path; the older standalone FSE module command is not the admitted contract."),
    C("e2-017", "log4j-2.17.2-2.18.0", "apache/logging-log4j2", "Core 2.17.2 -> 2.18.0 with API initially stale", "equinor/neqsim", "API/Core binary linkage mismatch", "results/log4j-neqsim-historical-screening-2026-08-24/run-results.tsv", ["a0\t6cea014", "a1\te23721", "a2\td62294"]),
    C("e2-018", "assertj-3.22.0-3.23.0", "assertj/assertj-core", "3.22.0 -> 3.23.0", "assertj/assertj-guava", "new transitive Byte Buddy dependency violates allowlist", "results/assertj-positive-screening-2026-08-24/run-results.tsv", ["assertj-guava\ta0", "assertj-guava\ta1", "assertj-guava\ta2"]),
    C("e2-019", "assertj-3.22.0-3.23.0", "assertj/assertj-core", "3.22.0 -> 3.23.0", "assertj/assertj-vavr", "removed internal Byte Buddy package", "results/assertj-positive-screening-2026-08-24/run-results.tsv", ["assertj-vavr\ta0", "assertj-vavr\ta1", "assertj-vavr\ta2"]),
    C("e2-020", "assertj-3.18.1-3.19.0", "assertj/assertj-core", "3.18.1 -> 3.19.0", "openzipkin/brave", "ComparisonFailure appends expected/actual details", "results/assertj-3.19-brave-fse-2026-08-25/summary.json", ["openzipkin/brave", '"result": "fail"', '"result": "pass"']),
    C("e2-021", "commons-io-2.7-2.11.0", "apache/commons-io", "2.7 -> 2.11.0", "damianszczepanik/cucumber-reporting", "changed validation rejects target input", "results/commons-io-initial-screening-2026-08-24/summary.json", ["damianszczepanik/cucumber-reporting", "illegal_argument_exception", "success_345_tests"]),
    C("e2-022", "commons-io-2.11.0-2.13.0", "apache/commons-io", "2.11.0 -> 2.13.0", "jcabi/jcabi-maven-plugin", "deprecated constructor triggers warnings-as-errors", "results/commons-io-initial-screening-2026-08-24/summary.json", ["jcabi/jcabi-maven-plugin", "deprecated_constructor_werror", "success_4_tests"]),
    C("e2-023", "checkstyle-10.12.1-10.12.2", "checkstyle/checkstyle", "10.12.1 -> 10.12.2", "getgauge/gauge-java", "new FinalClass findings", "results/checkstyle-positive-screening-2026-08-24/run-results.tsv", ["gauge-java\ta0", "gauge-java\ta1", "gauge-java\ta2"]),
    C("e2-024", "checkstyle-10.12.1-10.12.2", "checkstyle/checkstyle", "10.12.1 -> 10.12.2", "apache/ws-wss4j", "new FinalClass findings", "results/checkstyle-positive-screening-2026-08-24/run-results.tsv", ["ws-wss4j\ta0", "ws-wss4j\ta1", "ws-wss4j\ta2"]),
    C("e2-025", "mockito-1.10.19-5.1.1", "mockito/mockito", "1.10.19 -> 5.1.1", "apache/bval", "legacy getArgumentAt API removed", "results/mockito-initial-screening-2026-08-24/summary.json", ["apache/bval", "get_argument_at_missing", "1313_tests"]),
    C("e2-026", "mockito-3.12.4-4.1.0", "mockito/mockito", "3.12.4 -> 4.1.0", "pholser/junit-quickcheck", "legacy JUnit runner integration removed", "results/mockito-initial-screening-2026-08-24/summary.json", ["pholser/junit-quickcheck", "old_junit_runner_missing", "1114_tests"]),
    C("e2-027", "logback-classic-1.2.11-1.4.0", "qos-ch/logback", "Classic 1.2.11 -> 1.4.0 while Core stays 1.2.11", "matteobaccan/html2pop3", "Classic/Core binary mismatch", "results/logback-project-package-screening-2026-08-24/run-results.tsv", ["html2pop3\ta0", "html2pop3\ta1", "html2pop3\ta2"]),
    C("e2-028", "react-redux-4.1.2-4.2.0", "reduxjs/react-redux", "4.1.2 -> 4.2.0", "loggur/react-redux-provide", "private isPlainObject module removed", "results/react-redux-provide-screening-2026-08-24/summary.json", ["Cannot find module react-redux/lib/utils/isPlainObject", '"exit_status": 1', '"passing_tests": 6']),
    C("e2-029", "babel-preset-es2015-6.13.0-6.13.1", "babel/babel", "babel-preset-es2015 6.13.0 -> 6.13.1", "rollup/babel-preset-es2015-rollup", "module transform emits CommonJS", "results/babel-preset-rollup-local-three-arm-2026-08-24/summary.json", ["CommonJS exports.default emitted", '"arm": "A0"', '"arm": "A2"']),
    C("e2-030", "imagemin-optipng-4.1.0-4.2.0", "imagemin/imagemin-optipng", "4.1.0 -> 4.2.0", "Brightspace/images-to-variables", "optimized output fixture changed", "results/imagemin-optipng-screening-2026-08-24/summary.json", ["Brightspace/images-to-variables", '"failures": 3', '"contract_result": "pass"'], note="The historical Gulp/Jasmine runner exits zero even on failures, so the declared primary result channel is the structured Jasmine failure count: 0/3/0 failures across A0/A1/A2."),
    C("e2-031", "eslint-4.18.2-4.19.0", "eslint/eslint", "4.18.2 -> 4.19.0", "DevExpress/testcafe", "no-control-regex rule became stricter", "results/eslint-testcafe-screening-2026-08-24/summary.json", ["DevExpress/testcafe", "Unexpected control character", "accepted_single_positive"]),
    C("e2-032", "backbone-1.1.0-1.1.1", "jashkenas/backbone", "1.1.0 -> 1.1.1", ["vidigami/backbone-mongo", "vidigami/backbone-orm"], "model identity behavior requires coordinated two-repository repair", "results/backbone-mongo-family-2026-08-24/summary.json", ["accepted_two-target-causal-anchor", '"A0"', '"A1"', '"A2"'], note="One relation: both target repositories are jointly required; target count is not case count."),
    C("e2-033", "socket.io-1.3.7-1.4.0", "socketio/socket.io", "1.3.7 -> 1.4.0", "karma-runner/karma", "socket object shape changed", "results/socketio-karma-screening-2026-08-24/summary.json", ["socket_io_object_shape_change", '"contract_result": "fail"', '"contract_result": "pass"']),
    C("e2-034", "h2-1.4.199-1.4.200-mvcc", "h2database/h2database", "1.4.199 -> 1.4.200", "database-rider/database-rider", "MVCC connection setting rejected", "results/h2-mvcc-clients-family-2026-08-24/summary.json", ["database-rider/database-rider", "fail-90113", '"A2": "pass"']),
    C("e2-035", "h2-1.4.199-1.4.200-mvcc", "h2database/h2database", "1.4.199 -> 1.4.200", "CloudSlang/score", "MVCC connection setting rejected", "results/h2-mvcc-clients-family-2026-08-24/summary.json", ["CloudSlang/score", "fail-90113-both-tests", "pass-both-tests"]),
    C("e2-036", "h2-1.4.200-2.0.202-value", "h2database/h2database", "1.4.200 -> 2.0.202", "jhannes/fluent-jdbc", "VALUE became a reserved keyword", "results/h2-2.0-fse-screening-2026-08-25/summary.json", ["jhannes/fluent-jdbc", "JdbcSQLSyntaxErrorException 42001", '"result": "pass"']),
    C("e2-037", "h2-1.4.200-2.0.202-value", "h2database/h2database", "1.4.200 -> 2.0.202", "BrunoEberhard/minimal-j", "VALUE became a reserved keyword", "results/h2-2.0-fse-screening-2026-08-25/summary.json", ["BrunoEberhard/minimal-j", "JdbcSQLSyntaxErrorException 42001", '"result": "fail"']),
    C("e2-038", "h2-1.4.199-1.4.200-trailing-comma", "h2database/h2database", "1.4.199 -> 1.4.200", "arey/spring-batch-toolkit", "trailing comma in SQL rejected", "results/h2-1.4.200-fse-extension-2026-08-25/summary.json", ["arey/spring-batch-toolkit", "fail_exact_42001_200", '"a2": "pass"']),
    C("e2-039", "log4j-core-2.14.1-2.15.0", "apache/logging-log4j2", "Core 2.14.1 -> 2.15.0 while API stays 2.14.1", "oboehm/gdv.xport", "API/Core binary linkage mismatch", "results/log4j-core-2.15-fse-replay-2026-08-25/summary.json", ["oboehm/gdv.xport", "NoSuchFieldError: EMPTY_BYTE_ARRAY", '"accepted_positive": true']),
    C("e2-040", "derby-driver-jar-move", "apache/derby", "EmbeddedDriver moved from derby.jar to derbytools.jar", "susom/database", "driver class moved between artifacts", "results/derby-10.15-fse-susom-source-isolation-2026-08-25/summary.json", ["susom/database", "Failed to load driver class", '"result": "pass"']),
    C("e2-041", "swagger-models-2.1.6-2.1.10", "swagger-api/swagger-core", "swagger-models 2.1.6 -> 2.1.10", "javalin/javalin", "new exampleSetFlag getter leaks through client mapper", "results/swagger-models-2.1.10-fse-screening-2026-08-25/summary.json", ["53 passed", "14 failed", "exampleSetFlag"]),
    C("e2-042", "jackson-core-2.8.0-2.11.0", "FasterXML/jackson-core", "2.8.0 -> 2.11.0", "internetitem/logback-elasticsearch-appender", "formerly final convenience methods became mock-interceptable", "results/jackson-core-2.11-fse-screening-2026-08-25/summary.json", ["8 passed", "8 failed", "accepted_positive_relations"]),
    C("e2-043", "rust-pr-155193", "rust-lang/rust", "compiler PR 155193", "aalexandrov/spectest", "malformed inline attribute becomes an error", "results/crater-replay-pr-155193-2026-08-23.json", ["spectest-0.1.2", '"result": "fail"', "E0539"]),
    C("e2-044", "rust-pr-154992", "rust-lang/rust", "compiler PR 154992", "tjtelan/git-url-parse-rs", "dyn-incompatible projection rejected", "results/crater-replay-pr-154992-2026-08-23.json", ["git-url-parse-0.6.0", '"result": "fail"', "E0038"], repair="external_contributor_unmerged", note="Repair efficacy is verified; maintainer adoption was not established at replay time."),
    C("e2-045", "rust-pr-156776", "rust-lang/rust", "compiler PR 156776", "polyfloyd/rust-id3", "lifetime escapes under stricter compiler behavior", "results/crater-replay-pr-156776-id3-2026-08-23.json", ["id3-1.16.4", '"result": "fail"', "E0521"], repair="external_contributor_unmerged", note="Repair efficacy is verified; maintainer adoption was not established at replay time."),
    C("e2-046", "rust-pr-156776", "rust-lang/rust", "compiler PR 156776", "rustunit/bevy_channel_trigger", "lifetime bound breaks archived dependent package", "results/crater-replay-pr-156776-bevy-ios-app-delegate-2026-08-23.json", ["bevy_ios_app_delegate-0.4.0", '"result": "fail"', "must outlive 'static"], note="Execution subject is the archived dependent package bevy_ios_app_delegate; repaired component is bevy_channel_trigger."),
    C("e2-047", "jackson-yaml-2.12.4-2.13.0", "FasterXML/jackson-dataformats-text", "jackson-dataformat-yaml 2.12.4 -> 2.13.0", "SchemaCrawler/SchemaCrawler", "Jackson component linkage mismatch", "results/final-e2-dataset-50-2026-08-25/new-replays/schemacrawler/summary.json", ["NoSuchMethodError", '"decision": "accepted_strict_e2"']),
    C("e2-048", "nv-i18n-1.28-1.29", "TakahikoKawasaki/nv-i18n", "1.28 -> 1.29", "marcwrobel/jbanking", "new ISO country code invalidates completeness expectation", "results/final-e2-dataset-50-2026-08-25/new-replays/jbanking/summary.json", ["Missing countries : [XU]", '"decision": "accepted_strict_e2"']),
    C("e2-049", "asm-9.2-9.3", "ow2/asm", "aggregate 9.2 -> 9.3", "raphw/byte-buddy", "new class-file version requires target constant update", "results/final-e2-dataset-50-2026-08-25/new-replays/bytebuddy/summary.json", ["expected class-file version 63", '"decision": "accepted_strict_e2"']),
    C("e2-050", "micrometer-1.8.5-1.9.0", "micrometer-metrics/micrometer", "aggregate 1.8.5 -> 1.9.0", "rabbitmq/rabbitmq-perf-test", "JMX object-name layout adds meter type", "results/final-e2-dataset-50-2026-08-25/new-replays/rabbitmq-perf/summary.json", ["type=gauges", '"decision": "accepted_strict_e2"']),
]


REJECTED = [{
    "case_id": "rejected-terser-preconstruct",
    "source_change_family": "terser-4.2.1-4.3.0",
    "target_repository": "preconstruct/preconstruct",
    "reason": "A0 and A2 process exits remain nonzero because 39 unrelated stale snapshots are reported; the same command therefore does not satisfy pass/fail/pass.",
    "evidence_path": "results/terser-unified-430-repetitions-2026-08-24/summary.json",
}]


def J(file, path, expected, op="eq"):
    return {"kind": "json", "file": file, "path": path, "op": op, "expected": expected}


def JS(file, list_path, where, value_path, expected, op="eq"):
    return {
        "kind": "json_select",
        "file": file,
        "list_path": list_path,
        "where": where,
        "value_path": value_path,
        "op": op,
        "expected": expected,
    }


def T(file, where, field, expected):
    return {"kind": "tsv", "file": file, "where": where, "field": field, "expected": str(expected)}


def TG(pattern, where, field, expected, count):
    return {"kind": "tsv_glob", "pattern": pattern, "where": where, "field": field, "expected": str(expected), "count": count}


R = "results/"
ARM_RULES = {
    "e2-001": {
        "A0": [J(R + "requirements-cinder-active-pilot-2026-08-24/summary.json", ["arms", "a0", "exit_status"], 0)],
        "A1": [J(R + "requirements-cinder-active-pilot-2026-08-24/summary.json", ["arms", "a1", "exit_status"], 1)],
        "A2": [J(R + "requirements-cinder-active-pilot-2026-08-24/summary.json", ["arms", "a2", "exit_status"], 0)],
    },
    "e2-002": {
        "A0": [J(R + "jcabi-formal-repetitions-2026-08-24/summary.json", ["configurations", "a0", "tests_reported_per_repetition", "jcabi-s3"], 12), J(R + "jcabi-formal-repetitions-2026-08-24/summary.json", ["configurations", "a0", "failed"], 0)],
        "A1": [J(R + "jcabi-formal-repetitions-2026-08-24/summary.json", ["configurations", "a1", "target_failure_signatures", "jcabi-s3"], "Tv", "contains")],
        "A2": [J(R + "jcabi-formal-repetitions-2026-08-24/summary.json", ["configurations", "a2", "tests_reported_per_repetition", "jcabi-s3"], 12), J(R + "jcabi-formal-repetitions-2026-08-24/summary.json", ["configurations", "a2", "failed"], 0)],
    },
    "e2-003": {
        "A0": [J(R + "jcabi-formal-repetitions-2026-08-24/summary.json", ["configurations", "a0", "tests_reported_per_repetition", "jcabi-simpledb"], 5), J(R + "jcabi-formal-repetitions-2026-08-24/summary.json", ["configurations", "a0", "failed"], 0)],
        "A1": [J(R + "jcabi-formal-repetitions-2026-08-24/summary.json", ["configurations", "a1", "target_failure_signatures", "jcabi-simpledb"], "Tv", "contains")],
        "A2": [J(R + "jcabi-formal-repetitions-2026-08-24/summary.json", ["configurations", "a2", "tests_reported_per_repetition", "jcabi-simpledb"], 5), J(R + "jcabi-formal-repetitions-2026-08-24/summary.json", ["configurations", "a2", "failed"], 0)],
    },
    "e2-004": {
        "A0": [J(R + "slf4j-formal-repetitions-2026-08-24/summary.json", ["aggregate", "by_arm", "a0", "expected_fail"], 0), J(R + "slf4j-formal-repetitions-2026-08-24/summary.json", ["consumer_results", "jadler-mocking/jadler", "other_arms"], "passed", "contains")],
        "A1": [J(R + "slf4j-formal-repetitions-2026-08-24/summary.json", ["consumer_results", "jadler-mocking/jadler", "a1"], "failed in all three repetitions", "contains")],
        "A2": [J(R + "slf4j-formal-repetitions-2026-08-24/summary.json", ["aggregate", "by_arm", "a2", "pass"], 12), J(R + "slf4j-formal-repetitions-2026-08-24/summary.json", ["consumer_results", "jadler-mocking/jadler", "repair"], "A2 changed only", "contains")],
    },
    "e2-005": {
        "A0": [J(R + "slf4j-rabbit-contract-formal-repetitions-2026-08-25/summary.json", ["arms", "A0", "result"], "pass_in_all_runs")],
        "A1": [J(R + "slf4j-rabbit-contract-formal-repetitions-2026-08-25/summary.json", ["arms", "A1", "result"], "expected_unique_failure_in_all_runs")],
        "A2": [J(R + "slf4j-rabbit-contract-formal-repetitions-2026-08-25/summary.json", ["arms", "A2", "result"], "recovered_in_all_runs")],
    },
    "e2-006": {
        arm: [JS(R + "ipa-requirements-local-three-arm-2026-08-24/summary.json", ["arms"], {"arm": arm}, ["exit_code"], code)]
        for arm, code in (("A0", 0), ("A1", 1), ("A2", 0))
    },
    "e2-007": {
        arm: [JS(R + "escope-babel-eslint-screening-2026-08-24.json", ["arms"], {"arm": arm}, ["exit_code"], code)]
        for arm, code in (("A0", 0), ("A1", 1), ("A2", 0))
    },
    "e2-008": {
        arm: [JS(R + "window-stream-godot-screening-2026-08-24.json", ["arms"], {"arm": arm}, ["result"], result)]
        for arm, result in (("A0", "21 honored, 0 broken"), ("A1", "20 honored, 1 broken"), ("A2", "21 honored, 0 broken"))
    },
    "e2-009": {
        arm: [TG(R + "terser-unified-430-repetitions-2026-08-24/repeat-*/run-results.tsv", {"repository": "assetgraph/assetgraph-builder", "config": arm.lower()}, "exit_code", code, 3)]
        for arm, code in (("A0", 0), ("A1", 1), ("A2", 0))
    },
    "e2-010": {
        arm: [TG(R + "terser-unified-430-repetitions-2026-08-24/repeat-*/run-results.tsv", {"repository": "SAP/ui5-builder", "config": arm.lower()}, "exit_code", code, 3)]
        for arm, code in (("A0", 0), ("A1", 1), ("A2", 0))
    },
    "e2-011": {
        arm: [JS(R + "snakeyaml-project-package-screening-2026-08-24/summary.json", ["positive_consumers"], {"repository": "apache/jclouds"}, [arm.lower(), "exit_code"], code)]
        for arm, code in (("A0", 0), ("A1", 1), ("A2", 0))
    },
    "e2-012": {
        arm: [JS(R + "snakeyaml-project-package-screening-2026-08-24/summary.json", ["positive_consumers"], {"repository": "zio/zio-json"}, [arm.lower(), "exit_code"], code)]
        for arm, code in (("A0", 0), ("A1", 1), ("A2", 0))
    },
    "e2-013": {
        arm: [JS(R + "plexus-utils-project-package-screening-2026-08-24/summary.json", ["positive_targets"], {"repository": "s4u/pgpverify-maven-plugin"}, [arm.lower(), "exit_code"], code)]
        for arm, code in (("A0", 0), ("A1", 1), ("A2", 0))
    },
    "e2-014": {
        arm: [JS(R + "plexus-utils-project-package-screening-2026-08-24/summary.json", ["positive_targets"], {"repository": "mathieucarbou/license-maven-plugin"}, [arm.lower(), "exit_code"], code)]
        for arm, code in (("A0", 0), ("A1", 1), ("A2", 0))
    },
    "e2-015": {
        arm: [T(R + "jackson-initial-screening-2026-08-24/run-results.tsv", {"configuration": arm.lower(), "repository": "splunk/kafka-connect-splunk"}, "exit_code", code)]
        for arm, code in (("A0", 0), ("A1", 1), ("A2", 0))
    },
    "e2-016": {
        arm: [J(R + "jackson-second-positive-dxa-2026-08-25/summary.json", ["accepted_anchor", "arms", arm, "result"], result)]
        for arm, result in (("A0", "pass"), ("A1", "fail"), ("A2", "pass"))
    },
    "e2-017": {
        arm: [T(R + "log4j-neqsim-historical-screening-2026-08-24/run-results.tsv", {"config": arm.lower()}, "exit_code", code)]
        for arm, code in (("A0", 0), ("A1", 1), ("A2", 0))
    },
    "e2-018": {
        arm: [T(R + "assertj-positive-screening-2026-08-24/run-results.tsv", {"repository": "assertj-guava", "arm": arm.lower()}, "exit_code", code)]
        for arm, code in (("A0", 0), ("A1", 1), ("A2", 0))
    },
    "e2-019": {
        arm: [T(R + "assertj-positive-screening-2026-08-24/run-results.tsv", {"repository": "assertj-vavr", "arm": arm.lower()}, "exit_code", code)]
        for arm, code in (("A0", 0), ("A1", 1), ("A2", 0))
    },
    "e2-020": {
        arm: [J(R + "assertj-3.19-brave-fse-2026-08-25/summary.json", ["arms", arm, "result"], result)]
        for arm, result in (("A0", "pass"), ("A1", "fail"), ("A2", "pass"))
    },
    "e2-021": {
        arm: [JS(R + "commons-io-initial-screening-2026-08-24/summary.json", ["anchors"], {"consumer_repository": "damianszczepanik/cucumber-reporting"}, [arm.lower()], prefix, "prefix")]
        for arm, prefix in (("A0", "success_"), ("A1", "failure_"), ("A2", "success_"))
    },
    "e2-022": {
        arm: [JS(R + "commons-io-initial-screening-2026-08-24/summary.json", ["anchors"], {"consumer_repository": "jcabi/jcabi-maven-plugin"}, [arm.lower()], prefix, "prefix")]
        for arm, prefix in (("A0", "success_"), ("A1", "failure_"), ("A2", "success_"))
    },
    "e2-023": {
        arm: [T(R + "checkstyle-positive-screening-2026-08-24/run-results.tsv", {"repository": "gauge-java", "arm": arm.lower()}, "exit_code", code)]
        for arm, code in (("A0", 0), ("A1", 1), ("A2", 0))
    },
    "e2-024": {
        arm: [T(R + "checkstyle-positive-screening-2026-08-24/run-results.tsv", {"repository": "ws-wss4j", "arm": arm.lower()}, "exit_code", code)]
        for arm, code in (("A0", 0), ("A1", 1), ("A2", 0))
    },
    "e2-025": {
        arm: [JS(R + "mockito-initial-screening-2026-08-24/summary.json", ["anchors"], {"consumer_repository": "apache/bval"}, [arm.lower()], prefix, "prefix")]
        for arm, prefix in (("A0", "success_"), ("A1", "failure_"), ("A2", "success_"))
    },
    "e2-026": {
        arm: [JS(R + "mockito-initial-screening-2026-08-24/summary.json", ["anchors"], {"consumer_repository": "pholser/junit-quickcheck"}, [arm.lower()], prefix, "prefix")]
        for arm, prefix in (("A0", "success_"), ("A1", "failure_"), ("A2", "success_"))
    },
    "e2-027": {
        arm: [T(R + "logback-project-package-screening-2026-08-24/run-results.tsv", {"repository": "html2pop3", "config": arm.lower()}, "exit_code", code)]
        for arm, code in (("A0", 0), ("A1", 1), ("A2", 0))
    },
    "e2-028": {
        arm: [JS(R + "react-redux-provide-screening-2026-08-24/summary.json", ["causal_case", "arms"], {"arm": arm}, ["exit_status"], code)]
        for arm, code in (("A0", 0), ("A1", 1), ("A2", 0))
    },
    "e2-029": {
        arm: [JS(R + "babel-preset-rollup-local-three-arm-2026-08-24/summary.json", ["arms"], {"arm": arm}, ["exit_code"], code)]
        for arm, code in (("A0", 0), ("A1", 1), ("A2", 0))
    },
    "e2-030": {
        arm: [JS(R + "imagemin-optipng-screening-2026-08-24/summary.json", ["observations"], {"name": arm.lower()}, ["contract_result"], result)]
        for arm, result in (("A0", "pass"), ("A1", "fail"), ("A2", "pass"))
    },
    "e2-031": {
        arm: [JS(R + "eslint-testcafe-screening-2026-08-24/summary.json", ["arms"], {"arm": arm}, ["exit_status"], code)]
        for arm, code in (("A0", 0), ("A1", 1), ("A2", 0))
    },
    "e2-032": {
        arm: [J(R + "backbone-mongo-family-2026-08-24/summary.json", ["backbone_relation", "arms", arm, "result"], result)]
        for arm, result in (("A0", "pass"), ("A1", "fail"), ("A2", "pass"))
    },
    "e2-033": {
        arm: [JS(R + "socketio-karma-screening-2026-08-24/summary.json", ["observations"], {"arm": arm.lower()}, ["contract_result"], result)]
        for arm, result in (("A0", "pass"), ("A1", "fail"), ("A2", "pass"))
    },
    "e2-034": {
        arm: [J(R + "h2-mvcc-clients-family-2026-08-24/summary.json", ["targets", "database-rider/database-rider", "arms", arm], token, "prefix")]
        for arm, token in (("A0", "pass"), ("A1", "fail"), ("A2", "pass"))
    },
    "e2-035": {
        arm: [J(R + "h2-mvcc-clients-family-2026-08-24/summary.json", ["targets", "CloudSlang/score", "arms", arm], token, "prefix")]
        for arm, token in (("A0", "pass"), ("A1", "fail"), ("A2", "pass"))
    },
    "e2-036": {
        arm: [JS(R + "h2-2.0-fse-screening-2026-08-25/summary.json", ["accepted_anchors"], {"target_repository": "jhannes/fluent-jdbc"}, ["arms", arm, "result"], result)]
        for arm, result in (("A0", "pass"), ("A1", "fail"), ("A2", "pass"))
    },
    "e2-037": {
        arm: [JS(R + "h2-2.0-fse-screening-2026-08-25/summary.json", ["accepted_anchors"], {"target_repository": "BrunoEberhard/minimal-j"}, ["arms", arm, "result"], result)]
        for arm, result in (("A0", "pass"), ("A1", "fail"), ("A2", "pass"))
    },
    "e2-038": {
        arm: [J(R + "h2-1.4.200-fse-extension-2026-08-25/summary.json", ["formal_case", arm.lower()], token, "prefix")]
        for arm, token in (("A0", "pass"), ("A1", "fail"), ("A2", "pass"))
    },
    "e2-039": {
        arm: [JS(R + "log4j-core-2.15-fse-replay-2026-08-25/summary.json", ["arms"], {"arm": arm.lower()}, ["exit_code"], code)]
        for arm, code in (("A0", 0), ("A1", 1), ("A2", 0))
    },
    "e2-040": {
        "A0": [J(R + "derby-10.15-fse-susom-source-isolation-2026-08-25/summary.json", ["target", "parent", "exit_code"], 0)],
        "A1": [J(R + "derby-10.15-fse-susom-source-isolation-2026-08-25/summary.json", ["target", "child", "exit_code"], 1)],
        "A2": [J(R + "derby-10.15-fse-susom-source-isolation-2026-08-25/summary.json", ["target", "child_repaired", "exit_code"], 0)],
    },
    "e2-041": {
        "A0": [J(R + "swagger-models-2.1.10-fse-screening-2026-08-25/summary.json", ["javalin_execution", "a0"], "53 passed")],
        "A1": [J(R + "swagger-models-2.1.10-fse-screening-2026-08-25/summary.json", ["javalin_execution", "a1"], "14 failed", "contains")],
        "A2": [J(R + "swagger-models-2.1.10-fse-screening-2026-08-25/summary.json", ["javalin_execution", "a2"], "53 passed")],
    },
    "e2-042": {
        "A0": [J(R + "jackson-core-2.11-fse-screening-2026-08-25/summary.json", ["execution", "a0"], "8 passed")],
        "A1": [J(R + "jackson-core-2.11-fse-screening-2026-08-25/summary.json", ["execution", "a1"], "8 failed")],
        "A2": [J(R + "jackson-core-2.11-fse-screening-2026-08-25/summary.json", ["execution", "a2"], "8 passed")],
    },
    "e2-043": {
        "A0": [JS(R + "crater-replay-pr-155193-2026-08-23.json", ["local_replay", "arms"], {"name": "baseline_compiler_with_published_source"}, ["exit_codes"], [0, 0, 0])],
        "A1": [JS(R + "crater-replay-pr-155193-2026-08-23.json", ["local_replay", "arms"], {"name": "target_compiler_with_published_source"}, ["exit_codes"], [101, 101, 101])],
        "A2": [JS(R + "crater-replay-pr-155193-2026-08-23.json", ["local_replay", "arms"], {"name": "target_compiler_with_downstream_fix"}, ["exit_codes"], [0, 0, 0])],
    },
    "e2-044": {
        "A0": [JS(R + "crater-replay-pr-154992-2026-08-23.json", ["local_replay", "arms"], {"name": "baseline_compiler_with_published_source"}, ["exit_codes"], [0, 0, 0])],
        "A1": [JS(R + "crater-replay-pr-154992-2026-08-23.json", ["local_replay", "arms"], {"name": "target_compiler_with_published_source"}, ["exit_codes"], [101, 101, 101])],
        "A2": [JS(R + "crater-replay-pr-154992-2026-08-23.json", ["local_replay", "arms"], {"name": "target_compiler_with_downstream_fix"}, ["exit_codes"], [0, 0, 0])],
    },
    "e2-045": {
        "A0": [JS(R + "crater-replay-pr-156776-id3-2026-08-23.json", ["local_replay", "arms"], {"name": "baseline_compiler_with_published_source"}, ["exit_codes"], [0, 0, 0])],
        "A1": [JS(R + "crater-replay-pr-156776-id3-2026-08-23.json", ["local_replay", "arms"], {"name": "target_compiler_with_published_source"}, ["exit_codes"], [101, 101, 101])],
        "A2": [JS(R + "crater-replay-pr-156776-id3-2026-08-23.json", ["local_replay", "arms"], {"name": "target_compiler_with_single_fix_commit"}, ["exit_codes"], [0, 0, 0])],
    },
    "e2-046": {
        "A0": [JS(R + "crater-replay-pr-156776-bevy-ios-app-delegate-2026-08-23.json", ["local_replay", "arms"], {"name": "baseline_compiler_with_published_dependency"}, ["exit_codes"], [0, 0, 0])],
        "A1": [JS(R + "crater-replay-pr-156776-bevy-ios-app-delegate-2026-08-23.json", ["local_replay", "arms"], {"name": "target_compiler_with_published_dependency"}, ["exit_codes"], [101, 101, 101])],
        "A2": [JS(R + "crater-replay-pr-156776-bevy-ios-app-delegate-2026-08-23.json", ["local_replay", "arms"], {"name": "target_compiler_with_repaired_dependency"}, ["exit_codes"], [0, 0, 0])],
    },
}

for case_id, directory in (("e2-047", "schemacrawler"), ("e2-048", "jbanking"), ("e2-049", "bytebuddy"), ("e2-050", "rabbitmq-perf")):
    ARM_RULES[case_id] = {
        arm: [J(R + f"final-e2-dataset-50-2026-08-25/new-replays/{directory}/summary.json", ["arms", arm, "exit_code"], code)]
        for arm, code in (("A0", 0), ("A1", 1), ("A2", 0))
    }


def value_at(value, path):
    for component in path:
        value = value[component]
    return value


def compare_value(observed, expected, op):
    if op == "eq":
        return observed == expected
    if op == "contains":
        return isinstance(observed, str) and str(expected) in observed
    if op == "prefix":
        return isinstance(observed, str) and observed.startswith(str(expected))
    raise AssertionError(f"unknown comparison operator: {op}")


def read_tsv(path):
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def matching_rows(rows, where):
    return [row for row in rows if all(row.get(key) == str(value) for key, value in where.items())]


def evaluate_rule(case_id, arm, rule, json_cache, tsv_cache):
    kind = rule["kind"]
    paths = []
    if kind in {"json", "json_select"}:
        relative = rule["file"]
        path = ROOT / relative
        paths.append(relative)
        if relative not in json_cache:
            json_cache[relative] = json.loads(path.read_text(encoding="utf-8"))
        document = json_cache[relative]
        if kind == "json":
            observed = value_at(document, rule["path"])
            selector = {"path": rule["path"]}
        else:
            candidates = value_at(document, rule["list_path"])
            selected = [item for item in candidates if all(item.get(key) == value for key, value in rule["where"].items())]
            if len(selected) != 1:
                raise AssertionError(f"{case_id} {arm}: selector {rule['where']} matched {len(selected)} JSON rows")
            observed = value_at(selected[0], rule["value_path"])
            selector = {"list_path": rule["list_path"], "where": rule["where"], "value_path": rule["value_path"]}
        if not compare_value(observed, rule["expected"], rule["op"]):
            raise AssertionError(f"{case_id} {arm}: observed {observed!r}, expected {rule['op']} {rule['expected']!r}")
        return {"kind": kind, "path": relative, "selector": selector, "observed": observed, "expected": rule["expected"], "operator": rule["op"]}, paths

    if kind == "tsv":
        relative_files = [rule["file"]]
    elif kind == "tsv_glob":
        relative_files = [str(path.relative_to(ROOT)) for path in sorted(ROOT.glob(rule["pattern"]))]
        if len(relative_files) != rule["count"]:
            raise AssertionError(f"{case_id} {arm}: glob matched {len(relative_files)}, expected {rule['count']}")
    else:
        raise AssertionError(f"unknown rule kind: {kind}")
    observations = []
    for relative in relative_files:
        paths.append(relative)
        if relative not in tsv_cache:
            tsv_cache[relative] = read_tsv(ROOT / relative)
        selected = matching_rows(tsv_cache[relative], rule["where"])
        if len(selected) != 1:
            raise AssertionError(f"{case_id} {arm}: selector {rule['where']} matched {len(selected)} TSV rows in {relative}")
        observed = selected[0].get(rule["field"])
        if observed != rule["expected"]:
            raise AssertionError(f"{case_id} {arm}: {relative} {rule['field']}={observed!r}, expected {rule['expected']!r}")
        observations.append({"path": relative, "observed": observed})
    return {"kind": kind, "selector": rule["where"], "field": rule["field"], "expected": rule["expected"], "observations": observations}, paths


def verify_structured_arms(case_id, json_cache, tsv_cache):
    rules_by_arm = ARM_RULES.get(case_id)
    if set(rules_by_arm or {}) != {"A0", "A1", "A2"}:
        raise AssertionError(f"{case_id}: missing complete structured arm rules")
    arm_results = {}
    evidence_paths = set()
    for arm, expected_result in (("A0", "pass"), ("A1", "fail"), ("A2", "pass")):
        checks = []
        for rule in rules_by_arm[arm]:
            check, paths = evaluate_rule(case_id, arm, rule, json_cache, tsv_cache)
            checks.append(check)
            evidence_paths.update(paths)
        arm_results[arm] = {"machine_verified": True, "derived_result": expected_result, "checks": checks}
    return arm_results, sorted(evidence_paths)


def split_for(index: int) -> str:
    if index <= 30:
        return "development"
    if index <= 40:
        return "evaluation_proposal"
    return "holdout_proposal"


def write_jsonl(path: Path, rows):
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def verify_new_replay(case_id: str, output: Path):
    names = {"e2-047": "schemacrawler", "e2-048": "jbanking", "e2-049": "bytebuddy", "e2-050": "rabbitmq-perf"}
    if case_id not in names:
        return
    case_dir = output / "new-replays" / names[case_id]
    with (case_dir / "run-results.tsv").open(encoding="utf-8") as handle:
        rows = list(csv.reader(handle, delimiter="\t"))
    observed = {arm.upper(): int(code) for arm, code in rows}
    if observed != {"A0": 0, "A1": 1, "A2": 0}:
        raise AssertionError(f"{case_id}: replay exits are {observed}")
    a1 = (case_dir / "a1.log").read_text(encoding="utf-8", errors="replace")
    signatures = {
        "e2-047": "NoSuchMethodError",
        "e2-048": "Missing countries : [XU]",
        "e2-049": "Expected: is <63s>",
        "e2-050": "expected: <1> but was: <0>",
    }
    if signatures[case_id] not in a1:
        raise AssertionError(f"{case_id}: A1 signature absent")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    if len(CASES) != 50:
        raise AssertionError(f"expected 50 cases, found {len(CASES)}")
    if len({case["case_id"] for case in CASES}) != 50:
        raise AssertionError("case IDs are not unique")
    if set(ARM_RULES) != {case["case_id"] for case in CASES}:
        missing = sorted({case["case_id"] for case in CASES} - set(ARM_RULES))
        extra = sorted(set(ARM_RULES) - {case["case_id"] for case in CASES})
        raise AssertionError(f"structured arm rules mismatch; missing={missing}, extra={extra}")
    relation_keys = {(case["source_change_family"], tuple(case["target_repositories"])) for case in CASES}
    if len(relation_keys) != 50:
        raise AssertionError("relation keys are not unique")

    final_rows = []
    audit_rows = []
    json_cache = {}
    tsv_cache = {}
    for position, original in enumerate(CASES, 1):
        case = dict(original)
        case["split"] = split_for(position)
        context_checks = []
        for relative in case["evidence_paths"]:
            path = ROOT / relative
            if not path.is_file():
                raise AssertionError(f"{case['case_id']}: missing evidence {relative}")
            text = path.read_text(encoding="utf-8", errors="replace")
            if path.suffix == ".json":
                json.loads(text)
            missing = [needle for needle in case["evidence_needles"] if needle not in text]
            if missing:
                raise AssertionError(f"{case['case_id']}: {relative} missing markers {missing}")
            context_checks.append({
                "path": relative,
                "exists": True,
                "markers_found": True,
                "required_markers": case["evidence_needles"],
            })
        arm_results, structured_paths = verify_structured_arms(case["case_id"], json_cache, tsv_cache)
        derived = {arm: result["derived_result"] for arm, result in arm_results.items()}
        if case["arms"] != derived:
            raise AssertionError(f"{case['case_id']}: index arms {case['arms']} disagree with parsed evidence {derived}")
        case["evidence_paths"] = sorted(set(case["evidence_paths"]) | set(structured_paths))
        case["machine_arm_verification"] = "passed"
        case["blind_evaluation_eligible"] = False
        rule_kinds = {rule["kind"] for rules in ARM_RULES[case["case_id"]].values() for rule in rules}
        if case["case_id"] == "e2-030":
            case["primary_result_channel"] = "structured_native_test_failure_count"
        elif case["case_id"] in {"e2-009", "e2-010"}:
            case["primary_result_channel"] = "process_exit_across_three_repetitions"
        elif rule_kinds <= {"tsv", "tsv_glob"} or all("exit" in json.dumps(rule) for rules in ARM_RULES[case["case_id"]].values() for rule in rules):
            case["primary_result_channel"] = "process_exit"
        else:
            case["primary_result_channel"] = "structured_test_or_contract_result"
        case.pop("evidence_needles")
        final_rows.append(case)
        audit_rows.append({
            "case_id": case["case_id"],
            "accepted": True,
            "classification": "strict_E2",
            "machine_arm_verification": "passed",
            "parsed_arms": arm_results,
            "context_marker_checks": context_checks,
            "audit_note": "A0/A1/A2 were derived from parsed JSON fields or selected TSV rows. Context markers are supplemental identity/signature checks and do not determine arm direction.",
        })
        verify_new_replay(case["case_id"], output)

    group_to_splits = defaultdict(set)
    for row in final_rows:
        group_to_splits[row["source_change_family"]].add(row["split"])
    leaks = {group: sorted(splits) for group, splits in group_to_splits.items() if len(splits) > 1}
    if leaks:
        raise AssertionError(f"source-change families cross split proposal: {leaks}")

    write_jsonl(output / "final-index.jsonl", final_rows)
    write_jsonl(output / "evidence-audit.jsonl", audit_rows)
    write_jsonl(output / "rejected.jsonl", REJECTED)
    inventory = [dict(row, disposition="accepted") for row in final_rows] + [dict(row, disposition="rejected") for row in REJECTED]
    write_jsonl(output / "candidate-inventory.jsonl", inventory)
    groups = [{"source_change_family": family, "case_ids": [row["case_id"] for row in final_rows if row["source_change_family"] == family], "split": next(iter(splits))} for family, splits in sorted(group_to_splits.items())]
    write_jsonl(output / "group-manifest.jsonl", groups)
    write_jsonl(output / "split-proposal.jsonl", [{"case_id": row["case_id"], "source_change_family": row["source_change_family"], "split": row["split"]} for row in final_rows])

    machine_verified = sum(row["machine_arm_verification"] == "passed" for row in final_rows)
    strict_e2_count = sum(row["arms"] == {"A0": "pass", "A1": "fail", "A2": "pass"} and row["machine_arm_verification"] == "passed" for row in final_rows)
    metrics = {
        "schema_version": "1.0",
        "case_count": len(final_rows),
        "strict_e2_count": strict_e2_count,
        "machine_arm_verified_case_count": machine_verified,
        "declared_only_arm_case_count": len(final_rows) - machine_verified,
        "arm_direction": {"A0": "pass", "A1": "fail", "A2": "pass"},
        "source_change_family_count": len(group_to_splits),
        "target_repository_occurrences": sum(len(row["target_repositories"]) for row in final_rows),
        "repair_origin_counts": dict(sorted(Counter(row["repair_origin"] for row in final_rows).items())),
        "split_counts": dict(sorted(Counter(row["split"] for row in final_rows).items())),
        "rejected_count": len(REJECTED),
        "source_family_split_leaks": 0,
        "precision_f1_specificity_reported": False,
        "formal_no_leak_benchmark": False,
        "blind_evaluation_ready": False,
    }
    (output / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    run_manifest = {
        "schema_version": "1.0",
        "validator": str(Path(__file__).relative_to(ROOT)),
        "status": "passed",
        "verified_case_count": strict_e2_count,
        "machine_arm_verified_case_count": machine_verified,
        "declared_only_arm_case_count": len(final_rows) - machine_verified,
        "new_replays_checked": 4,
        "existing_execution_evidence_parsed": len(final_rows) - 4,
        "known_rejection_preserved": "rejected-terser-preconstruct",
        "command": "python3 benchmarks/cross-repo-pr-impact/verify_final_e2_dataset.py",
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
        },
        "seed": "not_applicable_deterministic_evidence_parser",
    }
    (output / "run-manifest.json").write_text(json.dumps(run_manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    evaluation_summary = {
        "outcome": "supported",
        "metrics": {
            "case_count": len(final_rows),
            "machine_arm_verified_case_count": machine_verified,
            "declared_only_arm_case_count": len(final_rows) - machine_verified,
        },
        "claim_update": "All 50 arm directions are now derived from parsed JSON or TSV evidence; context-marker checks no longer determine admission.",
        "baseline_relation": "The previous validator checked direction structurally only for four new replays and used context strings for 46 existing cases.",
        "failure_mode": "No arm-parser failure in the repaired run; negative mutation tests confirm JSON and TSV direction changes are rejected.",
        "next_action": "Treat the package as development/diagnostic; require provenance and blind split work before a formal benchmark release.",
    }
    (output / "evaluation-summary.json").write_text(json.dumps(evaluation_summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

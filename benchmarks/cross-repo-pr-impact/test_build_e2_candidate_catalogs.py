import tempfile
import unittest
from pathlib import Path

from build_e2_candidate_catalogs import (
    E2_INDEX,
    OPENSTACK_CATALOG_ID,
    build_openstack_catalog,
    build_github_org_catalog,
    build_h2_fse_catalog,
    build_checkstyle_bump_catalog,
    build_bump_component_catalog,
    import_ecosystem_catalog_audit,
    parse_github_org_snapshot,
    parse_source_family_frame,
    parse_openstack_projects,
    parse_jackson_fse_component_frame,
    read_jsonl,
    run,
)


class E2CandidateCatalogBuilderTests(unittest.TestCase):
    def setUp(self):
        self.cases = read_jsonl(E2_INDEX)
        self.projects = "\n".join([
            "openstack/cinder",
            "openstack/ironic-python-agent",
            "openstack/nova",
        ]) + "\n"

    def test_membership_is_constructed_without_targets(self):
        repositories = parse_openstack_projects(self.projects)
        self.assertEqual([
            "openstack/cinder",
            "openstack/ironic-python-agent",
            "openstack/nova",
            "openstack/requirements",
        ], repositories)

    def test_openstack_catalog_is_reused_and_covers_both_cases(self):
        catalog, assignments, coverage = build_openstack_catalog(
            self.cases, self.projects
        )
        self.assertEqual(OPENSTACK_CATALOG_ID, catalog["catalog_id"])
        self.assertFalse(catalog["membership_reads_e2_targets"])
        self.assertEqual(["e2-001", "e2-006"], [row["case_id"] for row in assignments])
        self.assertTrue(coverage["reused_across_cases"])
        self.assertTrue(coverage["all_sources_covered"])
        self.assertTrue(coverage["all_targets_covered"])
        self.assertTrue(coverage["formal_catalog_eligible"])

    def test_target_is_not_silently_added(self):
        incomplete = "openstack/ironic-python-agent\nopenstack/nova\n"
        catalog, _, coverage = build_openstack_catalog(self.cases, incomplete)
        self.assertNotIn("openstack/cinder", catalog["repositories"])
        self.assertFalse(coverage["all_targets_covered"])
        self.assertFalse(coverage["formal_catalog_eligible"])

    def test_invalid_source_row_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_openstack_projects("openstack/cinder extra\n")

    def test_github_org_membership_excludes_forks_without_reading_targets(self):
        snapshot = {
            "organization": "assertj",
            "endpoint": "https://api.github.test/orgs/assertj/repos",
            "fetched_at": "2026-08-25T00:00:00Z",
            "repositories": [
                {"full_name": "assertj/assertj-core", "private": False, "fork": False},
                {"full_name": "assertj/assertj-guava", "private": False, "fork": False},
                {"full_name": "assertj/assertj-vavr", "private": False, "fork": False},
                {"full_name": "assertj/fork", "private": False, "fork": True},
            ],
        }
        self.assertNotIn("assertj/fork", parse_github_org_snapshot(snapshot, "assertj"))
        catalog, assignments, coverage = build_github_org_catalog(
            self.cases, "assertj", snapshot
        )
        self.assertFalse(catalog["membership_reads_e2_targets"])
        self.assertEqual(["e2-018", "e2-019"], [row["case_id"] for row in assignments])
        self.assertTrue(coverage["formal_catalog_eligible"])

    def test_h2_source_family_frame_is_reused_but_development_only(self):
        frame = "\n".join([
            '{"root_repository":"jhannes/fluent-jdbc"}',
            '{"root_repository":"BrunoEberhard/minimal-j"}',
            '{"root_repository":"example/unjudged"}',
        ]) + "\n"
        self.assertEqual(
            ["BrunoEberhard/minimal-j", "example/unjudged", "jhannes/fluent-jdbc"],
            parse_source_family_frame(frame, ("root_repository",)),
        )
        catalog, assignments, coverage = build_h2_fse_catalog(
            self.cases, "h2-2.0.202", frame
        )
        self.assertFalse(catalog["membership_reads_e2_targets"])
        self.assertTrue(catalog["source_selection_is_outcome_conditioned"])
        self.assertEqual(["e2-036", "e2-037"], [row["case_id"] for row in assignments])
        self.assertTrue(coverage["development_catalog_eligible"])
        self.assertFalse(coverage["formal_catalog_eligible"])

    def test_checkstyle_component_frame_is_reused_but_development_only(self):
        frame = "\n".join([
            '{"repository":"getgauge/gauge-java"}',
            '{"repository":"apache/ws-wss4j"}',
            '{"repository":"example/unjudged"}',
        ]) + "\n"
        catalog, assignments, coverage = build_checkstyle_bump_catalog(
            self.cases, frame
        )
        self.assertFalse(catalog["membership_reads_e2_targets"])
        self.assertTrue(catalog["source_selection_is_outcome_conditioned"])
        self.assertEqual(["e2-023", "e2-024"], [row["case_id"] for row in assignments])
        self.assertTrue(coverage["development_catalog_eligible"])
        self.assertFalse(coverage["formal_catalog_eligible"])

    def test_mockito_component_frame_tracks_case_specific_cutoffs(self):
        frame = "\n".join([
            '{"repository":"apache/bval"}',
            '{"repository":"pholser/junit-quickcheck"}',
            '{"repository":"example/unjudged"}',
        ]) + "\n"
        catalog, assignments, coverage = build_bump_component_catalog(
            self.cases, "mockito", frame
        )
        self.assertFalse(catalog["membership_reads_e2_targets"])
        self.assertEqual(["e2-025", "e2-026"], [row["case_id"] for row in assignments])
        self.assertFalse(assignments[0]["input_spec_opening_cutoff_conformant"])
        self.assertTrue(assignments[1]["input_spec_opening_cutoff_conformant"])
        self.assertTrue(coverage["development_catalog_eligible"])

    def test_commons_io_direct_commit_cases_are_nonconformant_development(self):
        frame = "\n".join([
            '{"repository":"damianszczepanik/cucumber-reporting"}',
            '{"repository":"jcabi/jcabi-maven-plugin"}',
            '{"repository":"example/unjudged"}',
        ]) + "\n"
        _, assignments, coverage = build_bump_component_catalog(
            self.cases, "commons-io", frame
        )
        self.assertEqual(["e2-021", "e2-022"], [row["case_id"] for row in assignments])
        self.assertFalse(assignments[0]["input_spec_opening_cutoff_conformant"])
        self.assertFalse(assignments[1]["input_spec_opening_cutoff_conformant"])
        self.assertTrue(coverage["development_catalog_eligible"])

    def test_slf4j_mixed_screening_frame_uses_root_repository(self):
        frame = "\n".join([
            '{"root_repository":"jadler-mocking/jadler"}',
            '{"root_repository":"rabbitmq/rabbitmq-jms-client"}',
            '{"root_repository":"example/unjudged"}',
        ]) + "\n"
        catalog, assignments, coverage = build_bump_component_catalog(
            self.cases, "slf4j", frame
        )
        self.assertEqual("local_dependency_screening_frame", catalog["membership_source"]["kind"])
        self.assertEqual(["e2-004", "e2-005"], [row["case_id"] for row in assignments])
        self.assertTrue(coverage["development_catalog_eligible"])

    def test_jackson_fse_slice_resolves_all_component_roots_before_labels(self):
        frame = "\n".join([
            '{"dependency":{"coordinate":"com.fasterxml.jackson.core:jackson-core"},"client":{"repository_directory_hint":"internetitem_logback-elasticsearch-appender"}}',
            '{"dependency":{"coordinate":"com.fasterxml.jackson.dataformat:jackson-dataformat-yaml"},"client":{"repository_directory_hint":"sualeh_SchemaCrawler\\\\schemacrawler-loader"}}',
            '{"dependency":{"coordinate":"other:artifact"},"client":{"repository_directory_hint":"ignored_repo"}}',
        ]) + "\n"
        self.assertEqual(
            ["SchemaCrawler/SchemaCrawler", "internetitem/logback-elasticsearch-appender"],
            parse_jackson_fse_component_frame(frame),
        )

    def test_project_package_frames_reuse_complete_positive_and_bounded_rows(self):
        snakeyaml = "\n".join([
            '{"repository":"apache/jclouds"}',
            '{"repository":"zio/zio-json"}',
            '{"repository":"xlate/yaml-json"}',
            '{"repository":"xvik/yaml-updater"}',
        ]) + "\n"
        _, assignments, coverage = build_bump_component_catalog(
            self.cases, "snakeyaml", snakeyaml
        )
        self.assertEqual(["e2-011", "e2-012"], [row["case_id"] for row in assignments])
        self.assertTrue(coverage["development_catalog_eligible"])

        fse_union = "\n".join([
            '{"repository":"openzipkin/brave"}',
            '{"repository":"susom/database"}',
            '{"repository":"example/assertj-distractor"}',
            '{"repository":"example/derby-distractor"}',
        ]) + "\n"
        _, assignments, coverage = build_bump_component_catalog(
            self.cases, "fse-assertj-derby", fse_union
        )
        self.assertEqual(["e2-020", "e2-040"], [row["case_id"] for row in assignments])
        self.assertTrue(coverage["development_catalog_eligible"])

        java_compat_union = "\n".join([
            '{"repository":"oboehm/gdv.xport"}',
            '{"repository":"javalin/javalin"}',
            '{"repository":"marcwrobel/jbanking"}',
            '{"repository":"raphw/byte-buddy"}',
            '{"repository":"rabbitmq/rabbitmq-perf-test"}',
            '{"repository":"example/unjudged"}',
        ]) + "\n"
        _, assignments, coverage = build_bump_component_catalog(
            self.cases, "fse-java-compat", java_compat_union
        )
        self.assertEqual(
            ["e2-039", "e2-041", "e2-048", "e2-049", "e2-050"],
            [row["case_id"] for row in assignments],
        )
        self.assertEqual(
            [False, True, False, True, False],
            [row["input_spec_opening_cutoff_conformant"] for row in assignments],
        )
        self.assertTrue(coverage["development_catalog_eligible"])

        crater = "\n".join([
            '{"fix":{"repository":"aalexandrov/spectest"}}',
            '{"fix":{"repository":"tjtelan/git-url-parse-rs"}}',
            '{"fix":{"repository":"polyfloyd/rust-id3"}}',
            '{"fix":{"repository":"rustunit/bevy_channel_trigger"}}',
        ]) + "\n"
        _, assignments, coverage = build_bump_component_catalog(
            self.cases, "crater-linked-fixes", crater
        )
        self.assertEqual(
            ["e2-043", "e2-044", "e2-045", "e2-046"],
            [row["case_id"] for row in assignments],
        )
        self.assertTrue(all(
            row["input_spec_opening_cutoff_conformant"] for row in assignments
        ))
        self.assertTrue(coverage["development_catalog_eligible"])

        legacy = (
            Path("workstreams/legacy-component-screening/candidate-frame.jsonl")
            .read_text(encoding="utf-8")
        )
        _, assignments, coverage = build_bump_component_catalog(
            self.cases, "legacy-component-screening", legacy
        )
        self.assertEqual(11, len(assignments))
        self.assertEqual("e2-007", assignments[0]["case_id"])
        self.assertEqual("e2-033", assignments[-1]["case_id"])
        self.assertTrue(coverage["development_catalog_eligible"])
        by_case = {row["case_id"]: row for row in assignments}
        self.assertEqual(
            "72bba55b6464ae2dfa060ecb04a3346e35d8bf04",
            by_case["e2-028"]["candidate_snapshot_overrides"]
            ["loggur/react-redux-provide"]["commit"],
        )
        self.assertEqual(
            "94da609777c4af78dc06bd9a0f773531ec0635e6",
            by_case["e2-030"]["candidate_snapshot_overrides"]
            ["Brightspace/images-to-variables"]["commit"],
        )

        terser = "\n".join([
            '{"repository":"assetgraph/assetgraph-builder"}',
            '{"repository":"SAP/ui5-builder"}',
            '{"repository":"preconstruct/preconstruct"}',
            '{"repository":"angular/angular-cli"}',
        ]) + "\n"
        _, assignments, coverage = build_bump_component_catalog(
            self.cases, "terser", terser
        )
        self.assertEqual(["e2-009", "e2-010"], [row["case_id"] for row in assignments])
        self.assertTrue(all(row["input_spec_opening_cutoff_conformant"] for row in assignments))
        self.assertTrue(coverage["development_catalog_eligible"])


    def test_offline_run_materializes_auditable_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "projects.txt"
            source.write_text(self.projects, encoding="utf-8")
            output = root / "output"
            summary = run(E2_INDEX, output, source)
            self.assertEqual(2, summary["formal_catalog_eligible_case_count"])
            self.assertEqual(0, summary["snapshot_ready_case_count"])
            self.assertEqual(2, len(read_jsonl(output / "case-catalog-assignments.jsonl")))

    def test_complete_maven_ecosystem_audit_replaces_only_covered_assignments(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sources").mkdir()
            catalog_id = "ecosystems-maven-dependent-package-slices-2026-08-26"
            repositories = [
                "javalin/javalin",
                "marcwrobel/jbanking",
                "example/unjudged",
            ]
            (root / "candidate-repositories.json").write_text(
                __import__("json").dumps({"catalogs": {catalog_id: {
                    "catalog_id": catalog_id,
                    "catalog_status": "label_independent_reusable_coverage_audit",
                    "membership_reads_e2_targets": False,
                    "source_selection_is_outcome_conditioned": False,
                    "query_failure_count": 0,
                    "repositories": repositories,
                    "membership_source": {
                        "catalog_cutoff": "2026-08-26T00:00:00Z",
                        "snapshot": "sources/dependent-package-query-snapshots.jsonl",
                    },
                }}}),
                encoding="utf-8",
            )
            (root / "coverage-audit.jsonl").write_text(
                '\n'.join([
                    '{"case_id":"e2-041","ecosystem":"maven","targets_covered":true}',
                    '{"case_id":"e2-048","ecosystem":"maven","targets_covered":true}',
                ]) + '\n',
                encoding="utf-8",
            )
            (root / "sources" / "dependent-package-query-snapshots.jsonl").write_text(
                '{"ecosystem":"maven","url":"https://example.invalid/query"}\n',
                encoding="utf-8",
            )
            assignments = [{
                "case_id": case_id,
                "candidate_repository_catalog": "candidate-repositories.json#old",
                "observation_cutoff": "2021-01-01T00:00:00Z",
                "input_spec_opening_cutoff_conformant": True,
                "cutoff_policy": "pull_request_creation",
            } for case_id in ("e2-041", "e2-048")]
            catalog, replacements, coverage, snapshot = import_ecosystem_catalog_audit(
                self.cases, assignments, root
            )
            self.assertEqual(2, len(replacements))
            self.assertTrue(coverage["formal_catalog_eligible"])
            self.assertFalse(catalog["membership_reads_e2_targets"])
            self.assertIn('"ecosystem": "maven"', snapshot)

    def test_incomplete_paginated_component_catalog_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sources").mkdir()
            catalog_id = "ecosystems-maven-mockito-complete-dependent-packages-2026-08-26"
            (root / "candidate-repositories.json").write_text(
                __import__("json").dumps({"catalogs": {catalog_id: {
                    "catalog_id": catalog_id,
                    "membership_reads_e2_targets": False,
                    "source_selection_is_outcome_conditioned": False,
                    "query_failure_count": 0,
                    "complete_query_audit": {"complete_query_verified": False},
                    "repositories": ["apache/bval", "pholser/junit-quickcheck"],
                    "membership_source": {
                        "catalog_cutoff": "2026-08-26T00:00:00Z",
                        "snapshot": "sources/dependent-package-query-snapshots.jsonl",
                    },
                }}}),
                encoding="utf-8",
            )
            (root / "coverage-audit.jsonl").write_text(
                '\n'.join([
                    f'{{"case_id":"e2-025","ecosystem":"maven","catalog_id":"{catalog_id}","targets_covered":true}}',
                    f'{{"case_id":"e2-026","ecosystem":"maven","catalog_id":"{catalog_id}","targets_covered":true}}',
                ]) + '\n',
                encoding="utf-8",
            )
            assignments = [{
                "case_id": case_id,
                "candidate_repository_catalog": "candidate-repositories.json#old",
                "observation_cutoff": "2021-01-01T00:00:00Z",
                "input_spec_opening_cutoff_conformant": True,
                "cutoff_policy": "pull_request_creation",
            } for case_id in ("e2-025", "e2-026")]
            with self.assertRaisesRegex(ValueError, "is not complete"):
                import_ecosystem_catalog_audit(
                    self.cases, assignments, root, "maven", catalog_id
                )


if __name__ == "__main__":
    unittest.main()

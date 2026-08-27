import base64
import unittest

from materialize_e2_inputs import materialize
from prepare_case_inputs import code_only_diff


class E2InputMaterializationTests(unittest.TestCase):
    def test_fse_union_cases_use_isolated_direct_commits(self):
        assignments = [
            {
                "case_id": "e2-020",
                "observation_cutoff": "2021-01-24T05:06:38Z",
                "candidate_repository_catalog": "candidate-repositories.json#fse-assertj-derby-component-family-2026-08-25",
            },
            {
                "case_id": "e2-040",
                "observation_cutoff": "2019-03-10T23:36:25Z",
                "candidate_repository_catalog": "candidate-repositories.json#fse-assertj-derby-component-family-2026-08-25",
            },
        ]
        rows = {row["case_id"]: row["source"] for row in materialize(assignments)}
        self.assertIn("AssertionErrorCreator.java", rows["e2-020"]["changed_paths"][1])
        self.assertEqual("build.xml", rows["e2-040"]["changed_paths"][0])
        self.assertTrue(all(row["source_change_kind"] == "direct_commit_released_later" for row in rows.values()))

    def test_terser_uses_causal_head_present_at_pr_opening(self):
        assignment = {
            "case_id": "e2-009",
            "observation_cutoff": "2019-08-19T21:20:06Z",
            "candidate_repository_catalog": "candidate-repositories.json#terser-project-package-frame-2026-08-25",
        }
        source = materialize([assignment])[0]["source"]
        self.assertEqual(433, source["pull_request_number"])
        self.assertEqual("b3c6765b958157d0452ddd2099981ac55d14c2ce", source["candidate_commit"])
        self.assertIn("lib/output.js", source["changed_paths"])

    def test_project_package_source_mechanisms_are_direct_commits(self):
        assignments = [
            {
                "case_id": "e2-012",
                "observation_cutoff": "2023-02-26T11:07:37Z",
                "candidate_repository_catalog": "candidate-repositories.json#snakeyaml-project-package-frame-2026-08-25",
            },
            {
                "case_id": "e2-013",
                "observation_cutoff": "2023-05-22T15:15:06Z",
                "candidate_repository_catalog": "candidate-repositories.json#plexus-utils-project-package-frame-2026-08-25",
            },
        ]
        rows = {row["case_id"]: row["source"] for row in materialize(assignments)}
        self.assertEqual(
            "direct_commit_released_later", rows["e2-012"]["source_change_kind"]
        )
        self.assertIn("SafeConstructor.java", rows["e2-012"]["changed_paths"][0])
        self.assertIn(
            "src/main/java/org/codehaus/plexus/util/xml/Xpp3Dom.java",
            rows["e2-013"]["changed_paths"],
        )

    def test_jackson_databind_object_cache_uses_isolated_direct_commit(self):
        assignment = {
            "case_id": "e2-016",
            "observation_cutoff": "2020-04-25T23:57:08Z",
            "candidate_repository_catalog": (
                "candidate-repositories.json#jackson-fse-component-family-2026-08-25"
            ),
        }
        source = materialize([assignment])[0]["source"]
        self.assertIsNone(source["pull_request_number"])
        self.assertEqual(
            [
                "src/main/java/com/fasterxml/jackson/databind/introspect/BasicClassIntrospector.java"
            ],
            source["changed_paths"],
        )

    def test_materializes_schema_v1_shape(self):
        assignments = [{
            "case_id": "e2-001",
            "observation_cutoff": "2026-08-15T12:56:38Z",
            "candidate_repository_catalog": (
                "candidate-repositories.json#openstack-global-requirements-2026-08-11"
            ),
        }]
        row = materialize(assignments)[0]
        self.assertEqual("repository-snapshots.jsonl#e2-001", row["candidate_repository_snapshots"])
        self.assertEqual(["upper-constraints.txt"], row["source"]["changed_paths"])

    def test_opendev_mail_metadata_is_removed(self):
        mail_patch = (
            b"From deadbeef Mon Sep 17 00:00:00 2001\n"
            b"Depends-On: https://review.example/target\n\n"
            b"diff --git a/source.txt b/source.txt\n"
            b"--- a/source.txt\n+++ b/source.txt\n"
        )
        encoded = base64.b64encode(mail_patch)
        decoded = code_only_diff(base64.b64decode(encoded))
        self.assertTrue(decoded.startswith(b"diff --git"))
        self.assertNotIn(b"Depends-On", decoded)
        self.assertNotIn(b"review.example", decoded)

    def test_missing_diff_boundary_is_rejected(self):
        with self.assertRaises(ValueError):
            code_only_diff(b"commit message only")

    def test_recovered_pre_force_push_head_is_used_for_assertj(self):
        assignment = {
            "case_id": "e2-018",
            "observation_cutoff": "2022-01-29T12:04:35Z",
            "candidate_repository_catalog": (
                "candidate-repositories.json#assertj-github-organization-2026-08-25"
            ),
        }
        source = materialize([assignment])[0]["source"]
        self.assertEqual("463004be40302f0543e8c3ba5d73515d50527d10", source["candidate_commit"])
        self.assertTrue(source["patch_url"].endswith(".diff"))

    def test_h2_late_pr_commit_exposes_complete_diff_paths(self):
        assignment = {
            "case_id": "e2-036",
            "observation_cutoff": "2019-12-01T14:50:19Z",
            "candidate_repository_catalog": (
                "candidate-repositories.json#h2-fse-2.0.202-source-family-2026-08-25"
            ),
        }
        source = materialize([assignment])[0]["source"]
        self.assertEqual(2297, source["pull_request_number"])
        self.assertIn("h2/src/main/org/h2/util/ParserUtil.java", source["changed_paths"])
        self.assertGreater(len(source["changed_paths"]), 40)

    def test_checkstyle_causal_pull_request_head_is_materialized(self):
        assignment = {
            "case_id": "e2-023",
            "observation_cutoff": "2023-06-27T16:38:11Z",
            "candidate_repository_catalog": (
                "candidate-repositories.json#checkstyle-bump-source-family-2026-08-25"
            ),
        }
        source = materialize([assignment])[0]["source"]
        self.assertEqual(12737, source["pull_request_number"])
        self.assertEqual("e286af7405332a59b48189590f0b7d29ab925066", source["candidate_commit"])
        self.assertIn("FinalClassCheck.java", source["changed_paths"][0])

    def test_mockito_opening_head_exposes_complete_removed_api_diff(self):
        assignment = {
            "case_id": "e2-026",
            "observation_cutoff": "2021-09-01T17:26:27Z",
            "candidate_repository_catalog": (
                "candidate-repositories.json#mockito-bump-source-family-2026-08-25"
            ),
        }
        source = materialize([assignment])[0]["source"]
        self.assertEqual(2418, source["pull_request_number"])
        self.assertIn(
            "src/main/java/org/mockito/runners/MockitoJUnitRunner.java",
            source["changed_paths"],
        )
        self.assertEqual(109, len(source["changed_paths"]))

    def test_commons_io_direct_commit_is_explicit(self):
        assignment = {
            "case_id": "e2-021",
            "observation_cutoff": "2021-01-11T06:45:34Z",
            "candidate_repository_catalog": (
                "candidate-repositories.json#commons-io-bump-source-family-2026-08-25"
            ),
        }
        source = materialize([assignment])[0]["source"]
        self.assertIsNone(source["pull_request_number"])
        self.assertEqual("direct_commit", source["source_change_kind"])
        self.assertIn("src/main/java/org/apache/commons/io/FileUtils.java", source["changed_paths"])

    def test_slf4j_uses_causal_provider_discovery_diff(self):
        assignment = {
            "case_id": "e2-004",
            "observation_cutoff": "2022-08-20T19:04:05Z",
            "candidate_repository_catalog": (
                "candidate-repositories.json#slf4j-screening-source-family-2026-08-25"
            ),
        }
        source = materialize([assignment])[0]["source"]
        self.assertEqual("direct_commit_released_later", source["source_change_kind"])
        self.assertIn("slf4j-api/src/main/java/org/slf4j/LoggerFactory.java", source["changed_paths"])
        self.assertIn("slf4j-api/src/main/java/org/slf4j/spi/SLF4JServiceProvider.java", source["changed_paths"])

    def test_jackson_yaml_uses_isolated_content_reference_commit(self):
        assignment = {
            "case_id": "e2-047",
            "observation_cutoff": "2021-09-30T21:38:57Z",
            "candidate_repository_catalog": (
                "candidate-repositories.json#jackson-fse-component-family-2026-08-25"
            ),
        }
        source = materialize([assignment])[0]["source"]
        self.assertEqual("e5dc40f55321161c94b4d1088a030cf9de936497", source["candidate_commit"])
        self.assertIn(
            "yaml/src/main/java/com/fasterxml/jackson/dataformat/yaml/YAMLFactory.java",
            source["changed_paths"],
        )


if __name__ == "__main__":
    unittest.main()

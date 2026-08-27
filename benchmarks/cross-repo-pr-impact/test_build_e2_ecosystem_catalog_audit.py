import tempfile
import unittest
from pathlib import Path

from build_e2_ecosystem_catalog_audit import (
    audit_coverage,
    compact_query_snapshot,
    complete_package_membership,
    construct_membership,
    github_repository,
    query_url,
)


class EcosystemCatalogAuditTests(unittest.TestCase):
    def test_github_repository_normalizes_common_package_metadata_urls(self):
        self.assertEqual(
            "owner/repository",
            github_repository("git+https://github.com/owner/repository.git"),
        )
        self.assertEqual(
            "owner/repository",
            github_repository("git@github.com:owner/repository.git"),
        )
        self.assertIsNone(github_repository("https://gitlab.com/owner/repository"))

    def test_query_is_historical_fixed_first_page(self):
        url = query_url("npmjs.org", "@scope/package", "downloads", "desc", 20)
        self.assertIn("%40scope%2Fpackage", url)
        self.assertIn("latest=false", url)
        self.assertIn("per_page=20", url)
        self.assertIn("page=1", url)

    def test_query_snapshot_drops_unneeded_nested_package_payload(self):
        compact = compact_query_snapshot({
            "url": "https://example.invalid/query",
            "rows": [{
                "id": 1,
                "name": "consumer",
                "repository_url": "https://github.com/example/consumer",
                "versions": [{"large": "payload"}],
            }],
        })
        self.assertEqual("consumer", compact["rows"][0]["name"])
        self.assertNotIn("versions", compact["rows"][0])

    def test_membership_is_constructed_from_source_queries_only(self):
        calls = []

        def fetcher(url):
            calls.append(url)
            return [
                {"repository_url": "https://github.com/example/consumer"},
                {"repository_url": "https://gitlab.com/ignored/project"},
            ]

        membership, snapshots = construct_membership(2, 4, fetcher=fetcher)
        self.assertEqual(["example/consumer"], membership["npm"])
        self.assertEqual(["example/consumer"], membership["maven"])
        self.assertEqual(len(calls), len(snapshots))

    def test_persistent_historical_query_failure_uses_recorded_latest_fallback(self):
        calls = []

        def fetcher(url):
            calls.append(url)
            if "latest=false" in url:
                raise RuntimeError("historical query unavailable")
            return [{"repository_url": "https://github.com/example/fallback"}]

        membership, snapshots = construct_membership(1, 8, fetcher=fetcher)
        self.assertEqual(["example/fallback"], membership["npm"])
        self.assertTrue(all(row["latest_only_fallback"] for row in snapshots))
        self.assertTrue(all("historical_query_error" in row for row in snapshots))

    def test_coverage_is_a_separate_post_construction_operation(self):
        membership = {"npm": ["example/target", "example/unjudged"], "maven": []}
        cases = [{
            "case_id": "e2-007",
            "source_repository": "estools/escope",
            "target_repositories": ["example/target"],
        }]
        # Supply minimal placeholders for every configured case so the audit can
        # perform its post-construction join without influencing membership.
        configured = {
            case_id
            for definition in __import__(
                "build_e2_ecosystem_catalog_audit"
            ).SOURCE_COMPONENTS.values()
            for case_ids in definition["components"].values()
            for case_id in case_ids
        }
        for case_id in sorted(configured - {"e2-007"}):
            cases.append({
                "case_id": case_id,
                "source_repository": "example/source",
                "target_repositories": ["example/missing"],
            })
        rows = audit_coverage(membership, cases)
        row = next(item for item in rows if item["case_id"] == "e2-007")
        self.assertTrue(row["targets_covered"])
        self.assertTrue(row["labels_read_after_membership_construction"])

    def test_complete_package_subset_excludes_failed_package_before_coverage(self):
        snapshots = [
            {"ecosystem": "npm", "package": "escope", "repositories": ["org/a"]},
            {"ecosystem": "npm", "package": "eslint", "repositories": [], "error": "failed"},
        ]
        repositories, complete, failed = complete_package_membership(
            snapshots, "npm"
        )
        self.assertEqual(["org/a"], repositories)
        self.assertIn("escope", complete)
        self.assertNotIn("eslint", complete)
        self.assertEqual(["eslint"], failed)


if __name__ == "__main__":
    unittest.main()

import unittest
import urllib.parse

from build_e2_component_catalog_audit import (
    COMPONENTS,
    audit,
    construct,
    construct_complete,
)


class E2ComponentCatalogAuditTests(unittest.TestCase):
    def test_membership_is_built_without_cases_or_targets(self):
        calls = []

        def fetcher(url):
            calls.append(url)
            return [{"repository_url": "https://github.com/example/consumer"}]

        repositories, snapshots = construct(
            COMPONENTS["mockito"], item_cap=20, page_size=10, workers=2,
            fetcher=fetcher,
        )
        self.assertEqual(["example/consumer"], repositories)
        self.assertEqual(12, len(calls))
        self.assertEqual(12, len(snapshots))
        self.assertEqual({1, 2}, {snapshot["page"] for snapshot in snapshots})

    def test_last_page_is_trimmed_to_the_slice_cap(self):
        def fetcher(url):
            page = int(urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["page"][0])
            return [
                {"repository_url": f"https://github.com/example/p{page}-{row}"}
                for row in range(10)
            ]

        repositories, snapshots = construct(
            COMPONENTS["mockito"], item_cap=15, page_size=10, workers=2,
            fetcher=fetcher,
        )
        self.assertEqual(15, len(repositories))
        self.assertEqual({5, 10}, {len(snapshot["rows"]) for snapshot in snapshots})

    def test_targets_are_read_only_in_separate_coverage_audit(self):
        cases = [
            {"case_id": "e2-025", "source_repository": "mockito/mockito", "target_repositories": ["example/a"]},
            {"case_id": "e2-026", "source_repository": "mockito/mockito", "target_repositories": ["example/b"]},
        ]
        rows = audit(
            "mockito", ["example/a", "example/b", "example/unjudged"], cases, "catalog"
        )
        self.assertTrue(all(row["targets_covered"] for row in rows))
        self.assertTrue(all(row["labels_read_after_membership_construction"] for row in rows))

    def test_complete_query_matches_metadata_count_and_unique_ids(self):
        def fetcher(url):
            page = int(urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["page"][0])
            first = (page - 1) * 10
            return [
                {
                    "id": row,
                    "name": f"package-{row}",
                    "repository_url": f"https://github.com/example/repo-{row}",
                }
                for row in range(first, min(first + 10, 15))
            ]

        repositories, snapshots, completeness = construct_complete(
            COMPONENTS["mockito"], page_size=10, workers=2,
            package_metadata={"dependent_packages_count": 15}, fetcher=fetcher,
            extra_pages=2,
        )
        self.assertEqual(15, len(repositories))
        self.assertEqual(4, len(snapshots))
        self.assertTrue(completeness["complete_query_verified"])
        self.assertEqual(3, completeness["first_empty_page"])

    def test_complete_query_rejects_duplicate_page_rows(self):
        def fetcher(_url):
            return [{"id": 1, "repository_url": "https://github.com/example/repo"}]

        _, _, completeness = construct_complete(
            COMPONENTS["mockito"], page_size=1, workers=2,
            package_metadata={"dependent_packages_count": 2}, fetcher=fetcher,
            extra_pages=1,
        )
        self.assertFalse(completeness["complete_query_verified"])


if __name__ == "__main__":
    unittest.main()

import unittest

from audit_e2_opening_catalog_resolution import crates_tested, crater_log_url


class E2OpeningCatalogResolutionTests(unittest.TestCase):
    def test_crater_count_is_parsed_from_official_download_page(self):
        self.assertEqual(890207, crates_tested('<div class="count">890207 crates tested</div>'))

    def test_log_url_uses_explicit_experiment_baseline_and_unit_kind(self):
        self.assertEqual(
            "https://crater-reports.s3.amazonaws.com/pr-x/master%23abc/gh/owner.repo/log.txt",
            crater_log_url("pr-x", "abc", "gh", "owner.repo"),
        )


if __name__ == "__main__":
    unittest.main()

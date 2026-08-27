import unittest

from audit_formal_e2_registry import audit


class FormalE2RegistryAuditTests(unittest.TestCase):
    def fixture(self):
        catalogs = {"formal": {
            "membership_reads_labels": False,
            "reused_across_source_events": True,
            "repositories": ["org/target", "org/unjudged"],
        }}
        sources = [{
            "candidate_id": "new-1",
            "source_change_family": "new-family",
            "candidate_repository_catalog": "candidate-repositories.json#formal",
            "opening": {"base_commit": "base", "head_commit": "head", "changed_paths": ["src/a.py"]},
        }]
        predictions = [{"candidate_id": "new-1", "created_at": "2026-08-26T01:00:00Z"}]
        labels = [{
            "candidate_id": "new-1",
            "revealed_at": "2026-08-26T02:00:00Z",
            "target_repositories": ["org/target"],
            "arms": {"A0": "pass", "A1": "fail", "A2": "pass"},
            "same_command_all_arms": True,
            "a1_failure_signature_removed_in_a2": True,
        }]
        return catalogs, sources, predictions, labels

    def test_accepts_new_case_with_prior_catalog_prediction_and_strict_arms(self):
        rows, summary = audit(*self.fixture(), set())
        self.assertTrue(rows[0]["formal_e2_eligible"])
        self.assertEqual(1, summary["formal_e2_eligible_count"])

    def test_rejects_prediction_after_label_and_legacy_overlap(self):
        catalogs, sources, predictions, labels = self.fixture()
        predictions[0]["created_at"] = "2026-08-26T03:00:00Z"
        rows, _ = audit(catalogs, sources, predictions, labels, {"new-family"})
        self.assertEqual(
            ["overlaps_legacy_development_family", "prediction_not_before_label_reveal"],
            rows[0]["blockers"],
        )

    def test_rejects_target_missing_from_catalog(self):
        catalogs, sources, predictions, labels = self.fixture()
        labels[0]["target_repositories"] = ["org/missing"]
        rows, _ = audit(catalogs, sources, predictions, labels, set())
        self.assertIn("target_not_covered_by_prior_catalog", rows[0]["blockers"])


if __name__ == "__main__":
    unittest.main()

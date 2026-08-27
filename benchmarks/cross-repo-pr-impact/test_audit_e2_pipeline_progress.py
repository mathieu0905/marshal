import unittest

from audit_e2_pipeline_progress import audit


class E2PipelineProgressAuditTests(unittest.TestCase):
    def test_distinguishes_formal_preconditions_development_and_missing(self):
        cases = [
            {"case_id": "e2-a", "source_change_family": "a", "target_repositories": ["org/a"]},
            {"case_id": "e2-b", "source_change_family": "b", "target_repositories": ["org/b"]},
            {"case_id": "e2-c", "source_change_family": "c", "target_repositories": ["org/c"]},
        ]
        assignments = [
            {"case_id": "e2-a", "candidate_repository_catalog": "candidate-repositories.json#formal", "input_spec_opening_cutoff_conformant": True},
            {"case_id": "e2-b", "candidate_repository_catalog": "candidate-repositories.json#development", "input_spec_opening_cutoff_conformant": False},
        ]
        coverage = {"catalogs": {
            "formal": {"formal_catalog_eligible": True},
            "development": {"formal_catalog_eligible": False, "development_catalog_eligible": True},
        }}
        snapshots = [
            {"case_id": "e2-a", "repositories": [{"repository": "org/a", "status": "available"}]},
            {"case_id": "e2-b", "repositories": [{"repository": "org/b", "status": "available"}]},
        ]
        inputs = [{"case_id": "e2-a"}, {"case_id": "e2-b"}]
        visibility = [{"case_id": "e2-a", "status": "pass"}, {"case_id": "e2-b", "status": "pass"}]
        predictions = [{"case_id": "e2-a", "targets": []}, {"case_id": "e2-b", "targets": []}]
        rows, summary = audit(cases, assignments, coverage, snapshots, inputs, visibility, predictions)
        self.assertEqual("actual_run_formal_input_preconditions", rows[0]["disposition"])
        self.assertEqual("actual_run_development_only", rows[1]["disposition"])
        self.assertEqual("missing_catalog", rows[2]["disposition"])
        self.assertEqual(1, summary["formal_input_preconditions_case_count"])
        self.assertEqual(1, summary["development_only_actual_run_case_count"])
        self.assertEqual(1, summary["missing_catalog_case_count"])
        self.assertEqual(
            [
                "1 cases lack reusable independently constructed catalogs",
                "1 cases use outcome-conditioned external candidate frames",
                "1 actual-run cases do not use the PR-opening state",
                "the relation-group split is not finalized as a blind release split",
            ],
            summary["formal_result_blockers"],
        )

    def test_frozen_split_makes_only_complete_formal_case_publishable(self):
        cases = [{
            "case_id": "e2-a",
            "source_change_family": "a",
            "target_repositories": ["org/a"],
        }]
        assignments = [{
            "case_id": "e2-a",
            "candidate_repository_catalog": "candidate-repositories.json#formal",
            "input_spec_opening_cutoff_conformant": True,
        }]
        coverage = {"catalogs": {"formal": {"formal_catalog_eligible": True}}}
        snapshots = [{
            "case_id": "e2-a",
            "repositories": [{"repository": "org/a", "status": "available"}],
        }]
        rows, summary = audit(
            cases,
            assignments,
            coverage,
            snapshots,
            [{"case_id": "e2-a"}],
            [{"case_id": "e2-a", "status": "pass"}],
            [{"case_id": "e2-a", "targets": []}],
            [{"case_id": "e2-a", "split": "holdout"}],
        )
        self.assertTrue(rows[0]["formal_scoring_eligible"])
        self.assertEqual(1, summary["formal_scoring_eligible_case_count"])
        self.assertTrue(summary["formal_subset_result_publishable"])


if __name__ == "__main__":
    unittest.main()

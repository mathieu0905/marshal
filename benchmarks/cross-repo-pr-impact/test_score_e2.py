import unittest

from score_e2 import score_e2


class E2ScoreTests(unittest.TestCase):
    def test_denominators_include_missed_targets(self):
        cases = [{
            "case_id": "e2-a",
            "target_repositories": ["org/a", "org/b"],
        }]
        predictions = [{
            "case_id": "e2-a",
            "targets": [{
                "repository": "org/a",
                "paths": ["fix.py"],
                "tests": [],
                "commands": [],
                "execution_result": "not_assessed",
            }],
        }]
        report = score_e2(
            cases, predictions, {"e2-a": {"org/a": ["fix.py"], "org/b": ["b.py"]}}
        )
        self.assertEqual(0.5, report["target_repository_retrieval"]["macro_recall"])
        self.assertEqual(0.5, report["check_position_retrieval"]["hit_rate"])
        self.assertEqual(0.0, report["runnable_check_rate"]["rate"])
        self.assertEqual(1.0, report["failure_recovery_judgment"]["not_assessed_rate"])

    def test_extra_predictions_remain_unjudged(self):
        cases = [{"case_id": "e2-a", "target_repositories": ["org/a"]}]
        predictions = [{
            "case_id": "e2-a",
            "targets": [{
                "repository": "org/unknown",
                "paths": [],
                "tests": [],
                "commands": [],
                "execution_result": "not_assessed",
            }],
        }]
        report = score_e2(cases, predictions, {})
        retrieval = report["target_repository_retrieval"]
        self.assertEqual(1, retrieval["unjudged_repository_predictions"])
        self.assertFalse(retrieval["precision_reported"])

    def test_explicit_formal_holdout_status_is_preserved(self):
        report = score_e2(
            [{"case_id": "e2-a", "target_repositories": ["org/a"]}],
            [],
            {},
            "formal_holdout",
        )
        self.assertEqual("formal_holdout", report["dataset_status"])


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from pathlib import Path

from build_restraint_e3_set import build
from build_ratchet_sequences import build as build_ratchets
from score_ratchet_sequences import score as score_ratchets
from score_product_evaluation import score_product
from verify_restraint_e3_set import verify

TEST_WORK = Path(__file__).resolve().parents[2] / ".work" / "test-construct-validity"
TEST_WORK.mkdir(parents=True, exist_ok=True)


class RestraintDatasetTests(unittest.TestCase):
    def test_builder_and_independent_verifier_accept_ten_cases(self):
        with tempfile.TemporaryDirectory(dir=TEST_WORK) as temporary:
            output = Path(temporary)
            report = build(output)
            checked = verify(output)
        self.assertEqual(report["case_count"], 10)
        self.assertEqual(report["project_pack_count"], 3)
        self.assertTrue(checked["verified"])
        self.assertEqual(checked["raw_evidence_verified_count"], 10)


class ProductScorerTests(unittest.TestCase):
    def test_self_report_is_ignored_without_evaluator_execution(self):
        report = score_product(
            [{"case_id": "e2", "target_repositories": ["org/target"]}],
            [], [],
            [{"case_id": "e2", "targets": [{
                "repository": "org/target",
                "execution_result": "fail_without_companion_pass_with_companion",
            }]}],
            [],
        )
        execution = report["e2"]["causal_execution"]
        self.assertEqual(execution["strict_a0_a1_a2_accuracy"], 0.0)
        self.assertEqual(execution["not_assessed_rate"], 1.0)
        self.assertFalse(execution["prediction_self_reports_used"])

    def test_evidence_backed_e2_and_restraint_are_scored(self):
        card3 = {"command": ["test"], "arm_logs": {"A0": "a0", "A1": "a1", "A2": "a2"}}
        card2 = {"command": ["test"], "arm_logs": {"A0": "a0", "A1": "a1"}}
        report = score_product(
            [{"case_id": "e2", "target_repositories": ["org/positive"]}],
            [{"pack_id": "pack", "target_repository": "org/negative"}],
            [{
                "pack_id": "pack", "bounded_universe_complete": True,
                "candidate_repositories": ["org/positive", "org/negative"],
                "breakage_repositories": ["org/positive"],
                "bounded_negative_repositories": ["org/negative"],
            }],
            [
                {"case_id": "e2", "targets": [{"repository": "org/positive"}]},
                {"case_id": "pack", "targets": [
                    {"repository": "org/positive", "verdict": "breakage"},
                    {"repository": "org/negative", "verdict": "compatible"},
                ]},
            ],
            [
                {"case_id": "e2", "repository": "org/positive", "status": "assessed", "arms": {"A0": {"exit_code": 0}, "A1": {"exit_code": 1}, "A2": {"exit_code": 0}}, "evidence": card3},
                {"case_id": "pack", "repository": "org/positive", "status": "assessed", "arms": {"A0": {"exit_code": 0}, "A1": {"exit_code": 1}, "A2": {"exit_code": 0}}, "evidence": card3},
                {"case_id": "pack", "repository": "org/negative", "status": "assessed", "arms": {"A0": {"exit_code": 0}, "A1": {"exit_code": 0}}, "evidence": card2},
            ],
        )
        self.assertEqual(report["e2"]["causal_execution"]["strict_a0_a1_a2_accuracy"], 1.0)
        self.assertEqual(report["restraint"]["confusion"], {"tp": 1, "fp": 0, "tn": 1, "fn": 0, "abstained": 0})
        self.assertEqual(report["restraint"]["precision"], 1.0)
        self.assertEqual(report["restraint"]["specificity"], 1.0)


class RatchetSequenceTests(unittest.TestCase):
    def test_builder_emits_three_ordered_sequences(self):
        release = Path(__file__).resolve().parent / "results" / "formal-e2-benchmark-50-v2-2026-08-30"
        with tempfile.TemporaryDirectory(dir=TEST_WORK) as temporary:
            report = build_ratchets(release, Path(temporary))
        self.assertEqual(report["sequence_count"], 3)
        self.assertEqual(report["recurrence_count"], 3)

    def test_scorer_requires_registration_schedule_execution_block_and_control(self):
        sequence = {
            "sequence_id": "seq",
            "registration": {"check_id": "check"},
        }
        perfect = score_ratchets([sequence], [{
            "sequence_id": "seq",
            "registered_check_id": "check",
            "recurrence_scheduled_check_ids": ["check"],
            "unrelated_scheduled_check_ids": [],
            "recurrence_execution": {"status": "assessed", "exit_code": 1, "evidence_log": "a1.log"},
            "recurrence_decision": "block",
        }])
        missing_execution = score_ratchets([sequence], [{
            "sequence_id": "seq",
            "registered_check_id": "check",
            "recurrence_scheduled_check_ids": ["check"],
            "unrelated_scheduled_check_ids": [],
            "recurrence_execution": {"status": "not_assessed"},
            "recurrence_decision": "not_assessed",
        }])
        self.assertEqual(perfect["end_to_end_ratchet_rate"], 1.0)
        self.assertEqual(missing_execution["end_to_end_ratchet_rate"], 0.0)


if __name__ == "__main__":
    unittest.main()

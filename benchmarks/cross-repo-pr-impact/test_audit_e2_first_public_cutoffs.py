import unittest

from audit_e2_first_public_cutoffs import audit, exclusion_for_policy


class E2FirstPublicCutoffAuditTests(unittest.TestCase):
    def test_classifies_after_opening_no_pr_and_release_cases(self):
        self.assertEqual(
            "opening_state_lacks_causal_change",
            exclusion_for_policy(
                "causal_commit_first_public_time_after_pr_creation"
            )[0],
        )
        self.assertEqual(
            "no_source_opening_event",
            exclusion_for_policy(
                "causal_direct_commit_public_timestamp_no_source_pr"
            )[0],
        )
        self.assertEqual(
            "release_transition_has_no_recoverable_opening_snapshot",
            exclusion_for_policy(
                "causal_direct_commit_diff_with_release_publication_cutoff"
            )[0],
        )

    def test_audit_retains_opening_case_and_excludes_nonopening_case(self):
        assignments = [
            {
                "case_id": "e2-a",
                "observation_cutoff": "2020-01-01T00:00:00Z",
                "cutoff_policy": "pull_request_creation_with_causal_head_already_present",
                "input_spec_opening_cutoff_conformant": True,
            },
            {
                "case_id": "e2-b",
                "observation_cutoff": "2020-01-02T00:00:00Z",
                "cutoff_policy": "causal_direct_commit_public_timestamp_no_source_pr",
                "input_spec_opening_cutoff_conformant": False,
            },
        ]
        sources = {
            "e2-a": {
                "repository": "org/a",
                "pull_request_number": 1,
                "candidate_commit": "a" * 40,
            },
            "e2-b": {
                "repository": "org/b",
                "pull_request_number": None,
                "candidate_commit": "b" * 40,
            },
        }
        rows, summary = audit(assignments, sources)
        self.assertEqual("opening_snapshot_recovered", rows[0]["disposition"])
        self.assertEqual("excluded_nonopening_source_state", rows[1]["disposition"])
        self.assertEqual(1, summary["opening_snapshot_recovered_case_count"])
        self.assertEqual(1, summary["formal_source_state_excluded_case_count"])

    def test_unknown_nonopening_policy_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "unclassified"):
            exclusion_for_policy("unknown")


if __name__ == "__main__":
    unittest.main()

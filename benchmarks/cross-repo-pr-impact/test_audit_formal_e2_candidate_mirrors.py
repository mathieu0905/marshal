import unittest
from pathlib import Path

from audit_formal_e2_candidate_mirrors import audit


class FormalE2CandidateMirrorAuditTests(unittest.TestCase):
    def test_audit_deduplicates_commits_and_counts_snapshot_references(self):
        snapshots = [
            {"case_id": "a", "repositories": [
                {"repository": "org/repo", "status": "available", "commit": "1"},
                {"repository": "org/future", "status": "not_created_by_cutoff"},
            ]},
            {"case_id": "b", "repositories": [
                {"repository": "org/repo", "status": "available", "commit": "1"},
                {"repository": "org/repo2", "status": "available", "commit": "2"},
            ]},
        ]
        seen = {}

        def checker(repository, commits, mirror_root):
            seen[repository] = commits
            return {
                "repository": repository, "status": "available",
                "requested_commit_count": len(commits), "missing_commits": [],
            }

        rows, metrics = audit(snapshots, Path("mirrors"), 2, checker)
        self.assertEqual({"org/repo": ["1"], "org/repo2": ["2"]}, seen)
        self.assertEqual(3, metrics["available_snapshot_reference_count"])
        self.assertEqual(2, metrics["unique_cutoff_commit_count"])
        self.assertTrue(metrics["all_cutoff_code_available_offline"])
        self.assertEqual(2, len(rows))

    def test_missing_commit_prevents_offline_readiness(self):
        snapshots = [{"case_id": "a", "repositories": [
            {"repository": "org/repo", "status": "available", "commit": "1"},
        ]}]

        def checker(repository, commits, mirror_root):
            return {
                "repository": repository, "status": "commit_missing",
                "requested_commit_count": 1, "missing_commits": ["1"],
            }

        _, metrics = audit(snapshots, Path("mirrors"), 1, checker)
        self.assertFalse(metrics["all_cutoff_code_available_offline"])
        self.assertEqual(1, metrics["missing_cutoff_commit_count"])


if __name__ == "__main__":
    unittest.main()

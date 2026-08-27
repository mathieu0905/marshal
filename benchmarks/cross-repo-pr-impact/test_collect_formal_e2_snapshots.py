import tempfile
import unittest
from pathlib import Path

from collect_formal_e2_snapshots import collect_checkpointed


class FormalE2SnapshotTests(unittest.TestCase):
    def test_checkpoint_resumes_terminal_cases(self):
        assignments = [
            {"case_id": "a", "candidate_repository_catalog": "candidate-repositories.json#c", "observation_cutoff": "2024-01-01T00:00:00Z"},
            {"case_id": "b", "candidate_repository_catalog": "candidate-repositories.json#c", "observation_cutoff": "2024-01-02T00:00:00Z"},
        ]
        calls = []

        def fake(catalogs, selected, workers, prior_rows=None):
            case_id = selected[0]["case_id"]
            calls.append(case_id)
            return [{
                "case_id": case_id,
                "repositories": [{"repository": "org/repo", "status": "available"}],
            }]

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            first = collect_checkpointed({"c": {}}, assignments, output, 1, fake)
            second = collect_checkpointed({"c": {}}, assignments, output, 1, fake)
        self.assertEqual(["a", "b"], calls)
        self.assertEqual(2, first["completed_case_count"])
        self.assertEqual(2, second["completed_case_count"])

    def test_checkpoint_writes_completed_batches(self):
        assignments = [
            {"case_id": letter, "candidate_repository_catalog": "candidate-repositories.json#c", "observation_cutoff": "2024-01-01T00:00:00Z"}
            for letter in ("a", "b", "c")
        ]
        calls = []

        def fake(catalogs, selected, workers, prior_rows=None):
            calls.append([row["case_id"] for row in selected])
            return [{
                "case_id": row["case_id"],
                "repositories": [{"repository": "org/repo", "status": "available"}],
            } for row in selected]

        with tempfile.TemporaryDirectory() as temporary:
            metrics = collect_checkpointed(
                {"c": {}}, assignments, Path(temporary), 1, fake, case_batch_size=2
            )
        self.assertEqual([["a", "b"], ["c"]], calls)
        self.assertEqual(3, metrics["completed_case_count"])


if __name__ == "__main__":
    unittest.main()

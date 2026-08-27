import unittest
from types import SimpleNamespace

from run_formal_e2_marshal_native import predict


class FakePack:
    def contracts_hit(self, scope):
        return ["contract.example"]

    def list_invariants(self, scope):
        return [
            SimpleNamespace(domain="cross-repo", location_repo="org/target", location_path="a.py", location_test=None, run_command=None),
            SimpleNamespace(domain="cross-repo", location_repo="org/outside", location_path=None, location_test=None, run_command=None),
        ]


class FormalE2NativeMarshalTests(unittest.TestCase):
    def test_predictions_are_bounded_by_catalog(self):
        inputs = [{
            "case_id": "formal-1",
            "candidate_repository_catalog": "candidate-repositories.json#c",
            "source": {"repository": "org/source", "changed_paths": ["src/a.py"]},
        }]
        catalogs = {"c": {"repositories": ["org/source", "org/target"]}}
        predictions, diagnostics = predict(inputs, catalogs, FakePack(), "2026-08-26T00:00:00Z")
        self.assertEqual("org/target", predictions[0]["targets"][0]["repository"])
        self.assertEqual(1, diagnostics[0]["predicted_target_count"])
        self.assertFalse(diagnostics[0]["candidate_code_read"])


if __name__ == "__main__":
    unittest.main()

import unittest

from triage_formal_e2_contract_changes import relation_score


class FormalE2ContractTriageTests(unittest.TestCase):
    def test_ranks_removed_consumer_identifier(self):
        source = "-def old_method():\n+def new_method():\n"
        target = "-client.old_method()\n+client.new_method()\n"
        result = relation_score(source, target)
        self.assertIn("old_method", result["removed_identifier_overlap"])
        self.assertIn("new_method", result["replacement_identifier_overlap"])
        self.assertGreaterEqual(result["triage_score"], 1)


if __name__ == "__main__":
    unittest.main()

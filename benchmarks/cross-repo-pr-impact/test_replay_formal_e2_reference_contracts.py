import unittest

from replay_formal_e2_reference_contracts import (
    count_signature,
    count_token,
    diff_token_paths,
    token_quality,
)


class FormalE2ReferenceContractTests(unittest.TestCase):
    def test_extracts_deleted_token_path(self):
        patch = "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n-old_method()\n"
        self.assertEqual({"a.py"}, diff_token_paths(patch, "-")["old_method"])

    def test_counts_identifier_boundaries(self):
        self.assertEqual(1, count_token(b"old_method old_method_extra", "old_method"))
        self.assertEqual(1, count_signature(b"  client.old_method()\n", "client.old_method()"))

    def test_downranks_generic_token(self):
        self.assertEqual(0, token_quality("interface"))
        self.assertGreater(token_quality("old_method"), token_quality("interface"))


if __name__ == "__main__":
    unittest.main()

import unittest

from audit_e2_input_visibility import audit_patch


class E2InputVisibilityAuditTests(unittest.TestCase):
    def setUp(self):
        self.item = {
            "case_id": "e2-test",
            "source": {"changed_paths": ["pom.xml"]},
        }

    def test_code_only_patch_passes(self):
        row = audit_patch(
            self.item,
            b"diff --git a/pom.xml b/pom.xml\n--- a/pom.xml\n+++ b/pom.xml\n",
            ["example/target"],
        )
        self.assertEqual("pass", row["status"])

    def test_target_and_coordination_metadata_fail(self):
        row = audit_patch(
            self.item,
            b"diff --git a/pom.xml b/pom.xml\n+Depends-On: https://review.opendev.org/1\n+example/target\n",
            ["example/target"],
        )
        self.assertEqual("fail", row["status"])
        self.assertTrue(row["forbidden_metadata_hits"])
        self.assertEqual(["example/target"], row["target_name_hits"])


if __name__ == "__main__":
    unittest.main()

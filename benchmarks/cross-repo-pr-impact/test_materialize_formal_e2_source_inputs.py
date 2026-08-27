import unittest

from materialize_formal_e2_source_inputs import materialize


class FormalE2SourceInputTests(unittest.TestCase):
    def fixture(self):
        return [{
            "candidate_id": "formal-opendev-123",
            "candidate_repository_catalog": "candidate-repositories.json#formal-catalog",
            "label_review_state": "not_started",
            "opening": {
                "provider": "gerrit",
                "repository": "example/source",
                "number": 123,
                "subject": "Change public API",
                "base_commit": "a" * 40,
                "head_commit": "b" * 40,
                "changed_paths": ["src/api.py"],
                "created_at": "2024-01-02 03:04:05.000000000",
            },
        }]

    def test_materializes_opening_revision_without_label_fields(self):
        row = materialize(self.fixture())[0]
        self.assertEqual("formal-opendev-123", row["case_id"])
        self.assertEqual("gerrit_opening_revision", row["source"]["source_change_kind"])
        self.assertEqual("b" * 40, row["source"]["candidate_commit"])
        self.assertEqual(
            "https://review.opendev.org/changes/123/revisions/1/patch",
            row["source"]["patch_url"],
        )
        rendered = str(row).lower()
        self.assertNotIn("target", rendered)
        self.assertNotIn("depends-on", rendered)

    def test_rejects_started_label_review(self):
        events = self.fixture()
        events[0]["label_review_state"] = "started"
        with self.assertRaises(ValueError):
            materialize(events)


if __name__ == "__main__":
    unittest.main()

import unittest

from select_strict_e2_public_sources import break_score, select


def row(identifier, subject, paths):
    return {
        "candidate_id": identifier,
        "opening": {
            "subject": subject,
            "changed_paths": paths,
            "created_at": "2025-01-01 00:00:00.000000000",
        },
    }


class StrictE2PublicSourceSelectionTests(unittest.TestCase):
    def test_removal_in_production_ranks_above_docs(self):
        breaking = row("a", "Remove deprecated API", ["src/api.py"])
        docs = row("b", "Update guide", ["doc/guide.rst"])
        self.assertGreater(break_score(breaking), break_score(docs))
        self.assertEqual("a", select([docs, breaking], 1)[0]["candidate_id"])


if __name__ == "__main__":
    unittest.main()

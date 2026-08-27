import unittest

from build_formal_e2_release import assign_splits, subset_sum


class FormalE2ReleaseTests(unittest.TestCase):
    def test_subset_sum_is_exact(self):
        self.assertEqual({"a", "b"}, subset_sum([("a", 4), ("b", 6), ("c", 8)], 10))

    def test_split_keeps_source_families_together(self):
        labels = []
        for index in range(50):
            labels.append({"source_change_family": f"family-{index // 2}"})
        splits = assign_splits(labels)
        counts = {name: 0 for name in ("development", "evaluation", "holdout")}
        for row in labels:
            counts[splits[row["source_change_family"]]] += 1
        self.assertEqual({"development": 30, "evaluation": 10, "holdout": 10}, counts)


if __name__ == "__main__":
    unittest.main()

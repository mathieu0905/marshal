import unittest

from freeze_e2_grouped_split import REPAIR_TEMPLATES, grouped_cases


class E2GroupedSplitTests(unittest.TestCase):
    def test_same_family_mechanism_and_repair_template_are_connected(self):
        original = dict(REPAIR_TEMPLATES)
        try:
            REPAIR_TEMPLATES.clear()
            REPAIR_TEMPLATES.update({"a": "repair-1", "b": "repair-2", "c": "repair-2"})
            cases = [
                {"case_id": "a", "source_repository": "src/a", "target_repositories": ["dst/a"], "source_change_family": "family", "mechanism": "one"},
                {"case_id": "b", "source_repository": "src/b", "target_repositories": ["dst/b"], "source_change_family": "family", "mechanism": "two"},
                {"case_id": "c", "source_repository": "src/c", "target_repositories": ["dst/c"], "source_change_family": "other", "mechanism": "three"},
            ]
            components, _ = grouped_cases(cases)
            self.assertEqual([["a", "b", "c"]], components)
        finally:
            REPAIR_TEMPLATES.clear()
            REPAIR_TEMPLATES.update(original)

    def test_relation_with_multiple_targets_connects_to_matching_edge(self):
        original = dict(REPAIR_TEMPLATES)
        try:
            REPAIR_TEMPLATES.clear()
            REPAIR_TEMPLATES.update({"a": "one", "b": "two"})
            cases = [
                {"case_id": "a", "source_repository": "src/a", "target_repositories": ["dst/a", "dst/b"], "source_change_family": "one", "mechanism": "one"},
                {"case_id": "b", "source_repository": "src/a", "target_repositories": ["dst/b"], "source_change_family": "two", "mechanism": "two"},
            ]
            components, _ = grouped_cases(cases)
            self.assertEqual([["a", "b"]], components)
        finally:
            REPAIR_TEMPLATES.clear()
            REPAIR_TEMPLATES.update(original)


if __name__ == "__main__":
    unittest.main()

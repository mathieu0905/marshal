#!/usr/bin/env python3
"""Focused scoring tests for partial predictions and invalid input."""

from __future__ import annotations

import unittest

from score import score, validate_prediction_set


def target(repository: str, paths: list[str]) -> dict:
    return {
        "repository": repository,
        "changed_paths": [*paths, "unrelated.txt"],
        "label_scope": "causal_impact",
        "expected_checks": {
            "paths": paths,
            "tests": [paths[0]],
            "commands": [["tool", "check"]],
            "expected_result": "fail_without_companion_pass_with_companion",
        },
        "evidence": [{"level": "ci_contrast_proven"}],
    }


class ScoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cases = [{
            "case_id": "case-1",
            "project": "project-a",
            "source": {
                "repository": "org/spec",
                "pull_request": {"created": "2024-06-01T00:00:00Z"},
            },
            "relations": [
                {"target_repository": "org/a", "relation_kind": "specification_implementation"},
                {"target_repository": "org/b", "relation_kind": "specification_implementation"},
            ],
            "targets": [target("org/a", ["a.py", "b.py"]), target("org/b", ["c.py"])],
        }]

    def test_partial_prediction_has_recall_without_false_precision_claim(self) -> None:
        predictions = [{
            "case_id": "case-1",
            "targets": [
                {
                    "repository": "org/a",
                    "paths": ["a.py"],
                    "tests": ["a.py"],
                    "commands": [["tool", "other"]],
                    "execution_result": "fail_without_companion_pass_with_companion",
                },
                {
                    "repository": "org/unjudged",
                    "paths": [],
                    "tests": [],
                    "commands": [],
                    "execution_result": None,
                },
            ],
        }]
        report = score(self.cases, predictions)
        primary = report["primary_task"]
        diagnostics = report["secondary_diagnostics"]
        self.assertEqual(primary["known_target_macro_recall"], 0.5)
        self.assertEqual(primary["mean_reciprocal_rank"], 1.0)
        self.assertEqual(primary["recall_at_1"], 0.5)
        self.assertFalse(primary["precision_reported"])
        self.assertEqual(primary["unjudged_repository_predictions"], 1)
        self.assertEqual(primary["repository_predictions_per_case"]["maximum"], 2)
        self.assertEqual(primary["by_project"]["project-a"]["cases"], 1)
        self.assertEqual(primary["by_year"]["2024"]["known_target_macro_recall"], 0.5)
        self.assertEqual(
            primary["by_directed_repository_relation"]["org/spec -> org/a"][
                "known_target_macro_recall"
            ],
            1.0,
        )
        self.assertEqual(
            primary["by_evidence_level"]["ci_contrast_proven"]["cases"], 2
        )
        self.assertEqual(
            diagnostics["curated_impact_position"]["path_recall_at_5"], 0.25
        )
        self.assertEqual(diagnostics["check_selection"]["exact_command_recall"], 0.0)
        self.assertEqual(diagnostics["execution_result"]["accuracy"], 0.5)

    def test_missing_prediction_scores_zero_and_wrong_execution_result_fails(self) -> None:
        second_case = {
            "case_id": "case-2",
            "project": "project-a",
            "source": {
                "repository": "org/spec",
                "pull_request": {"created": "2025-01-01T00:00:00Z"},
            },
            "relations": [
                {"target_repository": "org/c", "relation_kind": "specification_implementation"},
            ],
            "targets": [target("org/c", ["d.py"])],
        }
        predictions = [{
            "case_id": "case-1",
            "targets": [{
                "repository": "org/a",
                "paths": ["a.py"],
                "tests": [],
                "commands": [],
                "execution_result": "pass",
            }],
        }]
        report = score([*self.cases, second_case], predictions)
        self.assertEqual(report["missing_predictions"], 1)
        self.assertEqual(report["primary_task"]["known_target_macro_recall"], 0.25)
        self.assertEqual(report["primary_task"]["mean_reciprocal_rank"], 0.5)
        self.assertEqual(
            report["secondary_diagnostics"]["execution_result"]["accuracy"],
            0.0,
        )

    def test_repository_order_controls_reciprocal_rank(self) -> None:
        predictions = [{
            "case_id": "case-1",
            "targets": [
                {
                    "repository": "org/unjudged",
                    "paths": [],
                    "tests": [],
                    "commands": [],
                    "execution_result": None,
                },
                {
                    "repository": "org/a",
                    "paths": [],
                    "tests": [],
                    "commands": [],
                    "execution_result": None,
                },
            ],
        }]
        primary = score(self.cases, predictions)["primary_task"]
        self.assertEqual(primary["mean_reciprocal_rank"], 0.5)
        self.assertEqual(primary["recall_at_1"], 0.0)
        self.assertEqual(primary["recall_at_3"], 0.5)

    def test_unknown_case_id_is_rejected(self) -> None:
        predictions = [{"case_id": "unknown", "targets": []}]
        with self.assertRaisesRegex(SystemExit, "unknown case_id"):
            validate_prediction_set(self.cases, predictions)


if __name__ == "__main__":
    unittest.main()

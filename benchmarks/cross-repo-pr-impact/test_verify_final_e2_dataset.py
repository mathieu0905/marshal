#!/usr/bin/env python3
"""Negative and coverage tests for the strict-E2 evidence parser."""

from __future__ import annotations

import json
import unittest

from verify_final_e2_dataset import ARM_RULES, CASES, ROOT, read_tsv, verify_structured_arms


class FinalE2EvidenceTests(unittest.TestCase):
    def test_every_case_has_three_structured_arm_rules(self) -> None:
        self.assertEqual(set(ARM_RULES), {case["case_id"] for case in CASES})
        self.assertTrue(all(set(rules) == {"A0", "A1", "A2"} for rules in ARM_RULES.values()))

    def test_all_fifty_cases_parse_to_pass_fail_pass(self) -> None:
        json_cache = {}
        tsv_cache = {}
        for case in CASES:
            arms, _ = verify_structured_arms(case["case_id"], json_cache, tsv_cache)
            self.assertEqual(
                {arm: result["derived_result"] for arm, result in arms.items()},
                {"A0": "pass", "A1": "fail", "A2": "pass"},
            )

    def test_json_arm_mutation_is_rejected(self) -> None:
        relative = "results/requirements-cinder-active-pilot-2026-08-24/summary.json"
        document = json.loads((ROOT / relative).read_text(encoding="utf-8"))
        document["arms"]["a1"]["exit_status"] = 0
        with self.assertRaises(AssertionError):
            verify_structured_arms("e2-001", {relative: document}, {})

    def test_tsv_arm_mutation_is_rejected(self) -> None:
        relative = "results/log4j-neqsim-historical-screening-2026-08-24/run-results.tsv"
        rows = read_tsv(ROOT / relative)
        for row in rows:
            if row["config"] == "a1":
                row["exit_code"] = "0"
        with self.assertRaises(AssertionError):
            verify_structured_arms("e2-017", {}, {relative: rows})

    def test_repeated_terser_exit_mutation_is_rejected(self) -> None:
        cache = {}
        for repetition in (1, 2, 3):
            relative = f"results/terser-unified-430-repetitions-2026-08-24/repeat-{repetition}/run-results.tsv"
            cache[relative] = read_tsv(ROOT / relative)
        for row in cache["results/terser-unified-430-repetitions-2026-08-24/repeat-2/run-results.tsv"]:
            if row["repository"] == "assetgraph/assetgraph-builder" and row["config"] == "a2":
                row["exit_code"] = "1"
        with self.assertRaises(AssertionError):
            verify_structured_arms("e2-009", {}, cache)


if __name__ == "__main__":
    unittest.main()

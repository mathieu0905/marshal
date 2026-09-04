#!/usr/bin/env python3
"""Score a prediction against the full cross-repo execution gold."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _plan_map(rows: list[dict]) -> dict[str, tuple[str, str]]:
    return {
        row["invariant_id"]: (row["location_repo"], row["executor_kind"])
        for row in rows
    }


def _result_map(rows: list[dict]) -> dict[str, bool]:
    return {row["invariant_id"]: row["passed"] for row in rows}


def score(prediction: dict, gold: dict) -> dict:
    expected = gold["capable_cross_repo_runner"]
    pred_plan = prediction["plan"]["invariants"]
    gold_plan = gold["planning"]["invariants"]
    checks = {
        "tier": prediction["classification"]["tier"] == gold["classification"]["tier"],
        "contract_set": set(prediction["classification"]["contracts_hit"])
        == set(gold["classification"]["contracts_hit"]),
        "invariant_set": {row["invariant_id"] for row in pred_plan}
        == {row["invariant_id"] for row in gold_plan},
        "route_map": _plan_map(pred_plan) == _plan_map(gold_plan),
        "execution_result": (
            prediction["execution"]["status"] == expected["execution"]["status"]
            and _result_map(prediction["execution"]["results"])
            == _result_map(expected["execution"]["results"])
            and {row["invariant_id"] for row in prediction["execution"]["not_run"]}
            == set(expected["execution"]["not_run"])
        ),
        "verdict": prediction["decision"] == expected["decision"],
    }
    checks["end_to_end"] = all(checks.values())
    return {
        "schema_version": "marshal-gate-score-1",
        "case_id": gold["case_id"],
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("prediction", type=Path)
    parser.add_argument("gold", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = score(
        json.loads(args.prediction.read_text(encoding="utf-8")),
        json.loads(args.gold.read_text(encoding="utf-8")),
    )
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

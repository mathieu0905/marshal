#!/usr/bin/env python3
"""Run current Marshal and score every accepted construction case."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from run_current_marshal import run
from score_prediction import score


def run_suite(cases_root: Path, output_root: Path) -> dict:
    rows = []
    for case_dir in sorted(path for path in cases_root.iterdir() if path.is_dir()):
        public_case = case_dir / "public" / "case.json"
        gold_path = case_dir / "private" / "gold.json"
        if not public_case.is_file() and not gold_path.is_file():
            continue
        assert public_case.is_file() and gold_path.is_file()
        prediction = run(public_case)
        gold = json.loads(gold_path.read_text(encoding="utf-8"))
        case_score = score(prediction, gold)
        case_output = output_root / case_dir.name
        case_output.mkdir(parents=True, exist_ok=True)
        (case_output / "current-marshal-prediction.json").write_text(
            json.dumps(prediction, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (case_output / "score.json").write_text(
            json.dumps(case_score, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        rows.append(case_score)

    keys = [
        "tier",
        "contract_set",
        "invariant_set",
        "route_map",
        "execution_result",
        "verdict",
        "end_to_end",
    ]
    totals = {
        key: {
            "correct": sum(row["checks"][key] for row in rows),
            "total": len(rows),
        }
        for key in keys
    }
    return {
        "schema_version": "marshal-gate-suite-score-1",
        "case_count": len(rows),
        "metrics": totals,
        "formal_benchmark": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cases-root",
        type=Path,
        default=Path(__file__).resolve().parent / "cases",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(__file__).resolve().parent / "results",
    )
    args = parser.parse_args()
    result = run_suite(args.cases_root, args.output_root)
    args.output_root.mkdir(parents=True, exist_ok=True)
    (args.output_root / "summary.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

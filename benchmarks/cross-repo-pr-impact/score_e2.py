#!/usr/bin/env python3
"""Score strict-E2 candidate-bounded predictions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from score import reciprocal_rank, safe_mean, set_recall, unique_ordered, validate_prediction


ROOT = Path(__file__).resolve().parent
E2_INDEX = ROOT / "results" / "final-e2-dataset-50-2026-08-25" / "final-index.jsonl"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def score_e2(
    cases: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    locations: dict[str, dict[str, list[str]]],
    dataset_status: str = "development_diagnostic",
) -> dict[str, Any]:
    for index, prediction in enumerate(predictions, start=1):
        validate_prediction(prediction, index)
    prediction_by_id = {row["case_id"]: row for row in predictions}
    if len(prediction_by_id) != len(predictions):
        raise ValueError("duplicate prediction case_id")
    case_by_id = {row["case_id"]: row for row in cases}
    unknown = sorted(set(prediction_by_id) - set(case_by_id))
    if unknown:
        raise ValueError(f"unknown prediction cases: {unknown}")

    case_records = []
    target_records = []
    unjudged_predictions = 0
    for case in cases:
        prediction = prediction_by_id.get(case["case_id"], {"targets": []})
        predicted = prediction["targets"]
        ranked = unique_ordered([target["repository"] for target in predicted])
        gold = set(case["target_repositories"])
        unjudged_predictions += len(set(ranked) - gold)
        record = {
            "case_id": case["case_id"],
            "target_recall": set_recall(gold, set(ranked)),
            "reciprocal_rank": reciprocal_rank(gold, ranked),
            "recall_at_1": set_recall(gold, set(ranked[:1])),
            "recall_at_3": set_recall(gold, set(ranked[:3])),
            "recall_at_5": set_recall(gold, set(ranked[:5])),
            "prediction_count": len(ranked),
        }
        case_records.append(record)
        predicted_by_repo = {target["repository"]: target for target in predicted}
        for repository in sorted(gold):
            target = predicted_by_repo.get(repository)
            expected_paths = set(locations.get(case["case_id"], {}).get(repository, []))
            predicted_paths = set(target["paths"] if target else [])
            path_hit = bool(expected_paths & predicted_paths) if expected_paths else False
            runnable = bool(target and target["commands"])
            execution_result = target["execution_result"] if target else "not_assessed"
            judgment_correct = (
                execution_result == "fail_without_companion_pass_with_companion"
            )
            target_records.append({
                "case_id": case["case_id"],
                "repository": repository,
                "repository_found": repository in ranked,
                "rank": ranked.index(repository) + 1 if repository in ranked else None,
                "expected_check_paths": sorted(expected_paths),
                "predicted_check_paths": sorted(predicted_paths),
                "check_position_found": path_hit,
                "runnable_check_proposed": runnable,
                "execution_result": execution_result,
                "failure_recovery_judgment_correct": judgment_correct,
            })

    report = {
        "schema_version": "1.0",
        "evidence_layer": "E2",
        "dataset_status": dataset_status,
        "case_count": len(case_records),
        "target_occurrence_count": len(target_records),
        "target_repository_retrieval": {
            "macro_recall": safe_mean([row["target_recall"] for row in case_records]),
            "mean_reciprocal_rank": safe_mean([row["reciprocal_rank"] for row in case_records]),
            "recall_at_1": safe_mean([row["recall_at_1"] for row in case_records]),
            "recall_at_3": safe_mean([row["recall_at_3"] for row in case_records]),
            "recall_at_5": safe_mean([row["recall_at_5"] for row in case_records]),
            "unjudged_repository_predictions": unjudged_predictions,
            "precision_reported": False,
        },
        "check_position_retrieval": {
            "hit_rate": safe_mean([
                1.0 if row["check_position_found"] else 0.0 for row in target_records
            ]),
            "denominator": len(target_records),
        },
        "runnable_check_rate": {
            "rate": safe_mean([
                1.0 if row["runnable_check_proposed"] else 0.0 for row in target_records
            ]),
            "denominator": len(target_records),
        },
        "failure_recovery_judgment": {
            "accuracy": safe_mean([
                1.0 if row["failure_recovery_judgment_correct"] else 0.0
                for row in target_records
            ]),
            "not_assessed_rate": safe_mean([
                1.0 if row["execution_result"] == "not_assessed" else 0.0
                for row in target_records
            ]),
            "denominator": len(target_records),
        },
        "case_records": case_records,
        "target_records": target_records,
        "limitations": [
            "Non-target candidates are unjudged; precision, F1, false-positive rate, and specificity are not reported.",
            "This report covers only cases with completed independent catalog, cutoff snapshot, visibility audit, and actual system run.",
        ],
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("predictions", type=Path, nargs="+")
    parser.add_argument("--case-id", action="append", dest="case_ids", required=True)
    parser.add_argument("--locations", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--dataset-status",
        choices=("development_diagnostic", "formal_holdout"),
        default="development_diagnostic",
    )
    args = parser.parse_args()
    requested = set(args.case_ids)
    cases = [row for row in read_jsonl(E2_INDEX) if row["case_id"] in requested]
    if {row["case_id"] for row in cases} != requested:
        raise SystemExit("unknown or missing requested E2 case")
    predictions = [
        row for path in args.predictions for row in read_jsonl(path)
    ]
    locations = {}
    for path in args.locations:
        document = read_json(path)
        overlap = sorted(set(locations) & set(document))
        if overlap:
            raise SystemExit(f"duplicate location cases: {', '.join(overlap)}")
        locations.update(document)
    report = score_e2(cases, predictions, locations, args.dataset_status)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "cases": report["case_count"],
        "macro_recall": report["target_repository_retrieval"]["macro_recall"],
        "mrr": report["target_repository_retrieval"]["mean_reciprocal_rank"],
        "recall_at_5": report["target_repository_retrieval"]["recall_at_5"],
        "check_position_hit_rate": report["check_position_retrieval"]["hit_rate"],
        "runnable_check_rate": report["runnable_check_rate"]["rate"],
        "not_assessed_rate": report["failure_recovery_judgment"]["not_assessed_rate"],
    }, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

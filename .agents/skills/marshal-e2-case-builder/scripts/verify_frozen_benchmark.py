#!/usr/bin/env python3
"""Reparse a post-split, network-off 50-case Marshal run."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import build_case
import run_frozen_benchmark


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def verify(release: Path, output: Path) -> dict[str, Any]:
    predictions = read_jsonl(output / "predictions.jsonl")
    isolation_rows = read_jsonl(output / "blind-isolation.jsonl")
    scores = read_jsonl(output / "scores.jsonl")
    boundary = read_json(output / "blind-boundary.json")
    metrics = read_json(output / "metrics.json")
    if not (len(predictions) == len(isolation_rows) == len(scores) == 50):
        raise ValueError("frozen-run prediction, isolation, or score count is not 50")
    case_ids = {row["case_id"] for row in predictions}
    if len(case_ids) != 50 or {row["case_id"] for row in isolation_rows} != case_ids or {row["case_id"] for row in scores} != case_ids:
        raise ValueError("frozen-run artifacts disagree on 50 unique case ids")
    if boundary.get("all_50_blind_containers_exited") is not True or boundary.get("labels_read_before_boundary") is not False:
        raise ValueError("frozen-run blind boundary is invalid")
    boundary_time = build_case.timestamp(boundary["all_blind_completed_at"])
    verified_isolation = []
    for row in isolation_rows:
        case_output = output / "cases" / row["case_id"]
        parsed = build_case.verify_blind(case_output)
        if build_case.timestamp(row["completed_at"]) > boundary_time:
            raise ValueError(f"case completed after blind boundary: {row['case_id']}")
        if parsed["network_mode"] != "none" or parsed["labels_read"] or parsed["label_store_mounted"]:
            raise ValueError(f"case inference isolation failed: {row['case_id']}")
        verified_isolation.append(parsed)

    labels = read_jsonl(release / "final-index.jsonl")
    locations = read_json(release / "expected-locations.json")
    labels_by_id = {row["case_id"]: row for row in labels}
    if set(labels_by_id) != case_ids:
        raise ValueError("frozen-run case ids differ from the frozen release")
    recomputed_scores = sorted(
        (
            run_frozen_benchmark.score_prediction(row, labels_by_id[row["case_id"]], locations)
            for row in predictions
        ),
        key=lambda row: row["case_id"],
    )
    if recomputed_scores != scores:
        raise ValueError("stored scores differ from reparsed predictions and labels")
    recomputed_by_split = {
        split: run_frozen_benchmark.aggregate(
            [row for row in recomputed_scores if row["split"] == split]
        )
        for split in ("development", "evaluation", "holdout")
    }
    if recomputed_by_split != metrics["scores"]:
        raise ValueError("stored aggregate metrics differ from recomputed scores")
    split_counts = dict(Counter(row["split"] for row in labels))
    if split_counts != {"development": 30, "evaluation": 10, "holdout": 10}:
        raise ValueError("frozen-run release split is not 30/10/10")
    if build_case.timestamp(metrics["labels_read_at"]) < boundary_time:
        raise ValueError("labels were read before every blind container exited")
    return {
        "schema_version": "1.0",
        "verified": True,
        "case_count": 50,
        "split_counts": split_counts,
        "network_none_count": 50,
        "labels_read_during_inference_count": 0,
        "label_store_mounted_count": 0,
        "all_predictions_precede_label_read": True,
        "recomputed_score_count": 50,
        "aggregate_scores_match": True,
        "blockers": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    root = build_case.repository_root()
    release = build_case.resolve(root, args.release_dir)
    output = build_case.resolve(root, args.output_dir)
    try:
        result = verify(release, output)
    except (ValueError, OSError, KeyError, json.JSONDecodeError, RuntimeError) as error:
        print(f"error: {error}")
        return 1
    run_frozen_benchmark.write_json(output / "verification.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

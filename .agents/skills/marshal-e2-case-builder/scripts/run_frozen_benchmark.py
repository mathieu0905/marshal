#!/usr/bin/env python3
"""Run Marshal on a frozen formal release before reading any labels."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import build_case


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def now() -> str:
    return dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z")


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(rows)
    return {
        "case_count": count,
        "mrr": sum(row["mean_reciprocal_rank"] for row in rows) / count,
        "recall_at_1": sum(row["recall_at_1"] for row in rows) / count,
        "recall_at_3": sum(row["recall_at_3"] for row in rows) / count,
        "recall_at_5": sum(row["recall_at_5"] for row in rows) / count,
        "check_position_recall": sum(row["check_position_found"] for row in rows) / count,
        "runnable_check_rate": sum(row["runnable_check_proposed"] for row in rows) / count,
        "execution_not_assessed_count": sum(
            row["execution_result"] == "not_assessed" for row in rows
        ),
    }


def score_prediction(
    prediction: dict[str, Any], label: dict[str, Any], locations: dict[str, Any]
) -> dict[str, Any]:
    case_id = label["case_id"]
    target = label["target_repositories"][0]
    ranked = [row["repository"] for row in prediction["targets"]]
    rank = ranked.index(target) + 1 if target in ranked else None
    target_row = next(
        (row for row in prediction["targets"] if row["repository"] == target), None
    )
    expected = set(locations[case_id][target])
    predicted = set(target_row.get("paths", [])) if target_row else set()
    return {
        "schema_version": "1.0",
        "case_id": case_id,
        "split": label["split"],
        "target_repository": target,
        "rank": rank,
        "mean_reciprocal_rank": 1.0 / rank if rank else 0.0,
        "recall_at_1": 1.0 if rank == 1 else 0.0,
        "recall_at_3": 1.0 if rank is not None and rank <= 3 else 0.0,
        "recall_at_5": 1.0 if rank is not None and rank <= 5 else 0.0,
        "expected_check_paths": sorted(expected),
        "predicted_check_paths": sorted(predicted),
        "check_position_found": bool(expected & predicted),
        "runnable_check_proposed": bool(target_row and target_row.get("commands")),
        "execution_result": (
            target_row.get("execution_result", "not_assessed")
            if target_row else "not_assessed"
        ),
        "non_target_predictions": "unjudged",
        "precision_f1_specificity_reported": False,
    }


def run_benchmark(args: argparse.Namespace) -> dict[str, Any]:
    root = build_case.repository_root()
    release = build_case.resolve(root, args.release_dir)
    output = build_case.resolve(root, args.output_dir)
    if output.exists():
        raise ValueError(f"formal system-run output already exists: {output}")
    verification = read_json(release / "verification.json")
    if verification.get("verified") is not True or verification.get("case_count") != 50:
        raise ValueError("release is not verifier-clean before the frozen run")

    # Public-only phase. Do not read final-index, expected locations, case
    # reports, group manifests, or private labels until every container exits.
    public_inputs = read_jsonl(release / "inputs.jsonl")
    if len(public_inputs) != 50 or len({row["case_id"] for row in public_inputs}) != 50:
        raise ValueError("release public input does not contain 50 unique cases")
    output.mkdir(parents=True)
    ordered_inputs = sorted(public_inputs, key=lambda row: row["case_id"])

    def run_public_case(item: tuple[int, dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
        number, public_input = item
        case_id = public_input["case_id"]
        package = release / "cases" / case_id
        manifest = read_json(package / "public" / "manifest.json")
        storage_key = (
            "snapshot_archive_root" if "snapshot_archive_root" in manifest else "mirror_root"
        )
        prepared = {
            "candidate_id": manifest["candidate_id"],
            "public_dir": package / "public",
            "candidate_root": build_case.resolve(root, manifest[storage_key]),
            "candidate_storage": (
                "exact_commit_archive" if storage_key == "snapshot_archive_root" else "git_mirror"
            ),
            "blind": manifest.get("blind", {}),
        }
        case_output = output / "cases" / case_id
        case_output.mkdir(parents=True)
        shutil.copytree(package / "public", case_output / "public")
        prepared["public_dir"] = case_output / "public"
        build_case.run_blind(
            root,
            prepared,
            package / "private" / "label.json",
            case_output,
        )
        blind = build_case.verify_blind(case_output)
        prediction = read_jsonl(case_output / "blind" / "predictions.jsonl")[0]
        isolation = read_json(case_output / "blind" / "isolation.json")
        isolation_row = {
            "case_id": case_id,
            "ordinal": number,
            "created_at": prediction["created_at"],
            "completed_at": isolation["completed_at"],
            "network_mode": blind["network_mode"],
            "labels_read": blind["labels_read"],
            "label_store_mounted": blind["label_store_mounted"],
            "candidate_repository_reads": blind["candidate_repository_reads"],
            "candidate_text_file_reads": blind["candidate_text_file_reads"],
        }
        return {"case_id": case_id, "targets": prediction["targets"]}, isolation_row

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        completed = list(executor.map(run_public_case, enumerate(ordered_inputs, start=1)))
    predictions = [row[0] for row in completed]
    isolation_rows = [row[1] for row in completed]

    all_blind_completed_at = now()
    write_jsonl(output / "predictions.jsonl", predictions)
    write_jsonl(output / "blind-isolation.jsonl", isolation_rows)
    write_json(output / "blind-boundary.json", {
        "schema_version": "1.0",
        "all_50_blind_containers_exited": True,
        "all_blind_completed_at": all_blind_completed_at,
        "labels_read_before_boundary": False,
        "network_mode": "none",
    })

    # Label/scoring phase begins only after the durable boundary above.
    labels_read_at = now()
    labels = read_jsonl(release / "final-index.jsonl")
    locations = read_json(release / "expected-locations.json")
    labels_by_id = {row["case_id"]: row for row in labels}
    if set(labels_by_id) != {row["case_id"] for row in predictions}:
        raise ValueError("frozen-run predictions and release labels disagree on case ids")
    if any(build_case.timestamp(row["completed_at"]) > build_case.timestamp(all_blind_completed_at) for row in isolation_rows):
        raise ValueError("a blind container completed after the label-read boundary")
    scores = [
        score_prediction(row, labels_by_id[row["case_id"]], locations)
        for row in predictions
    ]
    score_by_split = {
        split: aggregate([row for row in scores if row["split"] == split])
        for split in ("development", "evaluation", "holdout")
    }
    metrics = {
        "schema_version": "1.0",
        "formal_system_run": True,
        "case_count": 50,
        "split_counts": dict(Counter(row["split"] for row in labels)),
        "all_blind_completed_at": all_blind_completed_at,
        "labels_read_at": labels_read_at,
        "network_none_count": sum(row["network_mode"] == "none" for row in isolation_rows),
        "labels_read_during_inference_count": sum(row["labels_read"] for row in isolation_rows),
        "label_store_mounted_count": sum(row["label_store_mounted"] for row in isolation_rows),
        "candidate_repository_reads": sum(row["candidate_repository_reads"] for row in isolation_rows),
        "candidate_text_file_reads": sum(row["candidate_text_file_reads"] for row in isolation_rows),
        "non_target_candidates": "unjudged",
        "precision_f1_specificity_reported": False,
        "scores": score_by_split,
    }
    if metrics["split_counts"] != {"development": 30, "evaluation": 10, "holdout": 10}:
        raise ValueError("frozen-run labels do not retain the 30/10/10 split")
    if metrics["network_none_count"] != 50 or metrics["labels_read_during_inference_count"] or metrics["label_store_mounted_count"]:
        raise ValueError("frozen-run isolation verification failed")
    write_jsonl(output / "scores.jsonl", sorted(scores, key=lambda row: row["case_id"]))
    write_json(output / "metrics.json", metrics)
    write_json(output / "verification.json", {
        "schema_version": "1.0",
        "verified": True,
        "case_count": 50,
        "all_predictions_precede_label_read": True,
        "network_none_count": 50,
        "labels_read_during_inference_count": 0,
        "label_store_mounted_count": 0,
        "blockers": [],
    })
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.workers < 1 or args.workers > 8:
        parser.error("--workers must be between 1 and 8")
    try:
        metrics = run_benchmark(args)
    except (ValueError, OSError, KeyError, json.JSONDecodeError, RuntimeError) as error:
        print(f"error: {error}")
        return 1
    print(json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

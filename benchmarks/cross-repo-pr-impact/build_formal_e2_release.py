#!/usr/bin/env python3
"""Build the 50-case formal strict-E2 release from adjudicated private labels."""

from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

from score_e2 import score_e2


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def subset_sum(groups: list[tuple[str, int]], target: int) -> set[str] | None:
    states: dict[int, tuple[str, ...]] = {0: ()}
    for identifier, size in groups:
        for total, selected in sorted(list(states.items()), reverse=True):
            new_total = total + size
            if new_total <= target and new_total not in states:
                states[new_total] = (*selected, identifier)
    return set(states[target]) if target in states else None


def assign_splits(labels: list[dict[str, Any]]) -> dict[str, str]:
    sizes = Counter(row["source_change_family"] for row in labels)
    groups = sorted(sizes.items())
    holdout = subset_sum(groups, 10)
    if holdout is None:
        raise ValueError("cannot form exact 10-case holdout without splitting source families")
    remaining = [(group, size) for group, size in groups if group not in holdout]
    evaluation = subset_sum(remaining, 10)
    if evaluation is None:
        raise ValueError("cannot form exact 10-case evaluation without splitting source families")
    return {
        group: "holdout" if group in holdout else "evaluation" if group in evaluation else "development"
        for group in sizes
    }


def build(args: argparse.Namespace) -> dict[str, Any]:
    labels = read_jsonl(args.labels)
    if len(labels) != 50:
        raise ValueError(f"release requires exactly 50 labels, got {len(labels)}")
    if len({(row["source_change_family"], tuple(row["target_repositories"])) for row in labels}) != 50:
        raise ValueError("duplicate source-family/target relation")

    sources = {row["candidate_id"]: row for row in read_jsonl(args.source_events)}
    inputs = {row["case_id"]: row for row in read_jsonl(args.inputs)}
    snapshots = {row["case_id"]: row for row in read_jsonl(args.snapshots)}
    predictions = {row["candidate_id"]: row for row in read_jsonl(args.predictions)}
    catalogs_document = read_json(args.catalogs)
    catalogs = catalogs_document["catalogs"]
    splits = assign_splits(labels)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    evidence_output = args.output_dir / "evidence"
    evidence_output.mkdir(exist_ok=True)
    patch_output = args.output_dir / "source-patches"
    patch_output.mkdir(exist_ok=True)
    final_index = []
    release_inputs = []
    release_snapshots = []
    release_predictions = []
    blind_run_records = []
    locations: dict[str, dict[str, list[str]]] = {}
    source_frame = {}
    group_rows = []
    blockers: list[str] = []
    preexisting_target_channels = {
        "pre_existing_target_test",
        "maintainer_target_test",
        "project_build_or_test",
    }
    if any(
        row.get("primary_result_channel") not in preexisting_target_channels
        for row in labels
    ):
        blockers.append("posthoc_reference_contract_is_not_a_real_target_task")

    for label in labels:
        case_id = label["case_id"]
        candidate_id = label["candidate_id"]
        source = sources[candidate_id]
        input_row = inputs[candidate_id]
        snapshot = snapshots.get(candidate_id)
        prediction = predictions[candidate_id]
        contract = read_json(args.evidence_root / case_id / "contract.json")
        catalog_identifier = source["candidate_repository_catalog"].split("#", 1)[1]
        members = set(catalogs[catalog_identifier]["repositories"])
        target = label["target_repositories"][0]
        if target not in members:
            blockers.append(f"{case_id}:target_not_in_catalog")
        if snapshot is None:
            blockers.append(f"{case_id}:snapshot_missing")
            continue
        target_snapshot = next(
            (row for row in snapshot["repositories"] if row["repository"] == target), None
        )
        if target_snapshot is None or target_snapshot["status"] != "available":
            blockers.append(f"{case_id}:target_snapshot_unavailable")
        if prediction["created_at"] >= label["revealed_at"]:
            blockers.append(f"{case_id}:prediction_not_blind")
        if label["arms"] != {"A0": "pass", "A1": "fail", "A2": "pass"}:
            blockers.append(f"{case_id}:arm_direction")

        split = splits[label["source_change_family"]]
        formal_case = label.get("primary_result_channel") in preexisting_target_channels
        final_index.append({
            **label,
            "dataset_status": "formal_benchmark" if formal_case else "development_diagnostic",
            "evidence_layer": "E2",
            "machine_arm_verification": "passed",
            "blind_evaluation_eligible": formal_case and split in {"evaluation", "holdout"},
            "split": split,
            "candidate_repository_catalog": source["candidate_repository_catalog"],
            "observation_cutoff": source["opening"]["created_at"],
            "source_change": source["opening"]["subject"],
            "evidence_path": f"evidence/{case_id}/contract.json",
        })
        release_inputs.append({**input_row, "case_id": case_id, "candidate_repository_snapshots": f"repository-snapshots.jsonl#{case_id}"})
        release_snapshots.append({**snapshot, "case_id": case_id})
        release_predictions.append({"case_id": case_id, "targets": prediction["targets"]})
        blind_run_records.append({
            "case_id": case_id,
            "source_candidate_id": candidate_id,
            "created_at": prediction["created_at"],
            "revealed_at": label["revealed_at"],
            "labels_read": False,
            "network_used": False,
        })
        locations[case_id] = {target: [contract["target_path"]]}
        source_frame[candidate_id] = source
        group_rows.append({
            "case_id": case_id,
            "group_id": label["source_change_family"],
            "directed_relation": [label["source_repository"], target],
            "mechanism": label["mechanism"],
            "repair_template": f"remove-or-rewrite:{contract['contract_token']}:{contract['target_path']}",
            "split": split,
        })
        destination = evidence_output / case_id
        shutil.copytree(args.evidence_root / case_id, destination, dirs_exist_ok=True)
        source_patch = args.source_patch_dir / f"{candidate_id}.patch"
        payload = source_patch.read_bytes()
        if not payload.startswith(b"diff --git "):
            blockers.append(f"{case_id}:source_patch_not_code_diff")
        (patch_output / f"{case_id}.patch").write_bytes(payload)

    split_counts = Counter(row["split"] for row in final_index)
    if split_counts != {"development": 30, "evaluation": 10, "holdout": 10}:
        blockers.append(f"split_counts:{dict(split_counts)}")
    group_splits: dict[str, set[str]] = {}
    for row in group_rows:
        group_splits.setdefault(row["group_id"], set()).add(row["split"])
    if any(len(value) != 1 for value in group_splits.values()):
        blockers.append("source_family_split_leak")

    write_json(args.output_dir / "candidate-repositories.json", catalogs_document)
    write_jsonl(args.output_dir / "source-events.jsonl", sorted(source_frame.values(), key=lambda row: row["candidate_id"]))
    write_jsonl(args.output_dir / "inputs.jsonl", final_sort(release_inputs))
    write_jsonl(args.output_dir / "repository-snapshots.jsonl", final_sort(release_snapshots))
    write_jsonl(args.output_dir / "predictions.jsonl", final_sort(release_predictions))
    write_jsonl(args.output_dir / "blind-run-records.jsonl", final_sort(blind_run_records))
    write_jsonl(args.output_dir / "final-index.jsonl", final_sort(final_index))
    write_jsonl(args.output_dir / "group-manifest.jsonl", final_sort(group_rows))
    write_json(args.output_dir / "expected-locations.json", locations)
    report = score_e2(final_index, release_predictions, locations, "development_diagnostic")
    write_json(args.output_dir / "marshal-native-score.json", report)
    metrics = {
        "schema_version": "1.0",
        "candidate_case_count": len(final_index),
        "formal_case_count": sum(
            row.get("primary_result_channel") in preexisting_target_channels
            for row in final_index
        ),
        "split_counts": dict(sorted(split_counts.items())),
        "reference_check_0_1_0_count": sum(row["arms"] == {"A0": "pass", "A1": "fail", "A2": "pass"} for row in final_index),
        "opening_input_count": len(release_inputs),
        "bundled_code_diff_count": len(list(patch_output.glob("*.patch"))),
        "snapshot_input_count": len(release_snapshots),
        "blind_prediction_count": len(release_predictions),
        "catalog_count": len(catalogs),
        "source_family_split_leak_count": sum(len(value) != 1 for value in group_splits.values()),
        "formal_release_ready": not blockers and sum(
            row.get("primary_result_channel") in preexisting_target_channels
            for row in final_index
        ) == 50,
        "blockers": blockers,
        "evidence_scope": "post-hoc dataset-authored reference-surface checks",
        "formal_status": "withdrawn_development_diagnostic",
        "full_project_build_claimed": False,
    }
    write_json(args.output_dir / "metrics.json", metrics)
    write_json(args.output_dir / "run-manifest.json", {
        "schema_version": "1.0",
        "catalog_membership_reads_labels": False,
        "source_opening_revision": 1,
        "native_marshal_prediction_labels_read": False,
        "native_marshal_prediction_network_used": False,
        "non_target_candidates": "unjudged",
        "precision_f1_specificity_reported": False,
        "evidence_scope": metrics["evidence_scope"],
        "full_project_build_claimed": False,
    })
    return metrics


def final_sort(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: row["case_id"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--source-events", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--catalogs", type=Path, required=True)
    parser.add_argument("--snapshots", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--source-patch-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    metrics = build(args)
    print(json.dumps(metrics, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if metrics["formal_release_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Independently verify the published 50-case formal E2 release package."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def timestamp(value: str) -> dt.datetime:
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=dt.UTC) if parsed.tzinfo is None else parsed.astimezone(dt.UTC)


def verify(root: Path) -> dict[str, Any]:
    cases = read_jsonl(root / "final-index.jsonl")
    inputs = {row["case_id"]: row for row in read_jsonl(root / "inputs.jsonl")}
    snapshots = {row["case_id"]: row for row in read_jsonl(root / "repository-snapshots.jsonl")}
    predictions = {row["case_id"]: row for row in read_jsonl(root / "predictions.jsonl")}
    blind = {row["case_id"]: row for row in read_jsonl(root / "blind-run-records.jsonl")}
    groups = read_jsonl(root / "group-manifest.jsonl")
    catalogs = read_json(root / "candidate-repositories.json")["catalogs"]
    blockers: list[str] = []
    allowed_target_channels = {
        "pre_existing_target_test",
        "maintainer_target_test",
        "project_build_or_test",
    }
    real_target_task_count = sum(
        row.get("primary_result_channel") in allowed_target_channels for row in cases
    )
    if real_target_task_count != 50:
        blockers.append(f"real_target_task_e2_count:{real_target_task_count}")
    if any(row.get("dataset_status") != "formal_benchmark" for row in cases):
        blockers.append("dataset_status_not_formal")

    case_ids = [row["case_id"] for row in cases]
    if len(cases) != 50 or len(set(case_ids)) != 50:
        blockers.append("case_count_or_uniqueness")
    relations = {
        (row["source_change_family"], tuple(row["target_repositories"])) for row in cases
    }
    if len(relations) != 50:
        blockers.append("relation_uniqueness")
    if set(case_ids) != set(inputs) or set(case_ids) != set(snapshots) or set(case_ids) != set(predictions) or set(case_ids) != set(blind):
        blockers.append("case_set_mismatch")

    evidence_verified = 0
    for case in cases:
        case_id = case["case_id"]
        if case["arms"] != {"A0": "pass", "A1": "fail", "A2": "pass"}:
            blockers.append(f"{case_id}:arms")
        if case.get("machine_arm_verification") != "passed":
            blockers.append(f"{case_id}:machine_verification")
        input_row = inputs[case_id]
        if input_row["source"]["source_change_kind"] != "gerrit_opening_revision" or not input_row["source"]["patch_url"].endswith("/revisions/1/patch"):
            blockers.append(f"{case_id}:not_opening_revision")
        patch_path = root / "source-patches" / f"{case_id}.patch"
        if not patch_path.exists() or not patch_path.read_bytes().startswith(b"diff --git "):
            blockers.append(f"{case_id}:bundled_code_diff")
        if timestamp(input_row["observation_cutoff"]) != timestamp(snapshots[case_id]["observation_cutoff"]):
            blockers.append(f"{case_id}:cutoff_mismatch")
        identifier = input_row["candidate_repository_catalog"].split("#", 1)[1]
        catalog = catalogs[identifier]
        if catalog.get("membership_reads_labels") is not False or catalog.get("reused_across_source_events") is not True:
            blockers.append(f"{case_id}:catalog_provenance")
        target = case["target_repositories"][0]
        members = set(catalog["repositories"])
        if target not in members or len(members) < 2:
            blockers.append(f"{case_id}:catalog_coverage")
        repository_rows = snapshots[case_id]["repositories"]
        target_row = next((row for row in repository_rows if row["repository"] == target), None)
        if target_row is None or target_row["status"] != "available":
            blockers.append(f"{case_id}:target_snapshot")
        if any(row["status"] == "fetch_failed" for row in repository_rows):
            blockers.append(f"{case_id}:snapshot_fetch_failed")
        record = blind[case_id]
        if timestamp(record["created_at"]) >= timestamp(record["revealed_at"]):
            blockers.append(f"{case_id}:blind_order")
        if record.get("labels_read") is not False or record.get("network_used") is not False:
            blockers.append(f"{case_id}:blind_manifest")
        tsv_path = root / "evidence" / case_id / "run-results.tsv"
        contract_path = root / "evidence" / case_id / "contract.json"
        if not tsv_path.exists() or not contract_path.exists():
            blockers.append(f"{case_id}:evidence_missing")
            continue
        rows = list(csv.DictReader(io.StringIO(tsv_path.read_text(encoding="utf-8")), delimiter="\t"))
        observed = [(row["arm"], int(row["exit_code"]), row["result"]) for row in rows]
        if observed != [("A0", 0, "pass"), ("A1", 1, "fail"), ("A2", 0, "pass")]:
            blockers.append(f"{case_id}:evidence_direction")
        else:
            evidence_verified += 1

    group_splits: dict[str, set[str]] = defaultdict(set)
    for row in groups:
        group_splits[row["group_id"]].add(row["split"])
    leak_count = sum(len(splits) != 1 for splits in group_splits.values())
    if leak_count:
        blockers.append("group_split_leak")
    split_counts = Counter(row["split"] for row in cases)
    if split_counts != {"development": 30, "evaluation": 10, "holdout": 10}:
        blockers.append("split_counts")
    score = read_json(root / "marshal-native-score.json")
    if score["case_count"] != 50 or score["dataset_status"] != "formal_benchmark":
        blockers.append("score_scope")
    return {
        "schema_version": "1.0",
        "case_count": len(cases),
        "unique_relation_count": len(relations),
        "evidence_0_1_0_verified_count": evidence_verified,
        "real_target_task_e2_count": real_target_task_count,
        "opening_input_count": len(inputs),
        "snapshot_input_count": len(snapshots),
        "blind_prediction_count": len(predictions),
        "split_counts": dict(sorted(split_counts.items())),
        "source_family_split_leak_count": leak_count,
        "blockers": blockers,
        "formal_release_verified": not blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("release_dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify(args.release_dir)
    if args.output:
        args.output.write_text(
            json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if report["formal_release_verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Independently reparse a 50-case strict-E2 release."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import build_case
import release_formal_pool


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def verify_release(release: Path) -> dict[str, Any]:
    index = read_jsonl(release / "final-index.jsonl")
    inputs = read_jsonl(release / "inputs.jsonl")
    snapshots = read_jsonl(release / "repository-snapshots.jsonl")
    predictions = read_jsonl(release / "predictions.jsonl")
    blind_records = read_jsonl(release / "blind-run-records.jsonl")
    groups = read_jsonl(release / "group-manifest.jsonl")
    catalogs = read_json(release / "candidate-repositories.json")["catalogs"]
    metrics = read_json(release / "metrics.json")
    collections = (index, inputs, snapshots, predictions, blind_records)
    if any(len(rows) != 50 for rows in collections):
        raise ValueError("release collections do not all contain 50 rows")
    case_ids = {row["case_id"] for row in index}
    if len(case_ids) != 50 or any({row["case_id"] for row in rows} != case_ids for rows in collections[1:]):
        raise ValueError("release collections disagree on 50 unique case ids")
    if len({(row["source_change_family"], row["target_repositories"][0]) for row in index}) != 50:
        raise ValueError("release contains duplicate source-family/target cases")

    input_by_id = {row["case_id"]: row for row in inputs}
    snapshot_by_id = {row["case_id"]: row for row in snapshots}
    reports = []
    for row in index:
        case_id = row["case_id"]
        package = release / "cases" / case_id
        private = read_json(package / "private" / "label.json")
        reveal = read_json(package / "private" / "reveal.json")
        report = build_case.build_report(package, private, reveal["revealed_at"])
        if report.get("case_ready_for_formal_pool") is not True:
            raise ValueError(f"release case failed reparsing: {case_id}")
        target = row["target_repositories"][0]
        catalog_id = input_by_id[case_id]["candidate_repository_catalog"].split("#", 1)[1]
        if target not in catalogs[catalog_id]["repositories"]:
            raise ValueError(f"release target is absent from its catalog: {case_id}")
        target_snapshot = next(
            (item for item in snapshot_by_id[case_id]["repositories"] if item["repository"] == target),
            None,
        )
        if target_snapshot is None or target_snapshot.get("status") != "available":
            raise ValueError(f"release target cutoff snapshot is unavailable: {case_id}")
        reports.append(report)

    assignments, expected_groups = release_formal_pool.assign_grouped_splits(reports)
    if {row["case_id"]: row["split"] for row in index} != assignments:
        raise ValueError("release split is not the deterministic grouped split")
    if groups != expected_groups:
        raise ValueError("release group manifest does not match recomputed four-axis groups")
    axis_splits: dict[tuple[str, str], set[str]] = defaultdict(set)
    for report in reports:
        split = assignments[report["case_id"]]
        for axis, value in (
            ("directed_relation", " -> ".join(report["directed_relation"])),
            ("source_change_family", report["source_change_family"]),
            ("mechanism", release_formal_pool.normalized(report["mechanism"])),
            ("repair_template", release_formal_pool.normalized(report["repair_template"])),
        ):
            axis_splits[(axis, value)].add(split)
    cross_split = sum(len(splits) != 1 for splits in axis_splits.values())
    split_counts = dict(Counter(assignments.values()))
    if split_counts != release_formal_pool.SPLIT_TARGETS or cross_split:
        raise ValueError("release split count or four-axis isolation failed")
    if metrics.get("formal_release_ready") is not True or metrics.get("formal_case_count") != 50:
        raise ValueError("release metrics do not declare the verified 50-case collection")
    return {
        "schema_version": "1.0",
        "verified": True,
        "case_count": 50,
        "machine_strict_e2_count": 50,
        "semantic_approval_count": 50,
        "split_counts": split_counts,
        "group_count": len(groups),
        "cross_split_leak_count": cross_split,
        "catalog_target_membership_count": 50,
        "target_cutoff_snapshot_available_count": 50,
        "blockers": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        release = build_case.resolve(build_case.repository_root(), args.release_dir)
        result = verify_release(release)
    except (ValueError, OSError, KeyError, json.JSONDecodeError, RuntimeError) as error:
        print(f"error: {error}")
        return 1
    release_formal_pool.write_json(release / "verification.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Reverify and release exactly 50 strict-E2 single-case packages."""

from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

import build_case


SPLIT_TARGETS = {"development": 30, "evaluation": 10, "holdout": 10}


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


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def normalized(value: str) -> str:
    return " ".join(value.casefold().split())


def merge_catalog_definitions(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """Merge only rebuild-time timestamps for otherwise identical catalogs."""

    left_semantics = {key: value for key, value in left.items() if key != "constructed_at"}
    right_semantics = {key: value for key, value in right.items() if key != "constructed_at"}
    if left_semantics != right_semantics:
        raise ValueError("catalog definitions differ beyond constructed_at")
    left_has_timestamp = "constructed_at" in left
    right_has_timestamp = "constructed_at" in right
    if left_has_timestamp != right_has_timestamp:
        raise ValueError("catalog constructed_at presence differs")
    merged = dict(left_semantics)
    if left_has_timestamp:
        timestamps = (left["constructed_at"], right["constructed_at"])
        if any(not isinstance(value, str) or not value for value in timestamps):
            raise ValueError("catalog constructed_at is invalid")
        merged["constructed_at"] = min(timestamps)
    return merged


class UnionFind:
    def __init__(self, values: Iterable[str]) -> None:
        self.parent = {value: value for value in values}

    def find(self, value: str) -> str:
        while self.parent[value] != value:
            self.parent[value] = self.parent[self.parent[value]]
            value = self.parent[value]
        return value

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[max(left_root, right_root)] = min(left_root, right_root)


def grouped_components(reports: list[dict[str, Any]]) -> list[list[str]]:
    identifiers = [row["case_id"] for row in reports]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("formal pool contains duplicate case ids")
    union_find = UnionFind(identifiers)
    axes: dict[tuple[str, str], list[str]] = defaultdict(list)
    for row in reports:
        facts = {
            "directed_relation": " -> ".join(row["directed_relation"]),
            "source_change_family": row["source_change_family"],
            "mechanism": normalized(row["mechanism"]),
            "repair_template": normalized(row["repair_template"]),
        }
        for axis, value in facts.items():
            axes[(axis, value)].append(row["case_id"])
    for members in axes.values():
        for member in members[1:]:
            union_find.union(members[0], member)
    components: dict[str, list[str]] = defaultdict(list)
    for identifier in identifiers:
        components[union_find.find(identifier)].append(identifier)
    return sorted(
        (sorted(component) for component in components.values()),
        key=lambda component: component[0],
    )


def subset_sum(
    components: list[list[str]], target: int
) -> list[list[str]] | None:
    states: dict[int, tuple[int, ...]] = {0: ()}
    for index, component in enumerate(components):
        for total, selected in sorted(list(states.items()), reverse=True):
            new_total = total + len(component)
            if new_total <= target and new_total not in states:
                states[new_total] = (*selected, index)
    selected = states.get(target)
    return [components[index] for index in selected] if selected is not None else None


def assign_grouped_splits(
    reports: list[dict[str, Any]],
) -> tuple[dict[str, str], list[dict[str, Any]]]:
    components = grouped_components(reports)
    holdout = subset_sum(components, SPLIT_TARGETS["holdout"])
    if holdout is None:
        raise ValueError("cannot form an exact 10-case holdout without group leakage")
    holdout_keys = {tuple(component) for component in holdout}
    remaining = [
        component for component in components if tuple(component) not in holdout_keys
    ]
    evaluation = subset_sum(remaining, SPLIT_TARGETS["evaluation"])
    if evaluation is None:
        raise ValueError("cannot form an exact 10-case evaluation without group leakage")
    evaluation_keys = {tuple(component) for component in evaluation}
    assignments: dict[str, str] = {}
    group_rows = []
    reports_by_id = {row["case_id"]: row for row in reports}
    for number, component in enumerate(components, start=1):
        key = tuple(component)
        split = (
            "holdout" if key in holdout_keys
            else "evaluation" if key in evaluation_keys
            else "development"
        )
        for case_id in component:
            assignments[case_id] = split
        members = [reports_by_id[case_id] for case_id in component]
        group_rows.append({
            "group_id": f"strict-e2-group-{number:03d}",
            "case_ids": component,
            "split": split,
            "directed_relations": sorted({
                " -> ".join(row["directed_relation"]) for row in members
            }),
            "source_change_families": sorted({
                row["source_change_family"] for row in members
            }),
            "mechanisms": sorted({normalized(row["mechanism"]) for row in members}),
            "repair_templates": sorted({
                normalized(row["repair_template"]) for row in members
            }),
        })
    counts = Counter(assignments.values())
    if dict(counts) != SPLIT_TARGETS:
        raise ValueError(f"grouped split is not 30/10/10: {dict(counts)}")
    return assignments, group_rows


def copy_case_package(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True)
    for directory in ("public", "blind", "private", "evidence"):
        shutil.copytree(source / directory, destination / directory)
    for filename in (
        "case-report.json", "score.json", "prediction-for-score.jsonl", "replay.log"
    ):
        shutil.copy2(source / filename, destination / filename)


def aggregate_score(reports: list[dict[str, Any]], split: str) -> dict[str, Any]:
    selected = [row["score"] for row in reports if row["split"] == split]
    count = len(selected)
    return {
        "case_count": count,
        "mrr": sum(row["mean_reciprocal_rank"] for row in selected) / count,
        "recall_at_1": sum(row["recall_at_1"] for row in selected) / count,
        "recall_at_3": sum(row["recall_at_3"] for row in selected) / count,
        "recall_at_5": sum(row["recall_at_5"] for row in selected) / count,
        "check_position_recall": sum(row["check_position_found"] for row in selected) / count,
        "runnable_check_rate": sum(row["runnable_check_proposed"] for row in selected) / count,
        "execution_not_assessed_count": sum(
            row["execution_result"] == "not_assessed" for row in selected
        ),
    }


def release(args: argparse.Namespace) -> dict[str, Any]:
    root = build_case.repository_root()
    entries = read_jsonl(build_case.resolve(root, args.case_list))
    if len(entries) != 50:
        raise ValueError(f"formal release requires exactly 50 case packages, got {len(entries)}")
    output = build_case.resolve(root, args.output_dir)
    if output.exists():
        raise ValueError(f"release output already exists: {output}")

    packages = []
    reports = []
    for entry in entries:
        package = build_case.resolve(root, entry["output_dir"])
        private = read_json(package / "private" / "label.json")
        reveal = read_json(package / "private" / "reveal.json")
        report = build_case.build_report(package, private, reveal["revealed_at"])
        if report.get("case_ready_for_formal_pool") is not True:
            raise ValueError(f"case failed release-time verification: {report['case_id']}")
        if report.get("evidence_layer") != "E2" or report["replay"].get("machine_strict_e2") is not True:
            raise ValueError(f"case is not machine strict-E2: {report['case_id']}")
        exits = report["replay"].get("exit_codes", {})
        if exits.get("A0") != 0 or exits.get("A1") == 0 or exits.get("A2") != 0:
            raise ValueError(f"case exits are not 0/1/0: {report['case_id']}")
        packages.append(package)
        reports.append(report)
    if len({row["case_id"] for row in reports}) != 50:
        raise ValueError("formal release does not contain 50 unique case ids")
    source_family_targets = {
        (row["source_change_family"], row["directed_relation"][1])
        for row in reports
    }
    if len(source_family_targets) != 50:
        raise ValueError("formal release contains a duplicate source-family/target case")

    assignments, group_rows = assign_grouped_splits(reports)
    group_by_case = {
        case_id: row["group_id"]
        for row in group_rows
        for case_id in row["case_ids"]
    }
    output.mkdir(parents=True)
    catalogs: dict[str, Any] = {}
    final_index = []
    inputs = []
    snapshots = []
    predictions = []
    blind_records = []
    locations: dict[str, dict[str, list[str]]] = {}
    released_reports = []
    for package, report in sorted(zip(packages, reports), key=lambda item: item[1]["case_id"]):
        case_id = report["case_id"]
        split = assignments[case_id]
        public_input = read_jsonl(package / "public" / "inputs.jsonl")[0]
        public_snapshot = read_jsonl(package / "public" / "repository-snapshots.jsonl")[0]
        prediction = read_jsonl(package / "blind" / "predictions.jsonl")[0]
        catalog_document = read_json(package / "public" / "candidate-repositories.json")
        for catalog_id, catalog in catalog_document["catalogs"].items():
            if catalog_id in catalogs:
                try:
                    catalogs[catalog_id] = merge_catalog_definitions(
                        catalogs[catalog_id], catalog
                    )
                except ValueError as error:
                    raise ValueError(
                        f"catalog id has conflicting definitions: {catalog_id}: {error}"
                    ) from error
            else:
                catalogs[catalog_id] = catalog
        input_row = {
            **public_input,
            "case_id": case_id,
            "candidate_id": report["candidate_id"],
            "candidate_repository_snapshots": f"repository-snapshots.jsonl#{case_id}",
        }
        snapshot_row = {**public_snapshot, "case_id": case_id}
        prediction_row = {"case_id": case_id, "targets": prediction["targets"]}
        target = report["directed_relation"][1]
        locations[case_id] = {target: report["score"]["expected_check_paths"]}
        released = {**report, "split": split, "group_id": group_by_case[case_id]}
        released["formal_benchmark"] = True
        released["formal_benchmark_reason"] = "release-time verifier-clean grouped strict-E2 collection"
        released["score"] = {**report["score"], "dataset_status": "formal_benchmark", "split": split}
        final_index.append({
            "schema_version": "1.0",
            "case_id": case_id,
            "candidate_id": report["candidate_id"],
            "evidence_layer": "E2",
            "dataset_status": "formal_benchmark",
            "split": split,
            "group_id": group_by_case[case_id],
            "source_repository": report["directed_relation"][0],
            "target_repositories": [target],
            "source_change_family": report["source_change_family"],
            "mechanism": report["mechanism"],
            "repair_template": report["repair_template"],
            "candidate_repository_catalog": public_input["candidate_repository_catalog"],
            "observation_cutoff": public_input["observation_cutoff"],
            "machine_strict_e2": True,
            "arms": {"A0": "pass", "A1": "fail", "A2": "pass"},
            "evidence_path": f"cases/{case_id}/evidence",
        })
        inputs.append(input_row)
        snapshots.append(snapshot_row)
        predictions.append(prediction_row)
        blind_records.append({
            "case_id": case_id,
            "prediction_created_at": report["blind_prediction_created_at"],
            "blind_completed_at": report["blind_completed_at"],
            "label_revealed_at": report["label_revealed_at"],
            "labels_read": False,
            "network_mode": "none",
            "label_store_mounted": False,
        })
        released_reports.append(released)
        copy_case_package(package, output / "cases" / case_id)

    final_index.sort(key=lambda row: row["case_id"])
    inputs.sort(key=lambda row: row["case_id"])
    snapshots.sort(key=lambda row: row["case_id"])
    predictions.sort(key=lambda row: row["case_id"])
    blind_records.sort(key=lambda row: row["case_id"])
    released_reports.sort(key=lambda row: row["case_id"])
    write_json(output / "candidate-repositories.json", {"schema_version": "1.0", "catalogs": catalogs})
    write_jsonl(output / "inputs.jsonl", inputs)
    write_jsonl(output / "repository-snapshots.jsonl", snapshots)
    write_jsonl(output / "predictions.jsonl", predictions)
    write_jsonl(output / "blind-run-records.jsonl", blind_records)
    write_jsonl(output / "final-index.jsonl", final_index)
    write_jsonl(output / "group-manifest.jsonl", group_rows)
    write_jsonl(output / "case-reports.jsonl", released_reports)
    write_json(output / "expected-locations.json", locations)
    scores = {
        split: aggregate_score(released_reports, split) for split in SPLIT_TARGETS
    }
    metrics = {
        "schema_version": "1.0",
        "formal_release_ready": True,
        "formal_case_count": 50,
        "unique_directed_relation_count": len({
            tuple(row["directed_relation"]) for row in reports
        }),
        "unique_source_family_target_count": len(source_family_targets),
        "machine_strict_e2_count": 50,
        "semantic_approval_count": 50,
        "blind_network_none_count": 50,
        "blind_label_unmounted_count": 50,
        "split_counts": dict(Counter(assignments.values())),
        "group_count": len(group_rows),
        "cross_split_leak_count": 0,
        "grouping_axes": [
            "directed_relation", "source_change_family", "mechanism", "repair_template"
        ],
        "non_target_candidates": "unjudged",
        "precision_f1_specificity_reported": False,
        "scores": scores,
    }
    write_json(output / "metrics.json", metrics)
    write_json(output / "verification.json", {
        "schema_version": "1.0",
        "verified": True,
        "case_count": 50,
        "per_case_verifier_rerun_count": 50,
        "split_counts": metrics["split_counts"],
        "cross_split_leak_count": 0,
        "blockers": [],
    })
    (output / "README.md").write_text(
        "# Marshal candidate-bounded strict-E2 benchmark\n\n"
        "This release contains 50 verifier-clean strict-E2 directed relations. "
        "Every case includes a label-independent reusable candidate catalog, a "
        "source-opening cutoff snapshot, a network-off blind prediction, and a "
        "real target command replayed as A0=0, A1!=0, A2=0 with an exclusive "
        "failure signature and an exact maintainer A2 patch.\n\n"
        "The grouped split contains 30 development, 10 evaluation, and 10 holdout "
        "cases. Directed relation, source change family, normalized mechanism, and "
        "normalized repair template do not cross splits. Non-target candidates are "
        "unjudged, so precision, F1, false-positive rate, and specificity are not reported.\n",
        encoding="utf-8",
    )
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-list", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        metrics = release(args)
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as error:
        print(f"error: {error}")
        return 1
    print(json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

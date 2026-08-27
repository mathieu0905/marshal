#!/usr/bin/env python3
"""Rebuild selected catalogs from label-independent source snapshots.

Membership is read only from catalog-source-snapshots.json. Hidden case targets are
used after construction solely to report whether the reconstructed input still
covers the existing development labels.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from collect_repository_snapshots import resolve, rfc3339


ROOT = Path(__file__).resolve().parent


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def rebuild(
    dataset_root: Path,
    projects: list[str],
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    source_snapshot = read_json(dataset_root / "catalog-source-snapshots.json")
    catalog = read_json(dataset_root / "candidate-repositories.json")
    inputs = read_jsonl(dataset_root / "inputs.jsonl")
    snapshots = read_jsonl(dataset_root / "repository-snapshots.jsonl")
    snapshot_by_case = {row["case_id"]: row for row in snapshots}
    case_by_id = {
        item["case_id"]: read_json(dataset_root / "cases" / f"{item['case_id']}.json")
        for item in inputs
    }

    unknown = sorted(set(projects) - set(source_snapshot["project_sources"]))
    if unknown:
        raise ValueError(f"projects lack independent source snapshots: {unknown}")

    report_projects = {}
    for project in projects:
        source_id = source_snapshot["project_sources"][project]
        source = source_snapshot["sources"][source_id]
        desired = sorted(source["repositories"])
        previous = catalog["catalogs"][project]["repositories"]
        catalog["catalogs"][project]["repositories"] = desired
        added = sorted(set(desired) - set(previous))
        removed = sorted(set(previous) - set(desired))
        project_inputs = [
            item
            for item in inputs
            if item["candidate_repository_catalog"].endswith(f"#{project}")
        ]
        fetch_failures = []
        statuses: dict[str, int] = {}
        for item in project_inputs:
            row = snapshot_by_case[item["case_id"]]
            existing = {
                repository["repository"]: repository
                for repository in row["repositories"]
            }
            rebuilt_repositories = []
            for repository in desired:
                result = existing.get(repository)
                if result is None or result["status"] == "fetch_failed":
                    result = resolve(
                        project,
                        repository,
                        rfc3339(item["observation_cutoff"]),
                    )
                rebuilt_repositories.append(result)
                statuses[result["status"]] = statuses.get(result["status"], 0) + 1
                if result["status"] == "fetch_failed":
                    fetch_failures.append({
                        "case_id": item["case_id"],
                        "repository": repository,
                        "error": result.get("error"),
                    })
            row["repositories"] = rebuilt_repositories

        targets = {
            target["repository"]
            for item in project_inputs
            for target in case_by_id[item["case_id"]]["targets"]
        }
        report_projects[project] = {
            "source_id": source_id,
            "selection_rule": source["selection_rule"],
            "source_urls": source["source_urls"],
            "case_count": len(project_inputs),
            "repository_count": len(desired),
            "added_repositories": added,
            "removed_repositories": removed,
            "known_targets_covered_after_construction": targets <= set(desired),
            "missing_known_targets_after_construction": sorted(targets - set(desired)),
            "snapshot_statuses": dict(sorted(statuses.items())),
            "fetch_failures": fetch_failures,
        }

    snapshots.sort(key=lambda row: row["case_id"])
    report = {
        "schema_version": "1.0",
        "membership_inputs_read": ["catalog-source-snapshots.json"],
        "hidden_labels_used_for_membership": False,
        "labels_read_after_membership_for_coverage_audit": True,
        "projects": report_projects,
        "success": all(
            not item["fetch_failures"]
            and item["known_targets_covered_after_construction"]
            for item in report_projects.values()
        ),
    }
    return catalog, snapshots, report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-dir", type=Path, default=ROOT)
    parser.add_argument("--project", action="append", dest="projects", required=True)
    parser.add_argument("--catalog-output", type=Path, required=True)
    parser.add_argument("--snapshots-output", type=Path, required=True)
    parser.add_argument("--report-output", type=Path, required=True)
    args = parser.parse_args()
    catalog, snapshots, report = rebuild(args.dataset_dir.resolve(), args.projects)
    write_json(args.catalog_output, catalog)
    write_jsonl(args.snapshots_output, snapshots)
    write_json(args.report_output, report)
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

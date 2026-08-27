#!/usr/bin/env python3
"""Annotate a selected development set with catalog and snapshot readiness."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from candidate_bounded_foundation import audit_catalogs, load_cases, read_jsonl


ROOT = Path(__file__).resolve().parent
ALLOWED_SNAPSHOT_STATUSES = {"available", "not_created_by_cutoff"}


def snapshot_readiness(
    catalog_repositories: set[str], snapshot: dict[str, Any]
) -> dict[str, Any]:
    repositories = {item["repository"] for item in snapshot["repositories"]}
    statuses = Counter(item["status"] for item in snapshot["repositories"])
    return {
        "catalog_snapshot_exact_match": repositories == catalog_repositories,
        "missing_catalog_repositories": sorted(catalog_repositories - repositories),
        "extra_snapshot_repositories": sorted(repositories - catalog_repositories),
        "snapshot_statuses": dict(sorted(statuses.items())),
        "fetch_failures": statuses["fetch_failed"],
        "snapshot_complete": (
            repositories == catalog_repositories
            and set(statuses) <= ALLOWED_SNAPSHOT_STATUSES
        ),
    }


def materialize(dataset_root: Path, selection: dict[str, Any]) -> dict[str, Any]:
    cases = load_cases(dataset_root)
    audit_by_project = {
        item["project"]: item for item in audit_catalogs(dataset_root, cases)
    }
    catalogs = json.loads(
        (dataset_root / "candidate-repositories.json").read_text(encoding="utf-8")
    )["catalogs"]
    snapshots = {
        item["case_id"]: item
        for item in read_jsonl(dataset_root / "repository-snapshots.jsonl")
    }
    selected_rows = []
    for selected in selection["cases"]:
        case_id = selected["case_id"]
        project = selected["project"]
        readiness = snapshot_readiness(
            set(catalogs[project]["repositories"]), snapshots[case_id]
        )
        selected_rows.append({
            **selected,
            "catalog_source_snapshot": audit_by_project[project][
                "current_source_snapshot"
            ],
            "catalog_label_independent": audit_by_project[project][
                "current_label_independent"
            ],
            **readiness,
        })

    project_counts = Counter(item["project"] for item in selected_rows)
    status_counts = Counter()
    for item in selected_rows:
        status_counts.update(item["snapshot_statuses"])
    ready = all(
        item["catalog_label_independent"] and item["snapshot_complete"]
        for item in selected_rows
    )
    return {
        "schema_version": "1.0",
        "material_type": "development_data_ready_manifest",
        "selection_rule": selection["selection_rule"],
        "label_fields_read_for_selection": selection["label_fields_read"],
        "case_count": len(selected_rows),
        "project_counts": dict(sorted(project_counts.items())),
        "candidate_repository_snapshots": sum(
            sum(item["snapshot_statuses"].values()) for item in selected_rows
        ),
        "snapshot_statuses": dict(sorted(status_counts.items())),
        "catalogs_label_independent": all(
            item["catalog_label_independent"] for item in selected_rows
        ),
        "snapshot_rows_complete": sum(
            item["snapshot_complete"] for item in selected_rows
        ),
        "development_data_ready": ready,
        "marshal_execution_completed": False,
        "scope_note": (
            "Data-ready means catalog provenance and observation-time snapshot metadata "
            "are complete. It does not mean Marshal has executed on the case."
        ),
        "cases": selected_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("selection", type=Path)
    parser.add_argument("--dataset-dir", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    selection = json.loads(args.selection.read_text(encoding="utf-8"))
    payload = materialize(args.dataset_dir.resolve(), selection)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "case_count": payload["case_count"],
        "project_counts": payload["project_counts"],
        "candidate_repository_snapshots": payload[
            "candidate_repository_snapshots"
        ],
        "snapshot_statuses": payload["snapshot_statuses"],
        "development_data_ready": payload["development_data_ready"],
        "marshal_execution_completed": payload["marshal_execution_completed"],
        "output": str(args.output.resolve()),
    }, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if payload["development_data_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

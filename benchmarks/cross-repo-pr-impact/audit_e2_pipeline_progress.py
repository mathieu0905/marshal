#!/usr/bin/env python3
"""Audit strict-E2 progress from catalog assignment through actual prediction."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


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


def catalog_id(reference: str) -> str:
    filename, separator, identifier = reference.partition("#")
    if filename != "candidate-repositories.json" or not separator or not identifier:
        raise ValueError(f"invalid catalog reference: {reference}")
    return identifier


def audit(
    cases: list[dict[str, Any]],
    assignments: list[dict[str, Any]],
    coverage: dict[str, Any],
    snapshots: list[dict[str, Any]],
    inputs: list[dict[str, Any]],
    visibility: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    split_rows: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    assignment_by_id = {row["case_id"]: row for row in assignments}
    snapshot_by_id = {row["case_id"]: row for row in snapshots}
    input_ids = {row["case_id"] for row in inputs}
    visibility_by_id = {row["case_id"]: row for row in visibility}
    prediction_ids = {row["case_id"] for row in predictions}
    if len(prediction_ids) != len(predictions):
        raise ValueError("duplicate prediction case_id")
    catalog_coverage = coverage["catalogs"]
    split_by_id = {row["case_id"]: row for row in (split_rows or [])}
    split_frozen = bool(split_rows) and len(split_by_id) == len(cases)
    rows = []
    for case in sorted(cases, key=lambda row: row["case_id"]):
        case_id = case["case_id"]
        assignment = assignment_by_id.get(case_id)
        release_blockers = []
        if not split_frozen:
            release_blockers.append("formal_group_split_not_finalized")
        if assignment is None:
            rows.append({
                "case_id": case_id,
                "source_change_family": case["source_change_family"],
                "catalog_assigned": False,
                "input_materialized": False,
                "visibility_passed": False,
                "actual_prediction_present": False,
                "formal_input_preconditions_met": False,
                "disposition": "missing_catalog",
                "primary_blocker": "no_reusable_label_independent_catalog_constructed",
                "release_blockers": [
                    "no_reusable_label_independent_catalog_constructed",
                    *release_blockers,
                ],
            })
            continue

        identifier = catalog_id(assignment["candidate_repository_catalog"])
        catalog = catalog_coverage[identifier]
        snapshot = snapshot_by_id.get(case_id)
        repositories = {
            row["repository"]: row for row in (snapshot or {}).get("repositories", [])
        }
        target_statuses = {
            target: repositories.get(target, {"status": "missing"})["status"]
            for target in case["target_repositories"]
        }
        target_snapshots_available = all(
            status == "available" for status in target_statuses.values()
        )
        snapshot_terminal = bool(snapshot) and all(
            row["status"] != "fetch_failed" for row in repositories.values()
        )
        materialized = case_id in input_ids
        visible = visibility_by_id.get(case_id, {}).get("status") == "pass"
        predicted = case_id in prediction_ids
        frozen_split = split_by_id.get(case_id, {}).get("split")
        cutoff_conformant = assignment.get(
            "input_spec_opening_cutoff_conformant", False
        )
        catalog_formal = bool(catalog["formal_catalog_eligible"])
        if not catalog_formal:
            release_blockers.append("catalog_is_development_only_outcome_conditioned")
        if not cutoff_conformant:
            release_blockers.append("observation_cutoff_not_pr_opening_state")
        if not target_snapshots_available:
            release_blockers.append("known_target_snapshot_not_available")
        if not materialized:
            release_blockers.append("input_not_materialized")
        if not visible:
            release_blockers.append("source_diff_visibility_not_passed")
        if not predicted:
            release_blockers.append("actual_system_prediction_missing")
        if split_frozen and frozen_split == "development":
            release_blockers.append("split_is_development")
        pipeline_complete = (
            snapshot_terminal
            and target_snapshots_available
            and materialized
            and visible
            and predicted
        )
        formal_input_preconditions = (
            pipeline_complete and catalog_formal and cutoff_conformant
        )
        formal_scoring_eligible = (
            formal_input_preconditions
            and split_frozen
            and frozen_split in {"evaluation", "holdout"}
        )
        disposition = (
            "actual_run_formal_input_preconditions"
            if formal_input_preconditions
            else "actual_run_development_only"
            if pipeline_complete
            else "assigned_pipeline_incomplete"
        )
        rows.append({
            "case_id": case_id,
            "source_change_family": case["source_change_family"],
            "catalog_assigned": True,
            "catalog_id": identifier,
            "catalog_formal_eligible": catalog_formal,
            "catalog_development_eligible": catalog.get(
                "development_catalog_eligible", False
            ),
            "input_spec_opening_cutoff_conformant": cutoff_conformant,
            "cutoff_policy": assignment.get("cutoff_policy"),
            "snapshot_terminal": snapshot_terminal,
            "target_snapshot_statuses": target_statuses,
            "input_materialized": materialized,
            "visibility_passed": visible,
            "actual_prediction_present": predicted,
            "formal_input_preconditions_met": formal_input_preconditions,
            "formal_scoring_eligible": formal_scoring_eligible,
            "frozen_split": frozen_split,
            "disposition": disposition,
            "primary_blocker": release_blockers[0] if release_blockers else None,
            "release_blockers": release_blockers,
        })

    dispositions = Counter(row["disposition"] for row in rows)
    missing_catalog_cases = dispositions.get("missing_catalog", 0)
    outcome_conditioned_cases = sum(
        row.get("actual_prediction_present", False)
        and row.get("catalog_development_eligible", False)
        and not row.get("catalog_formal_eligible", False)
        for row in rows
    )
    nonopening_input_cases = sum(
        row.get("actual_prediction_present", False)
        and not row.get("input_spec_opening_cutoff_conformant", False)
        for row in rows
        if row.get("catalog_assigned", False)
    )
    summary = {
        "schema_version": "1.0",
        "case_count": len(rows),
        "catalog_assigned_case_count": sum(row["catalog_assigned"] for row in rows),
        "actual_run_case_count": sum(row["actual_prediction_present"] for row in rows),
        "formal_input_preconditions_case_count": sum(
            row["formal_input_preconditions_met"] for row in rows
        ),
        "formal_scoring_eligible_case_count": sum(
            row.get("formal_scoring_eligible", False) for row in rows
        ),
        "development_only_actual_run_case_count": dispositions.get(
            "actual_run_development_only", 0
        ),
        "missing_catalog_case_count": missing_catalog_cases,
        "disposition_counts": dict(sorted(dispositions.items())),
        "grouped_split_frozen": split_frozen,
        "formal_subset_result_publishable": any(
            row.get("formal_scoring_eligible", False) for row in rows
        ),
        "full_50_formal_result_publishable": all(
            row.get("formal_scoring_eligible", False) for row in rows
        ),
        "formal_result_blockers": [
            f"{missing_catalog_cases} cases lack reusable independently constructed catalogs",
            f"{outcome_conditioned_cases} cases use outcome-conditioned external candidate frames",
            f"{nonopening_input_cases} actual-run cases do not use the PR-opening state",
            *([] if split_frozen else ["the relation-group split is not finalized as a blind release split"]),
        ],
        "unjudged_policy": (
            "Non-target candidates remain unjudged; precision, F1, false-positive "
            "rate, and specificity are not reported."
        ),
    }
    return rows, summary


def render(summary: dict[str, Any]) -> str:
    return "\n".join([
        "# Strict-E2 candidate-bounded pipeline progress",
        "",
        f"- Catalog assigned: {summary['catalog_assigned_case_count']}/{summary['case_count']}",
        f"- Actual offline prediction: {summary['actual_run_case_count']}/{summary['case_count']}",
        f"- Formal input preconditions (before split): {summary['formal_input_preconditions_case_count']}/{summary['case_count']}",
        f"- Development-only actual runs: {summary['development_only_actual_run_case_count']}",
        f"- Missing catalog: {summary['missing_catalog_case_count']}",
        "",
        (
            f"A formal subset contains {summary['formal_scoring_eligible_case_count']} cases; "
            "the full 50-case aggregate remains development/diagnostic."
            if summary["formal_subset_result_publishable"]
            else "No formal result is publishable."
        ),
        "The per-case audit records catalog, cutoff, snapshot, visibility, run status, split, and every release blocker.",
        "",
    ])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--e2-index", type=Path, default=E2_INDEX)
    parser.add_argument("--catalog-dir", type=Path, required=True)
    parser.add_argument("--snapshot-dir", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--visibility", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, action="append", required=True)
    parser.add_argument("--split-manifest", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    predictions = [
        row for path in args.predictions for row in read_jsonl(path)
    ]
    rows, summary = audit(
        read_jsonl(args.e2_index),
        read_jsonl(args.catalog_dir / "case-catalog-assignments.jsonl"),
        read_json(args.catalog_dir / "coverage-audit.json"),
        read_jsonl(args.snapshot_dir / "repository-snapshots.jsonl"),
        read_jsonl(args.inputs),
        read_jsonl(args.visibility),
        predictions,
        read_jsonl(args.split_manifest) if args.split_manifest else None,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "case-progress.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    (args.output_dir / "metrics.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (args.output_dir / "SUMMARY.md").write_text(render(summary), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

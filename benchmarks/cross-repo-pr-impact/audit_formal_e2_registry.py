#!/usr/bin/env python3
"""Audit chronological and evidence eligibility for a new formal E2 registry."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def catalog_id(reference: str) -> str:
    filename, separator, identifier = reference.partition("#")
    if filename != "candidate-repositories.json" or not separator or not identifier:
        raise ValueError(f"invalid catalog reference: {reference}")
    return identifier


def audit(
    catalogs: dict[str, Any],
    sources: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    labels: list[dict[str, Any]],
    legacy_source_families: set[str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_by_id = {row["candidate_id"]: row for row in sources}
    prediction_by_id = {row["candidate_id"]: row for row in predictions}
    label_by_id = {row["candidate_id"]: row for row in labels}
    if len(source_by_id) != len(sources) or len(prediction_by_id) != len(predictions) or len(label_by_id) != len(labels):
        raise ValueError("duplicate candidate_id")

    rows = []
    for candidate_id, source in sorted(source_by_id.items()):
        blockers = []
        identifier = catalog_id(source["candidate_repository_catalog"])
        catalog = catalogs.get(identifier)
        prediction = prediction_by_id.get(candidate_id)
        label = label_by_id.get(candidate_id)
        if catalog is None:
            blockers.append("catalog_missing")
        else:
            if catalog.get("membership_reads_labels") is not False:
                blockers.append("catalog_membership_reads_labels")
            if catalog.get("reused_across_source_events") is not True:
                blockers.append("catalog_not_reused")
            if len(catalog.get("repositories", [])) < 2:
                blockers.append("catalog_has_no_non_target_choice")
        opening = source.get("opening", {})
        if not opening.get("base_commit") or not opening.get("head_commit") or not opening.get("changed_paths"):
            blockers.append("opening_state_incomplete")
        if source.get("source_change_family") in legacy_source_families:
            blockers.append("overlaps_legacy_development_family")
        if prediction is None:
            blockers.append("blind_prediction_missing")
        if label is None:
            blockers.append("strict_e2_label_missing")
        else:
            if prediction and prediction["created_at"] >= label["revealed_at"]:
                blockers.append("prediction_not_before_label_reveal")
            targets = set(label.get("target_repositories", []))
            membership = set(catalog.get("repositories", [])) if catalog else set()
            if not targets or not targets.issubset(membership):
                blockers.append("target_not_covered_by_prior_catalog")
            arms = label.get("arms", {})
            if arms != {"A0": "pass", "A1": "fail", "A2": "pass"}:
                blockers.append("strict_three_arm_direction_missing")
            if label.get("same_command_all_arms") is not True:
                blockers.append("arm_command_changed")
            if label.get("a1_failure_signature_removed_in_a2") is not True:
                blockers.append("a2_does_not_remove_a1_signature")
        eligible = not blockers
        rows.append({
            "candidate_id": candidate_id,
            "source_change_family": source.get("source_change_family"),
            "catalog_id": identifier,
            "prediction_present": prediction is not None,
            "label_present": label is not None,
            "formal_e2_eligible": eligible,
            "blockers": blockers,
        })

    counts = Counter(blocker for row in rows for blocker in row["blockers"])
    eligible = [row["candidate_id"] for row in rows if row["formal_e2_eligible"]]
    summary = {
        "schema_version": "1.0",
        "source_candidate_count": len(rows),
        "blind_prediction_count": len(predictions),
        "label_count": len(labels),
        "formal_e2_eligible_count": len(eligible),
        "formal_e2_eligible_candidate_ids": eligible,
        "blocker_counts": dict(sorted(counts.items())),
        "formal_50_ready": len(eligible) == 50,
    }
    return rows, summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalogs", type=Path, required=True)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--legacy-index", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    legacy = {row["source_change_family"] for row in read_jsonl(args.legacy_index)}
    rows, summary = audit(
        read_json(args.catalogs)["catalogs"],
        read_jsonl(args.sources),
        read_jsonl(args.predictions),
        read_jsonl(args.labels),
        legacy,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "case-audit.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    (args.output_dir / "metrics.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if summary["formal_50_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

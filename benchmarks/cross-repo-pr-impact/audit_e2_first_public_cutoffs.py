#!/usr/bin/env python3
"""Record whether each E2 source diff can be observed at its opening event."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from materialize_e2_inputs import SOURCE_INPUTS


ROOT = Path(__file__).resolve().parent
DEFAULT_ASSIGNMENTS = (
    ROOT / "results" / "e2-candidate-catalog-build-2026-08-25"
    / "case-catalog-assignments.jsonl"
)


AFTER_OPENING_POLICIES = {
    "causal_commit_first_public_time_after_pr_creation",
    "causal_integration_commit_first_public_time_after_pr_creation",
    "causal_pull_request_commit_first_public_time_after_pr_creation",
    "causal_pull_request_head_first_public_time_after_pr_creation",
}
NO_OPENING_POLICIES = {
    "causal_direct_commit_diff_with_release_publication_cutoff_no_source_pr",
    "causal_direct_commit_public_timestamp_no_source_pr",
}
RELEASE_TRANSITION_POLICIES = {
    "causal_diff_with_release_publication_cutoff",
    "causal_direct_commit_diff_with_release_publication_cutoff",
    "causal_release_diff_with_release_publication_cutoff",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def exclusion_for_policy(policy: str) -> tuple[str, str, str]:
    if policy in AFTER_OPENING_POLICIES:
        return (
            "opening_state_lacks_causal_change",
            "An opening event is known, but the causal commit or head first appeared after it.",
            "Exclude from formal scoring: replacing the cutoff with the opening state removes the labeled source change.",
        )
    if policy in NO_OPENING_POLICIES:
        return (
            "no_source_opening_event",
            "The causal diff is a direct commit and no source pull/review opening event is recorded.",
            "Exclude from formal scoring: a commit or release timestamp is not a PR-opening snapshot under INPUT_SPEC.",
        )
    if policy in RELEASE_TRANSITION_POLICIES:
        return (
            "release_transition_has_no_recoverable_opening_snapshot",
            "The label is a release/version transition observed at publication; no singular opening snapshot is tied to the complete causal diff.",
            "Exclude from formal scoring: publication time can support development replay but cannot be relabeled as PR-opening time.",
        )
    raise ValueError(f"unclassified non-opening cutoff policy: {policy}")


def audit(
    assignments: list[dict[str, Any]],
    source_inputs: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = []
    for assignment in sorted(assignments, key=lambda row: row["case_id"]):
        case_id = assignment["case_id"]
        source = source_inputs.get(case_id)
        if source is None:
            raise ValueError(f"missing source input for {case_id}")
        conformant = bool(assignment.get("input_spec_opening_cutoff_conformant"))
        policy = assignment["cutoff_policy"]
        if conformant:
            disposition = "opening_snapshot_recovered"
            evidence_finding = (
                "The recorded source diff is the opening patch/head, or the causal "
                "change was already present at the recorded opening event."
            )
            formal_decision = "Retain for catalog and split eligibility checks."
            exclusion_class = None
        else:
            exclusion_class, evidence_finding, formal_decision = exclusion_for_policy(policy)
            disposition = "excluded_nonopening_source_state"
        rows.append({
            "case_id": case_id,
            "source_repository": source["repository"],
            "source_pull_request_number": source.get("pull_request_number"),
            "source_candidate_commit": source["candidate_commit"],
            "observation_cutoff": assignment["observation_cutoff"],
            "cutoff_policy": policy,
            "input_spec_opening_cutoff_conformant": conformant,
            "disposition": disposition,
            "exclusion_class": exclusion_class,
            "evidence_finding": evidence_finding,
            "formal_decision": formal_decision,
        })

    counts = Counter(row["disposition"] for row in rows)
    exclusions = Counter(
        row["exclusion_class"] for row in rows if row["exclusion_class"]
    )
    summary = {
        "schema_version": "1.0",
        "audit_scope": "strict_e2_source_first_public_opening_state",
        "case_count": len(rows),
        "opening_snapshot_recovered_case_count": counts.get(
            "opening_snapshot_recovered", 0
        ),
        "formal_source_state_excluded_case_count": counts.get(
            "excluded_nonopening_source_state", 0
        ),
        "exclusion_class_counts": dict(sorted(exclusions.items())),
        "all_nonopening_policies_explicitly_classified": True,
        "interpretation": (
            "Excluded cases retain valid strict-E2 causal evidence and may be used "
            "for development diagnostics, but their source state does not satisfy "
            "the INPUT_SPEC opening-time boundary."
        ),
    }
    return rows, summary


def render(summary: dict[str, Any]) -> str:
    return "\n".join([
        "# Strict-E2 first-public source-state audit",
        "",
        f"- Audited: {summary['case_count']}/{summary['case_count']}",
        f"- Opening-state conformant: {summary['opening_snapshot_recovered_case_count']}",
        f"- Explicitly excluded from formal scoring: {summary['formal_source_state_excluded_case_count']}",
        "",
        summary["interpretation"],
        "",
    ])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--assignments", type=Path, default=DEFAULT_ASSIGNMENTS)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    rows, summary = audit(read_jsonl(args.assignments), SOURCE_INPUTS)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.output_dir / "case-cutoff-audit.jsonl", rows)
    write_json(args.output_dir / "metrics.json", summary)
    (args.output_dir / "SUMMARY.md").write_text(render(summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

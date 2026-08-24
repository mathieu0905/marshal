#!/usr/bin/env python3
"""Capture and verify a recent OpenDev CI-contrast window."""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import json
from collections import Counter
from pathlib import Path
from typing import Any

from collect_opendev import ROOT, gerrit_json
from mine_ci_contrasts import build_records, mine_change, revision_records
from verify_ci_contrasts import verify_candidate


def query_changes(after: str) -> tuple[list[dict[str, Any]], int]:
    query = f'message:"Depends-On:" after:{after}'
    changes: list[dict[str, Any]] = []
    pages = 0
    while True:
        batch = gerrit_json(
            "/changes/",
            [
                ("q", query),
                ("n", "500"),
                ("S", str(len(changes))),
                ("o", "ALL_REVISIONS"),
                ("o", "ALL_COMMITS"),
                ("o", "MESSAGES"),
            ],
        )
        pages += 1
        changes.extend(batch)
        if not batch or not batch[-1].get("_more_changes"):
            return changes, pages


def search_frame_record(change: dict[str, Any]) -> dict[str, Any]:
    revisions = []
    for revision in revision_records(change):
        revisions.append({
            **revision,
            "check_builds": build_records(change, revision["number"]),
        })
    return {
        "change": int(change["_number"]),
        "project": change["project"],
        "status": change["status"],
        "subject": change["subject"],
        "created": change["created"],
        "updated": change["updated"],
        "current_revision": change.get("current_revision"),
        "revisions": revisions,
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def reason_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(row.get("reason", "unspecified") for row in rows).items()))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--after",
        required=True,
        help="Inclusive date used for both the Gerrit query and dependency-transition window.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "results" / f"opendev-rolling-{dt.date.today().isoformat()}",
    )
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    dt.date.fromisoformat(args.after)
    observed_at = dt.datetime.now(dt.timezone.utc).isoformat()
    query = f'message:"Depends-On:" after:{args.after}'
    changes, pages = query_changes(args.after)
    all_candidates = [
        candidate
        for change in changes
        for candidate in mine_change(change)
    ]
    candidates = [
        candidate
        for candidate in all_candidates
        if candidate["after_revision"]["created"] >= args.after
    ]

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(verify_candidate, candidate) for candidate in candidates]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())

    verified = sorted(
        (row for row in results if row["status"] == "composition_verified"),
        key=lambda row: (row["source_created"], row["source_pr"]),
    )
    unavailable = [row for row in results if row["status"] == "evidence_unavailable"]
    rejected = [row for row in results if row["status"] == "rejected"]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(
        args.output_dir / "search-frame.jsonl",
        sorted(
            (search_frame_record(change) for change in changes),
            key=lambda row: row["change"],
        ),
    )
    write_jsonl(args.output_dir / "transition-candidates.jsonl", candidates)
    write_jsonl(args.output_dir / "composition-verified.jsonl", verified)
    write_jsonl(args.output_dir / "composition-rejected.jsonl", rejected)
    write_jsonl(args.output_dir / "evidence-unavailable.jsonl", unavailable)

    summary = {
        "observed_at": observed_at,
        "query": query,
        "transition_after": args.after,
        "pages": pages,
        "matched_changes": len(changes),
        "matched_projects": len({change["project"] for change in changes}),
        "all_historical_transitions_in_matched_changes": len(all_candidates),
        "transitions_in_window": len(candidates),
        "composition_verified": len(verified),
        "composition_verified_jobs": sum(
            row["composition_verified_job_count"] for row in verified
        ),
        "evidence_unavailable": len(unavailable),
        "rejected": len(rejected),
        "rejection_reasons": reason_counts(rejected),
        "unavailable_reasons": reason_counts(unavailable),
        "semantic_review_status": "pending_manual_review",
        "claim_boundary": (
            "Composition verification is necessary but not sufficient. Every verified job "
            "must be checked against its failure signature and target patch before admission."
        ),
    }
    (args.output_dir / "run-summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

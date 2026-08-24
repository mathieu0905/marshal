#!/usr/bin/env python3
"""Audit opening revisions and semantic evidence for selected OpenDev pairs."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
from pathlib import Path
from typing import Any

from collect_opendev import ROOT, changed_paths, current_revision, gerrit_json


DEFAULT_REVIEWS = ROOT / "candidates" / "opendev-semantic-manual-review.jsonl"
DEFAULT_OUTPUT = ROOT / "candidates" / "opendev-semantic-revision-audit.jsonl"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def fetch_all_revisions(number: int) -> dict[str, Any]:
    detail = gerrit_json(
        f"/changes/{number}/detail",
        [("o", "ALL_REVISIONS"), ("o", "ALL_COMMITS")],
    )
    revisions = sorted(
        (
            {
                "commit": sha,
                "number": data["_number"],
                "created": data["created"],
                "commit_data": data.get("commit", {}),
            }
            for sha, data in detail["revisions"].items()
        ),
        key=lambda item: item["number"],
    )
    if not revisions:
        raise RuntimeError(f"change {number} has no revisions")
    return {"detail": detail, "revisions": revisions}


def revision_files(number: int, revision: str) -> list[str]:
    files = gerrit_json(f"/changes/{number}/revisions/{revision}/files/")
    return changed_paths(files)


def audit(review: dict[str, Any]) -> dict[str, Any]:
    source_number = review["source_change"]
    try:
        source_data = fetch_all_revisions(source_number)
        source_detail = source_data["detail"]
        opening = source_data["revisions"][0]
        opening_files = revision_files(source_number, opening["commit"])
        target_results = []
        for target_number in review["target_changes"]:
            target_data = fetch_all_revisions(target_number)
            target_detail = target_data["detail"]
            target_sha, target_revision = current_revision(target_detail)
            target_files = revision_files(target_number, target_sha)
            target_results.append({
                "change": target_number,
                "repository": target_detail["project"],
                "branch": target_detail["branch"],
                "subject": target_detail["subject"],
                "created": target_detail["created"],
                "submitted": target_detail.get("submitted"),
                "commit": target_sha,
                "commit_message": target_revision.get("commit", {}).get("message", ""),
                "changed_paths": target_files,
                "created_after_source": target_detail["created"] >= source_detail["created"],
            })
        checks = {
            "source_merged": source_detail["status"] == "MERGED",
            "opening_revision_available": bool(opening_files),
            "targets_merged": all(item["submitted"] for item in target_results),
            "targets_created_after_source": all(
                item["created_after_source"] for item in target_results
            ),
            "target_paths_available": all(item["changed_paths"] for item in target_results),
        }
        return {
            **review,
            "status": "passed" if all(checks.values()) else "failed",
            "checks": checks,
            "source": {
                "repository": source_detail["project"],
                "subject": source_detail["subject"],
                "created": source_detail["created"],
                "submitted": source_detail.get("submitted"),
                "branch": source_detail["branch"],
                "opening_revision_number": opening["number"],
                "opening_commit": opening["commit"],
                "opening_commit_message": opening["commit_data"].get("message", ""),
                "opening_parent": opening["commit_data"]["parents"][0]["commit"],
                "opening_changed_paths": opening_files,
                "revision_count": len(source_data["revisions"]),
            },
            "targets": target_results,
        }
    except Exception as exc:
        return {
            **review,
            "status": "fetch_failed",
            "error": str(exc),
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reviews", type=Path, default=DEFAULT_REVIEWS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    reviews = read_jsonl(args.reviews)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        results = list(executor.map(audit, reviews))
    results.sort(key=lambda item: item["source_change"])
    args.output.write_text(
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in results),
        encoding="utf-8",
    )
    statuses: dict[str, int] = {}
    for item in results:
        statuses[item["status"]] = statuses.get(item["status"], 0) + 1
    print(json.dumps({
        "cases": len(results),
        "statuses": statuses,
        "relation_families": sorted({item["relation_family"] for item in results}),
        "output": str(args.output),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Recover opening-time source snapshots for reviewed multi-target cases."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
from pathlib import Path
from typing import Any

from collect_opendev import ROOT
from recover_github_opening_snapshots import compare_details, gh_api, pull_timeline


DEFAULT_POOL = ROOT / "candidates" / "github-multi-target-review-enriched.jsonl"
DEFAULT_REVIEWS = ROOT / "candidates" / "github-multi-target-manual-review.jsonl"
DEFAULT_OUTPUT = ROOT / "candidates" / "github-multi-target-opening-snapshots.jsonl"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def recover(case: dict[str, Any]) -> dict[str, Any]:
    source = case["source"]
    repository = source["repository"]
    number = source["pull_request"]
    result: dict[str, Any] = {
        "source_repository": repository,
        "source_pull_request": number,
        "observation_cutoff": source["created_at"],
    }
    try:
        timeline = pull_timeline(repository, number)
        force_pushes = sorted(
            (
                item for item in timeline["timelineItems"]["nodes"]
                if item.get("__typename") == "HeadRefForcePushedEvent"
                and item.get("beforeCommit", {}).get("oid")
            ),
            key=lambda item: item["createdAt"],
        )
        title_changes = sorted(
            (
                item for item in timeline["timelineItems"]["nodes"]
                if item.get("__typename") == "RenamedTitleEvent"
            ),
            key=lambda item: item["createdAt"],
        )
        opening_title = (
            title_changes[0]["previousTitle"] if title_changes else source["title"]
        )
        if force_pushes:
            head = force_pushes[0]["beforeCommit"]["oid"]
            comparison_ref = timeline["baseRefName"]
            try:
                comparison = compare_details(repository, comparison_ref, head)
                method = "earliest_force_push_full_branch_diff"
            except RuntimeError:
                repository_detail = gh_api(f"repos/{repository}")
                default_branch = repository_detail["default_branch"]
                if comparison_ref == default_branch:
                    raise
                comparison_ref = default_branch
                comparison = compare_details(repository, comparison_ref, head)
                method = "earliest_force_push_diff_after_base_branch_rename"
            merge_base = comparison.get("merge_base_commit")
            if not merge_base:
                raise RuntimeError("opening head has no merge base with the target branch")
            base = merge_base["sha"]
        else:
            commits = [node["commit"] for node in timeline["commits"]["nodes"]]
            opening_commits = [
                commit for commit in commits
                if commit["committedDate"] <= source["created_at"]
            ]
            if not opening_commits:
                raise RuntimeError("no current-chain commit predates PR creation")
            first_parents = opening_commits[0]["parents"]["nodes"]
            if not first_parents:
                raise RuntimeError("first opening commit has no parent")
            base = first_parents[0]["oid"]
            head = opening_commits[-1]["oid"]
            comparison = compare_details(repository, base, head)
            method = "creation_time_current_chain"
        paths = sorted({item["filename"] for item in comparison.get("files", [])})
        if not paths:
            raise RuntimeError("opening snapshot has no changed paths")
        result.update({
            "status": "recovered",
            "method": method,
            "base_commit": base,
            "candidate_commit": head,
            "changed_paths": paths,
            "branch": timeline["baseRefName"],
            "comparison_ref": comparison_ref if force_pushes else None,
            "subject": opening_title,
            "force_push_events_observed": len(force_pushes),
            "timeline_complete_within_api_page": True,
        })
    except Exception as exc:
        result.update({"status": "unrecoverable", "error": str(exc)})
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pool", type=Path, default=DEFAULT_POOL)
    parser.add_argument("--reviews", type=Path, default=DEFAULT_REVIEWS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    pool = {
        (item["source_repository"], item["source_pull_request"]): item
        for item in read_jsonl(args.pool)
    }
    selected = [
        pool[(review["source_repository"], review["source_pull_request"])]
        for review in read_jsonl(args.reviews)
        if review["decision"] == "accept_for_target_audit"
    ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        results = list(executor.map(recover, selected))
    results.sort(key=lambda item: (
        item["source_repository"], item["source_pull_request"]
    ))
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
        "methods": {
            method: sum(item.get("method") == method for item in results)
            for method in sorted({item.get("method") for item in results if item.get("method")})
        },
        "output": str(args.output),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

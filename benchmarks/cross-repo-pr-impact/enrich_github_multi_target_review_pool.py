#!/usr/bin/env python3
"""Fetch source metadata and apply basic chronology checks to the review pool."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
from pathlib import Path
from typing import Any

from collect_github_spec_candidates import gh_api, pull_files
from collect_opendev import ROOT


DEFAULT_INPUT = ROOT / "candidates" / "github-multi-target-review-pool.jsonl"
DEFAULT_OUTPUT = ROOT / "candidates" / "github-multi-target-review-enriched.jsonl"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def enrich(case: dict[str, Any]) -> dict[str, Any]:
    result = dict(case)
    repository = case["source_repository"]
    number = case["source_pull_request"]
    try:
        pull = gh_api(f"repos/{repository}/pulls/{number}")
        changed_paths = pull_files(repository, number)
        source_created = pull["created_at"]
        eligible_targets = [
            target for target in case["candidate_targets"]
            if target["created_at"] >= source_created
        ]
        excluded_targets = [
            target for target in case["candidate_targets"]
            if target["created_at"] < source_created
        ]
        result.update({
            "source": {
                "repository": repository,
                "pull_request": number,
                "url": pull["html_url"],
                "title": pull["title"],
                "body": pull.get("body") or "",
                "created_at": source_created,
                "merged_at": pull.get("merged_at"),
                "base_branch": pull["base"]["ref"],
                "final_base_commit": pull["base"]["sha"],
                "final_head_commit": pull["head"]["sha"],
                "final_changed_paths": changed_paths,
            },
            "candidate_targets": eligible_targets,
            "chronology_excluded_targets": excluded_targets,
            "candidate_target_repositories": sorted({
                target["repository"] for target in eligible_targets
            }),
            "candidate_target_repository_count": len({
                target["repository"] for target in eligible_targets
            }),
            "candidate_target_pull_request_count": len(eligible_targets),
        })
        reasons = []
        if not pull.get("merged_at"):
            reasons.append("source_not_merged")
        if not changed_paths:
            reasons.append("source_changed_paths_empty")
        if not eligible_targets:
            reasons.append("no_target_created_after_source")
        result["machine_status"] = "eligible_for_manual_review" if not reasons else "rejected"
        result["machine_rejection_reasons"] = reasons
    except Exception as exc:
        result.update({
            "machine_status": "fetch_failed",
            "machine_rejection_reasons": ["source_fetch_failed"],
            "fetch_error": str(exc),
        })
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    cases = read_jsonl(args.input)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        results = list(executor.map(enrich, cases))
    results.sort(key=lambda item: item["review_rank"])
    args.output.write_text(
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in results),
        encoding="utf-8",
    )
    statuses: dict[str, int] = {}
    for item in results:
        statuses[item["machine_status"]] = statuses.get(item["machine_status"], 0) + 1
    eligible = [item for item in results if item["machine_status"] == "eligible_for_manual_review"]
    print(json.dumps({
        "cases": len(results),
        "statuses": statuses,
        "eligible_multi_target_cases": sum(
            item["candidate_target_repository_count"] > 1 for item in eligible
        ),
        "eligible_directed_repository_relations": len({
            (item["source_repository"], target)
            for item in eligible
            for target in item["candidate_target_repositories"]
        }),
        "chronology_excluded_targets": sum(
            len(item.get("chronology_excluded_targets", [])) for item in results
        ),
        "output": str(args.output),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Audit merged target metadata and changed paths for accepted review decisions."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
from pathlib import Path
from typing import Any

from collect_github_spec_candidates import gh_api, pull_files
from collect_opendev import ROOT


DEFAULT_POOL = ROOT / "candidates" / "github-multi-target-review-enriched.jsonl"
DEFAULT_REVIEWS = ROOT / "candidates" / "github-multi-target-manual-review.jsonl"
DEFAULT_OUTPUT = ROOT / "candidates" / "github-multi-target-target-audit.jsonl"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def audit_target(job: dict[str, Any]) -> dict[str, Any]:
    source = job["source"]
    target = job["target"]
    result = {
        "source_repository": source["repository"],
        "source_pull_request": source["pull_request"],
        "target_repository": target["repository"],
        "target_pull_request": target["pull_request"],
    }
    try:
        pull = gh_api(
            f"repos/{target['repository']}/pulls/{target['pull_request']}"
        )
        paths = pull_files(target["repository"], target["pull_request"])
        source_url = (
            f"github.com/{source['repository']}/pull/{source['pull_request']}"
        ).lower()
        checks = {
            "target_merged": bool(pull.get("merged_at")),
            "target_created_after_source": pull["created_at"] >= source["created_at"],
            "target_body_links_source": source_url in (pull.get("body") or "").lower(),
            "target_changed_paths_nonempty": bool(paths),
        }
        result.update({
            "status": "passed" if all(checks.values()) else "failed",
            "checks": checks,
            "target": {
                "url": pull["html_url"],
                "title": pull["title"],
                "created_at": pull["created_at"],
                "merged_at": pull.get("merged_at"),
                "base_branch": pull["base"]["ref"],
                "base_commit": pull["base"]["sha"],
                "head_commit": pull["head"]["sha"],
                "changed_paths": paths,
            },
        })
    except Exception as exc:
        result.update({"status": "fetch_failed", "error": str(exc)})
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
    jobs = []
    for review in read_jsonl(args.reviews):
        case = pool[(review["source_repository"], review["source_pull_request"])]
        for decision in review["target_decisions"]:
            if decision["decision"] != "accept":
                continue
            jobs.append({
                "source": case["source"],
                "target": decision,
            })
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        results = list(executor.map(audit_target, jobs))
    results.sort(key=lambda item: (
        item["source_repository"],
        item["source_pull_request"],
        item["target_repository"],
        item["target_pull_request"],
    ))
    args.output.write_text(
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in results),
        encoding="utf-8",
    )
    statuses: dict[str, int] = {}
    for item in results:
        statuses[item["status"]] = statuses.get(item["status"], 0) + 1
    print(json.dumps({
        "targets": len(results),
        "statuses": statuses,
        "source_cases_with_passed_targets": len({
            (item["source_repository"], item["source_pull_request"])
            for item in results if item["status"] == "passed"
        }),
        "output": str(args.output),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Collect cross-repository spec-to-implementation PR candidates from GitHub."""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any

from collect_opendev import ROOT


ECOSYSTEMS = {
    "ethereum": {
        "source": "ethereum/EIPs",
        "target": "ethereum/go-ethereum",
        "source_path": re.compile(r"^EIPS/eip-\d+\.md$", re.IGNORECASE),
        "sample": 30,
    },
    "kubernetes": {
        "source": "kubernetes/enhancements",
        "target": "kubernetes/kubernetes",
        "source_path": re.compile(r"^keps/", re.IGNORECASE),
        "sample": 55,
    },
    "python": {
        "source": "python/peps",
        "target": "python/cpython",
        "source_path": re.compile(r"^peps/pep-\d+\.rst$", re.IGNORECASE),
        "sample": 20,
    },
    "rust": {
        "source": "rust-lang/rfcs",
        "target": "rust-lang/rust",
        "source_path": re.compile(r"^text/\d+-.*\.md$", re.IGNORECASE),
        "sample": 55,
    },
}


def gh_api(endpoint: str, fields: dict[str, str] | None = None) -> Any:
    command = ["gh", "api", endpoint, "--method", "GET"]
    for key, value in (fields or {}).items():
        command.extend(["-f", f"{key}={value}"])
    for attempt in range(4):
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode == 0:
            return json.loads(result.stdout)
        if attempt == 3:
            raise RuntimeError(result.stderr.strip() or f"gh api failed for {endpoint}")
        time.sleep(1.5 * (attempt + 1))
    raise AssertionError("unreachable")


def search_target_prs(
    source: str, target: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    query = f'repo:{target} is:pr is:merged in:body "github.com/{source}/pull/"'
    items = []
    total_count = 0
    incomplete_results = False
    for page in range(1, 11):
        payload = gh_api("search/issues", {
            "q": query,
            "per_page": "100",
            "page": str(page),
            "sort": "created",
            "order": "asc",
        })
        total_count = int(payload["total_count"])
        incomplete_results = incomplete_results or bool(payload["incomplete_results"])
        items.extend(payload["items"])
        visible_count = min(total_count, 1000)
        if len(items) >= visible_count or not payload["items"]:
            break
    metadata = {
        "query": query,
        "sort": "created",
        "order": "asc",
        "total_count": total_count,
        "incomplete_results": incomplete_results,
        "search_items_fetched": len(items),
        "github_search_cap": 1000,
        "truncated": incomplete_results or total_count > 1000,
    }
    return items, metadata


def systematic_sample(items: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    if len(items) <= count:
        return items
    return [items[((2 * index + 1) * len(items)) // (2 * count)] for index in range(count)]


def pull_files(repository: str, number: int) -> list[str]:
    paths = []
    for page in range(1, 20):
        batch = gh_api(
            f"repos/{repository}/pulls/{number}/files",
            {"per_page": "100", "page": str(page)},
        )
        paths.extend(item["filename"] for item in batch)
        if len(batch) < 100:
            break
    return sorted(set(paths))


def link_excerpt(body: str, source: str, number: int) -> str:
    url = f"github.com/{source}/pull/{number}"
    lines = body.replace("\r", "").splitlines()
    for index, line in enumerate(lines):
        if url in line:
            start = max(0, index - 1)
            end = min(len(lines), index + 2)
            return "\n".join(part.strip() for part in lines[start:end] if part.strip())[:1200]
    return ""


def inspect_pair(ecosystem: str, source_number: int, target_number: int) -> dict[str, Any]:
    config = ECOSYSTEMS[ecosystem]
    source_repo = config["source"]
    target_repo = config["target"]
    source = gh_api(f"repos/{source_repo}/pulls/{source_number}")
    target = gh_api(f"repos/{target_repo}/pulls/{target_number}")
    source_commits = gh_api(
        f"repos/{source_repo}/pulls/{source_number}/commits",
        {"per_page": "1", "page": "1"},
    )
    first_source_commit = source_commits[0] if source_commits else None
    source_commit = (
        gh_api(f"repos/{source_repo}/commits/{first_source_commit['sha']}")
        if first_source_commit else None
    )
    source_paths = sorted({item["filename"] for item in (source_commit or {}).get("files", [])})
    target_paths = pull_files(target_repo, target_number)
    reasons = []
    if not source.get("merged_at") or not target.get("merged_at"):
        reasons.append("not_both_merged")
    if source.get("created_at") and source["created_at"] > target["created_at"]:
        reasons.append("source_pr_created_after_target")
    if not source_commit or not source_commit.get("parents"):
        reasons.append("source_initial_commit_unavailable")
    if not any(config["source_path"].search(path) for path in source_paths):
        reasons.append("source_does_not_change_expected_spec_path")
    excerpt = link_excerpt(target.get("body") or "", source_repo, source_number)
    if not excerpt:
        reasons.append("target_body_lacks_direct_source_pr_link")
    if not source_paths or not target_paths:
        reasons.append("empty_changed_paths")
    return {
        "status": "eligible_for_manual_review" if not reasons else "rejected",
        "rejection_reasons": reasons,
        "ecosystem": ecosystem,
        "source": {
            "repository": source_repo,
            "number": source_number,
            "url": source["html_url"],
            "title": source["title"],
            "body": source.get("body") or "",
            "created_at": source["created_at"],
            "merged_at": source["merged_at"],
            "base_commit": source_commit["parents"][0]["sha"] if source_commit and source_commit.get("parents") else None,
            "head_commit": source_commit["sha"] if source_commit else None,
            "candidate_created_at": (
                source_commit["commit"]["committer"]["date"] if source_commit else None
            ),
            "changed_paths": source_paths,
        },
        "target": {
            "repository": target_repo,
            "number": target_number,
            "url": target["html_url"],
            "title": target["title"],
            "body": target.get("body") or "",
            "created_at": target["created_at"],
            "merged_at": target["merged_at"],
            "base_commit": target["base"]["sha"],
            "head_commit": target["head"]["sha"],
            "changed_paths": target_paths,
            "source_link_excerpt": excerpt,
        },
    }


def candidate_pairs(
    ecosystem: str,
) -> tuple[list[tuple[str, int, int]], dict[str, Any]]:
    config = ECOSYSTEMS[ecosystem]
    source = config["source"]
    link_re = re.compile(rf"https?://github\.com/{re.escape(source)}/pull/(\d+)", re.IGNORECASE)
    pairs = []
    search_items, metadata = search_target_prs(source, config["target"])
    for item in search_items:
        source_numbers = sorted({int(match) for match in link_re.findall(item.get("body") or "")})
        if len(source_numbers) != 1:
            continue
        pairs.append((ecosystem, source_numbers[0], int(item["number"])))
    pairs.sort(key=lambda item: (item[1], item[2]))
    sampled = systematic_sample(pairs, config["sample"])
    metadata.update({
        "ecosystem": ecosystem,
        "source_repository": source,
        "target_repository": config["target"],
        "single_source_link_pairs": len(pairs),
        "configured_sample_quota": config["sample"],
        "sampled_pairs": len(sampled),
        "sampling_order": "source pull-request number, then target pull-request number",
    })
    return sampled, metadata


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "candidates" / "github-spec-candidates.jsonl",
    )
    parser.add_argument(
        "--search-metadata",
        type=Path,
        default=ROOT / "candidates" / "github-spec-search-metadata.json",
    )
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    pairs = []
    search_metadata = []
    for ecosystem in ECOSYSTEMS:
        ecosystem_pairs, metadata = candidate_pairs(ecosystem)
        pairs.extend(ecosystem_pairs)
        search_metadata.append(metadata)
    args.search_metadata.parent.mkdir(parents=True, exist_ok=True)
    args.search_metadata.write_text(
        json.dumps({
            "schema_version": "1.0",
            "observed_at": dt.datetime.now(dt.UTC).isoformat(),
            "search_order": "created ascending",
            "ecosystems": search_metadata,
            "limitations": (
                "查询只匹配目标 PR 正文中的完整源 PR 链接；裸编号、提交说明引用和"
                "间接 issue 引用不在抽样框内。"
            ),
        }, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(inspect_pair, *pair): pair for pair in pairs}
        for future in concurrent.futures.as_completed(futures):
            try:
                results.append(future.result())
            except Exception as exc:
                ecosystem, source_number, target_number = futures[future]
                results.append({
                    "status": "fetch_failed",
                    "ecosystem": ecosystem,
                    "source_number": source_number,
                    "target_number": target_number,
                    "error": str(exc),
                })
    results.sort(key=lambda item: (
        item["ecosystem"],
        item.get("source", {}).get("number", item.get("source_number", 0)),
        item.get("target", {}).get("number", item.get("target_number", 0)),
    ))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for item in results:
            handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
    counts: dict[str, int] = {}
    for item in results:
        key = f"{item['ecosystem']}:{item['status']}"
        counts[key] = counts.get(key, 0) + 1
    print(json.dumps({
        "pairs_inspected": len(pairs),
        "truncated_ecosystems": [
            item["ecosystem"] for item in search_metadata if item["truncated"]
        ],
        "results": counts,
        "output": str(args.output),
        "search_metadata": str(args.search_metadata),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

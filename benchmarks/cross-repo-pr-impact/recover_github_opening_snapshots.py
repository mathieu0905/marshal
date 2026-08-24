#!/usr/bin/env python3
"""Recover the source revision that was visible when each reviewed GitHub PR opened."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import subprocess
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
CANDIDATES = ROOT / "candidates" / "github-spec-candidates.jsonl"
REVIEWS = ROOT / "candidates" / "github-spec-manual-review.jsonl"
DEFAULT_OUTPUT = ROOT / "candidates" / "github-spec-opening-snapshots.jsonl"


def gh_api(endpoint: str, fields: dict[str, str | int] | None = None) -> Any:
    command = ["gh", "api", endpoint]
    for key, value in (fields or {}).items():
        flag = "-F" if isinstance(value, int) else "-f"
        command.extend([flag, f"{key}={value}"])
    for attempt in range(3):
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode == 0:
            return json.loads(result.stdout)
        if attempt < 2:
            time.sleep(attempt + 1)
    raise RuntimeError(result.stderr.strip() or f"gh api failed for {endpoint}")


def pull_timeline(repository: str, number: int) -> dict[str, Any]:
    owner, name = repository.split("/", 1)
    query = """
      query($owner:String!, $name:String!, $number:Int!) {
        repository(owner:$owner, name:$name) {
          pullRequest(number:$number) {
            createdAt
            baseRefName
            commits(first:100) {
              pageInfo { hasNextPage }
              nodes { commit { oid committedDate parents(first:1) { nodes { oid } } } }
            }
            timelineItems(first:100, itemTypes:[HEAD_REF_FORCE_PUSHED_EVENT, RENAMED_TITLE_EVENT]) {
              pageInfo { hasNextPage }
              nodes {
                ... on HeadRefForcePushedEvent {
                  __typename
                  createdAt
                  beforeCommit { oid }
                  afterCommit { oid }
                }
                ... on RenamedTitleEvent {
                  __typename
                  createdAt
                  previousTitle
                  currentTitle
                }
              }
            }
          }
        }
      }
    """
    payload = gh_api("graphql", {
        "query": query,
        "owner": owner,
        "name": name,
        "number": number,
    })
    pull = payload.get("data", {}).get("repository", {}).get("pullRequest")
    if not pull:
        raise RuntimeError("pull request timeline is unavailable")
    if pull["commits"]["pageInfo"]["hasNextPage"]:
        raise RuntimeError("pull request has more than 100 commits")
    return pull


def commit_details(repository: str, commit: str) -> dict[str, Any]:
    return gh_api(f"repos/{repository}/commits/{commit}")


def compare_details(repository: str, base: str, head: str) -> dict[str, Any]:
    return gh_api(f"repos/{repository}/compare/{base}...{head}")


def recover(candidate: dict[str, Any]) -> dict[str, Any]:
    source = candidate["source"]
    repository = source["repository"]
    number = source["number"]
    result: dict[str, Any] = {
        "ecosystem": candidate["ecosystem"],
        "source_repository": repository,
        "source_number": number,
        "target_repository": candidate["target"]["repository"],
        "target_number": candidate["target"]["number"],
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
            comparison = compare_details(repository, timeline["baseRefName"], head)
            merge_base = comparison.get("merge_base_commit")
            if not merge_base:
                raise RuntimeError("opening head has no merge base with the target branch")
            base = merge_base["sha"]
            paths = sorted({item["filename"] for item in comparison.get("files", [])})
            method = "earliest_force_push_full_branch_diff"
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
            paths = sorted({item["filename"] for item in comparison.get("files", [])})
            method = "creation_time_current_chain"
        if not paths:
            raise RuntimeError("opening snapshot has no changed paths")
        target_pull = gh_api(
            f"repos/{candidate['target']['repository']}/pulls/{candidate['target']['number']}"
        )
        result.update({
            "status": "recovered",
            "method": method,
            "base_commit": base,
            "candidate_commit": head,
            "changed_paths": paths,
            "branch": timeline["baseRefName"],
            "subject": opening_title,
            "target_branch": target_pull["base"]["ref"],
        })
    except Exception as exc:
        result.update({"status": "unrecoverable", "error": str(exc)})
    return result


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    accepted = {
        (row["ecosystem"], row["source_number"], row["target_number"])
        for row in read_jsonl(REVIEWS)
        if row["decision"] == "accept"
    }
    candidates = [
        row for row in read_jsonl(CANDIDATES)
        if "source" in row
        and "target" in row
        and (row["ecosystem"], row["source"]["number"], row["target"]["number"])
        in accepted
    ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        results = list(executor.map(recover, candidates))
    results.sort(key=lambda row: (row["ecosystem"], row["source_number"], row["target_number"]))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for row in results:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    counts: dict[str, int] = {}
    for row in results:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    print(json.dumps({"count": len(results), "status": counts, "output": str(args.output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

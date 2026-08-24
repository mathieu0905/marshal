#!/usr/bin/env python3
"""Resolve candidate repositories to their latest commit before each case cutoff."""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from collect_github_spec_candidates import gh_api
from collect_opendev import ROOT


DEFAULT_OUTPUT = ROOT / "repository-snapshots.jsonl"
GITHUB_PROJECTS = {
    "ethereum", "kubernetes", "opencontainers-image", "opencontainers-runtime",
    "opentelemetry", "python", "rust",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def rfc3339(value: str) -> str:
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.UTC)
    return parsed.astimezone(dt.UTC).isoformat().replace("+00:00", "Z")


def opendev_api(repository: str, cutoff: str) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode({"limit": 1, "until": cutoff})
    url = f"https://opendev.org/api/v1/repos/{repository}/commits?{query}"
    request = urllib.request.Request(url, headers={"User-Agent": "marshal-evaluation-collector"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except (urllib.error.URLError, TimeoutError):
            if attempt == 3:
                raise
            time.sleep(attempt + 1)
    raise AssertionError("unreachable")


def resolve(project: str, repository: str, cutoff: str) -> dict[str, Any]:
    host = "github.com" if project in GITHUB_PROJECTS else "opendev.org"
    try:
        if host == "github.com":
            commits = gh_api(
                f"repos/{repository}/commits",
                {"until": cutoff, "per_page": "1"},
            )
            if not commits:
                return {"repository": repository, "host": host, "status": "not_created_by_cutoff"}
            commit = commits[0]
            sha = commit["sha"]
            committed_at = commit["commit"]["committer"]["date"]
            archive_url = f"https://github.com/{repository}/archive/{sha}.tar.gz"
        else:
            commits = opendev_api(repository, cutoff)
            if not commits:
                return {"repository": repository, "host": host, "status": "not_created_by_cutoff"}
            commit = commits[0]
            sha = commit["sha"]
            committed_at = commit["created"]
            archive_url = (
                f"https://opendev.org/api/v1/repos/{repository}/archive/{sha}.tar.gz"
            )
        return {
            "repository": repository,
            "host": host,
            "status": "available",
            "commit": sha,
            "committed_at": committed_at,
            "archive_url": archive_url,
        }
    except Exception as exc:
        return {
            "repository": repository,
            "host": host,
            "status": "fetch_failed",
            "error": str(exc),
        }


def collect(workers: int) -> list[dict[str, Any]]:
    inputs = read_jsonl(ROOT / "inputs.jsonl")
    catalogs = json.loads(
        (ROOT / "candidate-repositories.json").read_text(encoding="utf-8")
    )["catalogs"]
    jobs = []
    for item in inputs:
        project = item["candidate_repository_catalog"].split("#", 1)[1]
        cutoff = rfc3339(item["observation_cutoff"])
        for repository in catalogs[project]["repositories"]:
            jobs.append((item["case_id"], project, repository, cutoff))

    def run(job: tuple[str, str, str, str]) -> tuple[str, dict[str, Any]]:
        case_id, project, repository, cutoff = job
        return case_id, resolve(project, repository, cutoff)

    by_case: dict[str, list[dict[str, Any]]] = {item["case_id"]: [] for item in inputs}
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        for case_id, result in executor.map(run, jobs):
            by_case[case_id].append(result)
    return [{
        "case_id": item["case_id"],
        "observation_cutoff": rfc3339(item["observation_cutoff"]),
        "repositories": sorted(by_case[item["case_id"]], key=lambda row: row["repository"]),
    } for item in inputs]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    rows = collect(args.workers)
    args.output.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    statuses: dict[str, int] = {}
    for row in rows:
        for repository in row["repositories"]:
            status = repository["status"]
            statuses[status] = statuses.get(status, 0) + 1
    print(json.dumps({
        "cases": len(rows),
        "repository_snapshots": sum(len(row["repositories"]) for row in rows),
        "statuses": statuses,
        "output": str(args.output),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

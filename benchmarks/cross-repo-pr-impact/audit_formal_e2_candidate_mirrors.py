#!/usr/bin/env python3
"""Verify that every available cutoff snapshot is readable from local mirrors."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

from collect_formal_e2_candidate_mirrors import repository_path


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def check_repository_commits(
    repository: str,
    commits: list[str],
    mirror_root: Path,
    runner: Callable[..., subprocess.CompletedProcess[bytes]] = subprocess.run,
) -> dict[str, Any]:
    mirror = repository_path(mirror_root, repository)
    if not mirror.is_dir():
        return {"repository": repository, "status": "mirror_missing", "missing_commits": commits}
    process = runner(
        ["git", "--git-dir", str(mirror), "cat-file", "--batch-check=%(objectname) %(objecttype)"],
        input="".join(f"{commit}^{{commit}}\n" for commit in commits).encode(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if process.returncode != 0:
        return {
            "repository": repository,
            "status": "git_read_failed",
            "missing_commits": commits,
            "error": process.stderr.decode(errors="replace")[-1000:],
        }
    responses = process.stdout.decode(errors="replace").splitlines()
    missing = [
        commit
        for commit, response in zip(commits, responses)
        if response.endswith(" missing") or not response.endswith(" commit")
    ]
    if len(responses) != len(commits):
        missing.extend(commits[len(responses):])
    return {
        "repository": repository,
        "status": "available" if not missing else "commit_missing",
        "requested_commit_count": len(commits),
        "missing_commits": sorted(set(missing)),
    }


def audit(
    snapshots: list[dict[str, Any]], mirror_root: Path, workers: int,
    checker: Callable[[str, list[str], Path], dict[str, Any]] = check_repository_commits,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    commits_by_repository: dict[str, set[str]] = defaultdict(set)
    available_references = 0
    for case in snapshots:
        for repository in case["repositories"]:
            if repository["status"] != "available":
                continue
            available_references += 1
            commits_by_repository[repository["repository"]].add(repository["commit"])
    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(checker, repository, sorted(commits), mirror_root): repository
            for repository, commits in commits_by_repository.items()
        }
        for future in concurrent.futures.as_completed(futures):
            rows.append(future.result())
    rows.sort(key=lambda row: row["repository"])
    missing = sum(len(row["missing_commits"]) for row in rows)
    metrics = {
        "schema_version": "1.0",
        "case_count": len(snapshots),
        "repository_count": len(rows),
        "available_snapshot_reference_count": available_references,
        "unique_cutoff_commit_count": sum(len(commits) for commits in commits_by_repository.values()),
        "missing_cutoff_commit_count": missing,
        "all_cutoff_code_available_offline": missing == 0 and all(
            row["status"] == "available" for row in rows
        ),
        "labels_read": False,
        "network_used": False,
    }
    return rows, metrics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshots", type=Path, required=True)
    parser.add_argument("--mirror-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args()
    rows, metrics = audit(read_jsonl(args.snapshots), args.mirror_root, args.workers)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "mirror-audit.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    write_json(args.output_dir / "metrics.json", metrics)
    print(json.dumps(metrics, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if metrics["all_cutoff_code_available_offline"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

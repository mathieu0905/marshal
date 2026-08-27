#!/usr/bin/env python3
"""Resolve formal source-frame snapshots with a durable per-case checkpoint."""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Callable

from collect_e2_candidate_snapshots import collect, read_json, read_jsonl, write_json, write_jsonl
from collect_formal_e2_candidate_mirrors import repository_path


def local_git_resolver(mirror_root: Path) -> Callable[[str, str, str], dict[str, Any]]:
    def resolve(_project: str, repository: str, cutoff: str) -> dict[str, Any]:
        mirror = repository_path(mirror_root, repository)
        if not mirror.is_dir():
            return {
                "repository": repository,
                "host": "opendev.org",
                "status": "fetch_failed",
                "error": f"complete local mirror is missing: {mirror}",
            }
        commit = subprocess.run(
            ["git", "--git-dir", str(mirror), "rev-list", "-1", f"--before={cutoff}", "refs/heads/master"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
        )
        if commit.returncode:
            return {
                "repository": repository,
                "host": "opendev.org",
                "status": "fetch_failed",
                "error": commit.stderr.strip()[-2000:],
            }
        revision = commit.stdout.strip()
        if not revision:
            return {"repository": repository, "host": "opendev.org", "status": "not_created_by_cutoff"}
        committed_at = subprocess.run(
            ["git", "--git-dir", str(mirror), "show", "-s", "--format=%cI", revision],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True,
        ).stdout.strip()
        return {
            "repository": repository,
            "host": "opendev.org",
            "status": "available",
            "commit": revision,
            "committed_at": committed_at,
            "archive_url": f"https://opendev.org/api/v1/repos/{repository}/archive/{revision}.tar.gz",
        }

    return resolve


def metrics_for(
    rows: list[dict[str, Any]], expected_cases: int, network_used: bool = True
) -> dict[str, Any]:
    statuses = Counter(
        repository["status"]
        for row in rows
        for repository in row["repositories"]
    )
    return {
        "schema_version": "1.0",
        "expected_case_count": expected_cases,
        "completed_case_count": len(rows),
        "repository_snapshot_count": sum(len(row["repositories"]) for row in rows),
        "status_counts": dict(sorted(statuses.items())),
        "all_cases_completed": len(rows) == expected_cases,
        "all_resolutions_terminal": not statuses.get("fetch_failed", 0),
        "network_used": network_used,
    }


def collect_checkpointed(
    catalogs: dict[str, Any],
    assignments: list[dict[str, Any]],
    output_dir: Path,
    workers: int,
    collector: Callable[..., list[dict[str, Any]]] = collect,
    case_batch_size: int = 1,
    network_used: bool = True,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = output_dir / "repository-snapshots.jsonl"
    prior_rows = read_jsonl(snapshot_path) if snapshot_path.exists() else []
    by_case = {row["case_id"]: row for row in prior_rows}
    expected_ids = {assignment["case_id"] for assignment in assignments}
    unknown = sorted(set(by_case) - expected_ids)
    if unknown:
        raise ValueError(f"checkpoint contains unknown cases: {', '.join(unknown)}")

    pending = []
    for assignment in assignments:
        prior = by_case.get(assignment["case_id"])
        if prior is None or any(
            repository.get("status") == "fetch_failed"
            for repository in prior["repositories"]
        ):
            pending.append(assignment)

    if case_batch_size < 1:
        raise ValueError("case_batch_size must be positive")
    for offset in range(0, len(pending), case_batch_size):
        batch = pending[offset:offset + case_batch_size]
        batch_priors = [
            by_case[assignment["case_id"]]
            for assignment in batch
            if assignment["case_id"] in by_case
        ]
        rows = collector(
            catalogs,
            batch,
            workers,
            prior_rows=batch_priors or None,
        )
        for row in rows:
            by_case[row["case_id"]] = row
        ordered = [by_case[item["case_id"]] for item in assignments if item["case_id"] in by_case]
        write_jsonl(snapshot_path, ordered)
        write_json(
            output_dir / "metrics.json",
            metrics_for(ordered, len(assignments), network_used=network_used),
        )

    rows = [by_case[item["case_id"]] for item in assignments]
    metrics = metrics_for(rows, len(assignments), network_used=network_used)
    write_json(output_dir / "metrics.json", metrics)
    write_json(output_dir / "run-manifest.json", {
        "schema_version": "1.0",
        "labels_read": False,
        "network_used": network_used,
        "checkpoint_unit": "case",
        "resolution_rule": "latest default-branch commit at or before observation_cutoff",
    })
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=24)
    parser.add_argument("--case-batch-size", type=int, default=16)
    parser.add_argument("--priority-case-id", action="append", dest="priority_case_ids")
    parser.add_argument("--priority-labels", type=Path)
    parser.add_argument(
        "--mirror-root",
        type=Path,
        help="Resolve cutoffs from complete local Git mirrors instead of the hosting API.",
    )
    args = parser.parse_args()
    catalogs = read_json(args.catalog_dir / "candidate-repositories.json")["catalogs"]
    assignments = read_jsonl(args.catalog_dir / "case-catalog-assignments.jsonl")
    priority = set(args.priority_case_ids or [])
    if args.priority_labels is not None:
        priority.update(row["candidate_id"] for row in read_jsonl(args.priority_labels))
    assignments.sort(key=lambda row: row["case_id"] not in priority)
    collector = collect
    if args.mirror_root is not None:
        resolver = local_git_resolver(args.mirror_root.resolve())

        def collector(catalogs, assignments, workers, prior_rows=None):
            return collect(catalogs, assignments, workers, resolver=resolver, prior_rows=prior_rows)

    metrics = collect_checkpointed(
        catalogs,
        assignments,
        args.output_dir,
        args.workers,
        collector=collector,
        case_batch_size=args.case_batch_size,
        network_used=args.mirror_root is None,
    )
    print(json.dumps(metrics, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if metrics["all_cases_completed"] and metrics["all_resolutions_terminal"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

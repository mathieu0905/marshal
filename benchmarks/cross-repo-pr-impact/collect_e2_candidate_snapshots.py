#!/usr/bin/env python3
"""Resolve E2 candidate catalogs to repository commits at case cutoffs."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
from collections import Counter
from pathlib import Path
from typing import Any, Callable

from collect_repository_snapshots import resolve, rfc3339


ROOT = Path(__file__).resolve().parent


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def catalog_id(reference: str) -> str:
    filename, separator, value = reference.partition("#")
    if filename != "candidate-repositories.json" or not separator or not value:
        raise ValueError(f"invalid E2 catalog reference: {reference}")
    return value


def classify_resolution(result: dict[str, Any]) -> dict[str, Any]:
    """Turn a stable missing-repository response into an auditable terminal state."""

    if result.get("status") != "fetch_failed":
        return result
    error = result.get("error", "")
    if "Not Found (HTTP 404)" in error:
        return {
            "repository": result["repository"],
            "host": result["host"],
            "status": "unavailable_at_collection",
            "reason": "hosting API returned HTTP 404; deletion, transfer, or rename is unresolved",
        }
    if "Git Repository is empty. (HTTP 409)" in error:
        return {
            "repository": result["repository"],
            "host": result["host"],
            "status": "unavailable_at_collection",
            "reason": "hosting API returned HTTP 409 because the repository has no commits",
        }
    if "Repository access blocked (HTTP 403)" in error:
        return {
            "repository": result["repository"],
            "host": result["host"],
            "status": "unavailable_at_collection",
            "reason": "hosting API explicitly reported that repository access is blocked",
        }
    return result


def collect(
    catalogs: dict[str, Any],
    assignments: list[dict[str, Any]],
    workers: int,
    resolver: Callable[[str, str, str], dict[str, Any]] = resolve,
    prior_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    prior_by_case_repository = {
        (row["case_id"], repository["repository"]): repository
        for row in (prior_rows or [])
        for repository in row["repositories"]
        if repository.get("status") != "fetch_failed"
    }
    jobs = []
    for assignment in assignments:
        identifier = catalog_id(assignment["candidate_repository_catalog"])
        catalog = catalogs[identifier]
        host = catalog["repository_host"]
        if host not in {"opendev.org", "github.com"}:
            raise ValueError(f"unsupported catalog host: {host}")
        # collect_repository_snapshots currently selects a host from a legacy
        # project-family name.  "rust" is only a host selector here; it does not
        # change catalog membership or snapshot semantics.
        project = "openstack" if host == "opendev.org" else "rust"
        cutoff = rfc3339(assignment["observation_cutoff"])
        for repository in catalog["repositories"]:
            jobs.append((
                assignment["case_id"],
                project,
                repository,
                cutoff,
                catalog.get("repository_created_at", {}).get(repository),
                catalog.get("known_unavailable_repositories", {}).get(repository),
                assignment.get("candidate_snapshot_overrides", {}).get(repository),
            ))

    def run(
        job: tuple[
            str,
            str,
            str,
            str,
            str | None,
            str | None,
            dict[str, Any] | None,
        ]
    ) -> tuple[str, dict[str, Any]]:
        (
            case_id,
            project,
            repository,
            cutoff,
            created_at,
            unavailable_reason,
            snapshot_override,
        ) = job
        prior = prior_by_case_repository.get((case_id, repository))
        if prior is not None:
            return case_id, prior
        if snapshot_override is not None:
            if snapshot_override.get("repository") != repository:
                raise ValueError(
                    f"snapshot override repository mismatch for {case_id}: {repository}"
                )
            if snapshot_override.get("status") != "available":
                raise ValueError(
                    f"snapshot override for {case_id}/{repository} is not available"
                )
            committed_at = rfc3339(snapshot_override["committed_at"])
            if committed_at > cutoff:
                raise ValueError(
                    f"snapshot override for {case_id}/{repository} is after cutoff"
                )
            return case_id, {
                **snapshot_override,
                "committed_at": committed_at,
            }
        if unavailable_reason is not None:
            return case_id, {
                "repository": repository,
                "host": "github.com",
                "status": "unavailable_at_collection",
                "reason": unavailable_reason,
            }
        if created_at is not None and rfc3339(created_at) > cutoff:
            return case_id, {
                "repository": repository,
                "host": "github.com",
                "status": "not_created_by_cutoff",
                "created_at": rfc3339(created_at),
            }
        return case_id, classify_resolution(resolver(project, repository, cutoff))

    by_case: dict[str, list[dict[str, Any]]] = {
        assignment["case_id"]: [] for assignment in assignments
    }
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        for case_id, result in executor.map(run, jobs):
            by_case[case_id].append(result)
    return [{
        "case_id": assignment["case_id"],
        "observation_cutoff": rfc3339(assignment["observation_cutoff"]),
        "candidate_repository_catalog": assignment["candidate_repository_catalog"],
        "repositories": sorted(
            by_case[assignment["case_id"]], key=lambda row: row["repository"]
        ),
    } for assignment in assignments]


def run(
    catalog_dir: Path,
    output_dir: Path,
    workers: int,
    resume_from: Path | None = None,
) -> dict[str, Any]:
    catalogs = read_json(catalog_dir / "candidate-repositories.json")["catalogs"]
    assignments = read_jsonl(catalog_dir / "case-catalog-assignments.jsonl")
    prior_rows = read_jsonl(resume_from) if resume_from is not None else None
    rows = collect(catalogs, assignments, workers, prior_rows=prior_rows)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_dir / "repository-snapshots.jsonl", rows)
    statuses = Counter(
        repository["status"]
        for row in rows
        for repository in row["repositories"]
    )
    metrics = {
        "schema_version": "1.0",
        "case_count": len(rows),
        "repository_snapshot_count": sum(len(row["repositories"]) for row in rows),
        "status_counts": dict(sorted(statuses.items())),
        "all_resolutions_terminal": not statuses.get("fetch_failed", 0),
        "network_used": True,
    }
    write_json(output_dir / "metrics.json", metrics)
    write_json(output_dir / "run-manifest.json", {
        "schema_version": "1.0",
        "inputs": [
            str(catalog_dir / "candidate-repositories.json"),
            str(catalog_dir / "case-catalog-assignments.jsonl"),
        ],
        "outputs": ["repository-snapshots.jsonl", "metrics.json"],
        "resolution_rule": "latest default-branch commit at or before observation_cutoff",
        "labels_read": False,
        "network_used": True,
        "resume_from": str(resume_from) if resume_from is not None else None,
    })
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument(
        "--resume-from",
        type=Path,
        help="Reuse terminal rows from an earlier repository-snapshots.jsonl and retry only fetch_failed rows.",
    )
    args = parser.parse_args()
    metrics = run(
        args.catalog_dir.resolve(),
        args.output_dir.resolve(),
        args.workers,
        args.resume_from.resolve() if args.resume_from is not None else None,
    )
    print(json.dumps(metrics, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if metrics["all_resolutions_terminal"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Prepare complete local Git mirrors for label-blind candidate-code inference.

The candidate catalogs, rather than any case labels, determine which repositories
are mirrored. Complete mirrors keep historical cutoff commits and their blobs
available after network access is disabled.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import json
import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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


def repository_path(mirror_root: Path, repository: str) -> Path:
    return mirror_root / (repository.replace("/", "__") + ".git")


def is_complete_mirror(path: Path) -> bool:
    if not path.is_dir():
        return False
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--is-bare-repository"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def clone_repository(repository: str, mirror_root: Path) -> dict[str, Any]:
    destination = repository_path(mirror_root, repository)
    if is_complete_mirror(destination):
        return {
            "repository": repository,
            "status": "available",
            "mirror": str(destination.resolve()),
            "network_action": "reused",
        }
    url = f"https://opendev.org/{repository}.git"
    result = None
    for attempt in range(1, 4):
        partial = mirror_root / f".{destination.name}.partial-{uuid.uuid4().hex}"
        result = subprocess.run(
            ["git", "clone", "--mirror", "--quiet", url, str(partial)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode == 0 and is_complete_mirror(partial):
            os.replace(partial, destination)
            return {
                "repository": repository,
                "status": "available",
                "mirror": str(destination.resolve()),
                "network_action": "cloned",
                "attempt_count": attempt,
            }
        if partial.exists():
            shutil.rmtree(partial)
        if attempt < 3:
            time.sleep(attempt)
    assert result is not None
    return {
        "repository": repository,
        "status": "clone_failed",
        "mirror": str(destination.resolve()),
        "network_action": "clone_attempted",
        "attempt_count": 3,
        "error": result.stderr.strip()[-2000:],
    }


def catalog_repositories(catalogs: dict[str, Any]) -> list[str]:
    return sorted({
        repository
        for catalog in catalogs.values()
        for repository in catalog["repositories"]
    })


def collect(
    catalogs: dict[str, Any], mirror_root: Path, output_dir: Path, workers: int
) -> dict[str, Any]:
    mirror_root.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    repositories = catalog_repositories(catalogs)
    rows_by_repository: dict[str, dict[str, Any]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(clone_repository, repository, mirror_root): repository
            for repository in repositories
        }
        for future in concurrent.futures.as_completed(futures):
            row = future.result()
            rows_by_repository[row["repository"]] = row
            write_jsonl(
                output_dir / "candidate-mirrors.jsonl",
                [rows_by_repository[key] for key in sorted(rows_by_repository)],
            )
    rows = [rows_by_repository[repository] for repository in repositories]
    available = sum(row["status"] == "available" for row in rows)
    metrics = {
        "schema_version": "1.0",
        "catalog_repository_count": len(repositories),
        "available_mirror_count": available,
        "clone_failed_count": len(rows) - available,
        "all_mirrors_available": available == len(rows),
        "labels_read": False,
        "network_used": True,
    }
    write_json(output_dir / "metrics.json", metrics)
    write_json(output_dir / "run-manifest.json", {
        "schema_version": "1.0",
        "created_at": dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z"),
        "selection_basis": "union of repositories in label-independent candidate catalogs",
        "mirror_kind": "complete Git mirror",
        "labels_read": False,
        "network_used": True,
    })
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalogs", type=Path, required=True)
    parser.add_argument("--mirror-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    if args.workers < 1:
        raise SystemExit("--workers must be positive")
    catalogs = read_json(args.catalogs)["catalogs"]
    metrics = collect(catalogs, args.mirror_root, args.output_dir, args.workers)
    print(json.dumps(metrics, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if metrics["all_mirrors_available"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

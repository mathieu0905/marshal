#!/usr/bin/env python3
"""Reveal and cache target-change metadata after the blind Marshal run."""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import json
from pathlib import Path
from typing import Any

from collect_opendev import META_FILES, gerrit_json


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def fetch_target(number: int) -> dict[str, Any]:
    detail = gerrit_json(f"/changes/{number}/detail", [("o", "ALL_REVISIONS")])
    revisions = detail.get("revisions", {})
    current = detail.get("current_revision")
    if not current or current not in revisions:
        raise ValueError(f"change {number} has no current revision")
    current_data = revisions[current]
    current_number = current_data["_number"]
    commit = gerrit_json(f"/changes/{number}/revisions/{current_number}/commit")
    files = gerrit_json(f"/changes/{number}/revisions/{current_number}/files/")
    parents = commit.get("parents", [])
    if not parents:
        raise ValueError(f"change {number} has no parent")
    return {
        "number": number,
        "repository": detail["project"],
        "branch": detail["branch"],
        "subject": detail["subject"],
        "status": detail["status"],
        "created_at": detail["created"],
        "submitted_at": detail.get("submitted"),
        "current_revision_number": current_number,
        "base_commit": parents[0]["commit"],
        "head_commit": current,
        "changed_paths": sorted(path for path in files if path not in META_FILES),
        "commit_message": commit.get("message", ""),
        "url": f"https://review.opendev.org/c/{detail['project']}/+/{number}",
    }


def run(
    leads_path: Path,
    source_events_path: Path,
    catalogs_path: Path,
    output_dir: Path,
    workers: int,
) -> dict[str, Any]:
    source_events = {
        row["candidate_id"]: row for row in read_jsonl(source_events_path)
    }
    all_leads = read_jsonl(leads_path)
    leads = [lead for lead in all_leads if lead["candidate_id"] in source_events]
    missing_leads = sorted(set(source_events) - {lead["candidate_id"] for lead in leads})
    if missing_leads:
        raise ValueError(f"selected source has no target lead: {missing_leads[0]}")
    catalogs = read_json(catalogs_path)["catalogs"]
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_path = output_dir / "target-change-cache.jsonl"
    cache = {row["number"]: row for row in read_jsonl(cache_path)}
    target_numbers = sorted({number for lead in leads for number in lead["target_change_leads"]})
    missing = [number for number in target_numbers if number not in cache]
    if missing:
        with cache_path.open("a", encoding="utf-8") as handle:
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {executor.submit(fetch_target, number): number for number in missing}
                for future in concurrent.futures.as_completed(futures):
                    number = futures[future]
                    try:
                        row = future.result()
                    except Exception as exc:
                        row = {"number": number, "fetch_error": str(exc)}
                    cache[number] = row
                    handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
                    handle.flush()

    revealed_at = dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z")
    rows = []
    covered_relations = 0
    for lead in leads:
        catalog_reference = source_events[lead["candidate_id"]]["candidate_repository_catalog"]
        identifier = catalog_reference.split("#", 1)[1]
        members = set(catalogs[identifier]["repositories"])
        targets = []
        for number in lead["target_change_leads"]:
            target = cache[number]
            covered = "fetch_error" not in target and target["repository"] in members
            covered_relations += covered
            targets.append({**target, "catalog_covered": covered})
        rows.append({
            "candidate_id": lead["candidate_id"],
            "source_change": lead["source_change"],
            "candidate_repository_catalog": catalog_reference,
            "revealed_at": revealed_at,
            "targets": targets,
        })
    output = output_dir / "target-metadata.jsonl"
    output.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    metrics = {
        "schema_version": "1.0",
        "candidate_count": len(rows),
        "private_lead_store_count": len(all_leads),
        "target_change_count": len(target_numbers),
        "catalog_covered_relation_count": covered_relations,
        "fetch_error_count": sum("fetch_error" in cache[number] for number in target_numbers),
        "revealed_at": revealed_at,
    }
    (output_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--leads", type=Path, required=True)
    parser.add_argument("--source-events", type=Path, required=True)
    parser.add_argument("--catalogs", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args()
    metrics = run(
        args.leads, args.source_events, args.catalogs, args.output_dir, args.workers
    )
    print(json.dumps(metrics, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if not metrics["fetch_error_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

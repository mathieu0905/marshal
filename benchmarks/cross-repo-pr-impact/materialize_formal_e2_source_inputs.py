#!/usr/bin/env python3
"""Materialize label-blind schema-v1 inputs from formal OpenDev source events."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def materialize(source_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for event in sorted(source_events, key=lambda item: item["candidate_id"]):
        case_id = event["candidate_id"]
        if case_id in seen:
            raise ValueError(f"duplicate candidate_id: {case_id}")
        seen.add(case_id)
        opening = event["opening"]
        if opening["provider"] != "gerrit":
            raise ValueError(f"unsupported opening provider for {case_id}")
        if event.get("label_review_state") != "not_started":
            raise ValueError(f"label review already started for {case_id}")
        rows.append({
            "case_id": case_id,
            "observation_cutoff": opening["created_at"],
            "source": {
                "host": "review.opendev.org",
                "repository": opening["repository"],
                "pull_request_number": opening["number"],
                "source_change_kind": "gerrit_opening_revision",
                "subject": opening["subject"],
                "base_commit": opening["base_commit"],
                "candidate_commit": opening["head_commit"],
                "changed_paths": opening["changed_paths"],
                "patch_url": (
                    f"https://review.opendev.org/changes/{opening['number']}"
                    "/revisions/1/patch"
                ),
            },
            "candidate_repository_catalog": event["candidate_repository_catalog"],
            "candidate_repository_snapshots": f"repository-snapshots.jsonl#{case_id}",
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-events", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--catalogs", type=Path, required=True)
    parser.add_argument("--snapshots", type=Path)
    args = parser.parse_args()

    rows = materialize(read_jsonl(args.source_events))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.output_dir / "inputs.jsonl", rows)
    shutil.copyfile(args.catalogs, args.output_dir / "candidate-repositories.json")
    if args.snapshots is not None:
        shutil.copyfile(
            args.snapshots, args.output_dir / "repository-snapshots.jsonl"
        )
    print(json.dumps({
        "inputs_materialized": len(rows),
        "labels_read": False,
        "opening_revision": 1,
        "source_patch_visibility": "code_diff_only_during_prepare",
        "snapshots_bundled": args.snapshots is not None,
    }, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

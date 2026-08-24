#!/usr/bin/env python3
"""Report every repository in the case's ecosystem catalog."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rows = []
    catalogs = json.loads(
        (ROOT / "candidate-repositories.json").read_text(encoding="utf-8")
    )["catalogs"]
    snapshots = {
        row["case_id"]: row
        for row in (
            json.loads(line)
            for line in (ROOT / "repository-snapshots.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    }
    for line in (ROOT / "inputs.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        project = item["candidate_repository_catalog"].split("#", 1)[1]
        available = {
            row["repository"]
            for row in snapshots[item["case_id"]]["repositories"]
            if row["status"] == "available"
        }
        rows.append({
            "case_id": item["case_id"],
            "targets": [{
                "repository": repository,
                "paths": [],
                "tests": [],
                "commands": [],
                "execution_result": None,
            } for repository in catalogs[project]["repositories"] if repository in available],
        })
    rendered = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
    )
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

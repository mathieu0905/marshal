#!/usr/bin/env python3
"""Rank targets by their dataset frequency for each source repository."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rows = []
    frequencies: dict[str, Counter[str]] = defaultdict(Counter)
    for line in (ROOT / "index.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        frequencies[item["source_repository"]].update(item["target_repositories"])
    for line in (ROOT / "inputs.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        ranked = [
            repository for repository, _ in sorted(
                frequencies[item["source"]["repository"]].items(),
                key=lambda pair: (-pair[1], pair[0]),
            )
        ]
        rows.append({
            "case_id": item["case_id"],
            "targets": [{
                "repository": repository,
                "paths": [],
                "tests": [],
                "commands": [],
                "execution_result": None,
            } for repository in ranked],
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

#!/usr/bin/env python3
"""Derive replay constraints while leaving local source/target projects unpinned."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


NAME = re.compile(r"^([A-Za-z0-9_.-]+)")


def normalize(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def derive(lines: list[str], excluded: set[str]) -> tuple[list[str], list[str]]:
    normalized = {normalize(value) for value in excluded}
    kept = []
    removed = []
    for line in lines:
        match = NAME.match(line.strip())
        if match and normalize(match.group(1)) in normalized:
            removed.append(line)
        else:
            kept.append(line)
    return kept, removed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--exclude", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    lines = args.input.read_text(encoding="utf-8").splitlines(keepends=True)
    kept, removed = derive(lines, set(args.exclude))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(kept), encoding="utf-8")
    print(json.dumps({
        "input_constraint_count": len(lines),
        "output_constraint_count": len(kept),
        "excluded_projects": sorted(args.exclude),
        "removed_lines": [line.strip() for line in removed],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

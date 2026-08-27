#!/usr/bin/env python3
"""Subset repository snapshots to an exact public input case frame."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--snapshots", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    order = [row["case_id"] for row in read_jsonl(args.inputs)]
    snapshots = {row["case_id"]: row for row in read_jsonl(args.snapshots)}
    missing = [case_id for case_id in order if case_id not in snapshots]
    if missing:
        raise SystemExit(f"missing snapshot case: {missing[0]}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(snapshots[case_id], ensure_ascii=False, sort_keys=True) + "\n" for case_id in order),
        encoding="utf-8",
    )
    print(json.dumps({"snapshot_case_count": len(order)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

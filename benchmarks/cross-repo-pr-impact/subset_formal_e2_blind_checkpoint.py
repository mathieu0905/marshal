#!/usr/bin/env python3
"""Seed a smaller label-blind wave from already frozen prediction checkpoints."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--diagnostics", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    selected = [row["case_id"] for row in read_jsonl(args.inputs)]
    predictions = {row["case_id"]: row for row in read_jsonl(args.predictions)}
    diagnostics = {row["case_id"]: row for row in read_jsonl(args.diagnostics)}
    if set(predictions) != set(diagnostics):
        raise SystemExit("source prediction and diagnostic checkpoints disagree")
    reused = [case_id for case_id in selected if case_id in predictions]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.output_dir / "predictions.jsonl", [predictions[case_id] for case_id in reused])
    write_jsonl(args.output_dir / "diagnostics.jsonl", [diagnostics[case_id] for case_id in reused])
    metrics = {
        "schema_version": "1.0",
        "selected_case_count": len(selected),
        "reused_frozen_case_count": len(reused),
        "labels_read": False,
    }
    (args.output_dir / "checkpoint-subset-metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(metrics, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

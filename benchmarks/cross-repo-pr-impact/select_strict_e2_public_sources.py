#!/usr/bin/env python3
"""Select a label-blind source wave using only public break-likelihood signals."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path
from typing import Any


STRONG = re.compile(
    r"\b(remove|removed|removal|drop|dropped|rename|renamed|deprecat|incompat|breaking|"
    r"disallow|disable|reject|require|retire|delete)\w*\b",
    re.IGNORECASE,
)
MEDIUM = re.compile(
    r"\b(upgrade|upversion|bump|migrat|switch|replace|refactor|rework|split|move|"
    r"change|api|version|schema|protocol)\w*\b",
    re.IGNORECASE,
)
DIAGNOSTIC_PARTS = ("test", "doc/", ".zuul", "releasenote", "api-ref")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def break_score(row: dict[str, Any]) -> tuple[int, int, int]:
    opening = row["opening"]
    subject = opening["subject"]
    paths = opening["changed_paths"]
    production = [
        path for path in paths
        if not any(part in path.lower() for part in DIAGNOSTIC_PARTS)
    ]
    score = 8 * len(STRONG.findall(subject)) + 3 * len(MEDIUM.findall(subject))
    score += min(len(production), 5)
    if not production:
        score -= 8
    if all(path.lower().endswith((".rst", ".md", ".txt")) for path in paths):
        score -= 5
    return score, len(production), -len(paths)


def select(rows: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    ranked = sorted(
        rows,
        key=lambda row: (
            *(-value for value in break_score(row)),
            row["opening"]["created_at"],
            row["candidate_id"],
        ),
    )
    return sorted(ranked[:count], key=lambda row: (row["opening"]["created_at"], row["candidate_id"]))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--count", type=int, default=400)
    parser.add_argument(
        "--exclude-source-events",
        type=Path,
        action="append",
        default=[],
        help="Previously selected public source events to exclude without reading labels.",
    )
    args = parser.parse_args()
    rows = read_jsonl(args.source_dir / "source-events.jsonl")
    excluded_ids = {
        row["candidate_id"]
        for path in args.exclude_source_events
        for row in read_jsonl(path)
    }
    eligible = [row for row in rows if row["candidate_id"] not in excluded_ids]
    selected = select(eligible, args.count)
    selected_ids = {row["candidate_id"] for row in selected}
    assignments = [
        row for row in read_jsonl(args.source_dir / "case-catalog-assignments.jsonl")
        if row["case_id"] in selected_ids
    ]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "source-events.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in selected),
        encoding="utf-8",
    )
    (args.output_dir / "case-catalog-assignments.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in assignments),
        encoding="utf-8",
    )
    shutil.copyfile(
        args.source_dir / "candidate-repositories.json",
        args.output_dir / "candidate-repositories.json",
    )
    metrics = {
        "schema_version": "1.0",
        "input_source_count": len(rows),
        "excluded_source_count": len(rows) - len(eligible),
        "selected_source_count": len(selected),
        "selection_reads_labels": False,
        "selection_fields": ["opening.subject", "opening.changed_paths", "opening.created_at"],
        "minimum_selected_break_score": min(break_score(row)[0] for row in selected),
    }
    (args.output_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(metrics, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

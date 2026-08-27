#!/usr/bin/env python3
"""Select a deterministic, label-blind development slice by project and time."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent


def read_inputs(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def project_name(item: dict[str, Any]) -> str:
    return item["candidate_repository_catalog"].split("#", 1)[1]


def evenly_spaced(items: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    if count < 1:
        raise ValueError("project counts must be positive")
    if count > len(items):
        raise ValueError(f"requested {count} cases from a project with {len(items)} cases")
    if count == 1:
        indices = [0]
    else:
        indices = [round(index * (len(items) - 1) / (count - 1)) for index in range(count)]
    if len(set(indices)) != count:
        raise ValueError("even-spacing rule produced duplicate indices")
    return [items[index] for index in indices]


def select_slice(
    inputs: list[dict[str, Any]], project_counts: dict[str, int]
) -> list[dict[str, Any]]:
    selected = []
    for project, count in project_counts.items():
        candidates = sorted(
            (item for item in inputs if project_name(item) == project),
            key=lambda item: (item["observation_cutoff"], item["case_id"]),
        )
        if not candidates:
            raise ValueError(f"unknown or empty project: {project}")
        selected.extend(evenly_spaced(candidates, count))
    return selected


def parse_project_count(value: str) -> tuple[str, int]:
    try:
        project, raw_count = value.rsplit("=", 1)
        count = int(raw_count)
    except (ValueError, TypeError) as error:
        raise argparse.ArgumentTypeError("expected PROJECT=COUNT") from error
    if not project or count < 1:
        raise argparse.ArgumentTypeError("expected PROJECT=COUNT with a positive count")
    return project, count


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-count", action="append", type=parse_project_count, required=True
    )
    parser.add_argument("--inputs", type=Path, default=ROOT / "inputs.jsonl")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    project_counts = dict(args.project_count)
    if len(project_counts) != len(args.project_count):
        raise SystemExit("duplicate --project-count project")
    try:
        selected = select_slice(read_inputs(args.inputs), project_counts)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    payload = {
        "schema_version": "1.0",
        "selection_rule": (
            "Within each requested candidate catalog, sort by observation_cutoff then "
            "case_id and select round(i * (n - 1) / (k - 1)) for i=0..k-1."
        ),
        "label_fields_read": False,
        "inputs_read": [
            "candidate_repository_catalog", "observation_cutoff", "case_id"
        ],
        "project_counts": project_counts,
        "cases": [
            {
                "case_id": item["case_id"],
                "project": project_name(item),
                "observation_cutoff": item["observation_cutoff"],
            }
            for item in selected
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "selected_cases": len(selected),
        "project_counts": project_counts,
        "output": str(args.output.resolve()),
    }, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

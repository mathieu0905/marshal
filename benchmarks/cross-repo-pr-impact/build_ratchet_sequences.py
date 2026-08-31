#!/usr/bin/env python3
"""Materialize ordered escape-to-permanent-check benchmark sequences."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build(release_dir: Path, output_dir: Path) -> dict[str, Any]:
    selected = [
        "formal-opendev-wandertracks-symbol-spacing--target-wandertracks-android",
        "formal-opendev-irc-meetings-matrix-location--target-yaml2ical",
        "formal-opendev-1001023--target-1000516",
    ]
    inputs = {row["case_id"]: row for row in read_jsonl(release_dir / "inputs.jsonl")}
    cases = {row["case_id"]: row for row in read_jsonl(release_dir / "final-index.jsonl")}
    rows = []
    for index, case_id in enumerate(selected, start=1):
        case_dir = release_dir / "cases" / case_id
        label = read_json(case_dir / "private" / "label.json")
        contract = read_json(case_dir / "evidence" / case_id / "contract.json")
        input_row = inputs[case_id]
        source = input_row["source"]
        check_id = f"ratchet.xrepo.{index:03d}"
        rows.append({
            "schema_version": "1.0",
            "sequence_id": f"ratchet-sequence-{index:03d}",
            "seed_e2_case_id": case_id,
            "source_change_family": cases[case_id]["source_change_family"],
            "escape_observation": {
                "source_repository": source["repository"],
                "change_ref": source.get("revision", case_id),
                "changed_paths": source["changed_paths"],
                "missed_target_repository": label["target_repository"],
                "observed_arms": {"A0": 0, "A1": 1, "A2": 0},
            },
            "registration": {
                "escape_id": f"escape.xrepo.{index:03d}",
                "check_id": check_id,
                "domain_pack": f"benchmark-{index:03d}",
                "invariant": {
                    "id": check_id,
                    "domain": "cross-repo",
                    "spec_ref": f"dataset:{case_id}",
                    "executor_kind": "command",
                    "location_repo": label["target_repository"],
                    "location_path": contract["target_test_path"],
                    "location_test": contract.get("test_selector", contract["target_test_path"]),
                    "severity": "mid",
                    "run_command": contract["test_command"],
                    "trigger_repo": source["repository"],
                    "trigger_paths": source["changed_paths"],
                },
                "dataset_fixed_command": contract["test_command"],
            },
            "recurrence": {
                "source_repository": source["repository"],
                "change_ref": f"{case_id}:recurrence",
                "changed_paths": source["changed_paths"],
                "expected_check_id": check_id,
                "expected_target_repository": label["target_repository"],
                "expected_outcome": "block_after_check_failure",
            },
            "unrelated_control": {
                "source_repository": source["repository"],
                "change_ref": f"{case_id}:unrelated-control",
                "changed_paths": ["README.ratchet-control.md"],
                "expected_check_ids": [],
                "synthetic_control": True,
            },
        })
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "sequences.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    report = {
        "schema_version": "1.0",
        "sequence_count": len(rows),
        "seed_strict_e2_count": len(rows),
        "recurrence_count": len(rows),
        "unrelated_control_count": len(rows),
        "task": "observe escape, register permanent check, schedule it on recurrence, and abstain on an unrelated change",
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report = build(args.release_dir, args.output_dir)
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

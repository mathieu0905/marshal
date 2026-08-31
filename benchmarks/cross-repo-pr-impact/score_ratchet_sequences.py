#!/usr/bin/env python3
"""Score the temporal behavior of escape-ratchet benchmark sequences."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def score(sequences: list[dict[str, Any]], outputs: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {row["sequence_id"]: row for row in outputs}
    if len(by_id) != len(outputs):
        raise ValueError("duplicate ratchet output sequence_id")
    records = []
    for sequence in sequences:
        sequence_id = sequence["sequence_id"]
        output = by_id.get(sequence_id, {})
        check_id = sequence["registration"]["check_id"]
        registered = output.get("registered_check_id") == check_id
        recurrence_checks = output.get("recurrence_scheduled_check_ids", [])
        unrelated_checks = output.get("unrelated_scheduled_check_ids", [])
        recurrence_scheduled = isinstance(recurrence_checks, list) and check_id in recurrence_checks
        unrelated_abstained = unrelated_checks == []
        recurrence_execution = output.get("recurrence_execution", {})
        failure_observed = (
            recurrence_execution.get("status") == "assessed"
            and recurrence_execution.get("exit_code") not in (None, 0)
            and isinstance(recurrence_execution.get("evidence_log"), str)
            and bool(recurrence_execution["evidence_log"])
        )
        blocked = output.get("recurrence_decision") == "block"
        end_to_end = registered and recurrence_scheduled and failure_observed and blocked and unrelated_abstained
        records.append({
            "sequence_id": sequence_id,
            "registration_accepted": registered,
            "recurrence_scheduled": recurrence_scheduled,
            "recurrence_failure_evidenced": failure_observed,
            "recurrence_blocked": blocked,
            "unrelated_change_abstained": unrelated_abstained,
            "end_to_end_pass": end_to_end,
        })
    denominator = len(records)
    rate = lambda key: sum(row[key] for row in records) / denominator if denominator else None
    return {
        "schema_version": "1.0",
        "sequence_count": denominator,
        "registration_rate": rate("registration_accepted"),
        "recurrence_schedule_rate": rate("recurrence_scheduled"),
        "recurrence_failure_evidence_rate": rate("recurrence_failure_evidenced"),
        "recurrence_block_rate": rate("recurrence_blocked"),
        "unrelated_abstention_rate": rate("unrelated_change_abstained"),
        "end_to_end_ratchet_rate": rate("end_to_end_pass"),
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sequences", type=Path, required=True)
    parser.add_argument("--outputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = score(read_jsonl(args.sequences), read_jsonl(args.outputs))
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key.endswith("_rate")}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

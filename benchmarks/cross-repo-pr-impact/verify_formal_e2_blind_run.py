#!/usr/bin/env python3
"""Verify chronology-sensitive, label-blind candidate-code prediction artifacts."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any


NETWORK_CALL = re.compile(
    r"\b(?:socket|socketpair|connect|bind|listen|accept|accept4|sendto|recvfrom|"
    r"sendmsg|recvmsg|shutdown|getsockname|getpeername|setsockopt|getsockopt)\("
)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def unique_by_case(rows: list[dict[str, Any]], name: str) -> dict[str, dict[str, Any]]:
    result = {}
    for row in rows:
        case_id = row["case_id"]
        if case_id in result:
            raise ValueError(f"duplicate {name} case: {case_id}")
        result[case_id] = row
    return result


def verify(
    inputs: list[dict[str, Any]],
    snapshots: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    diagnostics: list[dict[str, Any]],
    manifest: dict[str, Any],
    network_trace: str | None = None,
    network_enforcement: dict[str, Any] | None = None,
) -> dict[str, Any]:
    input_by_case = unique_by_case(inputs, "input")
    snapshot_by_case = unique_by_case(snapshots, "snapshot")
    prediction_by_case = unique_by_case(predictions, "prediction")
    diagnostic_by_case = unique_by_case(diagnostics, "diagnostic")
    expected = set(input_by_case)
    if set(snapshot_by_case) != expected:
        raise ValueError("snapshot cases do not exactly match inputs")
    if set(prediction_by_case) != expected or set(diagnostic_by_case) != expected:
        raise ValueError("prediction or diagnostic cases do not exactly match inputs")
    if manifest.get("labels_read") is not False or manifest.get("network_used") is not False:
        raise ValueError("blind-run manifest does not declare label/network isolation")
    if manifest.get("candidate_code_read") is not True:
        raise ValueError("blind-run manifest does not declare candidate-code reads")
    started_at = manifest.get("started_at", manifest.get("created_at"))
    completed_at = manifest.get("completed_at")
    if completed_at is not None:
        if not started_at or dt.datetime.fromisoformat(completed_at.replace("Z", "+00:00")) < dt.datetime.fromisoformat(started_at.replace("Z", "+00:00")):
            raise ValueError("blind-run completion precedes its start")
    isolation = "strace_observation"
    if network_trace is not None:
        network_calls = [line for line in network_trace.splitlines() if NETWORK_CALL.search(line)]
        if network_calls:
            raise ValueError(f"network syscall observed: {network_calls[0]}")
    elif network_enforcement is not None:
        if (
            network_enforcement.get("mechanism") != "libseccomp_inherited_syscall_filter"
            or network_enforcement.get("socket_probe_blocked") is not True
            or network_enforcement.get("socket_probe_errno") != 1
        ):
            raise ValueError("network enforcement probe did not prove syscall blocking")
        if manifest.get("network_enforcement") != network_enforcement["mechanism"]:
            raise ValueError("blind-run manifest and network enforcement disagree")
        isolation = network_enforcement["mechanism"]
    else:
        raise ValueError("no network isolation evidence supplied")

    repositories_read = 0
    text_files_read = 0
    for case_id in sorted(expected):
        item = input_by_case[case_id]
        prediction = prediction_by_case[case_id]
        diagnostic = diagnostic_by_case[case_id]
        available = {
            row["repository"]
            for row in snapshot_by_case[case_id]["repositories"]
            if row["status"] == "available"
            and row["repository"] != item["source"]["repository"]
        }
        predicted = [target["repository"] for target in prediction["targets"]]
        if len(predicted) > 5 or len(predicted) != len(set(predicted)):
            raise ValueError(f"invalid bounded prediction list for {case_id}")
        if not set(predicted) <= available:
            raise ValueError(f"prediction outside cutoff candidates for {case_id}")
        if diagnostic.get("label_inputs_read") is not False:
            raise ValueError(f"diagnostic label isolation failed for {case_id}")
        if diagnostic.get("candidate_code_read") is not True:
            raise ValueError(f"candidate code not read for {case_id}")
        ranking = diagnostic["ranking"]
        if {row["repository"] for row in ranking} != available:
            raise ValueError(f"candidate coverage mismatch for {case_id}")
        if any(row.get("files_read", 0) <= 0 or row.get("text_files_read", 0) <= 0 for row in ranking):
            raise ValueError(f"zero candidate text-code reads for {case_id}")
        repositories_read += len(ranking)
        text_files_read += sum(row["text_files_read"] for row in ranking)
    return {
        "schema_version": "1.0",
        "blind_run_valid": True,
        "case_count": len(expected),
        "candidate_repository_reads": repositories_read,
        "candidate_text_file_reads": text_files_read,
        "network_syscall_count": 0,
        "network_isolation": isolation,
        "labels_read": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--snapshots", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--diagnostics", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    network = parser.add_mutually_exclusive_group(required=True)
    network.add_argument("--network-trace", type=Path)
    network.add_argument("--network-enforcement", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    metrics = verify(
        read_jsonl(args.inputs), read_jsonl(args.snapshots),
        read_jsonl(args.predictions), read_jsonl(args.diagnostics),
        read_json(args.manifest),
        args.network_trace.read_text(encoding="utf-8") if args.network_trace else None,
        read_json(args.network_enforcement) if args.network_enforcement else None,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(metrics, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

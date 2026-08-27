#!/usr/bin/env python3
"""Merge independently network-isolated label-blind prediction shards."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--shard-dir", type=Path, action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    order = [row["case_id"] for row in read_jsonl(args.inputs)]
    predictions: dict[str, dict[str, Any]] = {}
    diagnostics: dict[str, dict[str, Any]] = {}
    manifests = []
    probes = []
    for directory in args.shard_dir:
        manifest = read_json(directory / "run-manifest.json")
        probe = read_json(directory / "network-enforcement.json")
        if manifest.get("labels_read") is not False or manifest.get("network_used") is not False:
            raise SystemExit(f"invalid blind shard manifest: {directory}")
        if probe.get("socket_probe_blocked") is not True:
            raise SystemExit(f"invalid network probe: {directory}")
        manifests.append(manifest)
        probes.append(probe)
        for row in read_jsonl(directory / "predictions.jsonl"):
            if row["case_id"] in predictions:
                raise SystemExit(f"duplicate prediction case: {row['case_id']}")
            predictions[row["case_id"]] = row
        for row in read_jsonl(directory / "diagnostics.jsonl"):
            if row["case_id"] in diagnostics:
                raise SystemExit(f"duplicate diagnostic case: {row['case_id']}")
            diagnostics[row["case_id"]] = row
    if set(predictions) != set(order) or set(diagnostics) != set(order):
        raise SystemExit("merged shards do not exactly cover input cases")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.output_dir / "predictions.jsonl", [predictions[key] for key in order])
    write_jsonl(args.output_dir / "diagnostics.jsonl", [diagnostics[key] for key in order])
    started = min(manifest.get("started_at", manifest["created_at"]) for manifest in manifests)
    completed = max(manifest["completed_at"] for manifest in manifests)
    mechanism = "libseccomp_inherited_syscall_filter"
    write_json(args.output_dir / "run-manifest.json", {
        "schema_version": "1.0",
        "system": manifests[0]["system"],
        "created_at": started,
        "started_at": started,
        "completed_at": completed,
        "case_count": len(order),
        "labels_read": False,
        "network_used": False,
        "candidate_code_read": True,
        "candidate_code_source": manifests[0]["candidate_code_source"],
        "network_enforcement": mechanism,
        "parallel_shard_count": len(manifests),
    })
    write_json(args.output_dir / "network-enforcement.json", {
        "schema_version": "1.0",
        "mechanism": mechanism,
        "socket_probe_blocked": True,
        "socket_probe_errno": 1,
        "shard_probe_count": len(probes),
    })
    print(json.dumps({"case_count": len(order), "shard_count": len(manifests)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

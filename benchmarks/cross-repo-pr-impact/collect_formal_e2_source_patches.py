#!/usr/bin/env python3
"""Download code-only opening diffs for the label-blind formal source frame."""

from __future__ import annotations

import argparse
import base64
import concurrent.futures
import json
import tempfile
from pathlib import Path
from typing import Any

from prepare_case_inputs import code_only_diff, download


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def collect_patch(event: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    case_id = event["candidate_id"]
    destination = output_dir / f"{case_id}.patch"
    if destination.exists() and destination.stat().st_size:
        return {"case_id": case_id, "status": "available", "bytes": destination.stat().st_size}
    number = event["opening"]["number"]
    url = f"https://review.opendev.org/changes/{number}/revisions/1/patch"
    try:
        with tempfile.TemporaryDirectory(prefix="formal-e2-patch-") as temporary:
            response = Path(temporary) / "response"
            download(url, response)
            patch = code_only_diff(base64.b64decode(response.read_bytes()))
        partial = destination.with_suffix(".patch.part")
        partial.write_bytes(patch)
        partial.replace(destination)
        return {"case_id": case_id, "status": "available", "bytes": len(patch)}
    except Exception as exc:
        return {"case_id": case_id, "status": "fetch_failed", "error": str(exc)}


def run(source_events: Path, output_dir: Path, workers: int) -> dict[str, Any]:
    events = read_jsonl(source_events)
    output_dir.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        rows = list(executor.map(lambda event: collect_patch(event, output_dir), events))
    manifest = output_dir / "patches.jsonl"
    manifest.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    metrics = {
        "schema_version": "1.0",
        "source_event_count": len(events),
        "available_patch_count": sum(row["status"] == "available" for row in rows),
        "fetch_failed_count": sum(row["status"] == "fetch_failed" for row in rows),
        "code_diff_only": True,
        "labels_read": False,
        "network_used": True,
    }
    (output_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-events", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args()
    metrics = run(args.source_events, args.output_dir, args.workers)
    print(json.dumps(metrics, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if not metrics["fetch_failed_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

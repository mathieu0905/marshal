#!/usr/bin/env python3
"""Audit prepared-visible E2 source patches for answer leakage."""

from __future__ import annotations

import argparse
import base64
import json
import tempfile
from pathlib import Path
from typing import Any

from prepare_case_inputs import code_only_diff, download


ROOT = Path(__file__).resolve().parent
E2_INDEX = ROOT / "results" / "final-e2-dataset-50-2026-08-25" / "final-index.jsonl"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def download_patch(item: dict[str, Any]) -> bytes:
    with tempfile.TemporaryDirectory(prefix="marshal-visibility-patch-") as directory:
        path = Path(directory) / "source.patch"
        download(item["source"]["patch_url"], path)
        payload = path.read_bytes()
    if item["source"]["host"] == "review.opendev.org":
        payload = code_only_diff(base64.b64decode(payload))
    return payload


def audit_patch(
    item: dict[str, Any], patch: bytes, targets: list[str]
) -> dict[str, Any]:
    text = patch.decode("utf-8", errors="replace")
    target_tokens = sorted({
        repository.lower()
        for repository in targets
    })
    forbidden_hits = []
    lower = text.lower()
    for marker in ("depends-on:", "depends-on ", "review.opendev.org/"):
        if marker in lower:
            forbidden_hits.append(marker)
    target_hits = [token for token in target_tokens if token in lower]
    missing_paths = [
        path
        for path in item["source"]["changed_paths"]
        if f"a/{path}" not in text and f"b/{path}" not in text
    ]
    code_diff_only = text.startswith(("diff --git ", "diff -urN "))
    passed = not forbidden_hits and not target_hits and not missing_paths and code_diff_only
    return {
        "case_id": item["case_id"],
        "status": "pass" if passed else "fail",
        "code_diff_only": code_diff_only,
        "forbidden_metadata_hits": forbidden_hits,
        "target_name_hits": target_hits,
        "changed_paths_missing_from_patch": missing_paths,
        "patch_bytes": len(patch),
        "labels_read_only_by_visibility_audit": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--e2-index", type=Path, default=E2_INDEX)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    inputs = read_jsonl(args.inputs)
    labels = {row["case_id"]: row["target_repositories"] for row in read_jsonl(args.e2_index)}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "patches").mkdir(exist_ok=True)
    rows = []
    for item in inputs:
        patch = download_patch(item)
        (args.output_dir / "patches" / f"{item['case_id']}.patch").write_bytes(patch)
        rows.append(audit_patch(item, patch, labels[item["case_id"]]))
    (args.output_dir / "input-visibility-audit.jsonl").write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )
    summary = {
        "case_count": len(rows),
        "passed": sum(row["status"] == "pass" for row in rows),
        "failed": sum(row["status"] == "fail" for row in rows),
        "network_used_during_preparation_audit": True,
        "inference_network_policy": "disabled",
    }
    (args.output_dir / "metrics.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if not summary["failed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

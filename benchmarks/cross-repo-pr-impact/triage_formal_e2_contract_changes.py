#!/usr/bin/env python3
"""Rank revealed OpenDev relations by source-removal/target-repair overlap."""

from __future__ import annotations

import argparse
import base64
import concurrent.futures
import json
import re
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from prepare_case_inputs import code_only_diff, download


TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")
IGNORED = {
    "and", "class", "def", "false", "from", "import", "none", "null",
    "return", "self", "test", "true", "with",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def diff_lines(payload: str, prefix: str) -> list[str]:
    return [
        line[1:]
        for line in payload.splitlines()
        if line.startswith(prefix) and not line.startswith(prefix * 3)
    ]


def token_counts(lines: list[str]) -> Counter[str]:
    return Counter(
        token
        for line in lines
        for token in TOKEN.findall(line)
        if token.lower() not in IGNORED
    )


def relation_score(source_patch: str, target_patch: str) -> dict[str, Any]:
    source_removed = token_counts(diff_lines(source_patch, "-"))
    source_added = token_counts(diff_lines(source_patch, "+"))
    target_removed = token_counts(diff_lines(target_patch, "-"))
    target_added = token_counts(diff_lines(target_patch, "+"))
    removed_overlap = sorted(
        set(source_removed) & set(target_removed),
        key=lambda token: (-(source_removed[token] + target_removed[token]), token),
    )
    replacement_overlap = sorted(
        set(source_added) & set(target_added),
        key=lambda token: (-(source_added[token] + target_added[token]), token),
    )
    strong_removed = [token for token in removed_overlap if len(token) >= 5]
    return {
        "removed_identifier_overlap": removed_overlap[:30],
        "replacement_identifier_overlap": replacement_overlap[:30],
        "strong_removed_identifier_count": len(strong_removed),
        "triage_score": sum(
            2 if token not in source_added and token not in target_added else 1
            for token in strong_removed
        ),
    }


def fetch_patch(number: int, revision: int, destination: Path) -> None:
    if destination.exists() and destination.stat().st_size:
        return
    url = f"https://review.opendev.org/changes/{number}/revisions/{revision}/patch"
    with tempfile.TemporaryDirectory(prefix="formal-e2-target-patch-") as temporary:
        response = Path(temporary) / "response"
        download(url, response)
        patch = code_only_diff(base64.b64decode(response.read_bytes()))
    partial = destination.with_suffix(".patch.part")
    partial.write_bytes(patch)
    partial.replace(destination)


def run(
    source_patch_dir: Path,
    target_metadata: Path,
    output_dir: Path,
    workers: int,
) -> dict[str, Any]:
    rows = read_jsonl(target_metadata)
    output_dir.mkdir(parents=True, exist_ok=True)
    patches = output_dir / "target-patches"
    patches.mkdir(exist_ok=True)
    jobs = {
        (target["number"], target["current_revision_number"])
        for row in rows for target in row["targets"]
        if target.get("catalog_covered") and "fetch_error" not in target
    }
    failures: list[dict[str, Any]] = []

    def fetch(job: tuple[int, int]) -> None:
        number, revision = job
        try:
            fetch_patch(number, revision, patches / f"{number}.patch")
        except Exception as exc:
            failures.append({"number": number, "error": str(exc)})

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        list(executor.map(fetch, sorted(jobs)))

    triage = []
    for row in rows:
        source_path = source_patch_dir / f"{row['candidate_id']}.patch"
        if not source_path.exists():
            continue
        source_patch = source_path.read_text(encoding="utf-8", errors="ignore")
        for target in row["targets"]:
            target_path = patches / f"{target['number']}.patch"
            if not target.get("catalog_covered") or not target_path.exists():
                continue
            scores = relation_score(
                source_patch,
                target_path.read_text(encoding="utf-8", errors="ignore"),
            )
            triage.append({
                "candidate_id": row["candidate_id"],
                "source_change": row["source_change"],
                "target_change": target["number"],
                "target_repository": target["repository"],
                "target_subject": target["subject"],
                **scores,
            })
    triage.sort(key=lambda item: (-item["triage_score"], item["candidate_id"], item["target_change"]))
    (output_dir / "contract-triage.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in triage),
        encoding="utf-8",
    )
    metrics = {
        "schema_version": "1.0",
        "covered_relation_count": len(triage),
        "target_patch_fetch_failure_count": len(failures),
        "positive_triage_score_count": sum(row["triage_score"] > 0 for row in triage),
        "score_at_least_two_count": sum(row["triage_score"] >= 2 for row in triage),
        "labels_assigned": False,
    }
    (output_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-patch-dir", type=Path, required=True)
    parser.add_argument("--target-metadata", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args()
    metrics = run(args.source_patch_dir, args.target_metadata, args.output_dir, args.workers)
    print(json.dumps(metrics, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if not metrics["target_patch_fetch_failure_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

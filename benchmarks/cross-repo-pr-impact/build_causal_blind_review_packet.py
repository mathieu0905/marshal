#!/usr/bin/env python3
"""Build a deduplicated causal review packet without prior semantic decisions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from collect_opendev import GERRIT, ROOT


BATCHES = [
    (
        ROOT / "candidates" / "ci-contrast-semantic-review.jsonl",
        ROOT / "candidates" / "ci-contrast-composition-verified.jsonl",
    ),
    (
        ROOT / "results" / "opendev-rolling-2026-08-23" / "semantic-review.jsonl",
        ROOT / "results" / "opendev-rolling-2026-08-23" / "composition-verified.jsonl",
    ),
    (
        ROOT
        / "results"
        / "opendev-rolling-2026-08-01-to-2026-08-23"
        / "semantic-review.jsonl",
        ROOT
        / "results"
        / "opendev-rolling-2026-08-01-to-2026-08-23"
        / "composition-verified.jsonl",
    ),
    (
        ROOT
        / "results"
        / "opendev-rolling-2026-08-24-to-2026-08-25-noon"
        / "semantic-review.jsonl",
        ROOT
        / "results"
        / "opendev-rolling-2026-08-24-to-2026-08-25-noon"
        / "composition-verified.jsonl",
    ),
]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def job_records(record: dict[str, Any]) -> list[dict[str, Any]]:
    jobs = record.get("composition_verified_jobs") or [record]
    fields = [
        "job",
        "tenant",
        "failure_build_uuid",
        "failure_log_url",
        "success_build_uuid",
        "success_log_url",
        "target_commit",
        "target_revision_created",
        "times",
        "time_checks",
        "inventory_checks",
        "buildset_ref_patchsets",
    ]
    return [{key: job[key] for key in fields if key in job} for job in jobs]


def packet_record(
    record: dict[str, Any], composition_path: Path
) -> dict[str, Any]:
    source_pr = record["source_pr"]
    before = record["source_before_revision"]
    after = record["source_after_revision"]
    target_pr = record["target_pr"]
    target_commit = record["target_commit"]
    return {
        "review_id": f"blind-opendev-{source_pr}",
        "source": {
            "repository": record["source_repository"],
            "change": source_pr,
            "subject": record["source_subject"],
            "before_revision": before,
            "after_revision": after,
            "code_diff_identical": record["source_code_diff_identical"],
            "before_patch_url": (
                f"{GERRIT}/changes/{source_pr}/revisions/{before['sha']}/patch?download"
            ),
            "after_patch_url": (
                f"{GERRIT}/changes/{source_pr}/revisions/{after['sha']}/patch?download"
            ),
            "change_url": f"{GERRIT}/c/{record['source_repository']}/+/{source_pr}",
        },
        "proposed_target": {
            "repository": record["target_repository"],
            "change": target_pr,
            "subject": record["target_subject"],
            "commit": target_commit,
            "patch_url": (
                f"{GERRIT}/changes/{target_pr}/revisions/{target_commit}/patch?download"
            ),
            "change_url": f"{GERRIT}/c/{record['target_repository']}/+/{target_pr}",
        },
        "composition_verified_jobs": job_records(record),
        "composition_record": str(composition_path.relative_to(ROOT)),
    }


def collect() -> list[dict[str, Any]]:
    packet: dict[int, dict[str, Any]] = {}
    for review_path, composition_path in BATCHES:
        reviews = read_jsonl(review_path)
        records = {
            item["source_pr"]: item for item in read_jsonl(composition_path)
        }
        for review in reviews:
            if review["decision"] == "duplicate_prior_review":
                continue
            source_pr = review["source_pr"]
            if source_pr in packet:
                raise ValueError(f"source {source_pr} appears in more than one review batch")
            if source_pr not in records:
                raise ValueError(f"source {source_pr} lacks composition evidence")
            packet[source_pr] = packet_record(records[source_pr], composition_path)
    return [packet[source_pr] for source_pr in sorted(packet)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "causal-pilot" / "blind-review-packet.jsonl",
    )
    args = parser.parse_args()
    packet = collect()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n"
            for item in packet
        ),
        encoding="utf-8",
    )
    print(json.dumps({
        "review_units": len(packet),
        "jobs": sum(len(item["composition_verified_jobs"]) for item in packet),
        "output": str(args.output),
        "semantic_decisions_exposed": False,
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

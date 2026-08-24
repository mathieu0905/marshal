#!/usr/bin/env python3
"""Select the reviewed GitHub cases used by the cross-repository track."""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path
from typing import Any

from collect_opendev import ROOT


DEFAULT_REVIEWS = ROOT / "candidates" / "github-multi-target-manual-review.jsonl"
DEFAULT_SNAPSHOTS = ROOT / "candidates" / "github-multi-target-opening-snapshots.jsonl"
DEFAULT_OUTPUT = ROOT / "candidates" / "github-multi-target-selected.jsonl"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def accepted_targets(review: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in review["target_decisions"] if item["decision"] == "accept"]


def select(reviews: list[dict[str, Any]], snapshots: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    recovered = {
        (item["source_repository"], item["source_pull_request"])
        for item in snapshots
        if item["status"] == "recovered"
    }
    eligible = [
        review for review in reviews
        if review["decision"] == "accept_for_target_audit"
        and (review["source_repository"], review["source_pull_request"]) in recovered
    ]
    for review in eligible:
        targets = accepted_targets(review)
        review["accepted_target_repositories"] = sorted({item["repository"] for item in targets})
        review["accepted_target_repository_count"] = len(review["accepted_target_repositories"])

    selected = sorted(
        (item for item in eligible if item["accepted_target_repository_count"] > 1),
        key=lambda item: (
            -item["accepted_target_repository_count"],
            item["source_repository"],
            item["source_pull_request"],
        ),
    )
    selected_keys = {(item["source_repository"], item["source_pull_request"]) for item in selected}

    by_relation: dict[tuple[str, str], list[dict[str, Any]]] = collections.defaultdict(list)
    for item in eligible:
        key = (item["source_repository"], item["source_pull_request"])
        if key in selected_keys:
            continue
        relation = (item["source_repository"], item["accepted_target_repositories"][0])
        by_relation[relation].append(item)
    for rows in by_relation.values():
        rows.sort(key=lambda item: item["source_pull_request"])

    relations = sorted(by_relation, key=lambda relation: (len(by_relation[relation]), relation))
    offsets: collections.Counter[tuple[str, str]] = collections.Counter()
    while len(selected) < count:
        added = False
        for relation in relations:
            rows = by_relation[relation]
            if offsets[relation] >= len(rows):
                continue
            item = rows[offsets[relation]]
            offsets[relation] += 1
            selected.append(item)
            selected_keys.add((item["source_repository"], item["source_pull_request"]))
            added = True
            if len(selected) == count:
                break
        if not added:
            break

    if len(selected) != count:
        raise RuntimeError(f"requested {count} cases but only selected {len(selected)}")
    rows = []
    for rank, item in enumerate(selected, 1):
        rows.append({
            "selection_rank": rank,
            "selection_reason": (
                "all_reviewed_multi_repository_cases"
                if item["accepted_target_repository_count"] > 1
                else "round_robin_single_repository_relation"
            ),
            "source_repository": item["source_repository"],
            "source_pull_request": item["source_pull_request"],
            "accepted_target_repositories": item["accepted_target_repositories"],
            "accepted_target_repository_count": item["accepted_target_repository_count"],
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reviews", type=Path, default=DEFAULT_REVIEWS)
    parser.add_argument("--snapshots", type=Path, default=DEFAULT_SNAPSHOTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--count", type=int, default=85)
    args = parser.parse_args()
    rows = select(read_jsonl(args.reviews), read_jsonl(args.snapshots), args.count)
    args.output.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    print(json.dumps({
        "selected": len(rows),
        "multi_repository_cases": sum(item["accepted_target_repository_count"] > 1 for item in rows),
        "source_repositories": collections.Counter(item["source_repository"] for item in rows),
        "directed_repository_relations": len({
            (item["source_repository"], target)
            for item in rows
            for target in item["accepted_target_repositories"]
        }),
        "output": str(args.output),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

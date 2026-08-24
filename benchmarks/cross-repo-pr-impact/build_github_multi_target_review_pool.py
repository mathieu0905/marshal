#!/usr/bin/env python3
"""Aggregate direct-link rows and select a relation-diverse manual review pool."""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path
from typing import Any

from collect_opendev import ROOT


DEFAULT_FRAME = ROOT / "candidates" / "github-multi-target-search-frame.jsonl"
DEFAULT_OUTPUT = ROOT / "candidates" / "github-multi-target-review-pool.jsonl"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def aggregate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, int], dict[str, Any]] = {}
    for row in rows:
        key = (row["source_repository"], row["source_pull_request"])
        case = grouped.setdefault(key, {
            "ecosystem": row["ecosystem"],
            "relation_family": row["relation_family"],
            "source_repository": row["source_repository"],
            "source_pull_request": row["source_pull_request"],
            "candidate_targets": [],
            "excluded_ambiguous_targets": [],
        })
        target = {
            "repository": row["target_repository"],
            "pull_request": row["target_pull_request"],
            "url": row["target_url"],
            "title": row["target_title"],
            "created_at": row["target_created_at"],
            "updated_at": row["target_updated_at"],
            "body": row["target_body"],
        }
        destination = (
            "excluded_ambiguous_targets" if row["multiple_source_links"]
            else "candidate_targets"
        )
        case[destination].append(target)
    result = []
    for case in grouped.values():
        if not case["candidate_targets"]:
            continue
        repositories = sorted({item["repository"] for item in case["candidate_targets"]})
        case["candidate_target_repositories"] = repositories
        case["candidate_target_repository_count"] = len(repositories)
        case["candidate_target_pull_request_count"] = len(case["candidate_targets"])
        case["candidate_targets"].sort(
            key=lambda item: (item["repository"], item["pull_request"])
        )
        case["excluded_ambiguous_targets"].sort(
            key=lambda item: (item["repository"], item["pull_request"])
        )
        result.append(case)
    result.sort(key=lambda item: (
        item["source_repository"], item["source_pull_request"]
    ))
    return result


def select(cases: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    selected = []
    selected_keys = set()
    multi_target = sorted(
        (case for case in cases if case["candidate_target_repository_count"] > 1),
        key=lambda item: (
            -item["candidate_target_repository_count"],
            item["source_repository"],
            item["source_pull_request"],
        ),
    )
    for case in multi_target:
        case["selection_reason"] = "multiple_unambiguous_target_repositories"
        selected.append(case)
        selected_keys.add((case["source_repository"], case["source_pull_request"]))

    by_relation: dict[tuple[str, str], list[dict[str, Any]]] = collections.defaultdict(list)
    for case in cases:
        key = (case["source_repository"], case["source_pull_request"])
        if key in selected_keys:
            continue
        for target in case["candidate_target_repositories"]:
            by_relation[(case["source_repository"], target)].append(case)
    for relation_cases in by_relation.values():
        relation_cases.sort(key=lambda item: item["source_pull_request"])

    relations = sorted(by_relation, key=lambda key: (len(by_relation[key]), key))
    offsets = collections.Counter()
    while len(selected) < count:
        added = False
        for relation in relations:
            candidates = by_relation[relation]
            while offsets[relation] < len(candidates):
                case = candidates[offsets[relation]]
                offsets[relation] += 1
                key = (case["source_repository"], case["source_pull_request"])
                if key in selected_keys:
                    continue
                case["selection_reason"] = (
                    "round_robin_relation_diversity:"
                    f"{relation[0]}->{relation[1]}"
                )
                selected.append(case)
                selected_keys.add(key)
                added = True
                break
            if len(selected) >= count:
                break
        if not added:
            break

    formal_sources = {
        (item["source_repository"], item["source_pr"])
        for item in read_jsonl(ROOT / "index.jsonl")
    }
    for rank, case in enumerate(selected, 1):
        case["review_rank"] = rank
        case["already_in_formal_set"] = (
            case["source_repository"], case["source_pull_request"]
        ) in formal_sources
    return selected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frame", type=Path, default=DEFAULT_FRAME)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--count", type=int, default=180)
    args = parser.parse_args()
    cases = aggregate(read_jsonl(args.frame))
    selected = select(cases, args.count)
    args.output.write_text(
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in selected),
        encoding="utf-8",
    )
    print(json.dumps({
        "aggregated_unambiguous_cases": len(cases),
        "selected": len(selected),
        "selected_multi_target_cases": sum(
            item["candidate_target_repository_count"] > 1 for item in selected
        ),
        "selected_directed_repository_relations": len({
            (item["source_repository"], target)
            for item in selected
            for target in item["candidate_target_repositories"]
        }),
        "already_in_formal_set": sum(item["already_in_formal_set"] for item in selected),
        "output": str(args.output),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

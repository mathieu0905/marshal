#!/usr/bin/env python3
"""Produce objective mechanism, ecosystem, time, and catalog-use diagnostics."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def time_bucket(value: str) -> str:
    year = datetime.fromisoformat(value.replace("Z", "+00:00")).year
    if year >= 2025:
        return "recent_2025_or_later"
    if year >= 2021:
        return "middle_2021_2024"
    return "legacy_2020_or_earlier"


def ecosystem(source: str) -> str:
    if source.startswith("openstack/"):
        return "openstack"
    if source.startswith("opendev/") or source.startswith("wandertracks/"):
        return "other_opendev"
    return "github_jvm"


def analyze(release_dir: Path) -> dict[str, Any]:
    cases = read_jsonl(release_dir / "final-index.jsonl")
    catalogs = read_json(release_dir / "candidate-repositories.json")["catalogs"]
    adapters = {}
    for case in cases:
        label = read_json(release_dir / "cases" / case["case_id"] / "private" / "label.json")
        adapters[case["case_id"]] = label["replay_adapter"]
    catalog_use = Counter(row["candidate_repository_catalog"].split("#", 1)[1] for row in cases)
    single_observed = []
    for identifier, count in sorted(catalog_use.items()):
        if count != 1:
            continue
        catalog = catalogs[identifier]
        single_observed.append({
            "catalog_id": identifier,
            "observed_case_count": 1,
            "candidate_count": len(catalog["repositories"]),
            "membership_reads_labels": catalog.get("membership_reads_labels"),
            "catalog_status": catalog.get("catalog_status"),
            "selection_rule": catalog.get("selection_rule"),
            "admission_basis": "label-independent reusable directory observed once in this sample; not a target-tailored singleton directory",
        })
    split_mechanisms: dict[str, Counter] = defaultdict(Counter)
    split_ecosystems: dict[str, Counter] = defaultdict(Counter)
    for case in cases:
        split_mechanisms[case["split"]][adapters[case["case_id"]]] += 1
        split_ecosystems[case["split"]][ecosystem(case["source_repository"])] += 1
    return {
        "schema_version": "1.0",
        "case_count": len(cases),
        "ecosystem_counts": dict(sorted(Counter(ecosystem(row["source_repository"]) for row in cases).items())),
        "time_bucket_counts": dict(sorted(Counter(time_bucket(row["observation_cutoff"]) for row in cases).items())),
        "replay_adapter_counts": dict(sorted(Counter(adapters.values()).items())),
        "split_by_replay_adapter": {split: dict(sorted(counts.items())) for split, counts in sorted(split_mechanisms.items())},
        "split_by_ecosystem": {split: dict(sorted(counts.items())) for split, counts in sorted(split_ecosystems.items())},
        "catalog_use_counts": dict(sorted(catalog_use.items())),
        "catalogs_observed_once": single_observed,
        "claim_boundary": {
            "domain_generalization_supported": False,
            "reason": "The set is dominated by OpenStack requirements/constraint mechanisms; JVM cases are concentrated outside development.",
            "memory_stratification": "Report recent/middle/legacy buckets separately; the benchmark does not infer model memorization from age alone.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("release_dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = analyze(args.release_dir)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in (
        "case_count", "ecosystem_counts", "time_bucket_counts", "replay_adapter_counts",
        "split_by_ecosystem", "split_by_replay_adapter",
    )}, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

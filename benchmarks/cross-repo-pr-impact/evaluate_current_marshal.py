#!/usr/bin/env python3
"""Measure the current Cowboy contract configuration on the external cases."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ROOT.parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from marshal_pack_cowboy.pack import CowboyPack  # noqa: E402
from score import load_cases, score  # noqa: E402


def main() -> int:
    pack = CowboyPack()
    cases = load_cases()
    predictions = []
    hit_counts: Counter[str] = Counter()
    for case in cases:
        source = case["source"]
        repo_alias = source["repository"].rsplit("/", 1)[-1]
        scope = {"repo": repo_alias, "diff_paths": source["changed_paths"]}
        hits = pack.contracts_hit(scope)
        hit_counts.update(hits)
        predicted_targets = []
        for invariant in pack.list_invariants(scope):
            if invariant.domain != "cross-repo":
                continue
            predicted_targets.append({
                "repository": invariant.location_repo,
                "paths": [invariant.location_path] if invariant.location_path else [],
                "tests": [invariant.location_test] if invariant.location_test else [],
                "commands": [invariant.run_command] if invariant.run_command else [],
                "execution_result": "not_assessed",
            })
        predictions.append({"case_id": case["case_id"], "targets": predicted_targets})

    predictions_path = ROOT / "results" / "current-marshal-2026-08-22.jsonl"
    with predictions_path.open("w", encoding="utf-8") as handle:
        for prediction in predictions:
            handle.write(json.dumps(prediction, ensure_ascii=False, sort_keys=True) + "\n")
    report = score(cases, predictions)
    report["evaluation"] = {
        "system": "Marshal CowboyPack current configuration",
        "source_repo_input": "repository basename",
        "source_paths_input": "case source.changed_paths",
        "contracts_hit": dict(hit_counts),
        "cases_with_any_contract_hit": sum(bool(item["targets"]) for item in predictions),
        "interpretation": (
            "This measures current configured-contract coverage on external projects; "
            "it does not measure Marshal after project-specific contracts are supplied."
        ),
    }
    report_path = ROOT / "results" / "current-marshal-score-2026-08-22.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

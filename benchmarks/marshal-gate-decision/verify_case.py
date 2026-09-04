#!/usr/bin/env python3
"""Parse and verify one Marshal gate case and its retained execution evidence."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_ROOT = Path(__file__).resolve().parent
_CONSTRAINT_DIFF_RE = re.compile(r"^[+-]([A-Za-z0-9_.-]+)={2,3}([^;\s]+)$")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve(path: str) -> Path:
    resolved = ROOT / path
    if not resolved.is_file():
        raise AssertionError(f"missing evidence file: {resolved}")
    return resolved


def _dependency_labels(patch: str) -> set[str]:
    removed = {}
    added = {}
    for raw in patch.splitlines():
        match = _CONSTRAINT_DIFF_RE.match(raw.strip())
        if not match:
            continue
        distribution, version = match.groups()
        key = re.sub(r"[-_.]+", "_", distribution).lower()
        if raw.startswith("-"):
            removed[key] = version
        elif raw.startswith("+"):
            added[key] = version
    return {f"dependency:{key}" for key in removed.keys() & added.keys()
            if removed[key] != added[key]}


def verify(case_path: Path, gold_path: Path, current_prediction: Path | None) -> dict:
    case = _load(case_path)
    gold = _load(gold_path)
    assert case["case_id"] == gold["case_id"]

    pack = _load(case_path.parent / case["domain_pack_path"])
    assert pack["construction"]["outcome_inputs_read"] is False
    authoring = case["domain_pack_provenance"]["rule_authoring_case"]
    assert pack["construction"]["rule_authoring_case"] is authoring
    authoring_sources = _load(BENCHMARK_ROOT / "rule-authoring-sources.json")
    method = case["domain_pack_provenance"]["method"]
    source_used_for_rule_authoring = (
        case["source"]["candidate_commit"] in authoring_sources.get(method, [])
    )
    development_only = authoring or source_used_for_rule_authoring
    if development_only:
        assert case["split"] == "development"
    else:
        assert case["split"] == "unassigned"

    patch_path = case_path.parent / case["source"]["patch_path"]
    patch_text = patch_path.read_text(encoding="utf-8")
    expected_dependency_labels = _dependency_labels(patch_text)
    actual_dependency_labels = {
        label for label in case["event"]["labels"] if label.startswith("dependency:")
    }
    assert actual_dependency_labels == expected_dependency_labels

    invariant_ids = {row["id"] for row in pack["invariants"]}
    expected_ids = {row["invariant_id"] for row in gold["planning"]["invariants"]}
    assert expected_ids <= invariant_ids
    contracts_by_id = {row["id"]: row for row in pack["contracts"]}
    selected_by_public_pack = {
        invariant_id
        for contract_id in gold["classification"]["contracts_hit"]
        for invariant_id in contracts_by_id[contract_id]["verify_invariants"]
    }
    assert expected_ids == selected_by_public_pack
    pack_routes = {
        row["id"]: (row["location_repo"], row["executor_kind"])
        for row in pack["invariants"]
    }
    gold_routes = {
        row["invariant_id"]: (row["location_repo"], row["executor_kind"])
        for row in gold["planning"]["invariants"]
    }
    assert {invariant_id: pack_routes[invariant_id] for invariant_id in expected_ids} \
        == gold_routes
    contract_ids = set(contracts_by_id)
    assert set(gold["classification"]["contracts_hit"]) <= contract_ids

    public_text = case_path.read_text(encoding="utf-8") + "\n" + \
        (case_path.parent / case["domain_pack_path"]).read_text(encoding="utf-8")
    assert gold["causal_evidence"]["failure_signature"] not in public_text
    assert str(gold["causal_evidence"]["target_repair_pr"]) not in public_text

    arms = {}
    for arm, evidence in gold["causal_evidence"]["arms"].items():
        summary = _load(_resolve(evidence["summary_path"]))
        arms[arm] = summary["exit_code"]
        assert summary["command"] == gold["causal_evidence"]["command"]
    assert arms == {"A0": 0, "A1": 1, "A2": 0}

    a1_log = _resolve(gold["causal_evidence"]["arms"]["A1"]["log_path"])
    a0_log = _resolve(gold["causal_evidence"]["arms"]["A0"]["log_path"])
    a2_log = _resolve(gold["causal_evidence"]["arms"]["A2"]["log_path"])
    signature = gold["causal_evidence"]["failure_signature"]
    assert signature in a1_log.read_text(encoding="utf-8", errors="replace")
    assert signature not in a0_log.read_text(encoding="utf-8", errors="replace")
    assert signature not in a2_log.read_text(encoding="utf-8", errors="replace")

    primary = gold["capable_cross_repo_runner"]
    assert primary["execution"]["status"] == "ok"
    assert any(row["passed"] is False for row in primary["execution"]["results"])
    assert primary["decision"]["verdict"] == "block"

    current_ok = None
    if current_prediction:
        prediction = _load(current_prediction)
        diagnostic = gold["current_reporter_diagnostic"]
        current_ok = (
            prediction["execution"] == diagnostic["execution"]
            and prediction["decision"] == diagnostic["decision"]
        )
        assert current_ok

    status = "development_case_verified" if development_only else "case_ready_for_pool"
    return {
        "schema_version": "marshal-gate-verification-1",
        "case_id": case["case_id"],
        "status": status,
        "arms": arms,
        "pack_contracts": len(pack["contracts"]),
        "pack_invariants": len(pack["invariants"]),
        "current_reporter_diagnostic_verified": current_ok,
        "source_used_for_rule_authoring": source_used_for_rule_authoring,
        "formal_benchmark": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("case", type=Path)
    parser.add_argument("gold", type=Path)
    parser.add_argument("--current-prediction", type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            verify(args.case, args.gold, args.current_prediction),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

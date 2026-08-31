#!/usr/bin/env python3
"""Score selection, fresh causal execution, restraint, and evidence cards.

Unlike ``score_e2.py``, this scorer never treats a prediction's self-reported
``execution_result`` as execution evidence.  Arm outcomes must arrive through a
separate evaluator-owned file produced after predictions are frozen.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from score import reciprocal_rank, safe_mean, set_recall, unique_ordered


VERDICTS = {"breakage", "compatible", "not_assessed"}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def arm_code(result: dict[str, Any], arm: str) -> int | None:
    value = result.get("arms", {}).get(arm)
    if not isinstance(value, dict):
        return None
    code = value.get("exit_code")
    return code if isinstance(code, int) and not isinstance(code, bool) else None


def execution_kind(result: dict[str, Any] | None) -> str:
    if result is None or result.get("status") != "assessed":
        return "not_assessed"
    a0, a1, a2 = (arm_code(result, arm) for arm in ("A0", "A1", "A2"))
    if a0 == 0 and a1 is not None and a1 != 0 and a2 == 0:
        return "causal_breakage_recovered"
    if a0 == 0 and a1 == 0:
        return "bounded_compatible"
    return "inconclusive"


def evidence_card_complete(result: dict[str, Any] | None, required_arms: tuple[str, ...]) -> bool:
    if result is None or result.get("status") != "assessed":
        return False
    evidence = result.get("evidence")
    if not isinstance(evidence, dict) or not isinstance(evidence.get("command"), list) or not evidence["command"]:
        return False
    logs = evidence.get("arm_logs")
    return isinstance(logs, dict) and all(isinstance(logs.get(arm), str) and logs[arm] for arm in required_arms)


def prediction_map(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    mapped = {}
    for row in rows:
        case_id = row.get("case_id")
        if not isinstance(case_id, str) or not case_id or case_id in mapped:
            raise ValueError("prediction case_id must be unique non-empty strings")
        targets = row.get("targets")
        if not isinstance(targets, list) or len(targets) > 20:
            raise ValueError(f"{case_id}: targets must be a list of at most 20 entries")
        repositories = []
        for target in targets:
            repository = target.get("repository") if isinstance(target, dict) else None
            verdict = target.get("verdict", "not_assessed") if isinstance(target, dict) else None
            if not isinstance(repository, str) or not repository or verdict not in VERDICTS:
                raise ValueError(f"{case_id}: invalid target")
            repositories.append(repository)
        if len(set(repositories)) != len(repositories):
            raise ValueError(f"{case_id}: duplicate target repository")
        mapped[case_id] = row
    return mapped


def execution_map(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    mapped = {}
    for row in rows:
        key = (row.get("case_id"), row.get("repository"))
        if not all(isinstance(value, str) and value for value in key) or key in mapped:
            raise ValueError("execution result keys must be unique non-empty strings")
        if row.get("status") not in {"assessed", "not_assessed"}:
            raise ValueError(f"{key}: invalid execution status")
        mapped[key] = row
    return mapped


def score_product(
    e2_cases: list[dict[str, Any]],
    e3_cases: list[dict[str, Any]],
    packs: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    executions: list[dict[str, Any]],
) -> dict[str, Any]:
    predicted = prediction_map(predictions)
    executed = execution_map(executions)
    e2_records = []
    for case in e2_cases:
        case_id = case["case_id"]
        targets = predicted.get(case_id, {}).get("targets", [])
        ranked = unique_ordered([target["repository"] for target in targets])
        gold = set(case["target_repositories"])
        by_repository = {target["repository"]: target for target in targets}
        target_records = []
        for repository in sorted(gold):
            result = executed.get((case_id, repository))
            kind = execution_kind(result)
            target_records.append({
                "repository": repository,
                "selected": repository in ranked,
                "execution_kind": kind,
                "causal_judgment_correct": kind == "causal_breakage_recovered",
                "evidence_card_complete": evidence_card_complete(result, ("A0", "A1", "A2")),
                "not_assessed": kind == "not_assessed",
                "self_reported_execution_ignored": by_repository.get(repository, {}).get("execution_result") is not None,
            })
        e2_records.append({
            "case_id": case_id,
            "target_recall": set_recall(gold, set(ranked)),
            "reciprocal_rank": reciprocal_rank(gold, ranked),
            "recall_at_5": set_recall(gold, set(ranked[:5])),
            "prediction_count": len(ranked),
            "targets": target_records,
        })

    pack_by_id = {row["pack_id"]: row for row in packs}
    e3_by_pack: dict[str, set[str]] = {}
    for case in e3_cases:
        e3_by_pack.setdefault(case["pack_id"], set()).add(case["target_repository"])
    pack_records = []
    totals = {"tp": 0, "fp": 0, "tn": 0, "fn": 0, "abstained": 0}
    for pack_id, pack in sorted(pack_by_id.items()):
        if not pack.get("bounded_universe_complete"):
            continue
        targets = predicted.get(pack_id, {}).get("targets", [])
        by_repository = {target["repository"]: target for target in targets}
        positives = set(pack["breakage_repositories"])
        negatives = e3_by_pack.get(pack_id, set())
        if negatives != set(pack["bounded_negative_repositories"]):
            raise ValueError(f"{pack_id}: E3 cases do not cover the declared negative set")
        records = []
        for repository in pack["candidate_repositories"]:
            gold = "breakage" if repository in positives else "compatible"
            target = by_repository.get(repository)
            verdict = target.get("verdict", "not_assessed") if target else "not_assessed"
            result = executed.get((pack_id, repository))
            kind = execution_kind(result)
            backed = (
                verdict == "breakage" and kind == "causal_breakage_recovered"
            ) or (
                verdict == "compatible" and kind == "bounded_compatible"
                and evidence_card_complete(result, ("A0", "A1"))
            )
            effective = verdict if backed else "not_assessed"
            if effective == "not_assessed":
                bucket = "abstained"
            elif gold == "breakage" and effective == "breakage":
                bucket = "tp"
            elif gold == "compatible" and effective == "breakage":
                bucket = "fp"
            elif gold == "compatible" and effective == "compatible":
                bucket = "tn"
            else:
                bucket = "fn"
            totals[bucket] += 1
            records.append({
                "repository": repository,
                "gold": gold,
                "reported_verdict": verdict,
                "execution_kind": kind,
                "evidence_backed": backed,
                "scored_verdict": effective,
                "confusion_bucket": bucket,
            })
        pack_records.append({"pack_id": pack_id, "records": records})

    e2_targets = [target for record in e2_records for target in record["targets"]]
    assessed = totals["tp"] + totals["fp"] + totals["tn"] + totals["fn"]
    precision_denominator = totals["tp"] + totals["fp"]
    specificity_denominator = totals["tn"] + totals["fp"]
    return {
        "schema_version": "1.0",
        "task": "candidate_selection_plus_causal_execution",
        "e2": {
            "case_count": len(e2_records),
            "target_retrieval": {
                "macro_recall": safe_mean([row["target_recall"] for row in e2_records]),
                "mrr": safe_mean([row["reciprocal_rank"] for row in e2_records]),
                "recall_at_5": safe_mean([row["recall_at_5"] for row in e2_records]),
                "mean_prediction_count": safe_mean([float(row["prediction_count"]) for row in e2_records]),
            },
            "causal_execution": {
                "strict_a0_a1_a2_accuracy": safe_mean([1.0 if row["causal_judgment_correct"] else 0.0 for row in e2_targets]),
                "not_assessed_rate": safe_mean([1.0 if row["not_assessed"] else 0.0 for row in e2_targets]),
                "evidence_card_complete_rate": safe_mean([1.0 if row["evidence_card_complete"] else 0.0 for row in e2_targets]),
                "denominator": len(e2_targets),
                "prediction_self_reports_used": False,
            },
            "records": e2_records,
        },
        "restraint": {
            "bounded_pack_count": len(pack_records),
            "confusion": totals,
            "assessed_count": assessed,
            "precision": totals["tp"] / precision_denominator if precision_denominator else None,
            "specificity": totals["tn"] / specificity_denominator if specificity_denominator else None,
            "abstention_rate": totals["abstained"] / sum(totals.values()) if sum(totals.values()) else None,
            "scope": "Only the three fully executed bounded project packs; these metrics do not apply to unjudged main-set candidates.",
            "records": pack_records,
        },
        "limitations": [
            "The E2 main set still has unjudged non-target candidates, so main-set precision, F1, false-positive rate, and specificity remain unsupported.",
            "Execution results are evaluator-owned and must be created after predictions are frozen; prediction self-reports are ignored.",
            "A dataset-fixed command tests candidate selection, orchestration, causal judgment, and evidence handling, not arbitrary command synthesis.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--e2-index", type=Path, required=True)
    parser.add_argument("--e3-cases", type=Path, required=True)
    parser.add_argument("--project-packs", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--execution-results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = score_product(
        read_jsonl(args.e2_index), read_jsonl(args.e3_cases), read_jsonl(args.project_packs),
        read_jsonl(args.predictions), read_jsonl(args.execution_results),
    )
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"e2": report["e2"]["causal_execution"], "restraint": report["restraint"]["confusion"]}, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

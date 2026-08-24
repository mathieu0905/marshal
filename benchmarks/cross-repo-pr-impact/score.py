#!/usr/bin/env python3
"""Score cross-repository impact retrieval and secondary diagnostics."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from typing import Any


ROOT = Path(__file__).resolve().parent


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_cases() -> list[dict[str, Any]]:
    records = []
    with (ROOT / "index.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            item = json.loads(line)
            records.append(load_json(ROOT / item["path"]))
    return records


def validate_prediction(prediction: Any, index: int) -> None:
    location = f"prediction {index}"
    if not isinstance(prediction, dict) or set(prediction) != {"case_id", "targets"}:
        raise SystemExit(f"{location} must contain only case_id and targets")
    if not isinstance(prediction["case_id"], str) or not prediction["case_id"]:
        raise SystemExit(f"{location}.case_id must be a non-empty string")
    if not isinstance(prediction["targets"], list):
        raise SystemExit(f"{location}.targets must be a list")
    allowed_results = {
        "pass", "fail", "no_cross_repo_impact", "not_assessed",
        "fail_without_companion_pass_with_companion",
        "not_exercised_without_source_pass_with_source",
        None,
    }
    required = {"repository", "paths", "tests", "commands", "execution_result"}
    for target_index, target in enumerate(prediction["targets"]):
        where = f"{location}.targets[{target_index}]"
        if not isinstance(target, dict) or set(target) != required:
            raise SystemExit(f"{where} has missing or unknown fields")
        if not isinstance(target["repository"], str) or not target["repository"]:
            raise SystemExit(f"{where}.repository must be a non-empty string")
        for key in ("paths", "tests"):
            values = target[key]
            if not isinstance(values, list) or any(not isinstance(value, str) or not value for value in values):
                raise SystemExit(f"{where}.{key} must be a string list")
        commands = target["commands"]
        if not isinstance(commands, list) or any(
            not isinstance(command, list) or not command or any(not isinstance(arg, str) for arg in command)
            for command in commands
        ):
            raise SystemExit(f"{where}.commands must contain argument arrays")
        if target["execution_result"] not in allowed_results:
            raise SystemExit(f"{where}.execution_result is unsupported")


def unique_ordered(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def safe_mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def set_recall(gold: set[Any], predicted: set[Any]) -> float:
    return len(gold & predicted) / len(gold) if gold else 1.0


def reciprocal_rank(gold: set[str], ranked: list[str]) -> float:
    for index, value in enumerate(ranked, 1):
        if value in gold:
            return 1.0 / index
    return 0.0


def retrieval_metrics(records: list[dict[str, float]]) -> dict[str, Any]:
    return {
        "cases": len(records),
        "known_target_macro_recall": safe_mean([item["recall"] for item in records]),
        "mean_reciprocal_rank": safe_mean([item["reciprocal_rank"] for item in records]),
        "recall_at_1": safe_mean([item["recall_at_1"] for item in records]),
        "recall_at_3": safe_mean([item["recall_at_3"] for item in records]),
        "recall_at_5": safe_mean([item["recall_at_5"] for item in records]),
    }


def grouped_retrieval_metrics(
    records: list[dict[str, Any]], key: str,
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, float]]] = defaultdict(list)
    for item in records:
        grouped[item[key]].append(item)
    return {
        name: retrieval_metrics(items)
        for name, items in sorted(grouped.items())
    }


def merge_target_records(targets: list[dict[str, Any]], expected: bool) -> dict[str, dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for target in targets:
        repository = target["repository"]
        item = merged.setdefault(repository, {
            "repository": repository,
            "companion_paths": [],
            "impact_paths": [],
            "tests": [],
            "commands": [],
            "execution_result": None,
            "evidence_levels": set(),
            "label_scopes": set(),
        })
        checks = target["expected_checks"] if expected else target
        if expected:
            item["companion_paths"] = unique_ordered(
                item["companion_paths"] + target["changed_paths"]
            )
            item["impact_paths"] = unique_ordered(item["impact_paths"] + checks["paths"])
        else:
            item["impact_paths"] = unique_ordered(item["impact_paths"] + checks["paths"])
        item["tests"] = unique_ordered(item["tests"] + checks["tests"])
        known_commands = {tuple(command) for command in item["commands"]}
        for command in checks["commands"]:
            if tuple(command) not in known_commands:
                item["commands"].append(command)
                known_commands.add(tuple(command))
        if expected:
            levels = {evidence["level"] for evidence in target["evidence"]}
            item["evidence_levels"].update(levels)
            item["label_scopes"].add(target["label_scope"])
            if levels & {"executed", "ci_contrast_proven"}:
                item["execution_result"] = checks["expected_result"]
        elif target.get("execution_result") is not None:
            item["execution_result"] = target["execution_result"]
    return merged


def oracle_predictions(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for case in cases:
        merged = merge_target_records(case["targets"], expected=True)
        targets = [
            {
                "repository": item["repository"],
                "paths": item["impact_paths"] or item["companion_paths"],
                "tests": item["tests"],
                "commands": item["commands"],
                "execution_result": item["execution_result"],
            }
            for item in merged.values()
        ]
        result.append({"case_id": case["case_id"], "targets": targets})
    return result


def validate_prediction_set(cases: list[dict[str, Any]], predictions: list[dict[str, Any]]) -> None:
    for index, prediction in enumerate(predictions, 1):
        validate_prediction(prediction, index)
    if len({item["case_id"] for item in predictions}) != len(predictions):
        raise SystemExit("duplicate case_id in predictions")
    known_case_ids = {case["case_id"] for case in cases}
    unknown_case_ids = sorted({item["case_id"] for item in predictions} - known_case_ids)
    if unknown_case_ids:
        raise SystemExit(f"unknown case_id in predictions: {', '.join(unknown_case_ids)}")


def score(cases: list[dict[str, Any]], predictions: list[dict[str, Any]]) -> dict[str, Any]:
    prediction_by_id = {item["case_id"]: item for item in predictions}
    repo_recall_at = {1: [], 3: [], 5: []}
    unjudged_repository_predictions = 0
    companion_path_hit_at_5 = []
    companion_path_rr = []
    impact_path_recall_at_5 = []
    impact_path_normalized_recall_at_5 = []
    impact_path_recall_at_5_ceiling = []
    impact_path_hit_at_5 = []
    impact_path_rr = []
    test_recall = []
    test_hit_at_5 = []
    command_recall = []
    execution_correct = []
    missing_predictions = []
    retrieval_records = []
    target_retrieval_records = []
    evidence_retrieval_records = []
    relation_kind_retrieval_records = []
    repository_prediction_counts = []
    strata: dict[str, Counter[str]] = defaultdict(Counter)

    for case in cases:
        prediction = prediction_by_id.get(case["case_id"])
        if prediction is None:
            missing_predictions.append(case["case_id"])
            prediction = {"targets": []}
        predicted_targets = prediction["targets"]
        ranked_repositories = unique_ordered([item["repository"] for item in predicted_targets])
        predicted_repositories = set(ranked_repositories)
        repository_prediction_counts.append(len(ranked_repositories))
        gold_repositories = {item["repository"] for item in case["targets"]}
        recall = len(gold_repositories & predicted_repositories) / len(gold_repositories)
        rr = reciprocal_rank(gold_repositories, ranked_repositories)
        unjudged_repository_predictions += len(predicted_repositories - gold_repositories)
        for k in repo_recall_at:
            repo_recall_at[k].append(set_recall(gold_repositories, set(ranked_repositories[:k])))
        created = case["source"]["pull_request"]["created"]
        retrieval_records.append({
            "project": case["project"],
            "year": created[:4],
            "project_and_year": f"{case['project']}:{created[:4]}",
            "recall": recall,
            "reciprocal_rank": rr,
            "recall_at_1": repo_recall_at[1][-1],
            "recall_at_3": repo_recall_at[3][-1],
            "recall_at_5": repo_recall_at[5][-1],
        })

        relation_kinds_by_repository: dict[str, set[str]] = defaultdict(set)
        for relation in case["relations"]:
            relation_kinds_by_repository[relation["target_repository"]].add(
                relation["relation_kind"]
            )
        evidence_levels_by_repository: dict[str, set[str]] = defaultdict(set)
        for target in case["targets"]:
            evidence_levels_by_repository[target["repository"]].update(
                evidence["level"] for evidence in target["evidence"]
            )
        for repository in sorted(gold_repositories):
            target_record = {
                "directed_repository_relation": (
                    f"{case['source']['repository']} -> {repository}"
                ),
                "recall": 1.0 if repository in predicted_repositories else 0.0,
                "reciprocal_rank": reciprocal_rank({repository}, ranked_repositories),
                "recall_at_1": 1.0 if repository in ranked_repositories[:1] else 0.0,
                "recall_at_3": 1.0 if repository in ranked_repositories[:3] else 0.0,
                "recall_at_5": 1.0 if repository in ranked_repositories[:5] else 0.0,
            }
            target_retrieval_records.append(target_record)
            for evidence_level in evidence_levels_by_repository[repository]:
                evidence_retrieval_records.append({
                    **target_record,
                    "evidence_level": evidence_level,
                })
            for relation_kind in relation_kinds_by_repository[repository]:
                relation_kind_retrieval_records.append({
                    **target_record,
                    "relation_kind": relation_kind,
                })

        predicted_by_repo = merge_target_records(predicted_targets, expected=False)
        expected_by_repo = merge_target_records(case["targets"], expected=True)
        for repository, expected in expected_by_repo.items():
            predicted = predicted_by_repo.get(repository, {
                "impact_paths": [], "tests": [], "commands": [], "execution_result": None,
            })
            predicted_paths = predicted["impact_paths"]
            companion_paths = set(expected["companion_paths"])
            companion_hit = bool(companion_paths & set(predicted_paths[:5]))
            companion_path_hit_at_5.append(1.0 if companion_hit else 0.0)
            companion_path_rr.append(reciprocal_rank(companion_paths, predicted_paths))
            impact_paths = set(expected["impact_paths"])
            if impact_paths:
                hits_at_5 = len(impact_paths & set(predicted_paths[:5]))
                impact_path_recall_at_5.append(hits_at_5 / len(impact_paths))
                achievable_hits = min(5, len(impact_paths))
                impact_path_normalized_recall_at_5.append(hits_at_5 / achievable_hits)
                impact_path_recall_at_5_ceiling.append(achievable_hits / len(impact_paths))
                impact_path_hit_at_5.append(1.0 if impact_paths & set(predicted_paths[:5]) else 0.0)
                impact_path_rr.append(reciprocal_rank(impact_paths, predicted_paths))
            if expected["tests"]:
                test_recall.append(set_recall(set(expected["tests"]), set(predicted["tests"])))
                test_hit_at_5.append(
                    1.0 if set(expected["tests"]) & set(predicted["tests"][:5]) else 0.0
                )
            if expected["commands"]:
                gold_commands = {tuple(command) for command in expected["commands"]}
                predicted_commands = {tuple(command) for command in predicted["commands"]}
                command_recall.append(set_recall(gold_commands, predicted_commands))
            levels = expected["evidence_levels"]
            for level in levels:
                strata[level]["targets"] += 1
                if repository in predicted_repositories:
                    strata[level]["repository_found"] += 1
                if companion_paths & set(predicted_paths):
                    strata[level]["position_found"] += 1
            for label_scope in expected["label_scopes"]:
                strata[f"scope:{label_scope}"]["targets"] += 1
                if repository in predicted_repositories:
                    strata[f"scope:{label_scope}"]["repository_found"] += 1
                if companion_paths & set(predicted_paths):
                    strata[f"scope:{label_scope}"]["position_found"] += 1
            if levels & {"executed", "ci_contrast_proven"}:
                expected_result = expected["execution_result"]
                correct = predicted.get("execution_result") == expected_result
                execution_correct.append(1.0 if correct else 0.0)
                for level in levels & {"executed", "ci_contrast_proven"}:
                    strata[level]["execution_scored"] += 1
                    strata[level]["execution_correct"] += int(correct)

    evidence_report = {}
    for level, counts in sorted(strata.items()):
        targets = counts["targets"]
        item = {
            "targets": targets,
            "repository_found": counts["repository_found"],
            "repository_recall": counts["repository_found"] / targets if targets else None,
            "position_found": counts["position_found"],
            "position_hit_rate": counts["position_found"] / targets if targets else None,
        }
        if counts["execution_scored"]:
            item["execution_scored"] = counts["execution_scored"]
            item["execution_correct"] = counts["execution_correct"]
            item["execution_accuracy"] = counts["execution_correct"] / counts["execution_scored"]
        evidence_report[level] = item

    repository_report = retrieval_metrics(retrieval_records)
    repository_report.update({
        "task_name": "cross_repository_impact_repository_retrieval",
        "effective_directed_repository_relations": len({
            (case["source"]["repository"], target["repository"])
            for case in cases
            for target in case["targets"]
        }),
        "unjudged_repository_predictions": unjudged_repository_predictions,
        "repository_predictions_per_case": {
            "total": sum(repository_prediction_counts),
            "mean": safe_mean([float(value) for value in repository_prediction_counts]),
            "median": median(repository_prediction_counts) if repository_prediction_counts else None,
            "maximum": max(repository_prediction_counts, default=None),
        },
        "precision_reported": False,
        "precision_note": (
            "已知目标不是完整影响集合，额外预测只记为未判定；"
            "每案例预测数量用于显露全报候选仓等宽泛策略。"
        ),
        "by_project": grouped_retrieval_metrics(retrieval_records, "project"),
        "by_year": grouped_retrieval_metrics(retrieval_records, "year"),
        "by_project_and_year": grouped_retrieval_metrics(
            retrieval_records, "project_and_year"
        ),
        "by_directed_repository_relation": grouped_retrieval_metrics(
            target_retrieval_records, "directed_repository_relation"
        ),
        "by_relation_kind": grouped_retrieval_metrics(
            relation_kind_retrieval_records, "relation_kind"
        ),
        "by_evidence_level": grouped_retrieval_metrics(
            evidence_retrieval_records, "evidence_level"
        ),
    })

    return {
        "cases": len(cases),
        "missing_predictions": len(missing_predictions),
        "primary_task": repository_report,
        "secondary_diagnostics": {
            "warning": (
                "候选仓时点代码已提供，但绝大多数目标只有配套变更完整改动面，"
                "没有独立筛选的位置、测试或命令真值；这些诊断不属于主结果。"
            ),
            "known_companion_change_footprint": {
                "path_hit_at_5": safe_mean(companion_path_hit_at_5),
                "path_mean_reciprocal_rank": safe_mean(companion_path_rr),
                "scored_targets": len(companion_path_hit_at_5),
            },
            "curated_impact_position": {
                "path_recall_at_5": safe_mean(impact_path_recall_at_5),
                "path_recall_at_5_oracle_ceiling": safe_mean(impact_path_recall_at_5_ceiling),
                "path_normalized_recall_at_5": safe_mean(impact_path_normalized_recall_at_5),
                "path_hit_at_5": safe_mean(impact_path_hit_at_5),
                "path_mean_reciprocal_rank": safe_mean(impact_path_rr),
                "scored_targets": len(impact_path_recall_at_5),
            },
            "check_selection": {
                "test_recall": safe_mean(test_recall),
                "test_hit_at_5": safe_mean(test_hit_at_5),
                "test_scored_targets": len(test_recall),
                "exact_command_recall": safe_mean(command_recall),
                "command_scored_targets": len(command_recall),
            },
            "execution_result": {
                "accuracy": safe_mean(execution_correct),
                "scored_targets": len(execution_correct),
            },
            "by_evidence_level_or_scope": evidence_report,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("predictions", nargs="?", type=Path)
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    cases = load_cases()
    if args.self_check:
        predictions = oracle_predictions(cases)
    elif args.predictions:
        predictions = [
            json.loads(line)
            for line in args.predictions.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    else:
        parser.error("provide a predictions JSONL file or --self-check")
    validate_prediction_set(cases, predictions)
    report = score(cases, predictions)
    rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    if args.self_check:
        checks = [
            report["primary_task"]["known_target_macro_recall"],
            report["secondary_diagnostics"]["known_companion_change_footprint"]["path_mean_reciprocal_rank"],
            report["secondary_diagnostics"]["curated_impact_position"]["path_mean_reciprocal_rank"],
            report["secondary_diagnostics"]["check_selection"]["test_recall"],
            report["secondary_diagnostics"]["check_selection"]["exact_command_recall"],
            report["secondary_diagnostics"]["execution_result"]["accuracy"],
        ]
        if any(value is not None and value != 1.0 for value in checks):
            raise SystemExit("oracle self-check did not produce perfect scores")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

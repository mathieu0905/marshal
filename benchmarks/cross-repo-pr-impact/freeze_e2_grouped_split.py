#!/usr/bin/env python3
"""Freeze a group-isolated E2 split without using ranking outcomes."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parent
DEFAULT_INDEX = ROOT / "results/final-e2-dataset-50-2026-08-25/final-index.jsonl"


# These are target-repair edit shapes, not failure mechanisms. They are deliberately
# specific: two cases share a value only when the same kind of A2 edit could leak.
REPAIR_TEMPLATES = {
    "e2-001": "adapt_schema_reflection_expectation",
    "e2-002": "remove_deleted_test_utility_usage",
    "e2-003": "remove_deleted_test_utility_usage",
    "e2-004": "synchronize_runtime_component_versions",
    "e2-005": "synchronize_runtime_component_versions",
    "e2-006": "declare_new_governed_dependency",
    "e2-007": "adapt_imports_to_default_exports",
    "e2-008": "update_time_window_expectation",
    "e2-009": "relax_generated_output_expectation",
    "e2-010": "configure_generated_output_compatibility",
    "e2-011": "supply_new_required_constructor_argument",
    "e2-012": "supply_new_required_constructor_argument",
    "e2-013": "replace_moved_types_and_dependency",
    "e2-014": "replace_moved_types_and_dependency",
    "e2-015": "synchronize_runtime_component_versions",
    "e2-016": "preserve_mapper_customization_against_cache",
    "e2-017": "synchronize_runtime_component_versions",
    "e2-018": "update_dependency_allowlist",
    "e2-019": "replace_removed_internal_dependency_usage",
    "e2-020": "update_assertion_message_expectation",
    "e2-021": "replace_newly_rejected_test_input",
    "e2-022": "replace_deprecated_constructor_usage",
    "e2-023": "resolve_new_static_analysis_findings",
    "e2-024": "resolve_new_static_analysis_findings",
    "e2-025": "replace_removed_mocking_api",
    "e2-026": "replace_removed_test_runner_integration",
    "e2-027": "synchronize_runtime_component_versions",
    "e2-028": "replace_private_module_import",
    "e2-029": "configure_module_transform_mode",
    "e2-030": "refresh_binary_output_fixture",
    "e2-031": "adapt_rule_input_or_configuration",
    "e2-032": "coordinate_identity_handling_across_targets",
    "e2-033": "adapt_changed_runtime_object_shape",
    "e2-034": "remove_obsolete_connection_parameter",
    "e2-035": "remove_obsolete_connection_parameter",
    "e2-036": "quote_or_rename_reserved_identifier",
    "e2-037": "quote_or_rename_reserved_identifier",
    "e2-038": "remove_rejected_sql_trailing_comma",
    "e2-039": "synchronize_runtime_component_versions",
    "e2-040": "add_new_driver_artifact_dependency",
    "e2-041": "replace_partial_mapper_with_upstream_mapper",
    "e2-042": "adapt_mocking_of_newly_interceptable_methods",
    "e2-043": "correct_newly_rejected_attribute_syntax",
    "e2-044": "add_required_trait_bound_or_indirection",
    "e2-045": "constrain_callback_lifetime_or_ownership",
    "e2-046": "correct_lifetime_bound",
    "e2-047": "synchronize_runtime_component_versions",
    "e2-048": "update_closed_world_country_expectation",
    "e2-049": "update_supported_classfile_version_constant",
    "e2-050": "update_jmx_object_name_expectation",
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def catalog_id(reference: str) -> str:
    filename, separator, identifier = reference.partition("#")
    if filename != "candidate-repositories.json" or not separator or not identifier:
        raise ValueError(f"invalid catalog reference: {reference}")
    return identifier


class UnionFind:
    def __init__(self, values: Iterable[str]) -> None:
        self.parent = {value: value for value in values}

    def find(self, value: str) -> str:
        while self.parent[value] != value:
            self.parent[value] = self.parent[self.parent[value]]
            value = self.parent[value]
        return value

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[max(left_root, right_root)] = min(left_root, right_root)


def grouped_cases(cases: list[dict[str, Any]]) -> tuple[list[list[str]], dict[str, dict[str, Any]]]:
    case_ids = {case["case_id"] for case in cases}
    if case_ids != set(REPAIR_TEMPLATES):
        raise ValueError("repair-template taxonomy does not exactly cover the E2 index")
    union_find = UnionFind(case_ids)
    axes: dict[tuple[str, str], list[str]] = defaultdict(list)
    facts = {}
    for case in cases:
        case_id = case["case_id"]
        relations = sorted(
            f"{case['source_repository']} -> {target}"
            for target in case["target_repositories"]
        )
        facts[case_id] = {
            "directed_relation_units": relations,
            "source_change_family": case["source_change_family"],
            "mechanism": case["mechanism"].strip().casefold(),
            "repair_template": REPAIR_TEMPLATES[case_id],
        }
        for relation in relations:
            axes[("directed_relation", relation)].append(case_id)
        axes[("source_change_family", case["source_change_family"])].append(case_id)
        axes[("mechanism", case["mechanism"].strip().casefold())].append(case_id)
        axes[("repair_template", REPAIR_TEMPLATES[case_id])].append(case_id)
    for members in axes.values():
        for member in members[1:]:
            union_find.union(members[0], member)
    components: dict[str, list[str]] = defaultdict(list)
    for case_id in sorted(case_ids):
        components[union_find.find(case_id)].append(case_id)
    return sorted(components.values(), key=lambda rows: rows[0]), facts


def freeze(
    cases: list[dict[str, Any]],
    assignments: list[dict[str, Any]],
    coverage: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    components, facts = grouped_cases(cases)
    assignment_by_id = {row["case_id"]: row for row in assignments}
    formal_by_id = {}
    for case in cases:
        assignment = assignment_by_id[case["case_id"]]
        identifier = catalog_id(assignment["candidate_repository_catalog"])
        formal_by_id[case["case_id"]] = bool(
            coverage["catalogs"][identifier]["formal_catalog_eligible"]
        )

    # Assign whole components by case-count deficit. Catalog coverage, targets,
    # mechanisms' observed frequency, and ranking outcomes do not affect this step.
    target_case_counts = {
        "development": round(len(cases) * 0.6),
        "evaluation": round(len(cases) * 0.2),
        "holdout": len(cases) - round(len(cases) * 0.6) - round(len(cases) * 0.2),
    }
    assigned_case_counts = {split: 0 for split in target_case_counts}
    component_split = {}
    split_tie_priority = {"development": 2, "evaluation": 1, "holdout": 0}
    for component in sorted(components, key=lambda rows: (-len(rows), rows[0])):
        split = max(
            target_case_counts,
            key=lambda candidate: (
                target_case_counts[candidate] - assigned_case_counts[candidate],
                split_tie_priority[candidate],
            ),
        )
        component_split[tuple(component)] = split
        assigned_case_counts[split] += len(component)

    component_rows = []
    split_rows = []
    for group_number, component in enumerate(components, start=1):
        formal_catalog_only = all(formal_by_id[case_id] for case_id in component)
        split = component_split[tuple(component)]
        group_id = f"e2-group-{group_number:03d}"
        component_facts = [facts[case_id] for case_id in component]
        component_rows.append({
            "group_id": group_id,
            "case_ids": component,
            "split": split,
            "formal_catalog_only": formal_catalog_only,
            "directed_relation_units": sorted({
                relation
                for fact in component_facts
                for relation in fact["directed_relation_units"]
            }),
            "source_change_families": sorted({fact["source_change_family"] for fact in component_facts}),
            "mechanisms": sorted({fact["mechanism"] for fact in component_facts}),
            "repair_templates": sorted({fact["repair_template"] for fact in component_facts}),
        })
        for case_id in component:
            split_rows.append({
                "case_id": case_id,
                "group_id": group_id,
                "split": split,
                "formal_catalog_eligible": formal_by_id[case_id],
                **facts[case_id],
            })

    for axis in ("directed_relation_units", "source_change_family", "mechanism", "repair_template"):
        seen = {}
        for row in split_rows:
            values = row[axis] if axis == "directed_relation_units" else [row[axis]]
            for value in values:
                if value in seen and seen[value] != row["split"]:
                    raise AssertionError(f"{axis} crosses split: {value}")
                seen[value] = row["split"]

    split_counts = Counter(row["split"] for row in split_rows)
    formal_split_counts = Counter(
        row["split"] for row in split_rows if row["formal_catalog_eligible"]
    )
    summary = {
        "schema_version": "1.0",
        "case_count": len(split_rows),
        "group_count": len(component_rows),
        "split_case_counts": dict(sorted(split_counts.items())),
        "formal_catalog_case_split_counts": dict(sorted(formal_split_counts.items())),
        "leakage_axis_counts": {
            "directed_relation": len({value for row in split_rows for value in row["directed_relation_units"]}),
            "source_change_family": len({row["source_change_family"] for row in split_rows}),
            "mechanism": len({row["mechanism"] for row in split_rows}),
            "repair_template": len({row["repair_template"] for row in split_rows}),
        },
        "cross_split_leak_count": 0,
        "split_grouping_reads_relation_and_e2_taxonomy": True,
        "split_assignment_reads_target_frequency_or_ranking_outcomes": False,
        "split_status": "frozen_group_isolated_v1",
        "blind_evaluation_ready": True,
        "interpretation": (
            "The split is frozen before the next scored run. Cases without a formal "
            "catalog remain development-only even when assigned to a release group; "
            "only cases passing all per-case prerequisites may enter a formal score."
        ),
    }
    return component_rows, sorted(split_rows, key=lambda row: row["case_id"]), summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--e2-index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--catalog-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    components, splits, summary = freeze(
        read_jsonl(args.e2_index),
        read_jsonl(args.catalog_dir / "case-catalog-assignments.jsonl"),
        read_json(args.catalog_dir / "coverage-audit.json"),
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.output_dir / "group-manifest.jsonl", components)
    write_jsonl(args.output_dir / "split-manifest.jsonl", splits)
    write_json(args.output_dir / "metrics.json", summary)
    write_json(args.output_dir / "run-manifest.json", {
        "schema_version": "1.0",
        "inputs": [str(args.e2_index), str(args.catalog_dir)],
        "outputs": ["group-manifest.jsonl", "split-manifest.jsonl", "metrics.json"],
        "grouping_axes": ["directed_relation", "source_change_family", "mechanism", "repair_template"],
        "selection_inputs_excluded": ["ranking predictions", "ranking metrics", "target-frequency statistics"],
    })
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

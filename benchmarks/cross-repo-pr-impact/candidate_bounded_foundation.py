#!/usr/bin/env python3
"""Audit candidate catalogs and materialize conservative grouping/evidence manifests.

The generated files are diagnostic artifacts. They do not rewrite schema-v1 cases,
the published index, or the candidate catalogs.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parent
SPLITS = ("development", "evaluation", "holdout")


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
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
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


def load_cases(dataset_root: Path) -> list[dict[str, Any]]:
    return [
        read_json(dataset_root / item["path"])
        for item in read_jsonl(dataset_root / "index.jsonl")
    ]


def audit_catalogs(
    dataset_root: Path,
    cases: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    catalogs = read_json(dataset_root / "candidate-repositories.json")["catalogs"]
    provenance = read_json(dataset_root / "candidate-catalog-provenance.json")
    source_snapshots = read_json(dataset_root / "catalog-source-snapshots.json")
    if set(catalogs) != set(provenance["catalogs"]):
        missing = sorted(set(catalogs) - set(provenance["catalogs"]))
        extra = sorted(set(provenance["catalogs"]) - set(catalogs))
        raise ValueError(f"catalog provenance mismatch: missing={missing}, extra={extra}")

    cases_by_project: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        cases_by_project[case["project"]].append(case)

    rows = []
    for project, catalog in sorted(catalogs.items()):
        project_cases = cases_by_project[project]
        repositories = set(catalog["repositories"])
        targets = {
            target["repository"]
            for case in project_cases
            for target in case["targets"]
        }
        config = provenance["catalogs"][project]
        single_case = len(project_cases) == 1
        current_source = config.get("current_source_snapshot")
        source_id = current_source.split("#", 1)[1] if current_source else None
        source_membership = (
            set(source_snapshots["sources"][source_id]["repositories"])
            if source_id else set()
        )
        label_independent = bool(source_id) and repositories == source_membership
        if single_case:
            disposition = "development_sensitivity_only"
            reason = "catalog_is_used_by_one_case"
        elif label_independent:
            disposition = "formal_split_candidate"
            reason = "catalog_matches_recorded_label_independent_source_snapshot"
        else:
            disposition = "development_rebuild_required"
            reason = "current_catalog_was_built_from_hidden_targets"
        rows.append({
            "project": project,
            "case_count": len(project_cases),
            "catalog_repository_count": len(repositories),
            "known_target_repository_count": len(targets),
            "known_target_fraction": len(targets) / len(repositories),
            "catalog_covers_current_targets": targets <= repositories,
            "observed_construction": provenance["observed_construction"]["kind"],
            "current_source_snapshot": current_source,
            "current_label_independent": label_independent,
            "current_formal_eligible": label_independent and not single_case,
            "single_case_catalog": single_case,
            "disposition": disposition,
            "reason": reason,
            "proposed_rule": config["proposed_rule"],
            "proposed_sources": config["sources"],
            "rebuild_priority": config["priority"],
        })
    return rows


def mechanism_keys(case: dict[str, Any]) -> list[str]:
    values = {
        f"{case['project']}:{relation['relation_kind']}:{target['impact_kind']}"
        for relation in case["relations"]
        for target in case["targets"]
        if relation["target_repository"] == target["repository"]
    }
    return sorted(values)


def repair_template_keys(case: dict[str, Any]) -> list[str]:
    values = set()
    for target in case["targets"]:
        suffixes = sorted({Path(path).suffix or "<no_suffix>" for path in target["changed_paths"]})
        relation_kinds = sorted({
            relation["relation_kind"]
            for relation in case["relations"]
            if relation["target_repository"] == target["repository"]
        })
        values.add(
            f"{case['project']}:{'+'.join(relation_kinds)}:{'+'.join(suffixes)}"
        )
    return sorted(values)


def allocate_proposed_splits(case_counts: dict[str, int], singleton_projects: set[str]) -> dict[str, str]:
    """Greedily assign whole project groups near a 50/25/25 case ratio."""

    assignment = {project: "development" for project in singleton_projects}
    remaining = {
        "development": 50 - sum(case_counts[project] for project in singleton_projects),
        "evaluation": 25,
        "holdout": 25,
    }
    for project, count in sorted(
        ((project, count) for project, count in case_counts.items() if project not in assignment),
        key=lambda item: (-item[1], item[0]),
    ):
        split = max(SPLITS, key=lambda name: (remaining[name], -SPLITS.index(name)))
        assignment[project] = split
        remaining[split] -= count
    return assignment


def build_group_and_split_manifests(
    cases: list[dict[str, Any]],
    catalog_audit: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    audit_by_project = {row["project"]: row for row in catalog_audit}
    case_counts = Counter(case["project"] for case in cases)
    singleton_projects = {
        project for project, count in case_counts.items() if count == 1
    }
    proposed = allocate_proposed_splits(dict(case_counts), singleton_projects)

    group_rows = []
    split_rows = []
    for case in sorted(cases, key=lambda item: item["case_id"]):
        directed_relations = sorted({
            f"{relation['source_repository']} -> {relation['target_repository']}"
            for relation in case["relations"]
        })
        source_family = (
            f"{case['source']['repository']}:"
            f"{case['source']['base_commit']}..{case['source']['candidate_commit']}"
        )
        group_id = f"project:{case['project']}"
        group_rows.append({
            "case_id": case["case_id"],
            "group_id": group_id,
            "project": case["project"],
            "directed_relation_keys": directed_relations,
            "source_commit_family_key": source_family,
            "mechanism_keys": mechanism_keys(case),
            "repair_template_keys": repair_template_keys(case),
            "grouping_policy": "project_connected_component_conservative_v1",
        })
        split_rows.append({
            "case_id": case["case_id"],
            "group_id": group_id,
            "project": case["project"],
            "current_material_split": "development",
            "proposed_split_after_catalog_rebuild": proposed[case["project"]],
            "formal_split_blocked": not audit_by_project[case["project"]]["current_formal_eligible"],
            "blocker": "catalog_provenance" if not audit_by_project[case["project"]]["current_formal_eligible"] else None,
        })

    leakage_fields = (
        "directed_relation_keys",
        "source_commit_family_key",
        "mechanism_keys",
        "repair_template_keys",
    )
    leakage: dict[str, list[dict[str, Any]]] = {field: [] for field in leakage_fields}
    split_by_case = {
        row["case_id"]: row["proposed_split_after_catalog_rebuild"]
        for row in split_rows
    }
    for field in leakage_fields:
        seen: dict[str, set[str]] = defaultdict(set)
        for row in group_rows:
            value = row[field]
            values = value if isinstance(value, list) else [value]
            for key in values:
                seen[key].add(split_by_case[row["case_id"]])
        leakage[field] = [
            {"key": key, "splits": sorted(splits)}
            for key, splits in sorted(seen.items())
            if len(splits) > 1
        ]
    summary = {
        "grouping_policy": "All cases in one project catalog remain in one group.",
        "group_count": len(case_counts),
        "case_count": len(cases),
        "current_material_split_counts": {"development": len(cases)},
        "proposed_split_counts_after_catalog_rebuild": dict(sorted(Counter(
            row["proposed_split_after_catalog_rebuild"] for row in split_rows
        ).items())),
        "project_assignments_after_catalog_rebuild": dict(sorted(proposed.items())),
        "leakage_check": leakage,
        "leakage_free": not any(leakage.values()),
        "formal_split_blocked": any(
            not row["current_formal_eligible"] for row in catalog_audit
        ),
        "formal_split_blocker": (
            "Some project catalogs still lack label-independent provenance."
            if any(not row["current_formal_eligible"] for row in catalog_audit)
            else None
        ),
    }
    return group_rows, split_rows, summary


def cinder_three_arm_summary(dataset_root: Path) -> Path:
    return dataset_root / "results" / "requirements-cinder-active-pilot-2026-08-24" / "summary.json"


def validate_cinder_e2(summary: dict[str, Any]) -> bool:
    arms = summary.get("arms", {})
    return (
        arms.get("a0", {}).get("result") == "pass"
        and arms.get("a1", {}).get("result") == "expected_failure"
        and arms.get("a2", {}).get("result") == "pass"
        and arms.get("a2", {}).get("target_repair") is True
        and arms.get("a1", {}).get("alembic") == arms.get("a2", {}).get("alembic")
        and arms.get("a0", {}).get("target_repair") is False
        and arms.get("a1", {}).get("target_repair") is False
    )


def build_evidence_manifest(
    dataset_root: Path,
    cases: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cinder_path = cinder_three_arm_summary(dataset_root)
    cinder_e2 = cinder_path.exists() and validate_cinder_e2(read_json(cinder_path))
    rows = []
    for case in sorted(cases, key=lambda item: item["case_id"]):
        for target in case["targets"]:
            levels = sorted({item["level"] for item in target["evidence"]})
            relation_kinds = sorted({
                relation["relation_kind"]
                for relation in case["relations"]
                if relation["target_repository"] == target["repository"]
            })
            is_cinder_e2 = (
                cinder_e2
                and case["case_id"] == "opendev-1001023-cinder-impact"
                and target["repository"] == "openstack/cinder"
            )
            layers = ["E1"]
            evidence_paths = [f"cases/{case['case_id']}.json"]
            if is_cinder_e2:
                layers.append("E2")
                evidence_paths.append(str(cinder_path.relative_to(dataset_root)))
            rows.append({
                "record_id": f"{case['case_id']}::{target['repository']}",
                "case_id": case["case_id"],
                "project": case["project"],
                "source_repository": case["source"]["repository"],
                "target_repository": target["repository"],
                "directed_relation_unit": f"{case['source']['repository']} -> {target['repository']}",
                "relation_kinds": relation_kinds,
                "source_evidence_levels": levels,
                "admitted_layers": layers,
                "maximum_admitted_layer": layers[-1],
                "e2_arms": {
                    "a0_old_combination_pass": True,
                    "a1_source_only_failure": True,
                    "a2_exact_target_repair_pass": True,
                } if is_cinder_e2 else None,
                "e3_scope": None,
                "e4_scope": None,
                "evidence_paths": evidence_paths,
                "admission_note": (
                    "Local A0/A1/A2 summary satisfies the strict E2 definition."
                    if is_cinder_e2
                    else "Historical adoption or semantic companion evidence; not promoted to E2 by evidence-level name."
                ),
            })

    summary_paths = []
    for path in sorted((dataset_root / "results").glob("*/summary.json")):
        summary = read_json(path)
        if any(key in summary for key in ("arms", "configurations", "project_package", "consumer_results")):
            summary_paths.append(path)
    return rows, {
        "relation_records": len(rows),
        "independent_relation_units": len({
            row["directed_relation_unit"] for row in rows
        }),
        "admitted_layer_counts": dict(sorted(Counter(
            layer for row in rows for layer in row["admitted_layers"]
        ).items())),
        "maximum_layer_counts": dict(sorted(Counter(
            row["maximum_admitted_layer"] for row in rows
        ).items())),
        "e2_records": sum(row["maximum_admitted_layer"] == "E2" for row in rows),
        "e3_records": 0,
        "e4_records": 0,
        "unreviewed_execution_summary_count": len(summary_paths) - int(cinder_path in summary_paths),
        "unreviewed_execution_summaries": [
            str(path.relative_to(dataset_root))
            for path in summary_paths
            if path != cinder_path
        ],
        "scope_note": "Only the 100-case main material and one machine-checkable strict A0/A1/A2 anchor are admitted. Other execution summaries remain unreviewed rather than being promoted by filename or status text.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-dir", type=Path, default=ROOT)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    dataset_root = args.dataset_dir.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    cases = load_cases(dataset_root)

    catalog_audit = audit_catalogs(dataset_root, cases)
    groups, splits, split_summary = build_group_and_split_manifests(cases, catalog_audit)
    evidence, evidence_summary = build_evidence_manifest(dataset_root, cases)

    write_jsonl(output_dir / "catalog-provenance-audit.jsonl", catalog_audit)
    write_jsonl(output_dir / "group-manifest.jsonl", groups)
    write_jsonl(output_dir / "split-proposal.jsonl", splits)
    write_json(output_dir / "split-summary.json", split_summary)
    write_jsonl(output_dir / "evidence-manifest.jsonl", evidence)
    write_json(output_dir / "evidence-summary.json", evidence_summary)
    eligible_catalogs = [
        row["project"] for row in catalog_audit if row["current_formal_eligible"]
    ]
    development_ready = len(eligible_catalogs) >= 2
    summary = {
        "schema_version": "1.0",
        "experiment_tier": "development_diagnostic",
        "catalogs_audited": len(catalog_audit),
        "current_formal_eligible_catalogs": len(eligible_catalogs),
        "formal_eligible_catalog_names": eligible_catalogs,
        "single_case_catalogs": [
            row["project"] for row in catalog_audit if row["single_case_catalog"]
        ],
        "cases_grouped": len(groups),
        "groups": split_summary["group_count"],
        "proposed_split_leakage_free": split_summary["leakage_free"],
        "evidence_relation_records": len(evidence),
        "strict_e2_records": evidence_summary["e2_records"],
        "decision": (
            "launch_eligible_development_measurement"
            if development_ready else "continue_development_only"
        ),
        "decision_reason": (
            "At least two reusable multi-case catalogs now match recorded independent source snapshots; D4 may start on those development groups while evaluation/holdout remain blocked."
            if development_ready
            else "D1-D3 can run as development diagnostics, but D4 remains blocked until at least two multi-case catalogs are rebuilt from recorded independent rules."
        ),
    }
    write_json(output_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

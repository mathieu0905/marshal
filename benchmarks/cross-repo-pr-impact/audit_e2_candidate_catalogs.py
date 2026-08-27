#!/usr/bin/env python3
"""Audit whether strict-E2 cases have usable candidate-repository catalogs.

This is deliberately an audit, not a catalog constructor.  It only recognizes
catalog membership already present in candidate-repositories.json and provenance
already recorded in candidate-catalog-provenance.json/catalog-source-snapshots.json.
Known E2 targets are read after catalog selection solely to measure coverage.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parent
DEFAULT_E2_INDEX = ROOT / "results" / "final-e2-dataset-50-2026-08-25" / "final-index.jsonl"


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


def source_snapshot_membership(
    config: dict[str, Any], source_snapshots: dict[str, Any]
) -> tuple[str | None, set[str]]:
    reference = config.get("current_source_snapshot")
    if not reference:
        return None, set()
    filename, separator, source_id = reference.partition("#")
    if filename != "catalog-source-snapshots.json" or not separator:
        raise ValueError(f"unsupported source snapshot reference: {reference}")
    try:
        source = source_snapshots["sources"][source_id]
    except KeyError as error:
        raise ValueError(f"missing source snapshot: {reference}") from error
    return reference, set(source["repositories"])


def catalog_facts(
    catalogs: dict[str, Any],
    provenance: dict[str, Any],
    source_snapshots: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    if set(catalogs) != set(provenance["catalogs"]):
        raise ValueError("catalog and provenance project sets differ")
    facts = {}
    for catalog_id, value in sorted(catalogs.items()):
        repositories = set(value["repositories"])
        config = provenance["catalogs"][catalog_id]
        reference, source_membership = source_snapshot_membership(config, source_snapshots)
        facts[catalog_id] = {
            "catalog_id": catalog_id,
            "repositories": repositories,
            "repository_count": len(repositories),
            "source_snapshot": reference,
            "label_independent_membership": bool(reference) and repositories == source_membership,
            "observed_construction": provenance["observed_construction"]["kind"],
        }
    return facts


def audit_cases(
    cases: list[dict[str, Any]],
    facts: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    matched_case_counts = Counter(
        catalog_id
        for case in cases
        for catalog_id, fact in facts.items()
        if case["source_repository"] in fact["repositories"]
    )
    rows = []
    for case in sorted(cases, key=lambda item: item["case_id"]):
        source = case["source_repository"]
        targets = set(case["target_repositories"])
        catalog_reference = case.get("candidate_repository_catalog")
        matches = []
        for catalog_id, fact in facts.items():
            repositories = fact["repositories"]
            if source not in repositories:
                continue
            missing_targets = sorted(targets - repositories)
            non_target_candidates = sorted(repositories - targets - {source})
            reused_case_count = matched_case_counts[catalog_id]
            eligible = (
                fact["label_independent_membership"]
                and not missing_targets
                and bool(non_target_candidates)
                and reused_case_count > 1
            )
            matches.append({
                "catalog_id": catalog_id,
                "catalog_repository_count": fact["repository_count"],
                "catalog_reused_e2_case_count": reused_case_count,
                "source_snapshot": fact["source_snapshot"],
                "label_independent_membership": fact["label_independent_membership"],
                "target_coverage": not missing_targets,
                "missing_targets": missing_targets,
                "non_target_candidate_count": len(non_target_candidates),
                "formal_eligible": eligible,
            })

        selected_catalog_id = None
        malformed_reference = False
        if catalog_reference:
            filename, separator, selected_catalog_id = catalog_reference.partition("#")
            malformed_reference = (
                filename != "candidate-repositories.json"
                or not separator
                or selected_catalog_id not in facts
            )
        selected_match = next(
            (match for match in matches if match["catalog_id"] == selected_catalog_id),
            None,
        )

        if not catalog_reference:
            disposition = "missing_catalog_reference"
            blocker = "e2_case_does_not_reference_a_candidate_catalog"
        elif malformed_reference:
            disposition = "invalid_catalog_reference"
            blocker = "candidate_catalog_reference_is_not_resolvable"
        elif selected_match is None:
            disposition = "referenced_catalog_source_mismatch"
            blocker = "source_repository_is_not_in_referenced_catalog"
        elif selected_match["formal_eligible"]:
            disposition = "formally_eligible"
            blocker = None
        elif selected_match["label_independent_membership"]:
            disposition = "independent_catalog_missing_target"
            blocker = "existing_independent_catalog_does_not_cover_e2_target"
        else:
            disposition = "catalog_rebuild_required"
            blocker = "matched_catalog_membership_is_not_label_independent"

        rows.append({
            "case_id": case["case_id"],
            "source_change_family": case["source_change_family"],
            "source_repository": source,
            "target_repositories": sorted(targets),
            "candidate_repository_catalog": catalog_reference,
            "potential_catalogs_by_source_membership": matches,
            "selected_catalog_assessment": selected_match,
            "disposition": disposition,
            "formal_input_eligible": disposition == "formally_eligible",
            "blocker": blocker,
            "label_use_boundary": (
                "Catalog matching uses only source-repository membership; hidden E2 targets "
                "are read afterward only for coverage measurement."
            ),
        })
    return rows


def build_summary(
    cases: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    facts: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    dispositions = Counter(row["disposition"] for row in rows)
    matched_catalogs = sorted({
        match["catalog_id"]
        for row in rows
        for match in row["potential_catalogs_by_source_membership"]
    })
    potential_match_cases = sum(
        bool(row["potential_catalogs_by_source_membership"]) for row in rows
    )
    eligible = [row["case_id"] for row in rows if row["formal_input_eligible"]]
    return {
        "schema_version": "1.0",
        "audit_scope": "strict_e2_50_candidate_catalog_provenance",
        "case_count": len(cases),
        "source_repository_count": len({case["source_repository"] for case in cases}),
        "source_change_family_count": len({case["source_change_family"] for case in cases}),
        "target_repository_occurrence_count": sum(len(case["target_repositories"]) for case in cases),
        "available_catalog_count": len(facts),
        "potential_catalog_ids_by_source_membership": matched_catalogs,
        "case_count_with_potential_source_membership_match": potential_match_cases,
        "disposition_counts": dict(sorted(dispositions.items())),
        "formal_input_eligible_case_count": len(eligible),
        "formal_input_eligible_case_ids": eligible,
        "all_cases_audited": len(rows) == len(cases),
        "inputs_materialization_ready": len(eligible) == len(cases),
        "next_action": (
            "Construct label-independent candidate catalogs before running prepare_case_inputs.py."
            if len(eligible) != len(cases)
            else "Proceed to cutoff-time snapshot collection and input materialization."
        ),
        "interpretation": [
            "An E2 target is not admitted into a catalog merely because it is a verified positive.",
            "Non-target catalog members remain unjudged.",
            "No formal score is supported until catalog provenance, target coverage, reuse, and cutoff snapshots all pass.",
        ],
    }


def render_summary(summary: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    counts = summary["disposition_counts"]
    lines = [
        "# E2 candidate-catalog provenance audit",
        "",
        "## Result",
        "",
        f"- Audited cases: {summary['case_count']}/{summary['case_count']}",
        f"- Formal-input eligible now: {summary['formal_input_eligible_case_count']}/{summary['case_count']}",
        f"- Cases with no catalog reference: {counts.get('missing_catalog_reference', 0)}",
        f"- Cases with a potential existing catalog found by source membership only: {summary['case_count_with_potential_source_membership_match']}",
        "",
        "The audit discovers potential existing-catalog leads using source-repository membership before reading E2 targets. "
        "These leads are not assignments. Targets are read afterward only to measure whether a lead would cover the known positive.",
        "",
        "## Existing-catalog findings",
        "",
    ]
    for row in rows:
        if not row["potential_catalogs_by_source_membership"]:
            continue
        match_text = ", ".join(
            f"{match['catalog_id']} (independent={str(match['label_independent_membership']).lower()}, "
            f"target_coverage={str(match['target_coverage']).lower()})"
            for match in row["potential_catalogs_by_source_membership"]
        )
        lines.append(f"- `{row['case_id']}`: {match_text}")
    lines.extend([
        "",
        "## Boundary",
        "",
        "Source-membership matches are diagnostic leads, not catalog assignments; an unrelated catalog can contain "
        "the same source repository. This result does not invalidate the 50 E2 causal labels. It shows that none of the 50 can yet be "
        "assembled as a formal candidate-bounded system input from the catalogs currently recorded in this repository. "
        "Do not run `prepare_case_inputs.py` for this set yet.",
        "",
    ])
    return "\n".join(lines)


def run(dataset_root: Path, e2_index: Path, output_dir: Path) -> dict[str, Any]:
    cases = read_jsonl(e2_index)
    if len(cases) != 50 or len({case["case_id"] for case in cases}) != 50:
        raise ValueError("expected exactly 50 unique E2 cases")
    catalogs = read_json(dataset_root / "candidate-repositories.json")["catalogs"]
    provenance = read_json(dataset_root / "candidate-catalog-provenance.json")
    source_snapshots = read_json(dataset_root / "catalog-source-snapshots.json")
    facts = catalog_facts(catalogs, provenance, source_snapshots)
    rows = audit_cases(cases, facts)
    summary = build_summary(cases, rows, facts)

    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_dir / "case-audit.jsonl", rows)
    write_json(output_dir / "metrics.json", summary)
    (output_dir / "SUMMARY.md").write_text(
        render_summary(summary, rows), encoding="utf-8"
    )
    write_json(output_dir / "run-manifest.json", {
        "schema_version": "1.0",
        "inputs": [
            str(e2_index.relative_to(dataset_root)),
            "candidate-repositories.json",
            "candidate-catalog-provenance.json",
            "catalog-source-snapshots.json",
        ],
        "outputs": ["case-audit.jsonl", "metrics.json", "SUMMARY.md"],
        "membership_selection_reads_e2_targets": False,
        "targets_read_after_selection_for_coverage_audit": True,
        "network_used": False,
    })
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-dir", type=Path, default=ROOT)
    parser.add_argument("--e2-index", type=Path, default=DEFAULT_E2_INDEX)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    summary = run(
        args.dataset_dir.resolve(), args.e2_index.resolve(), args.output_dir.resolve()
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Resolve the remaining opening-state E2 candidate-catalog leads."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

from audit_e2_candidate_catalogs import catalog_facts


ROOT = Path(__file__).resolve().parent
E2_INDEX = ROOT / "results/final-e2-dataset-50-2026-08-25/final-index.jsonl"
CATALOG_BUILD = ROOT / "results/e2-candidate-catalog-build-2026-08-25"
ECOSYSTEM_AUDIT = ROOT / "results/e2-ecosystem-catalog-audit-2026-08-26"
MOCKITO_AUDIT = ROOT / "results/e2-mockito-ecosystem-catalog-audit-2026-08-26"
RUST_EXPERIMENTS = {
    "e2-043": ("pr-155193", "540f43a224317d894a9a0710a8d67704f179a33c", "spectest-0.1.2"),
    "e2-044": ("pr-154992", "1fe72d35998dea48aeecaf7fc07783b0b553f24f", "git-url-parse-0.6.0"),
    "e2-045": ("pr-156776", "b52edc25bfbaa955b4b83c10f998e5224c3478b2", "id3-1.16.4"),
    "e2-046": ("pr-156776", "b52edc25bfbaa955b4b83c10f998e5224c3478b2", "bevy_ios_app_delegate-0.4.0"),
}
CASE_IDS = ("e2-026", "e2-043", "e2-044", "e2-045", "e2-046", "e2-049")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "marshal-e2-opening-catalog-audit"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read().decode("utf-8")


def head_status(url: str) -> int:
    request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "marshal-e2-opening-catalog-audit"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code


def crates_tested(downloads_html: str) -> int:
    match = re.search(r'<div class="count">(\d+) crates tested</div>', downloads_html)
    if not match:
        raise ValueError("Crater downloads page lacks the tested-crate count")
    return int(match.group(1))


def crater_log_url(experiment: str, baseline: str, kind: str, key: str) -> str:
    return (
        f"https://crater-reports.s3.amazonaws.com/{experiment}/"
        f"master%23{baseline}/{kind}/{key}/log.txt"
    )


def run(
    output_dir: Path,
    e2_index: Path = E2_INDEX,
    catalog_build: Path = CATALOG_BUILD,
    ecosystem_audit: Path = ECOSYSTEM_AUDIT,
    mockito_audit: Path = MOCKITO_AUDIT,
    text_fetcher: Callable[[str], str] = fetch_text,
    status_fetcher: Callable[[str], int] = head_status,
) -> dict[str, Any]:
    cases = {row["case_id"]: row for row in read_jsonl(e2_index)}
    assignments = {row["case_id"]: row for row in read_jsonl(catalog_build / "case-catalog-assignments.jsonl")}
    built_catalogs = read_json(catalog_build / "candidate-repositories.json")["catalogs"]
    broad_coverage = {row["case_id"]: row for row in read_jsonl(ecosystem_audit / "coverage-audit.jsonl")}
    mockito_coverage = {row["case_id"]: row for row in read_jsonl(mockito_audit / "coverage-audit.jsonl")}
    mockito_catalog = next(iter(read_json(mockito_audit / "candidate-repositories.json")["catalogs"].values()))
    legacy_facts = catalog_facts(
        read_json(ROOT / "candidate-repositories.json")["catalogs"],
        read_json(ROOT / "candidate-catalog-provenance.json"),
        read_json(ROOT / "catalog-source-snapshots.json"),
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    sources = output_dir / "sources"
    sources.mkdir(exist_ok=True)
    experiment_pages: dict[str, str] = {}
    for experiment in sorted({value[0] for value in RUST_EXPERIMENTS.values()}):
        url = f"https://crater-reports.s3.amazonaws.com/{experiment}/downloads.html"
        page = text_fetcher(url)
        experiment_pages[experiment] = page
        (sources / f"{experiment}-downloads.html").write_text(page, encoding="utf-8")

    rows: list[dict[str, Any]] = []
    for case_id in CASE_IDS:
        case = cases[case_id]
        assignment = assignments[case_id]
        catalog_id = assignment["candidate_repository_catalog"].split("#", 1)[1]
        current_catalog = built_catalogs[catalog_id]
        base = {
            "case_id": case_id,
            "source_repository": case["source_repository"],
            "target_repositories": case["target_repositories"],
            "current_catalog_id": catalog_id,
            "current_catalog_outcome_conditioned": current_catalog.get("source_selection_is_outcome_conditioned") is True,
            "opening_cutoff_conformant": assignment["input_spec_opening_cutoff_conformant"],
            "formal_catalog_eligible": False,
        }
        if case_id == "e2-026":
            complete = mockito_catalog["complete_query_audit"]
            rows.append({
                **base,
                "independent_lead": "complete Mockito reverse-dependent package catalog",
                "independent_candidate_repository_count": len(mockito_catalog["repositories"]),
                "independent_package_row_count": complete["returned_dependent_package_count"],
                "independent_query_complete": complete["complete_query_verified"],
                "missing_targets": mockito_coverage[case_id]["missing_targets"],
                "exclusion_reason": "The complete label-independent Mockito reverse-dependent package catalog does not map the E2 target repository, so adding it would read the label.",
                "next_legitimate_path": "Use a reusable project-governance or build-orchestration directory that independently contains junit-quickcheck and non-target repositories.",
            })
        elif case_id in RUST_EXPERIMENTS:
            experiment, baseline, subject = RUST_EXPERIMENTS[case_id]
            target = case["target_repositories"][0]
            target_key = target.replace("/", ".")
            target_status = status_fetcher(crater_log_url(experiment, baseline, "gh", target_key))
            subject_status = status_fetcher(crater_log_url(experiment, baseline, "reg", subject))
            rust_fact = legacy_facts["rust"]
            rows.append({
                **base,
                "independent_lead": "complete Crater experiment input universe",
                "crater_experiment": experiment,
                "crater_tested_unit_count": crates_tested(experiment_pages[experiment]),
                "execution_subject": subject,
                "execution_subject_registry_log_status": subject_status,
                "target_top_level_repository_log_status": target_status,
                "target_is_top_level_crater_repository": target_status == 200,
                "existing_rust_catalog_repository_count": rust_fact["repository_count"],
                "existing_rust_catalog_label_independent": rust_fact["label_independent_membership"],
                "missing_targets": [target] if target not in rust_fact["repositories"] else [],
                "exclusion_reason": "The label-independent Rust directory misses the target, while the full Crater run identifies the registry execution subject but not the E2 target as a top-level repository candidate. Regression-only report rows would be outcome-conditioned.",
                "next_legitimate_path": "Map every unit in the complete Crater input universe to repository provenance and opening-time code, including transitive repaired components, before reading target coverage.",
            })
        else:
            coverage = broad_coverage[case_id]
            rows.append({
                **base,
                "independent_lead": "shared Maven dependent-package slice catalog",
                "independent_candidate_repository_count": coverage["catalog_repository_count"],
                "missing_targets": coverage["missing_targets"],
                "exclusion_reason": "The shared label-independent Maven catalog misses byte-buddy; an ASM-only reverse-dependent catalog would be assigned to one E2 case and fails the cross-case reuse requirement.",
                "next_legitimate_path": "Construct a reusable Maven-wide or build-orchestration catalog covering multiple source cases without reading target labels.",
            })

    write_jsonl(output_dir / "case-audit.jsonl", rows)
    metrics = {
        "schema_version": "1.0",
        "case_count": len(rows),
        "case_ids": list(CASE_IDS),
        "formal_catalog_eligible_case_count": sum(row["formal_catalog_eligible"] for row in rows),
        "all_cases_resolved": len(rows) == len(CASE_IDS),
        "network_used": True,
        "labels_read_only_for_post_construction_coverage": True,
        "generated_at": dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z"),
    }
    write_json(output_dir / "metrics.json", metrics)
    write_json(output_dir / "run-manifest.json", {
        "official_sources": sorted(
            f"https://crater-reports.s3.amazonaws.com/{experiment}/downloads.html"
            for experiment in experiment_pages
        ),
        "mockito_audit": str(mockito_audit),
        "ecosystem_audit": str(ecosystem_audit),
        "catalog_build": str(catalog_build),
    })
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.output_dir.resolve()), indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

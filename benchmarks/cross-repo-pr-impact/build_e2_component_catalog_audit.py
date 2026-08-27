#!/usr/bin/env python3
"""Build a fixed, label-independent reverse-dependent catalog for one component."""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import json
from pathlib import Path
from typing import Any
import urllib.parse

from build_e2_ecosystem_catalog_audit import (
    API_ROOT,
    QUERY_SLICES,
    compact_query_snapshot,
    fetch_json,
    fetch_rows,
    github_repository,
    query_url,
    read_jsonl,
    write_json,
    write_jsonl,
)


ROOT = Path(__file__).resolve().parent
E2_INDEX = ROOT / "results/final-e2-dataset-50-2026-08-25/final-index.jsonl"
COMPONENTS = {
    "mockito": {
        "ecosystem": "maven",
        "registry": "repo1.maven.org",
        "package": "org.mockito:mockito-core",
        "case_ids": ["e2-025", "e2-026"],
    },
}


def component_metadata_url(definition: dict[str, Any]) -> str:
    package = urllib.parse.quote(definition["package"], safe="")
    return f"{API_ROOT}/registries/{definition['registry']}/packages/{package}"


def compact_component_metadata(value: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "id",
        "name",
        "ecosystem",
        "registry_url",
        "dependent_packages_count",
        "dependent_repos_count",
        "updated_at",
        "last_synced_at",
    )
    return {key: value[key] for key in fields if key in value}


def paged_query_url(
    definition: dict[str, Any], sort: str, order: str, page_size: int, page: int
) -> str:
    base_url = query_url(
        definition["registry"], definition["package"], sort, order, page_size
    )
    parsed = urllib.parse.urlsplit(base_url)
    query = dict(urllib.parse.parse_qsl(parsed.query))
    query["page"] = str(page)
    return urllib.parse.urlunsplit(
        (*parsed[:3], urllib.parse.urlencode(query), parsed.fragment)
    )


def construct(
    definition: dict[str, Any],
    item_cap: int,
    page_size: int,
    workers: int,
    fetcher=fetch_rows,
) -> tuple[list[str], list[dict[str, Any]]]:
    jobs = []
    page_count = (item_cap + page_size - 1) // page_size
    for sort, order in QUERY_SLICES:
        for page in range(1, page_count + 1):
            jobs.append({
                "ecosystem": definition["ecosystem"],
                "registry": definition["registry"],
                "package": definition["package"],
                "sort": sort,
                "order": order,
                "page": page,
                "per_page": page_size,
                "take": min(page_size, item_cap - (page - 1) * page_size),
                "url": paged_query_url(
                    definition, sort, order, page_size, page
                ),
            })

    def run(job: dict[str, Any]) -> dict[str, Any]:
        try:
            rows = fetcher(job["url"])[0:job["take"]]
            effective_url = job["url"]
            fallback = False
            historical_error = None
        except Exception as error:
            historical_error = f"{type(error).__name__}: {error}"
            effective_url = job["url"].replace("latest=false", "latest=true")
            fallback = True
            try:
                rows = fetcher(effective_url)[0:job["take"]]
            except Exception as fallback_error:
                return {
                    **job,
                    "effective_url": effective_url,
                    "latest_only_fallback": True,
                    "historical_query_error": historical_error,
                    "rows": [],
                    "repositories": [],
                    "error": f"{type(fallback_error).__name__}: {fallback_error}",
                }
        return compact_query_snapshot({
            **job,
            "effective_url": effective_url,
            "latest_only_fallback": fallback,
            **({"historical_query_error": historical_error} if historical_error else {}),
            "rows": rows,
            "repositories": sorted({
                repository
                for row in rows
                if (repository := github_repository(row.get("repository_url")))
            }),
        })

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        snapshots = list(executor.map(run, jobs))
    repositories = sorted({
        repository for snapshot in snapshots for repository in snapshot["repositories"]
    })
    return repositories, snapshots


def construct_complete(
    definition: dict[str, Any],
    page_size: int,
    workers: int,
    package_metadata: dict[str, Any],
    fetcher=fetch_rows,
    cached_snapshots: list[dict[str, Any]] | None = None,
    extra_pages: int = 100,
) -> tuple[list[str], list[dict[str, Any]], dict[str, Any]]:
    expected_count = package_metadata.get("dependent_packages_count")
    if not isinstance(expected_count, int) or expected_count < 0:
        raise ValueError("package metadata lacks a valid dependent_packages_count")
    metadata_page_count = (expected_count + page_size - 1) // page_size
    page_count = metadata_page_count + extra_pages
    jobs = [{
        "ecosystem": definition["ecosystem"],
        "registry": definition["registry"],
        "package": definition["package"],
        "sort": "name",
        "order": "asc",
        "page": page,
        "per_page": page_size,
        "url": paged_query_url(definition, "name", "asc", page_size, page),
    } for page in range(1, page_count + 1)]
    cache = {
        snapshot["url"]: snapshot
        for snapshot in (cached_snapshots or [])
        if not snapshot.get("error")
    }

    def run(job: dict[str, Any]) -> dict[str, Any]:
        if job["url"] in cache:
            return cache[job["url"]]
        try:
            rows = fetcher(job["url"])
        except Exception as error:
            return {
                **job,
                "effective_url": job["url"],
                "latest_only_fallback": False,
                "rows": [],
                "repositories": [],
                "error": f"{type(error).__name__}: {error}",
            }
        return compact_query_snapshot({
            **job,
            "effective_url": job["url"],
            "latest_only_fallback": False,
            "rows": rows,
            "repositories": sorted({
                repository
                for row in rows
                if (repository := github_repository(row.get("repository_url")))
            }),
        })

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        snapshots = list(executor.map(run, jobs))
    failures = [snapshot for snapshot in snapshots if snapshot.get("error")]
    empty_pages = [
        snapshot["page"]
        for snapshot in snapshots
        if not snapshot.get("error") and not snapshot.get("rows")
    ]
    first_empty_page = min(empty_pages) if empty_pages else None
    terminal_empty_verified = (
        first_empty_page is not None
        and all(
            not snapshot.get("rows")
            for snapshot in snapshots
            if snapshot["page"] >= first_empty_page
        )
    )
    membership_snapshots = [
        snapshot for snapshot in snapshots
        if first_empty_page is None or snapshot["page"] < first_empty_page
    ]
    rows = [
        row for snapshot in membership_snapshots for row in snapshot.get("rows", [])
    ]
    ids = [row.get("id") for row in rows]
    unique_ids = {value for value in ids if value is not None}
    returned_count = len(rows)
    completeness = {
        "expected_dependent_package_count": expected_count,
        "metadata_page_count": metadata_page_count,
        "returned_dependent_package_count": returned_count,
        "unique_dependent_package_id_count": len(unique_ids),
        "missing_id_count": sum(value is None for value in ids),
        "page_count": page_count,
        "first_empty_page": first_empty_page,
        "terminal_empty_verified": terminal_empty_verified,
        "page_size": page_size,
        "query_failure_count": len(failures),
        "complete_query_verified": (
            not failures
            and terminal_empty_verified
            and len(unique_ids) == returned_count
            and not any(value is None for value in ids)
        ),
    }
    repositories = sorted({
        repository
        for snapshot in membership_snapshots
        for repository in snapshot["repositories"]
    })
    return repositories, snapshots, completeness


def audit(
    component: str,
    repositories: list[str],
    cases: list[dict[str, Any]],
    identifier: str,
) -> list[dict[str, Any]]:
    definition = COMPONENTS[component]
    by_id = {case["case_id"]: case for case in cases}
    normalized = {repository.lower() for repository in repositories}
    rows = []
    for case_id in definition["case_ids"]:
        case = by_id[case_id]
        targets = sorted(case["target_repositories"])
        missing = [target for target in targets if target.lower() not in normalized]
        rows.append({
            "case_id": case_id,
            "catalog_id": identifier,
            "ecosystem": definition["ecosystem"],
            "source_package": definition["package"],
            "source_repository": case["source_repository"],
            "target_repositories": targets,
            "targets_covered": not missing,
            "missing_targets": missing,
            "catalog_repository_count": len(repositories),
            "non_target_candidate_count": len(repositories) - len(targets) + len(missing),
            "labels_read_after_membership_construction": True,
        })
    return rows


def run(
    component: str,
    query_mode: str,
    item_cap: int,
    page_size: int,
    workers: int,
    output_dir: Path,
    e2_index: Path,
    fetcher=fetch_rows,
    metadata_fetcher=fetch_json,
    complete_extra_pages: int = 100,
) -> dict[str, Any]:
    definition = COMPONENTS[component]
    package_metadata = None
    completeness = None
    if query_mode == "complete":
        raw_package_metadata = metadata_fetcher(component_metadata_url(definition))
        if not isinstance(raw_package_metadata, dict):
            raise ValueError("component package endpoint did not return an object")
        package_metadata = compact_component_metadata(raw_package_metadata)
        cache_path = output_dir / "sources/dependent-package-query-snapshots.jsonl"
        cached_snapshots = read_jsonl(cache_path) if cache_path.exists() else []
        repositories, snapshots, completeness = construct_complete(
            definition,
            page_size,
            workers,
            package_metadata,
            fetcher,
            cached_snapshots,
            complete_extra_pages,
        )
        identifier = (
            f"ecosystems-{definition['ecosystem']}-{component}-complete-"
            "dependent-packages-2026-08-26"
        )
    else:
        repositories, snapshots = construct(
            definition, item_cap, page_size, workers, fetcher
        )
        identifier = (
            f"ecosystems-{definition['ecosystem']}-{component}-dependent-slices-"
            f"{item_cap}-2026-08-26"
        )
    fetched_at = dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z")
    cases = read_jsonl(e2_index)
    coverage = audit(component, repositories, cases, identifier)
    failures = [snapshot for snapshot in snapshots if snapshot.get("error")]
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "sources").mkdir(exist_ok=True)
    if package_metadata is not None:
        write_json(output_dir / "sources/component-package-metadata.json", package_metadata)
    write_jsonl(
        output_dir / "sources/dependent-package-query-snapshots.jsonl",
        (compact_query_snapshot(snapshot) for snapshot in snapshots),
    )
    construction_complete = (
        completeness["complete_query_verified"] if completeness is not None else True
    )
    if query_mode == "complete":
        selection_rule = (
            "All historical dependent packages returned by the Ecosyste.ms "
            f"{definition['package']} reverse-dependency endpoint, paginated in "
            "lexical name order. The expected row count is read from the source "
            "package metadata before E2 target labels are loaded. Only GitHub "
            "repositories declared in those package records become candidates."
        )
        membership_kind = "ecosystem_component_complete_reverse_dependencies"
        query_description = [{
            "sort": "name",
            "order": "asc",
            "page_size": page_size,
            "page_count": completeness["page_count"],
            "expected_row_count": completeness["expected_dependent_package_count"],
            "terminal_empty_page": completeness["first_empty_page"],
        }]
    else:
        selection_rule = (
            f"Union of GitHub repositories returned by the first {item_cap} "
            "historical dependent packages in each fixed stars, dependent-repository, "
            "downloads, oldest-creation, oldest-release, and lexical-name slice for "
            f"{definition['package']}. The two cases sharing that visible source "
            "component are selected before target coverage is read."
        )
        membership_kind = "ecosystem_component_reverse_dependency_slices"
        query_description = [
            {
                "sort": sort,
                "order": order,
                "item_cap": item_cap,
                "page_size": page_size,
                "page_count": (item_cap + page_size - 1) // page_size,
            }
            for sort, order in QUERY_SLICES
        ]
    catalog = {
        "catalog_id": identifier,
        "schema_version": "1.0",
        "catalog_status": (
            "label_independent_reusable_coverage_audit"
            if not failures and construction_complete
            else "incomplete_external_query_coverage_audit"
        ),
        "selection_rule": selection_rule,
        "membership_source": {
            "kind": membership_kind,
            "service": "packages.ecosyste.ms",
            "license": "CC-BY-SA-4.0",
            "api_root": API_ROOT,
            "registry": definition["registry"],
            "ecosystem": definition["ecosystem"],
            "catalog_cutoff": fetched_at,
            "snapshot": "sources/dependent-package-query-snapshots.jsonl",
            **({"package_metadata_snapshot": "sources/component-package-metadata.json"}
               if package_metadata is not None else {}),
            "source_packages": [definition["package"]],
            "queries": query_description,
        },
        "membership_reads_e2_targets": False,
        "source_selection_is_outcome_conditioned": False,
        "query_failure_count": len(failures),
        **({"complete_query_audit": completeness} if completeness is not None else {}),
        "repository_host": "github.com",
        "repositories": repositories,
    }
    write_json(output_dir / "candidate-repositories.json", {
        "schema_version": "1.0",
        "catalogs": {identifier: catalog},
    })
    write_jsonl(output_dir / "coverage-audit.jsonl", coverage)
    metrics = {
        "schema_version": "1.0",
        "component": component,
        "query_mode": query_mode,
        "case_count": len(coverage),
        "repository_count": len(repositories),
        "target_covered_case_count": sum(row["targets_covered"] for row in coverage),
        "query_count": len(snapshots),
        "query_failure_count": len(failures),
        "complete_query_verified": construction_complete,
        "item_cap_per_slice": item_cap,
        "page_size": page_size,
        "labels_read_only_after_membership_construction": True,
        "network_used": True,
    }
    write_json(output_dir / "metrics.json", metrics)
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--component", choices=sorted(COMPONENTS), required=True)
    parser.add_argument("--query-mode", choices=("slices", "complete"), default="slices")
    parser.add_argument("--item-cap", type=int, default=1000)
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--complete-extra-pages", type=int, default=100)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--e2-index", type=Path, default=E2_INDEX)
    args = parser.parse_args()
    if args.item_cap < 1:
        raise SystemExit("--item-cap must be positive")
    if args.page_size < 1 or args.page_size > 1000:
        raise SystemExit("--page-size must be between 1 and 1000")
    if args.complete_extra_pages < 1:
        raise SystemExit("--complete-extra-pages must be positive")
    metrics = run(
        args.component,
        args.query_mode,
        args.item_cap,
        args.page_size,
        args.workers,
        args.output_dir.resolve(),
        args.e2_index.resolve(),
        complete_extra_pages=args.complete_extra_pages,
    )
    print(json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if (
        metrics["query_failure_count"] == 0 and metrics["complete_query_verified"]
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())

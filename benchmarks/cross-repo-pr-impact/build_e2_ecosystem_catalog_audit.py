#!/usr/bin/env python3
"""Build outcome-independent ecosystem candidate catalogs for strict-E2 cases.

Membership is constructed only from the evaluated source package coordinates and
fixed Ecosyste.ms dependent-package queries.  E2 target labels are loaded after
both ecosystem unions are complete and are used only for coverage auditing.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import gzip
import http.client
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parent
E2_INDEX = ROOT / "results" / "final-e2-dataset-50-2026-08-25" / "final-index.jsonl"
API_ROOT = "https://packages.ecosyste.ms/api/v1"
QUERY_SLICES = (
    ("stargazers_count", "desc"),
    ("dependent_repos_count", "desc"),
    ("downloads", "desc"),
    ("created_at", "asc"),
    ("latest_release_published_at", "asc"),
    ("name", "asc"),
)
REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")

# Coordinates describe source changes, not hidden target repositories.  Multiple
# coordinates are allowed where a source change spans a component family.
SOURCE_COMPONENTS: dict[str, dict[str, Any]] = {
    "npm": {
        "registry": "npmjs.org",
        "components": {
            "escope": ["e2-007"],
            "window-stream": ["e2-008"],
            "terser": ["e2-009", "e2-010"],
            "react-redux": ["e2-028"],
            "babel-preset-es2015": ["e2-029"],
            "imagemin-optipng": ["e2-030"],
            "eslint": ["e2-031"],
            "backbone": ["e2-032"],
            "socket.io": ["e2-033"],
        },
    },
    "maven": {
        "registry": "repo1.maven.org",
        "components": {
            "org.slf4j:slf4j-api": ["e2-004", "e2-005"],
            "org.yaml:snakeyaml": ["e2-011", "e2-012"],
            "org.codehaus.plexus:plexus-utils": ["e2-013", "e2-014"],
            "com.fasterxml.jackson.core:jackson-databind": ["e2-015", "e2-016"],
            "org.apache.logging.log4j:log4j-core": ["e2-017", "e2-039"],
            "org.assertj:assertj-core": ["e2-020"],
            "commons-io:commons-io": ["e2-021", "e2-022"],
            "com.puppycrawl.tools:checkstyle": ["e2-023", "e2-024"],
            "org.mockito:mockito-core": ["e2-025", "e2-026"],
            "ch.qos.logback:logback-classic": ["e2-027"],
            "com.h2database:h2": ["e2-034", "e2-035", "e2-036", "e2-037", "e2-038"],
            "org.apache.derby:derby": ["e2-040"],
            "io.swagger.core.v3:swagger-models": ["e2-041"],
            "com.fasterxml.jackson.core:jackson-core": ["e2-042"],
            "com.fasterxml.jackson.dataformat:jackson-dataformat-yaml": ["e2-047"],
            "com.neovisionaries:nv-i18n": ["e2-048"],
            "org.ow2.asm:asm": ["e2-049"],
            "io.micrometer:micrometer-core": ["e2-050"],
        },
    },
}


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


def compact_query_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    package_fields = (
        "id",
        "name",
        "ecosystem",
        "repository_url",
        "created_at",
        "latest_release_published_at",
        "downloads",
        "dependent_repos_count",
        "stargazers_count",
    )
    return {
        **{key: value for key, value in snapshot.items() if key != "rows"},
        "rows": [
            {key: row.get(key) for key in package_fields if row.get(key) is not None}
            for row in snapshot.get("rows", [])
        ],
    }


def github_repository(url: str | None) -> str | None:
    if not url:
        return None
    value = url.strip()
    for prefix in ("git+", "git://"):
        if value.startswith(prefix):
            value = value[len(prefix):]
    value = re.sub(r"^git@github\.com:", "https://github.com/", value)
    value = re.sub(r"^ssh://git@github\.com/", "https://github.com/", value)
    parsed = urllib.parse.urlparse(value)
    if parsed.hostname is None or parsed.hostname.lower() != "github.com":
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        return None
    repository = f"{parts[0]}/{parts[1]}"
    if repository.endswith(".git"):
        repository = repository[:-4]
    return repository if REPOSITORY.fullmatch(repository) else None


def query_url(
    registry: str,
    package: str,
    sort: str,
    order: str,
    per_slice: int,
) -> str:
    package_name = urllib.parse.quote(package, safe="")
    query = urllib.parse.urlencode({
        "latest": "false",
        "sort": sort,
        "order": order,
        "per_page": per_slice,
        "page": 1,
    })
    return (
        f"{API_ROOT}/registries/{registry}/packages/{package_name}"
        f"/dependent_packages?{query}"
    )


def fetch_json(url: str) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "User-Agent": "marshal-e2-ecosystem-catalog-audit",
        },
    )
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                if response.headers.get("Content-Encoding", "").lower() == "gzip":
                    rows = json.loads(gzip.decompress(response.read()))
                else:
                    rows = json.load(response)
            break
        except (
            urllib.error.URLError,
            TimeoutError,
            http.client.IncompleteRead,
            EOFError,
            gzip.BadGzipFile,
        ):
            if attempt == 3:
                raise
            time.sleep(attempt + 1)
    return rows


def fetch_rows(url: str) -> list[dict[str, Any]]:
    rows = fetch_json(url)
    if not isinstance(rows, list):
        raise ValueError(f"dependent-package endpoint did not return a list: {url}")
    return rows


def construct_membership(
    per_slice: int,
    workers: int,
    fetcher=fetch_rows,
    cached_snapshots: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, list[str]], list[dict[str, Any]]]:
    jobs = []
    for ecosystem, definition in SOURCE_COMPONENTS.items():
        for package in definition["components"]:
            for sort, order in QUERY_SLICES:
                jobs.append({
                    "ecosystem": ecosystem,
                    "registry": definition["registry"],
                    "package": package,
                    "sort": sort,
                    "order": order,
                    "url": query_url(
                        definition["registry"], package, sort, order, per_slice
                    ),
                })

    cache = {
        snapshot["url"]: snapshot
        for snapshot in (cached_snapshots or [])
    }

    def run(job: dict[str, Any]) -> dict[str, Any]:
        if job["url"] in cache:
            return cache[job["url"]]
        try:
            rows = fetcher(job["url"])
            effective_url = job["url"]
            fallback = False
            historical_error = None
        except Exception as historical_error_value:
            historical_error = (
                f"{type(historical_error_value).__name__}: {historical_error_value}"
            )
            effective_url = job["url"].replace("latest=false", "latest=true")
            fallback = True
            try:
                rows = fetcher(effective_url)
            except Exception as error:
                return {
                    **job,
                    "effective_url": effective_url,
                    "latest_only_fallback": True,
                    "historical_query_error": historical_error,
                    "rows": [],
                    "repositories": [],
                    "error": f"{type(error).__name__}: {error}",
                }
        return {
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
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        snapshots = list(executor.map(run, jobs))
    membership = {
        ecosystem: sorted({
            repository
            for snapshot in snapshots
            if snapshot["ecosystem"] == ecosystem
            for repository in snapshot["repositories"]
        })
        for ecosystem in SOURCE_COMPONENTS
    }
    return membership, snapshots


def audit_coverage(
    membership: dict[str, list[str]], cases: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    rows = []
    for ecosystem, repositories in membership.items():
        identifier = f"ecosystems-{ecosystem}-dependent-package-slices-2026-08-26"
        rows.extend(audit_catalog_coverage(
            repositories,
            cases,
            ecosystem,
            identifier,
            set(SOURCE_COMPONENTS[ecosystem]["components"]),
        ))
    return rows


def audit_catalog_coverage(
    repositories: list[str],
    cases: list[dict[str, Any]],
    ecosystem: str,
    catalog_id: str,
    included_packages: set[str],
) -> list[dict[str, Any]]:
    case_to_package = {
        case_id: package
        for package, case_ids in SOURCE_COMPONENTS[ecosystem]["components"].items()
        if package in included_packages
        for case_id in case_ids
    }
    by_id = {case["case_id"]: case for case in cases}
    rows = []
    for case_id, package in sorted(case_to_package.items()):
        case = by_id[case_id]
        normalized_membership = {repository.lower() for repository in repositories}
        targets = sorted(case["target_repositories"])
        missing = [
            target for target in targets if target.lower() not in normalized_membership
        ]
        rows.append({
            "case_id": case_id,
            "ecosystem": ecosystem,
            "source_package": package,
            "catalog_id": catalog_id,
            "source_repository": case["source_repository"],
            "target_repositories": targets,
            "targets_covered": not missing,
            "missing_targets": missing,
            "catalog_repository_count": len(repositories),
            "non_target_candidate_count": len(repositories) - len(targets) + len(missing),
            "labels_read_after_membership_construction": True,
        })
    return rows


def complete_package_membership(
    snapshots: list[dict[str, Any]], ecosystem: str
) -> tuple[list[str], list[str], list[str]]:
    configured = set(SOURCE_COMPONENTS[ecosystem]["components"])
    failed = {
        snapshot["package"]
        for snapshot in snapshots
        if snapshot["ecosystem"] == ecosystem and snapshot.get("error")
    }
    complete = sorted(configured - failed)
    repositories = sorted({
        repository
        for snapshot in snapshots
        if snapshot["ecosystem"] == ecosystem
        and snapshot["package"] in complete
        for repository in snapshot["repositories"]
    })
    return repositories, complete, sorted(failed)


def run(
    output_dir: Path,
    e2_index: Path,
    per_slice: int,
    workers: int,
    fetcher=fetch_rows,
    cached_snapshots: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    membership, snapshots = construct_membership(
        per_slice, workers, fetcher, cached_snapshots
    )
    # Deliberately load labels only after membership construction is complete.
    cases = read_jsonl(e2_index)
    coverage = audit_coverage(membership, cases)
    fetched_at = dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z")
    output_dir.mkdir(parents=True, exist_ok=True)
    sources = output_dir / "sources"
    sources.mkdir(exist_ok=True)
    write_jsonl(
        sources / "dependent-package-query-snapshots.jsonl",
        (compact_query_snapshot(snapshot) for snapshot in snapshots),
    )
    catalogs = {}
    for ecosystem, repositories in membership.items():
        identifier = f"ecosystems-{ecosystem}-dependent-package-slices-2026-08-26"
        query_failures = [
            snapshot
            for snapshot in snapshots
            if snapshot["ecosystem"] == ecosystem and snapshot.get("error")
        ]
        catalogs[identifier] = {
            "catalog_id": identifier,
            "schema_version": "1.0",
            "catalog_status": (
                "label_independent_reusable_coverage_audit"
                if not query_failures
                else "incomplete_external_query_coverage_audit"
            ),
            "selection_rule": (
                "Union of GitHub repositories named by historical dependent packages "
                f"in the first {per_slice} records of each fixed Ecosyste.ms slice "
                "(stars, dependent repositories, downloads, oldest creation, oldest "
                "latest release, and lexical name) for every evaluated source package "
                f"in the {ecosystem} ecosystem. latest=false includes historical dependents."
            ),
            "membership_source": {
                "kind": "ecosystem_package_dependency_index",
                "service": "packages.ecosyste.ms",
                "license": "CC-BY-SA-4.0",
                "api_root": API_ROOT,
                "snapshot": "sources/dependent-package-query-snapshots.jsonl",
                "catalog_cutoff": fetched_at,
                "query_slices": [
                    {"sort": sort, "order": order, "per_page": per_slice}
                    for sort, order in QUERY_SLICES
                ],
                "historical_query_fallback": (
                    "If the service persistently rejects latest=false, the identical "
                    "fixed slice is retried with latest=true and recorded per query."
                ),
                "source_packages": sorted(
                    SOURCE_COMPONENTS[ecosystem]["components"]
                ),
            },
            "membership_reads_e2_targets": False,
            "source_selection_is_outcome_conditioned": False,
            "query_failure_count": len(query_failures),
            "repository_host": "github.com",
            "repositories": repositories,
        }
    npm_repositories, npm_complete_packages, npm_failed_packages = (
        complete_package_membership(snapshots, "npm")
    )
    if npm_failed_packages and npm_complete_packages:
        identifier = (
            "ecosystems-npm-complete-package-dependent-slices-2026-08-26"
        )
        catalogs[identifier] = {
            "catalog_id": identifier,
            "schema_version": "1.0",
            "catalog_status": "label_independent_reusable_coverage_audit",
            "selection_rule": (
                "Union of the same fixed dependent-package slices for every evaluated "
                "npm source package whose complete query suite returned. Packages with "
                "a persistent query failure are excluded before target coverage is read."
            ),
            "membership_source": {
                "kind": "ecosystem_package_dependency_index_complete_query_subset",
                "service": "packages.ecosyste.ms",
                "license": "CC-BY-SA-4.0",
                "api_root": API_ROOT,
                "snapshot": "sources/dependent-package-query-snapshots.jsonl",
                "catalog_cutoff": fetched_at,
                "query_slices": [
                    {"sort": sort, "order": order, "per_page": per_slice}
                    for sort, order in QUERY_SLICES
                ],
                "source_packages": npm_complete_packages,
                "excluded_source_packages_due_query_failure": npm_failed_packages,
            },
            "membership_reads_e2_targets": False,
            "source_selection_is_outcome_conditioned": False,
            "query_failure_count": 0,
            "repository_host": "github.com",
            "repositories": npm_repositories,
        }
        coverage.extend(audit_catalog_coverage(
            npm_repositories,
            cases,
            "npm",
            identifier,
            set(npm_complete_packages),
        ))
    write_json(output_dir / "candidate-repositories.json", {
        "schema_version": "1.0",
        "catalogs": catalogs,
    })
    write_jsonl(output_dir / "coverage-audit.jsonl", coverage)
    metrics = {
        "schema_version": "1.0",
        "case_count": len({row["case_id"] for row in coverage}),
        "catalog_case_coverage_row_count": len(coverage),
        "catalog_count": len(catalogs),
        "catalog_repository_counts": {
            identifier: len(catalog["repositories"])
            for identifier, catalog in catalogs.items()
        },
        "target_covered_case_count": len({
            row["case_id"] for row in coverage if row["targets_covered"]
        }),
        "target_missing_case_count": len({row["case_id"] for row in coverage}) - len({
            row["case_id"] for row in coverage if row["targets_covered"]
        }),
        "catalog_target_covered_row_count": sum(
            row["targets_covered"] for row in coverage
        ),
        "query_count": len(snapshots),
        "query_failure_count": sum(bool(row.get("error")) for row in snapshots),
        "latest_only_fallback_count": sum(
            bool(row.get("latest_only_fallback")) for row in snapshots
        ),
        "per_slice": per_slice,
        "labels_read_only_after_membership_construction": True,
        "network_used": cached_snapshots is None,
        "release_boundary": (
            "Coverage audit only. Catalogs are not assigned to formal inputs until "
            "target coverage, cutoff snapshot feasibility, and runtime cost are audited."
        ),
    }
    write_json(output_dir / "metrics.json", metrics)
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--e2-index", type=Path, default=E2_INDEX)
    parser.add_argument("--per-slice", type=int, default=20)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--reuse-snapshot", type=Path)
    args = parser.parse_args()
    if args.per_slice < 1 or args.per_slice > 100:
        raise SystemExit("--per-slice must be between 1 and 100")
    metrics = run(
        args.output_dir.resolve(),
        args.e2_index.resolve(),
        args.per_slice,
        args.workers,
        cached_snapshots=(
            read_jsonl(args.reuse_snapshot.resolve())
            if args.reuse_snapshot
            else None
        ),
    )
    print(json.dumps(metrics, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

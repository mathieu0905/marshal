#!/usr/bin/env python3
"""Build a reusable candidate catalog from every dependent of one source package."""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable


API_ROOT = "https://packages.ecosyste.ms/api/v1"
GITHUB_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


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
    repository = f"{parts[0]}/{parts[1]}".removesuffix(".git")
    return repository if GITHUB_REPOSITORY.fullmatch(repository) else None


def fetch_json(url: str) -> list[dict[str, Any]]:
    request = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "User-Agent": "marshal-e2-component-catalog",
    })
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = response.read()
        if response.headers.get("Content-Encoding", "").lower() == "gzip":
            payload = gzip.decompress(payload)
    result = json.loads(payload)
    if not isinstance(result, list):
        raise ValueError("dependent package endpoint did not return a list")
    return result


def page_url(registry: str, package: str, page: int, per_page: int) -> str:
    encoded = urllib.parse.quote(package, safe="")
    query = urllib.parse.urlencode({
        "latest": "false",
        "sort": "name",
        "order": "asc",
        "per_page": per_page,
        "page": page,
    })
    return f"{API_ROOT}/registries/{registry}/packages/{encoded}/dependent_packages?{query}"


def collect_pages(
    registry: str,
    package: str,
    per_page: int,
    fetcher: Callable[[str], list[dict[str, Any]]] = fetch_json,
) -> list[dict[str, Any]]:
    pages = []
    page = 1
    while True:
        url = page_url(registry, package, page, per_page)
        rows = fetcher(url)
        pages.append({"page": page, "url": url, "row_count": len(rows), "rows": rows})
        if len(rows) < per_page:
            return pages
        page += 1


def catalog_document(
    catalog_id: str,
    registry: str,
    package: str,
    pages: list[dict[str, Any]],
    collected_at: str,
) -> dict[str, Any]:
    repositories: dict[str, str | None] = {}
    for page in pages:
        for row in page["rows"]:
            repository = github_repository(row.get("repository_url"))
            if repository is None:
                continue
            created_at = (row.get("repo_metadata") or {}).get("created_at")
            if repository not in repositories or (
                created_at is not None
                and (repositories[repository] is None or created_at < repositories[repository])
            ):
                repositories[repository] = created_at
    return {
        "schema_version": "1.0",
        "catalogs": {
            catalog_id: {
                "schema_version": "1.0",
                "catalog_id": catalog_id,
                "catalog_status": "label_independent_reusable",
                "repository_host": "github.com",
                "membership_reads_e2_targets": False,
                "reused_across_source_events": True,
                "candidate_semantics": "downstream_consumer_roots",
                "selection_rule": (
                    "All canonical GitHub repositories associated with every dependent-package "
                    "row returned by exhaustive, name-ascending pagination for the source package; "
                    "no E2 target label is read during membership construction."
                ),
                "membership_source": {
                    "kind": "ecosystem_package_dependency_index",
                    "service": "packages.ecosyste.ms",
                    "api_root": API_ROOT,
                    "license": "CC-BY-SA-4.0",
                    "catalog_cutoff": collected_at,
                    "source_packages": [package],
                    "query_slices": [{
                        "latest": False,
                        "sort": "name",
                        "order": "asc",
                        "per_page": int(
                            urllib.parse.parse_qs(
                                urllib.parse.urlparse(pages[0]["url"]).query
                            )["per_page"][0]
                        ),
                        "pages": len(pages),
                    }],
                    "snapshot": "sources/dependent-packages.jsonl",
                    "registry": registry,
                },
                "repositories": sorted(repositories),
                "repository_created_at": {
                    repository: created_at
                    for repository, created_at in sorted(repositories.items())
                    if created_at is not None
                },
            }
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", default="repo1.maven.org")
    parser.add_argument("--package", required=True)
    parser.add_argument("--catalog-id", required=True)
    parser.add_argument("--per-page", type=int, default=1000)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.per_page < 1:
        raise ValueError("per-page must be positive")
    if args.output_dir.exists():
        raise ValueError(f"output directory already exists: {args.output_dir}")
    pages = collect_pages(args.registry, args.package, args.per_page)
    collected_at = dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z")
    document = catalog_document(
        args.catalog_id, args.registry, args.package, pages, collected_at
    )
    args.output_dir.mkdir(parents=True)
    sources = args.output_dir / "sources"
    sources.mkdir()
    (args.output_dir / "candidate-repositories.json").write_text(
        json.dumps(document, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with (sources / "dependent-packages.jsonl").open("w", encoding="utf-8") as handle:
        for page in pages:
            handle.write(json.dumps(page, ensure_ascii=False, sort_keys=True) + "\n")
    catalog = document["catalogs"][args.catalog_id]
    metrics = {
        "schema_version": "1.0",
        "catalog_id": args.catalog_id,
        "dependent_package_rows": sum(page["row_count"] for page in pages),
        "page_count": len(pages),
        "repository_count": len(catalog["repositories"]),
        "labels_read": False,
        "pagination_complete": pages[-1]["row_count"] < args.per_page,
    }
    (args.output_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(metrics, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

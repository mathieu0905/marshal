#!/usr/bin/env python3
"""Collect opening-only source inputs before formal-E2 target adjudication."""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any

from collect_opendev import (
    CollectionError,
    DEPENDS_RE,
    META_FILES,
    current_revision,
    gerrit_json,
    query_dependent_changes,
    raw_candidate_frame,
)


ROOT = Path(__file__).resolve().parent
LEGACY_E2 = ROOT / "results/final-e2-dataset-50-2026-08-25/final-index.jsonl"
LEGACY_E1 = ROOT / "results/final-dataset-verification-2026-08-25/final-index.jsonl"
MANUAL_OPENDEV = ROOT / "candidates/opendev-semantic-revision-audit.jsonl"
OPENDEV_ID = re.compile(r"(?:opendev-|opendev-change-)(\d+)")
KNOWN_LEGACY_OPENDEV_SOURCES = {1001023, 1001388}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def legacy_source_numbers(paths: list[Path]) -> set[int]:
    numbers: set[int] = set(KNOWN_LEGACY_OPENDEV_SOURCES)
    for path in paths:
        for row in read_jsonl(path):
            for key in ("case_id", "source_change_family"):
                value = row.get(key)
                if isinstance(value, str) and (match := OPENDEV_ID.search(value)):
                    numbers.add(int(match.group(1)))
            if isinstance(row.get("source_change"), int):
                numbers.add(row["source_change"])
            source = row.get("source", {})
            pull_request = source.get("pull_request", {}) if isinstance(source, dict) else {}
            if isinstance(pull_request.get("number"), int) and pull_request.get("provider") == "gerrit":
                numbers.add(pull_request["number"])
            targets = row.get("targets", [])
            if isinstance(targets, list):
                for target in targets:
                    if isinstance(target, dict) and isinstance(target.get("number"), int):
                        numbers.add(target["number"])
    return numbers


def systematic_frame_sample(frame: list[dict[str, Any]], count: int, excluded: set[int]) -> list[dict[str, Any]]:
    eligible = [row for row in frame if row["source_pr"] not in excluded]
    if count >= len(eligible):
        return eligible
    return [eligible[((2 * index + 1) * len(eligible)) // (2 * count)] for index in range(count)]


def opening_source(number: int) -> dict[str, Any]:
    detail = gerrit_json(f"/changes/{number}/detail", [("o", "ALL_REVISIONS")])
    revisions = detail.get("revisions", {})
    opening_sha = next(
        (sha for sha, value in revisions.items() if value.get("_number") == 1),
        None,
    )
    if not opening_sha:
        raise CollectionError(f"change {number} has no opening revision")
    commit = gerrit_json(f"/changes/{number}/revisions/{opening_sha}/commit")
    files = gerrit_json(f"/changes/{number}/revisions/{opening_sha}/files/")
    parents = commit.get("parents", [])
    if not parents:
        raise CollectionError(f"change {number} opening revision has no parent")
    paths = sorted(path for path in files if path not in META_FILES)
    if not paths:
        raise CollectionError(f"change {number} opening revision has no changed paths")
    return {
        "number": number,
        "change_id": detail["change_id"],
        "repository": detail["project"],
        "branch": detail["branch"],
        "subject": detail["subject"],
        "created": detail["created"],
        "status": detail["status"],
        "opening_revision_number": 1,
        "opening_base_commit": parents[0]["commit"],
        "opening_head_commit": opening_sha,
        "opening_changed_paths": paths,
        "opening_commit_message": commit.get("message", ""),
    }


def catalog_for(repository: str, catalogs: dict[str, Any]) -> str | None:
    matches = [identifier for identifier, value in catalogs.items() if repository in value["repositories"]]
    if repository.startswith("starlingx/"):
        matches = [identifier for identifier in matches if "starlingx" in identifier]
    elif repository.startswith("openstack/"):
        matches = [identifier for identifier in matches if "openstack" in identifier]
    return matches[0] if len(matches) == 1 else None


def collect_links(dependents: list[dict[str, Any]]) -> tuple[list[tuple[int, int, str]], list[dict[str, Any]]]:
    links = []
    for dependent in dependents:
        try:
            _, revision = current_revision(dependent)
        except CollectionError:
            continue
        message = revision.get("commit", {}).get("message", "")
        links.extend(
            (int(match.group(2)), int(dependent["_number"]), match.group(1))
            for match in DEPENDS_RE.finditer(message)
        )
    return links, raw_candidate_frame(dependents, links)


def dependent_source_frame(
    dependents: list[dict[str, Any]],
    links: list[tuple[int, int, str]],
    select_all: bool = False,
) -> list[dict[str, Any]]:
    """Use the dependent change as source and its prerequisites as hidden targets.

    This orientation is useful when a prerequisite is a consumer-side adaptation and
    the dependent change is the upstream API removal that makes the adaptation
    necessary. One representative is selected per undirected dependency component so
    source families remain independent before label review.
    """
    by_number = {int(change["_number"]): change for change in dependents}
    prerequisites: dict[int, set[int]] = {}
    graph: dict[int, set[int]] = {}
    for prerequisite, dependent, _ in links:
        prerequisites.setdefault(dependent, set()).add(prerequisite)
        graph.setdefault(prerequisite, set()).add(dependent)
        graph.setdefault(dependent, set()).add(prerequisite)

    components: list[set[int]] = []
    unseen = set(graph)
    while unseen:
        seed = min(unseen)
        unseen.remove(seed)
        component = {seed}
        queue = [seed]
        while queue:
            current = queue.pop()
            neighbors = graph[current] & unseen
            unseen.difference_update(neighbors)
            component.update(neighbors)
            queue.extend(neighbors)
        components.append(component)

    frame = []
    for component_number, component in enumerate(
        sorted(components, key=lambda members: min(members)), start=1
    ):
        candidates = component & prerequisites.keys() & by_number.keys()
        if not candidates:
            continue

        def created_hint(number: int) -> str:
            return str(by_number[number].get("created", ""))

        selected = sorted(candidates) if select_all else [max(
            candidates,
            key=lambda number: (len(prerequisites[number]), created_hint(number), number),
        )]
        for source_number in selected:
            frame.append({
                "source_pr": source_number,
                "target_prs": sorted(prerequisites[source_number]),
                "submitted_hint": created_hint(source_number),
                "component_size": len(component),
                "dependency_component": component_number,
            })
    return sorted(frame, key=lambda item: (item["submitted_hint"], item["source_pr"]))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalogs", type=Path, required=True)
    parser.add_argument("--max-pages", type=int, default=12)
    parser.add_argument("--source-fetch-count", type=int, default=600)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument(
        "--orientation",
        choices=("referenced-source", "dependent-source"),
        default="referenced-source",
        help="Which side of Depends-On becomes the public source change.",
    )
    parser.add_argument(
        "--component-sampling",
        choices=("representative", "all"),
        default="representative",
        help="For dependent-source orientation, keep one source per dependency component or all sources.",
    )
    parser.add_argument(
        "--exclude-source-events",
        type=Path,
        action="append",
        default=[],
        help="Additional public source frames whose source families must not be sampled again.",
    )
    parser.add_argument(
        "--exclude-target-metadata",
        type=Path,
        action="append",
        default=[],
        help="Previously revealed target metadata whose Gerrit changes must not become new sources.",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--private-dir", type=Path, required=True)
    args = parser.parse_args()

    explicit_exclusions = [*args.exclude_source_events, *args.exclude_target_metadata]
    missing_exclusions = [str(path) for path in explicit_exclusions if not path.is_file()]
    if missing_exclusions:
        parser.error(f"exclusion input does not exist: {', '.join(missing_exclusions)}")

    catalogs = read_json(args.catalogs)["catalogs"]
    excluded = legacy_source_numbers([
        LEGACY_E2,
        LEGACY_E1,
        MANUAL_OPENDEV,
        *args.exclude_source_events,
        *args.exclude_target_metadata,
    ])
    dependents = query_dependent_changes(args.max_pages)
    links, referenced_frame = collect_links(dependents)
    frame = (
        referenced_frame
        if args.orientation == "referenced-source"
        else dependent_source_frame(
            dependents, links, select_all=args.component_sampling == "all"
        )
    )
    sampled = systematic_frame_sample(frame, args.source_fetch_count, excluded)
    target_leads = {row["source_pr"]: row["target_prs"] for row in sampled}

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "sources").mkdir(exist_ok=True)
    args.private_dir.mkdir(parents=True, exist_ok=True)
    cache_path = args.output_dir / "sources/opening-source-cache.jsonl"
    cache = {row["number"]: row for row in read_jsonl(cache_path)}
    missing = [row["source_pr"] for row in sampled if row["source_pr"] not in cache]
    if missing:
        with cache_path.open("a", encoding="utf-8") as handle:
            with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
                futures = {executor.submit(opening_source, number): number for number in missing}
                for future in concurrent.futures.as_completed(futures):
                    try:
                        row = future.result()
                    except Exception:
                        continue
                    cache[row["number"]] = row
                    handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
                    handle.flush()

    selected_at = dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z")
    sources = []
    private = []
    for frame_row in sampled:
        number = frame_row["source_pr"]
        opening = cache.get(number)
        if not opening or opening["status"] != "MERGED":
            continue
        identifier = catalog_for(opening["repository"], catalogs)
        if not identifier:
            continue
        candidate_id = f"formal-opendev-{number}"
        sources.append({
            "schema_version": "1.0",
            "candidate_id": candidate_id,
            "source_change_family": f"opendev-change-{number}-opening",
            "candidate_repository_catalog": f"candidate-repositories.json#{identifier}",
            "catalog_selected_at": selected_at,
            "label_review_state": "not_started",
            "opening": {
                "provider": "gerrit",
                "repository": opening["repository"],
                "number": number,
                "change_id": opening["change_id"],
                "url": f"https://review.opendev.org/c/{opening['repository']}/+/{number}",
                "created_at": opening["created"],
                "branch": opening["branch"],
                "subject": opening["subject"],
                "base_commit": opening["opening_base_commit"],
                "head_commit": opening["opening_head_commit"],
                "changed_paths": opening["opening_changed_paths"],
            },
        })
        private.append({
            "candidate_id": candidate_id,
            "source_change": number,
            "target_change_leads": target_leads[number],
            "dependency_component": frame_row.get("dependency_component"),
            "label_state": "unreviewed",
        })
    sources.sort(key=lambda row: (row["opening"]["created_at"], row["candidate_id"]))
    private.sort(key=lambda row: row["candidate_id"])
    (args.output_dir / "source-events.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in sources),
        encoding="utf-8",
    )
    (args.output_dir / "candidate-repositories.json").write_text(
        args.catalogs.read_text(encoding="utf-8"), encoding="utf-8"
    )
    assignments = [{
        "case_id": row["candidate_id"],
        "candidate_repository_catalog": row["candidate_repository_catalog"],
        "observation_cutoff": row["opening"]["created_at"],
        "input_spec_opening_cutoff_conformant": True,
        "cutoff_policy": "gerrit_change_creation_revision_one",
    } for row in sources]
    (args.output_dir / "case-catalog-assignments.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in assignments),
        encoding="utf-8",
    )
    (args.private_dir / "opendev-label-leads.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in private),
        encoding="utf-8",
    )
    metrics = {
        "schema_version": "1.0",
        "queried_dependent_change_count": len(dependents),
        "raw_link_count": len(links),
        "chain_independent_source_count": len(frame),
        "source_orientation": args.orientation,
        "component_sampling": args.component_sampling,
        "legacy_source_exclusion_count": len(excluded),
        "sampled_source_count": len(sampled),
        "opening_source_fetch_success_count": sum(row["source_pr"] in cache for row in sampled),
        "catalog_eligible_source_count": len(sources),
        "public_source_frame_contains_target_fields": False,
        "private_label_lead_count": len(private),
    }
    (args.output_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(metrics, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

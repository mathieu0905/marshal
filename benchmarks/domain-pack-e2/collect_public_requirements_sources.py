#!/usr/bin/env python3
"""Collect public-first OpenStack requirements source-opening events.

Gerrit ``Depends-On`` trailers are used only to discover source changes and to
produce a separate private lead file.  The public frame is filtered, ordered,
and limited using source-opening records alone.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parent
CROSS_REPO_ROOT = ROOT.parent / "cross-repo-pr-impact"
if str(CROSS_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(CROSS_REPO_ROOT))

from collect_opendev import (  # noqa: E402
    CollectionError,
    DEPENDS_RE,
    META_FILES,
    current_revision,
    gerrit_json,
    query_dependent_changes,
)


SOURCE_REPOSITORY = "openstack/requirements"
REQUIREMENTS_QUERY = f"project:{SOURCE_REPOSITORY} status:merged"
AUTHORING_INFLUENCE = ROOT / "authoring-influence.json"
SOURCE_ID_RE = re.compile(r"(?:formal-opendev-|opendev-change-)(\d+)")
PUBLIC_SCHEMA_VERSION = "domain-pack-requirements-source-opening-1"
PRIVATE_SCHEMA_VERSION = "domain-pack-requirements-private-lead-1"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_number}: expected a JSON object")
        rows.append(row)
    return rows


def _number_from_identifier(value: Any) -> int | None:
    if not isinstance(value, str):
        return None
    match = SOURCE_ID_RE.search(value)
    return int(match.group(1)) if match else None


def source_numbers_from_rows(rows: Iterable[dict[str, Any]]) -> set[int]:
    """Read source-only identifiers without treating target metadata as exclusion."""
    numbers: set[int] = set()
    for row in rows:
        for key in (
            "source_change_id",
            "candidate_id",
            "case_id",
            "source_change_family",
        ):
            number = _number_from_identifier(row.get(key))
            if number is not None:
                numbers.add(number)

        for key in ("source_change", "source_change_number"):
            value = row.get(key)
            if isinstance(value, int) and not isinstance(value, bool):
                numbers.add(value)

        opening = row.get("opening")
        if isinstance(opening, dict):
            value = opening.get("number")
            if isinstance(value, int) and not isinstance(value, bool):
                numbers.add(value)

        values = row.get("source_change_ids")
        if isinstance(values, list):
            for value in values:
                number = _number_from_identifier(value)
                if number is not None:
                    numbers.add(number)
    return numbers


def load_excluded_source_numbers(
    authoring_influence: Path = AUTHORING_INFLUENCE,
    extra_jsonl: Iterable[Path] = (),
) -> set[int]:
    document = json.loads(authoring_influence.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError(f"{authoring_influence}: expected a JSON object")
    source_change_ids = document.get("source_change_ids")
    if not isinstance(source_change_ids, list):
        raise ValueError(f"{authoring_influence}: source_change_ids must be a list")
    excluded = source_numbers_from_rows([{"source_change_ids": source_change_ids}])
    if len(excluded) != len(source_change_ids):
        raise ValueError(
            f"{authoring_influence}: every source_change_ids entry must identify "
            "one formal OpenDev change"
        )
    for path in extra_jsonl:
        excluded.update(source_numbers_from_rows(read_jsonl(path)))
    return excluded


def depends_on_leads(
    dependent_changes: Iterable[dict[str, Any]],
) -> dict[int, list[dict[str, Any]]]:
    """Return private dependent-change leads keyed by referenced source number."""
    grouped: dict[int, set[tuple[int, str]]] = {}
    for dependent in dependent_changes:
        try:
            _, revision = current_revision(dependent)
        except CollectionError:
            continue
        message = revision.get("commit", {}).get("message", "")
        dependent_number = dependent.get("_number")
        dependent_repository = dependent.get("project")
        if not isinstance(dependent_number, int) or not isinstance(
            dependent_repository, str
        ):
            continue
        for match in DEPENDS_RE.finditer(message):
            source_number = int(match.group(2))
            grouped.setdefault(source_number, set()).add(
                (dependent_number, dependent_repository)
            )
    return {
        source_number: [
            {"change_number": number, "repository": repository}
            for number, repository in sorted(leads)
        ]
        for source_number, leads in grouped.items()
    }


def query_merged_requirements_change_numbers() -> set[int]:
    """Page through the cheap project query before fetching revision details."""
    numbers: set[int] = set()
    offset = 0
    while True:
        batch = gerrit_json(
            "/changes/",
            [
                ("q", REQUIREMENTS_QUERY),
                ("n", "500"),
                ("S", str(offset)),
            ],
        )
        if not isinstance(batch, list):
            raise CollectionError("requirements project query did not return a list")
        for change in batch:
            number = change.get("_number")
            if isinstance(number, int) and not isinstance(number, bool):
                numbers.add(number)
        if not batch or not batch[-1].get("_more_changes"):
            break
        offset += len(batch)
    return numbers


def fetch_source_opening(number: int) -> dict[str, Any]:
    """Fetch immutable revision-one source fields for one Gerrit change."""
    detail = gerrit_json(f"/changes/{number}/detail", [("o", "ALL_REVISIONS")])
    revisions = detail.get("revisions", {})
    opening_sha = next(
        (
            sha
            for sha, revision in revisions.items()
            if revision.get("_number") == 1
        ),
        None,
    )
    if opening_sha is None:
        raise CollectionError(f"change {number} has no opening revision")

    commit = gerrit_json(f"/changes/{number}/revisions/{opening_sha}/commit")
    files = gerrit_json(f"/changes/{number}/revisions/{opening_sha}/files/")
    parents = commit.get("parents", [])
    if not parents:
        raise CollectionError(f"change {number} opening revision has no parent")
    changed_paths = sorted(path for path in files if path not in META_FILES)
    if not changed_paths:
        raise CollectionError(f"change {number} opening revision has no changed paths")
    message = commit.get("message", "")
    subject = message.splitlines()[0] if message else ""
    return {
        "provider": "gerrit",
        "repository": detail["project"],
        "number": number,
        "change_id": detail["change_id"],
        "url": f"https://review.opendev.org/c/{detail['project']}/+/{number}",
        "created_at": detail["created"],
        "branch": detail["branch"],
        "subject": subject,
        "base_commit": parents[0]["commit"],
        "head_commit": opening_sha,
        "changed_paths": changed_paths,
    }


def source_opening_sort_key(opening: dict[str, Any]) -> tuple[Any, ...]:
    """A deterministic key containing only fields visible in the source opening."""
    return (
        opening["created_at"],
        opening["repository"],
        opening["branch"],
        opening["change_id"],
        opening["number"],
    )


def select_source_openings(
    openings: Iterable[dict[str, Any]],
    excluded_numbers: set[int],
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Filter and rank without accepting target leads or private labels as input."""
    eligible = [
        opening
        for opening in openings
        if opening.get("repository") == SOURCE_REPOSITORY
        and opening.get("number") not in excluded_numbers
    ]
    selected = sorted(eligible, key=source_opening_sort_key)
    if limit is not None:
        if limit < 0:
            raise ValueError("limit must be non-negative")
        selected = selected[:limit]
    return selected


def fetch_requirements_source_openings(
    lead_source_numbers: Iterable[int],
    requirements_change_numbers: set[int],
    workers: int,
) -> tuple[list[dict[str, Any]], list[int]]:
    """Fetch details only after the public project-query intersection."""
    source_numbers = sorted(set(lead_source_numbers) & requirements_change_numbers)
    openings: list[dict[str, Any]] = []
    failed_source_numbers: list[int] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(fetch_source_opening, number): number
            for number in source_numbers
        }
        for future in concurrent.futures.as_completed(futures):
            number = futures[future]
            try:
                openings.append(future.result())
            except Exception:
                failed_source_numbers.append(number)
    return openings, sorted(failed_source_numbers)


def public_source_row(opening: dict[str, Any]) -> dict[str, Any]:
    number = opening["number"]
    return {
        "schema_version": PUBLIC_SCHEMA_VERSION,
        "source_change_id": f"formal-opendev-{number}",
        "discovery": {"kind": "public_gerrit_depends_on_reference"},
        "opening": dict(opening),
    }


def private_lead_row(
    opening: dict[str, Any], leads: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "schema_version": PRIVATE_SCHEMA_VERSION,
        "source_change_id": f"formal-opendev-{opening['number']}",
        "dependent_change_leads": leads,
        "label_state": "unreviewed",
    }


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Collect openstack/requirements revision-one source inputs from public "
            "Gerrit Depends-On metadata."
        )
    )
    parser.add_argument("--public-output", type=Path, required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    parser.add_argument(
        "--authoring-influence", type=Path, default=AUTHORING_INFLUENCE
    )
    parser.add_argument("--exclude-jsonl", type=Path, action="append", default=[])
    parser.add_argument("--max-pages", type=int, default=12)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument(
        "--limit",
        type=int,
        help="Keep the earliest N eligible source openings after source-only sorting.",
    )
    args = parser.parse_args()

    if args.public_output.resolve() == args.private_output.resolve():
        parser.error("public and private outputs must be different files")
    required_inputs = [args.authoring_influence, *args.exclude_jsonl]
    missing_inputs = [str(path) for path in required_inputs if not path.is_file()]
    if missing_inputs:
        parser.error(f"exclusion input does not exist: {', '.join(missing_inputs)}")
    if args.workers < 1:
        parser.error("workers must be positive")
    if args.limit is not None and args.limit < 0:
        parser.error("limit must be non-negative")

    excluded = load_excluded_source_numbers(
        args.authoring_influence, args.exclude_jsonl
    )
    dependent_changes = query_dependent_changes(args.max_pages)
    private_leads = depends_on_leads(dependent_changes)
    requirements_change_numbers = query_merged_requirements_change_numbers()
    openings, failed_source_numbers = fetch_requirements_source_openings(
        private_leads, requirements_change_numbers, args.workers
    )

    selected = select_source_openings(openings, excluded, args.limit)
    public_rows = [public_source_row(opening) for opening in selected]
    private_rows = [
        private_lead_row(opening, private_leads[opening["number"]])
        for opening in selected
    ]
    write_jsonl(args.public_output, public_rows)
    write_jsonl(args.private_output, private_rows)

    print(
        json.dumps(
            {
                "authoring_and_extra_exclusion_count": len(excluded),
                "depends_on_referenced_source_count": len(private_leads),
                "requirements_project_change_count": len(
                    requirements_change_numbers
                ),
                "requirements_prefiltered_source_count": len(
                    private_leads.keys() & requirements_change_numbers
                ),
                "opening_fetch_failure_count": len(failed_source_numbers),
                "requirements_source_opening_count": len(selected),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

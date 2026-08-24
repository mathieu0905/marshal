#!/usr/bin/env python3

import argparse
import csv
import json
from pathlib import Path


SOURCE_DOI = "10.5281/zenodo.7475823"
SOURCE_FILE = "data.csv"
CSV_FIELD_LIMIT = 32 * 1024 * 1024


def integer(row: dict[str, str], key: str) -> int:
    value = row.get(key, "").strip()
    return int(value) if value else 0


def repository_name(url: str) -> str:
    prefix = "https://github.com/"
    return url[len(prefix) :].removesuffix(".git") if url.startswith(prefix) else url


def candidate(row: dict[str, str]) -> dict[str, object]:
    errors = row.get("errors", "").strip()
    return {
        "candidate_status": "static_impact_lead_only",
        "source_repository": repository_name(row["repoUrl"]),
        "source_pull_request": row["prUrl"],
        "pull_number": integer(row, "number"),
        "title": row["title"],
        "state_at_breakbot_collection": row["state"],
        "draft_at_breakbot_collection": row["draft"].lower() == "true",
        "created_at": row["createdAt"],
        "published_at": row["publishedAt"],
        "base": {
            "repository": row["baseRepo"],
            "ref": row["baseRef"],
            "resolved_revision": row["base"],
        },
        "head": {
            "repository": row["headRepo"],
            "ref": row["headRef"],
            "resolved_revision": row["head"],
        },
        "static_analysis": {
            "breaking_changes": integer(row, "breakingChanges"),
            "broken_clients": integer(row, "brokenClients"),
            "broken_uses": integer(row, "brokenUses"),
            "checked_clients": integer(row, "checkedClients"),
            "reported_clients": integer(row, "clients"),
            "changed_files": integer(row, "changedFiles"),
            "java_files": integer(row, "javaFiles"),
            "impacted_packages": integer(row, "impactedPackages"),
            "duration_seconds": integer(row, "seconds"),
            "errors": errors,
        },
        "label_boundary": (
            "Static broken-use detection is a mining lead, not execution evidence, "
            "a maintainer repair, or a complete impact label."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--observation-date", required=True)
    args = parser.parse_args()

    csv.field_size_limit(CSV_FIELD_LIMIT)
    with args.input.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))

    selected = [row for row in rows if integer(row, "brokenClients") > 0]
    selected.sort(key=lambda row: (row["repoUrl"], integer(row, "number")))
    candidates = [candidate(row) for row in selected]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for item in candidates:
            handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")

    metadata = {
        "observation_date": args.observation_date,
        "source": {
            "doi": SOURCE_DOI,
            "file": SOURCE_FILE,
            "url": "https://zenodo.org/records/7475823",
        },
        "selection": "brokenClients > 0",
        "source_rows": len(rows),
        "source_repositories": len({row["repoUrl"] for row in rows}),
        "candidate_rows": len(selected),
        "candidate_source_repositories": len({row["repoUrl"] for row in selected}),
        "broken_clients_sum": sum(integer(row, "brokenClients") for row in selected),
        "broken_uses_sum": sum(integer(row, "brokenUses") for row in selected),
        "checked_clients_sum_all_rows": sum(integer(row, "checkedClients") for row in rows),
        "limitations": [
            "The source reports static broken uses, not client test failures.",
            "The flat CSV does not provide maintainer repair commits.",
            "Current pull-request state and client identities require separate recovery.",
            "Rows are mining leads and must not be scored as positive or negative labels.",
        ],
    }
    args.metadata.parent.mkdir(parents=True, exist_ok=True)
    args.metadata.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

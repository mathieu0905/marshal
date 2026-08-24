#!/usr/bin/env python3
"""Build failure-time inputs and hidden labels for accepted causal pilot cases."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

from collect_opendev import GERRIT, META_FILES, ROOT, gerrit_json, request_bytes
from collect_github_spec_candidates import gh_api
from collect_repository_snapshots import resolve
from verify_ci_contrasts import build_record, inventory_text


SYSTEM_CONFIG_CANDIDATES = [
    "opendev/grafyaml",
    "opendev/zuul-providers",
    "openstack/project-config",
    "zuul/zuul",
    "zuul/zuul-jobs",
]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def accepted_job_record(
    record: dict[str, Any], review: dict[str, Any]
) -> dict[str, Any]:
    """Select the task that passed semantic review from a multi-task transition."""
    accepted_jobs = [
        item for item in review.get("job_reviews", []) if item["decision"] == "accepted"
    ]
    if not accepted_jobs:
        return record
    primary_jobs = [
        item for item in accepted_jobs if item.get("primary_for_materialization")
    ]
    if len(accepted_jobs) == 1:
        accepted = accepted_jobs[0]
    elif len(primary_jobs) == 1:
        accepted = primary_jobs[0]
    else:
        raise ValueError(
            f"source {record['source_pr']} has {len(accepted_jobs)} accepted jobs "
            f"and {len(primary_jobs)} materialization primaries"
        )
    matches = [
        item
        for item in record.get("composition_verified_jobs", [])
        if item["job"] == accepted["job"]
        and item["failure_build_uuid"] == accepted["failure_build_uuid"]
        and item["success_build_uuid"] == accepted["success_build_uuid"]
    ]
    if len(matches) != 1:
        raise ValueError(
            f"source {record['source_pr']} accepted job has {len(matches)} structural matches"
        )
    return {**record, **matches[0]}


def accepted_cases() -> dict[int, dict[str, Any]]:
    batches = [
        (
            ROOT / "candidates" / "ci-contrast-semantic-review.jsonl",
            ROOT / "candidates" / "ci-contrast-composition-verified.jsonl",
        )
    ]
    batches.extend(
        (review_path, review_path.with_name("composition-verified.jsonl"))
        for review_path in sorted(
            (ROOT / "results").glob("opendev-rolling-*/semantic-review.jsonl")
        )
    )
    accepted: dict[int, dict[str, Any]] = {}
    for review_path, verified_path in batches:
        if not verified_path.exists():
            raise ValueError(f"missing structural evidence next to {review_path}")
        reviews = {
            item["source_pr"]: item
            for item in read_jsonl(review_path)
            if item["decision"] == "accepted"
        }
        records = {
            item["source_pr"]: item for item in read_jsonl(verified_path)
        }
        for source_pr, review in reviews.items():
            if source_pr in accepted:
                raise ValueError(f"accepted source {source_pr} appears in multiple batches")
            if source_pr not in records:
                raise ValueError(f"accepted source {source_pr} lacks structural evidence")
            accepted[source_pr] = {
                "review": review,
                "record": accepted_job_record(records[source_pr], review),
                "review_path": review_path,
                "verified_path": verified_path,
            }
    return accepted


def opendev_commit(repository: str, commit: str) -> dict[str, Any]:
    url = f"https://opendev.org/api/v1/repos/{repository}/git/commits/{commit}"
    return json.loads(request_bytes(url))


def github_commit(repository: str, commit: str) -> dict[str, Any]:
    return gh_api(f"repos/{repository}/commits/{commit}")


def inventory_projects(record: dict[str, Any]) -> dict[str, dict[str, Any]]:
    build = build_record(record["tenant"], record["failure_build_uuid"])
    parsed = yaml.safe_load(inventory_text(build))
    projects = parsed["all"]["vars"]["zuul"]["projects"]
    return {item["name"]: item for item in projects.values()}


def candidate_repositories(
    record: dict[str, Any],
    projects: dict[str, dict[str, Any]],
    calibration_catalogs: dict[str, Any],
) -> list[str]:
    source_pr = record["source_pr"]
    if source_pr == 999031:
        repositories = SYSTEM_CONFIG_CANDIDATES
    elif source_pr == 1001023:
        repositories = calibration_catalogs["openstack"]["repositories"]
    elif source_pr == 1001168:
        repositories = list(projects)
    elif source_pr in {1000542, 1000668, 1000682}:
        repositories = list(projects) + calibration_catalogs["openstack"]["repositories"]
    else:
        raise ValueError(f"no causal candidate catalog rule for source {source_pr}")
    return sorted(set(repositories) - {record["source_repository"]})


def snapshot(
    repository: str,
    cutoff: str,
    projects: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if repository not in projects:
        result = resolve("causal-opendev", repository, cutoff)
        result["snapshot_source"] = "default_branch_before_failure"
        return result
    project = projects[repository]
    commit = project["commit"]
    host = project["canonical_hostname"]
    if host == "opendev.org":
        detail = opendev_commit(repository, commit)
        committed_at = detail["created"]
        archive_url = f"https://opendev.org/api/v1/repos/{repository}/archive/{commit}.tar.gz"
    elif host == "github.com":
        detail = github_commit(repository, commit)
        committed_at = detail["commit"]["committer"]["date"]
        archive_url = f"https://github.com/{repository}/archive/{commit}.tar.gz"
    else:
        raise ValueError(f"unsupported inventory host {host} for {repository}")
    return {
        "repository": repository,
        "host": host,
        "status": "available",
        "commit": commit,
        "committed_at": committed_at,
        "archive_url": archive_url,
        "snapshot_source": "zuul_failure_inventory",
    }


def source_input(record: dict[str, Any]) -> dict[str, Any]:
    source_pr = record["source_pr"]
    revision = record["source_before_revision"]
    commit = gerrit_json(f"/changes/{source_pr}/revisions/{revision['sha']}/commit")
    files = gerrit_json(f"/changes/{source_pr}/revisions/{revision['sha']}/files/")
    parents = commit.get("parents", [])
    if len(parents) != 1:
        raise ValueError(f"source {source_pr} has {len(parents)} parents")
    return {
        "host": "review.opendev.org",
        "repository": record["source_repository"],
        "pull_request_number": source_pr,
        "subject": record["source_subject"],
        "base_commit": parents[0]["commit"],
        "candidate_commit": revision["sha"],
        "changed_paths": sorted(path for path in files if path not in META_FILES),
        "patch_url": f"{GERRIT}/changes/{source_pr}/revisions/{revision['sha']}/patch",
    }


def target_paths(record: dict[str, Any]) -> list[str]:
    files = gerrit_json(
        f"/changes/{record['target_pr']}/revisions/{record['target_commit']}/files/"
    )
    return sorted(path for path in files if path not in META_FILES)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "causal-pilot")
    args = parser.parse_args()
    cases = accepted_cases()
    calibration_catalogs = json.loads(
        (ROOT / "candidate-repositories.json").read_text(encoding="utf-8")
    )["catalogs"]
    inputs = []
    labels = []
    snapshots = []
    catalogs: dict[str, Any] = {}
    for source_pr in sorted(cases):
        review = cases[source_pr]["review"]
        record = cases[source_pr]["record"]
        projects = inventory_projects(record)
        repositories = candidate_repositories(record, projects, calibration_catalogs)
        case_id = f"causal-opendev-{source_pr}"
        cutoff = record["times"]["failure_start_time"] + "Z"
        case_snapshots = [snapshot(repository, cutoff, projects) for repository in repositories]
        target_snapshot = next(
            item for item in case_snapshots if item["repository"] == record["target_repository"]
        )
        if target_snapshot["status"] != "available":
            raise ValueError(f"target snapshot unavailable for {case_id}")
        catalogs[case_id] = {"repositories": repositories}
        inputs.append({
            "case_id": case_id,
            "track": "cross_repository_breakage_discovery_causal_pilot",
            "observation_cutoff": cutoff,
            "source": source_input(record),
            "candidate_repository_catalog": f"candidate-repositories.json#{case_id}",
            "candidate_repository_snapshots": f"repository-snapshots.jsonl#{case_id}",
        })
        snapshots.append({
            "case_id": case_id,
            "observation_cutoff": cutoff,
            "repositories": case_snapshots,
        })
        labels.append({
            "case_id": case_id,
            "source_pr": source_pr,
            "target_repository": record["target_repository"],
            "target_pr": record["target_pr"],
            "target_fix_commit": record["target_commit"],
            "target_failure_arm_commit": target_snapshot["commit"],
            "target_changed_paths": target_paths(record),
            "impact_kind": review["impact_kind"],
            "failure_signature": [
                item["marker"]
                for item in review.get(
                    "failure_log_evidence",
                    review.get("evidence", {}).get("accepted_failure", []),
                )
            ],
            "job": record["job"],
            "failure_build_uuid": record["failure_build_uuid"],
            "success_build_uuid": record["success_build_uuid"],
            "evidence_record": "../"
            + str(cases[source_pr]["review_path"].relative_to(ROOT)),
            "composition_record": "../"
            + str(cases[source_pr]["verified_path"].relative_to(ROOT)),
        })
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "candidate-repositories.json").write_text(
        json.dumps({"schema_version": "0.1-pilot", "catalogs": catalogs}, indent=2, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    for name, rows in [
        ("inputs.jsonl", inputs),
        ("repository-snapshots.jsonl", snapshots),
        ("labels.jsonl", labels),
    ]:
        (args.output_dir / name).write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
            encoding="utf-8",
        )
    statuses: dict[str, int] = {}
    sources: dict[str, int] = {}
    for row in snapshots:
        for item in row["repositories"]:
            statuses[item["status"]] = statuses.get(item["status"], 0) + 1
            source = item["snapshot_source"]
            sources[source] = sources.get(source, 0) + 1
    print(json.dumps({
        "cases": len(inputs),
        "candidate_repository_snapshots": sum(len(row["repositories"]) for row in snapshots),
        "candidate_counts": {key: len(value["repositories"]) for key, value in catalogs.items()},
        "statuses": statuses,
        "snapshot_sources": sources,
        "output_directory": str(args.output_dir),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

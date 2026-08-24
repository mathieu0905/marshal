#!/usr/bin/env python3
"""Remote audit of target and distractor snapshots in each causal pilot case."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import tarfile
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import yaml

from collect_github_spec_candidates import gh_api
from collect_opendev import ROOT, request_bytes
from materialize_causal_pilot import accepted_cases
from verify_ci_contrasts import build_record, inventory_text


AUDIT_REPOSITORIES = {
    "causal-opendev-999031": ["opendev/grafyaml", "openstack/project-config"],
    "causal-opendev-1000542": ["openstack/magnum-capi-helm", "novnc/novnc"],
    "causal-opendev-1000668": ["openstack/requirements", "openstack/nova"],
    "causal-opendev-1000682": [
        "openstack/python-openstackclient",
        "openstack/cliff",
    ],
    "causal-opendev-1001023": ["openstack/cinder", "openstack/nova"],
    "causal-opendev-1001168": [
        "openstack/neutron-tempest-plugin",
        "openstack/tempest",
    ],
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def request_json(url: str) -> Any:
    return json.loads(request_bytes(url))


def parse_time(value: str) -> dt.datetime:
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.UTC)
    return parsed.astimezone(dt.UTC)


def inventory_commits(label: dict[str, Any]) -> dict[str, str]:
    verified = accepted_cases()[label["source_pr"]]["record"]
    build = build_record(verified["tenant"], verified["failure_build_uuid"])
    parsed = yaml.safe_load(inventory_text(build))
    return {
        item["name"]: item["commit"]
        for item in parsed["all"]["vars"]["zuul"]["projects"].values()
    }


def remote_commit(repository: str, commit: str, host: str) -> dict[str, str]:
    if host == "opendev.org":
        remote = request_json(
            f"https://opendev.org/api/v1/repos/{repository}/git/commits/{commit}"
        )
        return {"sha": remote["sha"], "created": remote["created"]}
    if host == "github.com":
        remote = gh_api(f"repos/{repository}/commits/{commit}")
        return {
            "sha": remote["sha"],
            "created": remote["commit"]["committer"]["date"],
        }
    raise ValueError(f"unsupported snapshot host {host} for {repository}")


def latest_before(repository: str, cutoff: str, host: str) -> str | None:
    if host == "github.com":
        rows = gh_api(
            f"repos/{repository}/commits",
            {"until": cutoff, "per_page": "1"},
        )
        return rows[0]["sha"] if rows else None
    if host != "opendev.org":
        raise ValueError(f"unsupported snapshot host {host} for {repository}")
    query = urllib.parse.urlencode({"limit": 1, "until": cutoff})
    rows = request_json(f"https://opendev.org/api/v1/repos/{repository}/commits?{query}")
    return rows[0]["sha"] if rows else None


def archive_expands(url: str) -> tuple[bool, int]:
    request = urllib.request.Request(url, headers={"User-Agent": "marshal-causal-pilot-audit"})
    with tempfile.NamedTemporaryFile(suffix=".tar.gz") as temporary:
        for attempt in range(4):
            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    while chunk := response.read(1024 * 1024):
                        temporary.write(chunk)
                break
            except (urllib.error.URLError, TimeoutError):
                temporary.seek(0)
                temporary.truncate()
                if attempt == 3:
                    raise
                time.sleep(attempt + 1)
        temporary.flush()
        with tarfile.open(temporary.name, "r:gz") as archive:
            files = sum(member.isfile() for member in archive.getmembers())
    return files > 0, files


def audit_snapshot(
    case: dict[str, Any],
    label: dict[str, Any],
    snapshot: dict[str, Any],
    inventories: dict[str, str],
) -> dict[str, Any]:
    repository = snapshot["repository"]
    commit = snapshot["commit"]
    host = snapshot["host"]
    remote = remote_commit(repository, commit, host)
    expands, file_count = archive_expands(snapshot["archive_url"])
    checks = {
        "remote_commit_matches": remote.get("sha") == commit,
        "commit_not_after_cutoff": (
            parse_time(remote["created"]) <= parse_time(case["observation_cutoff"])
        ),
        "archive_expands": expands,
    }
    if snapshot["snapshot_source"] == "zuul_failure_inventory":
        checks["failure_inventory_commit_matches"] = inventories.get(repository) == commit
    else:
        checks["latest_default_commit_before_cutoff"] = (
            latest_before(repository, case["observation_cutoff"], host) == commit
        )
    return {
        "case_id": case["case_id"],
        "repository": repository,
        "role": "target" if repository == label["target_repository"] else "distractor",
        "snapshot_source": snapshot["snapshot_source"],
        "commit": commit,
        "remote_created": remote["created"],
        "archive_file_count": file_count,
        "checks": checks,
        "passed": all(checks.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot-dir", type=Path, default=ROOT / "causal-pilot")
    args = parser.parse_args()
    cases = {item["case_id"]: item for item in read_jsonl(args.pilot_dir / "inputs.jsonl")}
    labels = {item["case_id"]: item for item in read_jsonl(args.pilot_dir / "labels.jsonl")}
    snapshots = {
        item["case_id"]: {row["repository"]: row for row in item["repositories"]}
        for item in read_jsonl(args.pilot_dir / "repository-snapshots.jsonl")
    }
    results = []
    for case_id, repositories in AUDIT_REPOSITORIES.items():
        inventories = inventory_commits(labels[case_id])
        for repository in repositories:
            results.append(audit_snapshot(
                cases[case_id],
                labels[case_id],
                snapshots[case_id][repository],
                inventories,
            ))
    output = args.pilot_dir / "audit-results.jsonl"
    output.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in results),
        encoding="utf-8",
    )
    print(json.dumps({
        "audited_snapshots": len(results),
        "targets": sum(item["role"] == "target" for item in results),
        "distractors": sum(item["role"] == "distractor" for item in results),
        "passed": sum(item["passed"] for item in results),
        "output": str(output),
    }, indent=2, ensure_ascii=False))
    return 0 if all(item["passed"] for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

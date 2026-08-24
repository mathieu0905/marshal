#!/usr/bin/env python3
"""Verify source-diff identity and Zuul composition for mined CI contrasts."""

from __future__ import annotations

import argparse
import base64
import concurrent.futures
import datetime as dt
import gzip
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import yaml

from collect_opendev import GERRIT, ROOT, gerrit_json, request_bytes


def load_candidates(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def code_diff(number: int, revision: int) -> bytes:
    encoded = request_bytes(f"{GERRIT}/changes/{number}/revisions/{revision}/patch?download")
    patch = base64.b64decode(encoded)
    marker = b"\ndiff --git "
    position = patch.find(marker)
    return patch[position + 1:] if position >= 0 else b""


def build_record(tenant: str, uuid: str) -> dict[str, Any]:
    return json.loads(request_bytes(
        f"https://zuul.opendev.org/api/tenant/{tenant}/build/{uuid}"
    ))


def inventory_text(build: dict[str, Any]) -> str:
    url = f"{build['log_url']}zuul-info/inventory.yaml"
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "marshal-cross-repo-benchmark/1.0"},
    )
    for attempt in range(2):
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                payload = response.read()
            break
        except urllib.error.HTTPError as exc:
            if exc.code == 404 or attempt == 1:
                raise
            time.sleep(attempt + 1)
        except (urllib.error.URLError, TimeoutError):
            if attempt == 1:
                raise
            time.sleep(attempt + 1)
    if payload.startswith(b"\x1f\x8b"):
        payload = gzip.decompress(payload)
    return payload.decode("utf-8", errors="replace")


def inventory_items(inventory: str) -> list[dict[str, Any]]:
    parsed = yaml.safe_load(inventory)
    items = (
        parsed.get("all", {})
        .get("vars", {})
        .get("zuul", {})
        .get("items")
    )
    if not isinstance(items, list):
        raise ValueError("inventory does not contain all.vars.zuul.items")
    return [item for item in items if isinstance(item, dict)]


def commits_for_change(items: list[dict[str, Any]], number: int) -> set[str]:
    commits = set()
    for item in items:
        try:
            item_number = int(item.get("change"))
        except (TypeError, ValueError):
            continue
        commit = item.get("commit_id")
        if item_number == number and isinstance(commit, str) and len(commit) == 40:
            commits.add(commit)
    return commits


def patchsets_for_change(build: dict[str, Any], number: int) -> set[int]:
    return {
        int(ref["patchset"])
        for ref in build.get("buildset", {}).get("refs", [])
        if ref.get("change") == number and ref.get("patchset") is not None
    }


def target_detail(number: int) -> dict[str, Any]:
    return gerrit_json(
        f"/changes/{number}/detail",
        [("o", "ALL_REVISIONS"), ("o", "CURRENT_COMMIT")],
    )


def parse_time(value: str) -> dt.datetime:
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def verify_times(
    before_created: str,
    after_created: str,
    target_revision_created: str,
    failure: dict[str, Any],
    success: dict[str, Any],
) -> tuple[dict[str, bool], dict[str, str]]:
    raw_times = {
        "source_before_revision_created": before_created,
        "failure_start_time": failure.get("start_time"),
        "failure_end_time": failure.get("end_time"),
        "source_after_revision_created": after_created,
        "target_revision_created": target_revision_created,
        "success_start_time": success.get("start_time"),
        "success_end_time": success.get("end_time"),
    }
    if any(not value for value in raw_times.values()):
        missing = sorted(key for key, value in raw_times.items() if not value)
        raise ValueError(f"missing timestamps: {','.join(missing)}")
    times = {key: parse_time(value) for key, value in raw_times.items()}
    checks = {
        "source_before_precedes_failure": (
            times["source_before_revision_created"] <= times["failure_start_time"]
        ),
        "failure_interval_valid": times["failure_start_time"] <= times["failure_end_time"],
        "dependency_added_after_failure": (
            times["failure_end_time"] <= times["source_after_revision_created"]
        ),
        "dependency_available_before_success": (
            times["source_after_revision_created"] <= times["success_start_time"]
        ),
        "target_revision_available_before_success": (
            times["target_revision_created"] <= times["success_start_time"]
        ),
        "failure_precedes_success": times["failure_end_time"] <= times["success_start_time"],
        "success_interval_valid": times["success_start_time"] <= times["success_end_time"],
    }
    return checks, {key: value for key, value in raw_times.items() if value is not None}


def verify_contrast(
    candidate: dict[str, Any],
    target: dict[str, Any],
    contrast: dict[str, Any],
) -> dict[str, Any]:
    source_pr = candidate["source_pr"]
    target_pr = candidate["added_dependency_prs"][0]
    before = candidate["before_revision"]
    after = candidate["after_revision"]
    job = contrast["job"]
    tenant = contrast.get("tenant")
    if not tenant:
        return {"status": "rejected", "reason": "missing_tenant", "job": job}
    try:
        failure = build_record(tenant, contrast["failure_build_uuid"])
        success = build_record(tenant, contrast["success_build_uuid"])
    except Exception as exc:
        return {
            "status": "evidence_unavailable",
            "reason": "build_metadata_unavailable",
            "job": job,
            "error": str(exc),
        }
    if failure.get("result") != "FAILURE" or success.get("result") != "SUCCESS":
        return {"status": "rejected", "reason": "unexpected_build_result", "job": job}
    if failure.get("job_name") != job or success.get("job_name") != job:
        return {"status": "rejected", "reason": "job_mismatch", "job": job}

    try:
        failure_items = inventory_items(inventory_text(failure))
        success_items = inventory_items(inventory_text(success))
    except Exception as exc:
        return {
            "status": "evidence_unavailable",
            "reason": "job_inventory_unavailable",
            "job": job,
            "error": str(exc),
        }

    failure_source_commits = commits_for_change(failure_items, source_pr)
    success_source_commits = commits_for_change(success_items, source_pr)
    failure_target_commits = commits_for_change(failure_items, target_pr)
    success_target_commits = commits_for_change(success_items, target_pr)
    if before["sha"] not in failure_source_commits:
        return {"status": "rejected", "reason": "failure_source_commit_missing", "job": job}
    if after["sha"] not in success_source_commits:
        return {"status": "rejected", "reason": "success_source_commit_missing", "job": job}
    if failure_target_commits:
        return {
            "status": "rejected",
            "reason": "failure_already_includes_target",
            "job": job,
            "target_commits": sorted(failure_target_commits),
        }
    if not success_target_commits:
        return {"status": "rejected", "reason": "success_omits_target", "job": job}
    if len(success_target_commits) != 1:
        return {
            "status": "rejected",
            "reason": "ambiguous_success_target_revision",
            "job": job,
            "target_commits": sorted(success_target_commits),
        }
    target_commit = next(iter(success_target_commits))
    try:
        gerrit_json(f"/changes/{target_pr}/revisions/{target_commit}/commit")
    except Exception as exc:
        return {
            "status": "evidence_unavailable",
            "reason": "target_revision_unavailable",
            "job": job,
            "error": str(exc),
        }
    target_revision = target.get("revisions", {}).get(target_commit, {})
    target_revision_created = target_revision.get("created")
    try:
        time_checks, times = verify_times(
            before["created"],
            after["created"],
            target_revision_created,
            failure,
            success,
        )
    except (TypeError, ValueError) as exc:
        return {
            "status": "evidence_unavailable",
            "reason": "transition_time_unavailable",
            "job": job,
            "error": str(exc),
        }
    if not all(time_checks.values()):
        return {
            "status": "rejected",
            "reason": "invalid_transition_order",
            "job": job,
            "time_checks": time_checks,
            "times": times,
        }
    return {
        "status": "composition_verified",
        "job": job,
        "tenant": tenant,
        "target_commit": target_commit,
        "target_revision_created": target_revision_created,
        "failure_build_uuid": contrast["failure_build_uuid"],
        "failure_log_url": failure["log_url"],
        "success_build_uuid": contrast["success_build_uuid"],
        "success_log_url": success["log_url"],
        "times": times,
        "time_checks": time_checks,
        "inventory_checks": {
            "failure_source_commit": before["sha"],
            "failure_target_absent": True,
            "success_source_commit": after["sha"],
            "success_target_commit": target_commit,
        },
        "buildset_ref_patchsets": {
            "failure_source": sorted(patchsets_for_change(failure, source_pr)),
            "failure_target": sorted(patchsets_for_change(failure, target_pr)),
            "success_source": sorted(patchsets_for_change(success, source_pr)),
            "success_target": sorted(patchsets_for_change(success, target_pr)),
        },
    }


def verify_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    if len(candidate["added_dependency_prs"]) != 1:
        return {"status": "rejected", "reason": "multiple_added_dependencies", "candidate": candidate}
    source_pr = candidate["source_pr"]
    target_pr = candidate["added_dependency_prs"][0]
    before = candidate["before_revision"]
    after = candidate["after_revision"]
    try:
        before_diff = code_diff(source_pr, before["number"])
        after_diff = code_diff(source_pr, after["number"])
    except Exception as exc:
        return {
            "status": "evidence_unavailable",
            "reason": "source_patch_unavailable",
            "error": str(exc),
            "candidate": candidate,
        }
    if before_diff != after_diff:
        return {"status": "rejected", "reason": "source_code_diff_changed", "candidate": candidate}

    try:
        target = target_detail(target_pr)
    except Exception as exc:
        return {
            "status": "evidence_unavailable",
            "reason": "target_change_unavailable",
            "error": str(exc),
            "candidate": candidate,
        }
    if target["project"] == candidate["source_repository"]:
        return {"status": "rejected", "reason": "same_repository", "candidate": candidate}
    if target["created"] > after["created"]:
        return {"status": "rejected", "reason": "target_change_created_after_transition", "candidate": candidate}

    job_checks = [verify_contrast(candidate, target, contrast) for contrast in candidate["same_job_contrasts"]]
    verified_jobs = [
        item for item in job_checks if item["status"] == "composition_verified"
    ]
    if verified_jobs:
        verified = verified_jobs[0]
        return {
            "status": "composition_verified",
            "source_repository": candidate["source_repository"],
            "source_pr": source_pr,
            "source_created": candidate["source_created"],
            "source_subject": candidate["source_subject"],
            "source_before_revision": before,
            "source_after_revision": after,
            "source_code_diff_identical": True,
            "target_repository": target["project"],
            "target_pr": target_pr,
            "target_created": target["created"],
            "target_revision_created": verified["target_revision_created"],
            "target_subject": target["subject"],
            "target_commit": verified["target_commit"],
            "composition_source": "zuul_job_inventory",
            "tenant": verified["tenant"],
            "job": verified["job"],
            "failure_build_uuid": verified["failure_build_uuid"],
            "failure_log_url": verified["failure_log_url"],
            "success_build_uuid": verified["success_build_uuid"],
            "success_log_url": verified["success_log_url"],
            "times": verified["times"],
            "time_checks": verified["time_checks"],
            "inventory_checks": verified["inventory_checks"],
            "buildset_ref_patchsets": verified["buildset_ref_patchsets"],
            "composition_verified_job_count": len(verified_jobs),
            "composition_verified_jobs": verified_jobs,
        }
    if any(item["status"] == "evidence_unavailable" for item in job_checks):
        return {
            "status": "evidence_unavailable",
            "reason": "no_archived_inventory_for_verifiable_job",
            "job_checks": job_checks,
            "candidate": candidate,
        }
    return {
        "status": "rejected",
        "reason": "all_jobs_contradict_composition_or_timing",
        "job_checks": job_checks,
        "candidate": candidate,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=ROOT / "candidates" / "ci-contrast-candidates.jsonl",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "candidates" / "ci-contrast-composition-verified.jsonl",
    )
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    candidates = load_candidates(args.input)
    if args.limit is not None:
        candidates = candidates[:args.limit]

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(verify_candidate, candidate) for candidate in candidates]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
    verified = sorted(
        (item for item in results if item["status"] == "composition_verified"),
        key=lambda item: (item["source_created"], item["source_pr"]),
    )
    unavailable = [item for item in results if item["status"] == "evidence_unavailable"]
    rejected = [item for item in results if item["status"] == "rejected"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for item in verified:
            handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
    rejection_path = args.output.with_name("ci-contrast-composition-rejected.jsonl")
    with rejection_path.open("w", encoding="utf-8") as handle:
        for item in rejected:
            handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
    unavailable_path = args.output.with_name("ci-contrast-evidence-unavailable.jsonl")
    with unavailable_path.open("w", encoding="utf-8") as handle:
        for item in unavailable:
            handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
    reasons: dict[str, int] = {}
    for item in rejected:
        reason = item["reason"]
        reasons[reason] = reasons.get(reason, 0) + 1
    unavailable_job_reasons: dict[str, int] = {}
    for item in unavailable:
        for job_check in item.get("job_checks", []):
            if job_check["status"] != "evidence_unavailable":
                continue
            reason = job_check["reason"]
            unavailable_job_reasons[reason] = unavailable_job_reasons.get(reason, 0) + 1
    print(json.dumps({
        "candidates": len(candidates),
        "composition_verified": len(verified),
        "evidence_unavailable": len(unavailable),
        "rejected": len(rejected),
        "rejection_reasons": reasons,
        "unavailable_job_reasons": unavailable_job_reasons,
        "output": str(args.output),
        "unavailable_output": str(unavailable_path),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

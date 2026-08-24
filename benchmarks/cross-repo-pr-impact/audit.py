#!/usr/bin/env python3
"""Re-fetch a deterministic sample and audit stored cross-repository evidence."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any

from collect_opendev import DEPENDS_RE, fetch_change, request_bytes
from audit_opendev_semantic_reviews import fetch_all_revisions, revision_files


ROOT = Path(__file__).resolve().parent


def github_api(endpoint: str) -> Any:
    for attempt in range(3):
        result = subprocess.run(
            ["gh", "api", endpoint], capture_output=True, text=True
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
        if attempt < 2:
            time.sleep(attempt + 1)
    raise RuntimeError(result.stderr.strip() or f"GitHub API failed: {endpoint}")


def load_cases() -> list[dict[str, Any]]:
    cases = []
    with (ROOT / "index.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                item = json.loads(line)
                with (ROOT / item["path"]).open(encoding="utf-8") as case_handle:
                    cases.append(json.load(case_handle))
    return sorted(cases, key=lambda item: item["case_id"])


def deterministic_sample(cases: list[dict[str, Any]], size: int) -> list[dict[str, Any]]:
    if size > len(cases):
        raise ValueError("sample is larger than dataset")
    mandatory_ids = {
        "github-ethereum-eips-2718",
        "github-ethereum-eips-4788",
        "opendev-1001023-cinder-impact",
        "opendev-1001388",
    }
    mandatory = [case for case in cases if case["case_id"] in mandatory_ids]
    represented_projects = {case["project"] for case in mandatory}
    for project in sorted({case["project"] for case in cases} - represented_projects):
        mandatory.append(next(case for case in cases if case["project"] == project))
    mandatory_ids = {case["case_id"] for case in mandatory}
    remaining_cases = [case for case in cases if case["case_id"] not in mandatory_ids]
    remaining = size - len(mandatory)
    if remaining < 0:
        raise ValueError("sample is smaller than the mandatory evidence and ecosystem audit")
    sampled = [
        remaining_cases[(index * len(remaining_cases)) // remaining]
        for index in range(remaining)
    ] if remaining else []
    return sorted(mandatory + sampled, key=lambda item: item["case_id"])


def url_available(url: str) -> bool:
    try:
        request_bytes(url, attempts=2)
        return True
    except Exception:
        return False


def patch_paths(payload: bytes) -> list[str]:
    text = payload.decode("utf-8", errors="replace")
    return sorted(set(re.findall(r"^diff --git a/(\S+) b/\S+$", text, re.MULTILINE)))


def github_pull_paths(repository: str, number: int) -> list[str]:
    paths = []
    for page in range(1, 20):
        payload = github_api(
            f"repos/{repository}/pulls/{number}/files?per_page=100&page={page}"
        )
        paths.extend(item["filename"] for item in payload)
        if len(payload) < 100:
            return sorted(set(paths))
    raise RuntimeError(f"target PR file list exceeds audit pagination limit: {repository}#{number}")


def audit_github_case(case: dict[str, Any]) -> dict[str, Any]:
    source = case["source"]
    source_meta = github_api(
        f"repos/{source['repository']}/pulls/{source['pull_request']['number']}"
    )
    request_bytes(source["patch_url"])
    source_commit = github_api(
        f"repos/{source['repository']}/commits/{source['candidate_commit']}"
    )
    comparison_diff = request_bytes(
        f"https://github.com/{source['repository']}/compare/"
        f"{source['base_commit']}...{source['candidate_commit']}.diff"
    )
    source_checks = {
        "candidate_commit": source_commit.get("sha") == source["candidate_commit"],
        "base_candidate_comparison": url_available(
            f"https://github.com/{source['repository']}/compare/"
            f"{source['base_commit']}...{source['candidate_commit']}"
        ),
        "changed_paths": patch_paths(comparison_diff) == source["changed_paths"],
        "patch_available": True,
        "pull_request_available": url_available(source["pull_request"]["url"]),
        "created": source_meta.get("created_at") == source["pull_request"]["created"],
        "submitted": source_meta.get("merged_at") == source["pull_request"]["submitted"],
    }
    target_results = []
    for target in case["targets"]:
        target_meta = github_api(
            f"repos/{target['repository']}/pulls/{target['pull_request']['number']}"
        )
        checks = {
            "commit": target_meta.get("head", {}).get("sha") == target["commit"],
            "changed_paths": (
                github_pull_paths(target["repository"], target["pull_request"]["number"])
                == target["changed_paths"]
            ),
            "specification_reference": (
                source["pull_request"]["url"] in (target_meta.get("body") or "")
                or source["pull_request"]["url"].replace("https://", "http://")
                in (target_meta.get("body") or "")
                or (
                    source["repository"] == "ethereum/EIPs"
                    and re.search(
                        rf"EIP[- ]{source['pull_request']['number']}\b",
                        (target_meta.get("title") or "") + "\n" + (target_meta.get("body") or ""),
                        re.IGNORECASE,
                    ) is not None
                )
            ),
            "pull_request_available": True,
            "created": target_meta.get("created_at") == target["pull_request"]["created"],
            "submitted": target_meta.get("merged_at") == target["pull_request"]["submitted"],
            "license_evidence_available": all(url_available(item["evidence_url"]) for item in case["licenses"]),
        }
        target_results.append({
            "repository": target["repository"],
            "pull_request": target["pull_request"]["number"],
            "checks": checks,
            "passed": all(checks.values()),
        })
    passed = all(source_checks.values()) and all(item["passed"] for item in target_results)
    return {
        "case_id": case["case_id"],
        "source_pull_request": source["pull_request"]["number"],
        "source_checks": source_checks,
        "targets": target_results,
        "passed": passed,
    }


def audit_cinder_contrast(case: dict[str, Any]) -> dict[str, Any]:
    failure_uuid = "a910bfbc663642c7b7bd5e3dab0c11c2"
    success_uuid = "6929808c35ff466080f9d39934e26125"
    api_root = "https://zuul.opendev.org/api/tenant/openstack/build"
    failure = json.loads(request_bytes(f"{api_root}/{failure_uuid}"))
    success = json.loads(request_bytes(f"{api_root}/{success_uuid}"))
    failure_inventory = request_bytes(f"{failure['log_url']}zuul-info/inventory.yaml").decode(
        "utf-8", errors="replace"
    )
    success_inventory = request_bytes(f"{success['log_url']}zuul-info/inventory.yaml").decode(
        "utf-8", errors="replace"
    )
    failure_log = request_bytes(f"{failure['log_url']}job-output.txt").decode(
        "utf-8", errors="replace"
    )
    success_log = request_bytes(f"{success['log_url']}job-output.txt").decode(
        "utf-8", errors="replace"
    )
    source_remote = fetch_change(1001023)
    target_remote = fetch_change(1000516)
    checks = {
        "source_candidate_commit": (
            case["source"]["candidate_commit"] == "978799539e019141d8b0710d09bf91c956976079"
            and url_available(case["source"]["patch_url"])
        ),
        "target_candidate_commit": target_remote["revision"] == case["targets"][0]["commit"],
        "source_created": (
            source_remote["detail"].get("created") == case["source"]["pull_request"]["created"]
        ),
        "target_created": (
            target_remote["detail"].get("created")
            == case["targets"][0]["pull_request"]["created"]
        ),
        "same_job": failure["job_name"] == success["job_name"] == "cross-cinder-py313",
        "failure_result": failure["result"] == "FAILURE",
        "success_result": success["result"] == "SUCCESS",
        "failure_uses_source_patchset_1": "978799539e019141d8b0710d09bf91c956976079" in failure_inventory,
        "failure_omits_target_change": "change: '1000516'" not in failure_inventory,
        "success_uses_source_patchset_2": "477af6b620bab5010fd8db17e5ae2d2b2a2817ad" in success_inventory,
        "success_includes_target_change": (
            "change: '1000516'" in success_inventory
            and "913fa91a8eee20bf852387fe8c01a2d3d45cb87e" in success_inventory
        ),
        "failure_is_labeled_test": (
            "TestModelsSyncMySQL.test_models_sync" in failure_log
            and "Models and migration scripts aren't in sync" in failure_log
        ),
        "same_test_passes": (
            "TestModelsSyncMySQL.test_models_sync" in success_log
            and "test_models_sync [" in success_log
            and "] ... ok" in success_log
        ),
    }
    return {
        "case_id": case["case_id"],
        "source_pull_request": 1001023,
        "checks": checks,
        "passed": all(checks.values()),
    }


def audit_case(case: dict[str, Any]) -> dict[str, Any]:
    if case["source"]["host"] == "github.com":
        return audit_github_case(case)
    if case["case_id"] == "opendev-1001023-cinder-impact":
        return audit_cinder_contrast(case)
    source_number = case["source"]["pull_request"]["number"]
    semantic_case = any(
        evidence["level"] == "implementation_proven"
        for target in case["targets"]
        for evidence in target["evidence"]
    )
    if semantic_case:
        source_data = fetch_all_revisions(source_number)
        source_detail = source_data["detail"]
        opening = source_data["revisions"][0]
        source_repository = source_detail["project"]
        source_created = source_detail.get("created")
        source_candidate = opening["commit"]
        source_base = opening["commit_data"]["parents"][0]["commit"]
        source_paths = revision_files(source_number, opening["commit"])
    else:
        source_remote = fetch_change(source_number)
        source_repository = source_remote["detail"]["project"]
        source_created = source_remote["detail"].get("created")
        source_candidate = source_remote["revision"]
        source_base = source_remote["base_commit"]
        source_paths = source_remote["paths"]
    source_checks = {
        "repository": source_repository == case["source"]["repository"],
        "created": source_created == case["source"]["pull_request"]["created"],
        "candidate_commit": source_candidate == case["source"]["candidate_commit"],
        "base_commit": source_base == case["source"]["base_commit"],
        "changed_paths": source_paths == case["source"]["changed_paths"],
        "patch_available": url_available(case["source"]["patch_url"]),
    }
    target_results = []
    for target in case["targets"]:
        target_number = target["pull_request"]["number"]
        target_remote = fetch_change(target_number)
        message = target_remote["commit"].get("message", "")
        dependency_numbers = {int(match.group(2)) for match in DEPENDS_RE.finditer(message)}
        ci_urls = [item.get("ci_url") for item in target["evidence"] if item.get("ci_url")]
        checks = {
            "repository": target_remote["detail"]["project"] == target["repository"],
            "created": target_remote["detail"].get("created") == target["pull_request"]["created"],
            "commit": target_remote["revision"] == target["commit"],
            "changed_paths": target_remote["paths"] == target["changed_paths"],
            "depends_on_statement": source_number in dependency_numbers,
            "ci_urls_available_when_recorded": all(url_available(url) for url in ci_urls),
        }
        target_results.append({
            "repository": target["repository"],
            "pull_request": target_number,
            "checks": checks,
            "passed": all(checks.values()),
        })
    passed = all(source_checks.values()) and all(item["passed"] for item in target_results)
    return {
        "case_id": case["case_id"],
        "source_pull_request": source_number,
        "source_checks": source_checks,
        "targets": target_results,
        "passed": passed,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample-size", type=int, default=20)
    parser.add_argument("--output", type=Path, default=ROOT / "audit-results.jsonl")
    args = parser.parse_args()
    sample = deterministic_sample(load_cases(), args.sample_size)
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(audit_case, case): case["case_id"] for case in sample}
        for future in concurrent.futures.as_completed(futures):
            case_id = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:
                results.append({"case_id": case_id, "passed": False, "error": str(exc)})
    results.sort(key=lambda item: item["case_id"])
    with args.output.open("w", encoding="utf-8") as handle:
        for item in results:
            handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
    passed = sum(item["passed"] for item in results)
    print(json.dumps({
        "sample_size": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "sample_case_ids": [item["case_id"] for item in results],
    }, indent=2, ensure_ascii=False))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

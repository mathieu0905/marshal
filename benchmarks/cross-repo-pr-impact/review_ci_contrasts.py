#!/usr/bin/env python3
"""Materialize the primary semantic review of composition-verified CI contrasts."""

from __future__ import annotations

import argparse
import base64
import gzip
import json
from pathlib import Path
from typing import Any

from collect_opendev import GERRIT, ROOT, gerrit_json, request_bytes
from mine_ci_contrasts import BUILD_RE


REVIEWS: dict[int, dict[str, Any]] = {
    997527: {
        "decision": "rejected",
        "reason": "same_revision_had_prior_successes_and_failure_is_not_semantically_aligned",
        "failure_markers": [
            "TestNovaModelBuilder.test_add_physical_layer_aggregates_timeout",
            "Expected 'get_compute_node_list' to not have been called",
        ],
        "success_markers": [
            "TestNovaModelBuilder.test_add_physical_layer_aggregates_timeout",
            "] ... ok",
        ],
        "success_absent_markers": [],
        "target_patch_markers": ["Keep fork as the default"],
        "assessment": (
            "The selected Watcher unit-test failure does not exercise the multiprocessing "
            "selection changed by the companion patch. The same source patchset had already "
            "passed this job three times before the selected failure, so the contrast is "
            "consistent with a flaky test rather than a cross-repository repair."
        ),
    },
    999031: {
        "decision": "accepted",
        "reason": "failure_signature_matches_target_api_migration",
        "impact_kind": "runtime_api_contract",
        "failure_markers": [
            'PUT /api/datasources/1 HTTP/1.1" 404',
            "404 Client Error: Not Found for url:",
        ],
        "success_markers": [
            "PUT /api/datasources/uid/",
            'HTTP/1.1" 200',
        ],
        "success_absent_markers": [
            'PUT /api/datasources/1 HTTP/1.1" 404',
        ],
        "target_patch_markers": [
            "Use datasource uids when updating datasources",
            "url = utils.urljoin(self.url, 'uid/')",
            "return datasource['uid']",
        ],
        "assessment": (
            "The failure uses Grafana's disabled numeric-id update endpoint and receives 404. "
            "The companion patch migrates Grafyaml to uid endpoints; the success arm exercises "
            "the uid endpoint twice and receives 200."
        ),
    },
    1001023: {
        "decision": "accepted",
        "reason": "failure_signature_matches_target_test_compatibility_fix",
        "impact_kind": "dependency_or_build_interface",
        "failure_markers": [
            "TestModelsSyncMySQL.test_models_sync",
            "Models and migration scripts aren't in sync",
            "CheckConstraint(",
        ],
        "success_markers": [
            "TestModelsSyncMySQL.test_models_sync",
            "] ... ok",
        ],
        "success_absent_markers": [
            "Models and migration scripts aren't in sync",
        ],
        "target_patch_markers": [
            "Ignore CHECK constraints in test_models_sync",
            "ignore_check_constraints",
            "sqlalchemy.CheckConstraint",
        ],
        "assessment": (
            "The source raises the Alembic version and exposes CHECK-constraint differences in "
            "Cinder's model-sync test. The companion patch filters those exact differences, and "
            "the same named test passes in the composed build."
        ),
    },
    1001103: {
        "decision": "rejected",
        "reason": "target_repairs_external_environment_not_source_induced_breakage",
        "failure_markers": [
            "TASK [openstack_hosts : Install gpg keys]",
            "gpg: packet(6) with unknown version 6",
        ],
        "success_markers": [
            "TASK [openstack_hosts : Install gpg keys]",
        ],
        "success_absent_markers": [
            "gpg: packet(6) with unknown version 6",
        ],
        "target_patch_markers": [
            "Remove Rocky release PQC GPG key",
            "gpg: packet(6) with unknown version 6",
            "rpm -e gpg-pubkey-2ebba43f-6a7b0932",
        ],
        "assessment": (
            "The selected job and companion patch form a real fail-to-pass repair, but not a "
            "source-induced impact. The source changes the Ceph release while the Rocky Linux "
            "job fails because images began receiving an external PQC GPG key on August 11. "
            "The target patch states that this problem affects all stable branches and removes "
            "the image key. The same repair would be required without the source diff, so this "
            "is an environment repair rather than a cross-repository consequence of the source."
        ),
    },
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def fetch_log(log_url: str) -> str:
    payload = request_bytes(f"{log_url}job-output.txt", attempts=2)
    if payload.startswith(b"\x1f\x8b"):
        payload = gzip.decompress(payload)
    return payload.decode("utf-8", errors="replace")


def fetch_patch(change: int, revision: str) -> str:
    encoded = request_bytes(f"{GERRIT}/changes/{change}/revisions/{revision}/patch?download")
    return base64.b64decode(encoded).decode("utf-8", errors="replace")


def marker_evidence(text: str, markers: list[str]) -> list[dict[str, Any]]:
    lines = text.splitlines()
    evidence = []
    for marker in markers:
        matches = [
            {"line": index + 1, "text": line[-800:]}
            for index, line in enumerate(lines)
            if marker in line
        ]
        evidence.append({"marker": marker, "matches": matches[:5], "count": len(matches)})
    return evidence


def job_history(change: int, patchset: int, job: str) -> list[dict[str, Any]]:
    detail = gerrit_json(f"/changes/{change}/detail", [("o", "MESSAGES")])
    history = []
    for message in detail.get("messages", []):
        if message.get("_revision_number") != patchset:
            continue
        for match in BUILD_RE.finditer(message.get("message", "")):
            record = match.groupdict()
            if record["job"] == job:
                history.append({
                    "reported_at": message.get("date"),
                    "result": record["result"],
                    "build_uuid": record["uuid"],
                })
    return sorted(history, key=lambda item: item["reported_at"] or "")


def review(record: dict[str, Any]) -> dict[str, Any]:
    source_pr = record["source_pr"]
    annotation = REVIEWS[source_pr]
    failure_log = fetch_log(record["failure_log_url"])
    success_log = fetch_log(record["success_log_url"])
    target_patch = fetch_patch(record["target_pr"], record["target_commit"])
    history = job_history(
        source_pr,
        record["source_before_revision"]["number"],
        record["job"],
    )
    failure_evidence = marker_evidence(failure_log, annotation["failure_markers"])
    success_evidence = marker_evidence(success_log, annotation["success_markers"])
    success_absence = marker_evidence(success_log, annotation["success_absent_markers"])
    target_evidence = marker_evidence(target_patch, annotation["target_patch_markers"])
    selected_failure_index = next(
        (
            index
            for index, item in enumerate(history)
            if item["build_uuid"] == record["failure_build_uuid"]
        ),
        None,
    )
    prior_history = history[:selected_failure_index] if selected_failure_index is not None else []
    checks = {
        "failure_markers_present": all(item["count"] > 0 for item in failure_evidence),
        "success_markers_present": all(item["count"] > 0 for item in success_evidence),
        "failure_signature_absent_from_success": all(item["count"] == 0 for item in success_absence),
        "target_patch_markers_present": all(item["count"] > 0 for item in target_evidence),
        "selected_failure_found_in_source_history": selected_failure_index is not None,
    }
    return {
        "source_pr": source_pr,
        "source_repository": record["source_repository"],
        "source_subject": record["source_subject"],
        "target_pr": record["target_pr"],
        "target_repository": record["target_repository"],
        "target_subject": record["target_subject"],
        "job": record["job"],
        "decision": annotation["decision"],
        "reason": annotation["reason"],
        "impact_kind": annotation.get("impact_kind"),
        "assessment": annotation["assessment"],
        "review_kind": "primary_manual_semantic_review",
        "independent_blind_review": False,
        "automated_checks": checks,
        "source_revision_job_history": history,
        "same_revision_successes_before_selected_failure": sum(
            item["result"] == "SUCCESS" for item in prior_history
        ),
        "failure_log_evidence": failure_evidence,
        "success_log_evidence": success_evidence,
        "success_absence_evidence": success_absence,
        "target_patch_evidence": target_evidence,
        "failure_log_url": record["failure_log_url"],
        "success_log_url": record["success_log_url"],
        "target_change_url": f"{GERRIT}/c/{record['target_repository']}/+/{record['target_pr']}",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=ROOT / "candidates" / "ci-contrast-composition-verified.jsonl",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "candidates" / "ci-contrast-semantic-review.jsonl",
    )
    args = parser.parse_args()
    records = load_jsonl(args.input)
    unknown = sorted({item["source_pr"] for item in records} - REVIEWS.keys())
    if unknown:
        raise SystemExit(f"missing primary semantic review for source changes: {unknown}")
    results = [review(item) for item in records]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for item in results:
            handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps({
        "composition_verified": len(results),
        "causal_accepted": sum(item["decision"] == "accepted" for item in results),
        "semantic_rejected": sum(item["decision"] == "rejected" for item in results),
        "all_automated_checks_pass": all(
            all(item["automated_checks"].values()) for item in results
        ),
        "output": str(args.output),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Verify and select a release-quality E1 historical-adaptation dataset."""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from candidate_bounded_foundation import audit_catalogs, load_cases, read_jsonl
from collect_github_spec_candidates import gh_api, pull_files
from materialize_data_ready_set import snapshot_readiness


ROOT = Path(__file__).resolve().parent


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def parse_mapping(value: str) -> tuple[str, str]:
    try:
        key, result = value.rsplit("=", 1)
    except ValueError as error:
        raise argparse.ArgumentTypeError("expected KEY=VALUE") from error
    if not key or not result:
        raise argparse.ArgumentTypeError("expected non-empty KEY=VALUE")
    return key, result


def checks_to_reasons(checks: dict[str, bool]) -> list[str]:
    return [name for name, passed in checks.items() if not passed]


def target_key(repository: str, number: int) -> tuple[str, int]:
    return repository.lower(), int(number)


def load_evidence(dataset_root: Path) -> dict[str, Any]:
    cases = load_cases(dataset_root)
    case_by_id = {item["case_id"]: item for item in cases}
    catalogs = read_json(dataset_root / "candidate-repositories.json")["catalogs"]
    catalog_audit = {
        item["project"]: item for item in audit_catalogs(dataset_root, cases)
    }
    repository_snapshots = {
        item["case_id"]: item
        for item in read_jsonl(dataset_root / "repository-snapshots.jsonl")
    }
    opening_snapshots = {
        (item["source_repository"], int(item["source_pull_request"])): item
        for item in read_jsonl(
            dataset_root / "candidates/github-multi-target-opening-snapshots.jsonl"
        )
    }
    reviews = {
        (item["source_repository"], int(item["source_pull_request"])): item
        for item in read_jsonl(
            dataset_root / "candidates/github-multi-target-manual-review.jsonl"
        )
    }
    target_audits = {
        (
            item["source_repository"],
            int(item["source_pull_request"]),
            item["target_repository"],
            int(item["target_pull_request"]),
        ): item
        for item in read_jsonl(
            dataset_root / "candidates/github-multi-target-target-audit.jsonl"
        )
    }
    return {
        "case_by_id": case_by_id,
        "catalogs": catalogs,
        "catalog_audit": catalog_audit,
        "repository_snapshots": repository_snapshots,
        "opening_snapshots": opening_snapshots,
        "reviews": reviews,
        "target_audits": target_audits,
    }


def local_case_audit(
    selected: dict[str, Any], evidence: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    case_id = selected["case_id"]
    project = selected["project"]
    case = evidence["case_by_id"].get(case_id)
    if case is None:
        return ({
            "case_id": case_id,
            "project": project,
            "local_status": "failed",
            "local_checks": {"case_exists": False},
            "local_failure_reasons": ["case_exists"],
        }, None)

    source = case["source"]
    source_pr = source["pull_request"]
    source_key = (source["repository"], int(source_pr["number"]))
    catalog_row = evidence["catalog_audit"].get(project, {})
    catalog = evidence["catalogs"].get(project, {})
    snapshot = evidence["repository_snapshots"].get(case_id)
    opening = evidence["opening_snapshots"].get(source_key)
    review = evidence["reviews"].get(source_key)
    readiness = (
        snapshot_readiness(set(catalog.get("repositories", [])), snapshot)
        if snapshot is not None
        else {"catalog_snapshot_exact_match": False, "snapshot_complete": False}
    )

    accepted_decisions = [] if review is None else [
        item for item in review.get("target_decisions", [])
        if item.get("decision") == "accept"
    ]
    decisions_by_key = {
        target_key(item["repository"], item["pull_request"]): item
        for item in accepted_decisions
    }
    case_targets_by_key = {
        target_key(item["repository"], item["pull_request"]["number"]): item
        for item in case["targets"]
    }

    target_checks: list[dict[str, Any]] = []
    for key, target in sorted(case_targets_by_key.items()):
        decision = decisions_by_key.get(key)
        audit_key = (*source_key, target["repository"], int(target["pull_request"]["number"]))
        audit = evidence["target_audits"].get(audit_key)
        durable = (audit or {}).get("target", {})
        target_pr = target["pull_request"]
        evidence_rows = target.get("evidence", [])
        relations = [
            item for item in case["relations"]
            if item["target_repository"] == target["repository"]
            and item["evidence_url"] == target_pr["url"]
        ]
        checks = {
            "accepted_manual_decision": decision is not None,
            "manual_reason_matches": bool(decision) and len(evidence_rows) == 1
            and evidence_rows[0].get("statement") == decision.get("reason"),
            "e1_evidence_level": len(evidence_rows) == 1
            and evidence_rows[0].get("level") == "specification_proven"
            and evidence_rows[0].get("kind")
            == "explicit_specification_to_implementation_reference",
            "evidence_url_matches": len(evidence_rows) == 1
            and evidence_rows[0].get("url") == target_pr["url"]
            and len(relations) == 1,
            "durable_target_audit_passed": bool(audit)
            and audit.get("status") == "passed"
            and all(audit.get("checks", {}).values()),
            "target_repository_matches": durable.get("url") == target_pr["url"],
            "target_title_matches": durable.get("title") == target_pr["subject"],
            "target_branch_matches": durable.get("base_branch") == target_pr["branch"],
            "target_timestamps_match": durable.get("created_at") == target_pr["created"]
            and durable.get("merged_at") == target_pr["submitted"],
            "target_commit_matches": durable.get("head_commit") == target["commit"],
            "target_paths_match": durable.get("changed_paths")
            == target["changed_paths"],
            "target_marked_merged": target_pr.get("status") == "MERGED",
            "target_created_after_source": target_pr.get("created", "")
            >= source_pr.get("created", ""),
        }
        target_checks.append({
            "repository": target["repository"],
            "pull_request": target_pr["number"],
            "checks": checks,
            "failure_reasons": checks_to_reasons(checks),
        })

    checks = {
        "case_exists": True,
        "selection_project_matches": case["project"] == project,
        "github_source": source.get("host") == "github.com"
        and source_pr.get("provider") == "github",
        "catalog_label_independent": bool(catalog_row.get("current_label_independent")),
        "catalog_formal_eligible": bool(catalog_row.get("current_formal_eligible")),
        "catalog_snapshot_exact": bool(readiness["catalog_snapshot_exact_match"]),
        "catalog_snapshot_complete": bool(readiness["snapshot_complete"]),
        "source_opening_snapshot_recovered": bool(opening)
        and opening.get("status") == "recovered",
        "source_base_commit_matches": bool(opening)
        and opening.get("base_commit") == source["base_commit"],
        "source_candidate_commit_matches": bool(opening)
        and opening.get("candidate_commit") == source["candidate_commit"],
        "source_paths_match": bool(opening)
        and opening.get("changed_paths") == source["changed_paths"],
        "source_branch_matches": bool(opening)
        and opening.get("branch") == source_pr["branch"],
        "source_observation_cutoff_matches": bool(opening)
        and opening.get("observation_cutoff") == source_pr["created"],
        "source_subject_matches": bool(opening)
        and opening.get("subject") == source_pr["subject"],
        "source_marked_merged": source_pr.get("status") == "MERGED",
        "manual_case_accepted": bool(review)
        and review.get("decision") == "accept_for_target_audit",
        "target_set_matches_manual_review": set(case_targets_by_key)
        == set(decisions_by_key),
        "targets_nonempty": bool(case_targets_by_key),
        "targets_unique_within_case": len(case_targets_by_key) == len(case["targets"]),
        "all_target_local_checks_pass": bool(target_checks)
        and all(all(item["checks"].values()) for item in target_checks),
    }
    record = {
        "case_id": case_id,
        "project": project,
        "source_repository": source["repository"],
        "source_pull_request": source_pr["number"],
        "target_relation_count": len(case["targets"]),
        "local_status": "passed" if all(checks.values()) else "failed",
        "local_checks": checks,
        "local_failure_reasons": checks_to_reasons(checks),
        "target_local_audits": target_checks,
        "snapshot_statuses": readiness.get("snapshot_statuses", {}),
    }
    return record, case


def live_case_audit(case: dict[str, Any]) -> dict[str, Any]:
    source = case["source"]
    source_pr = source["pull_request"]
    repository = source["repository"]
    number = source_pr["number"]
    try:
        pull = gh_api(f"repos/{repository}/pulls/{number}")
        comparison = gh_api(
            f"repos/{repository}/compare/"
            f"{source['base_commit']}...{source['candidate_commit']}"
        )
        comparison_paths = sorted({item["filename"] for item in comparison.get("files", [])})
        source_checks = {
            "source_live_merged": bool(pull.get("merged_at"))
            and pull.get("state") == "closed",
            "source_live_url_matches": pull.get("html_url") == source_pr["url"],
            "source_live_branch_matches": pull.get("base", {}).get("ref")
            == source_pr["branch"],
            "source_live_timestamps_match": pull.get("created_at") == source_pr["created"]
            and pull.get("merged_at") == source_pr["submitted"],
            "source_comparison_available": comparison.get("status") is not None,
            "source_comparison_paths_match": comparison_paths
            == sorted(source["changed_paths"]),
        }
        target_results = []
        source_link = f"github.com/{repository}/pull/{number}".lower()
        for target in case["targets"]:
            target_pr = target["pull_request"]
            target_pull = gh_api(
                f"repos/{target['repository']}/pulls/{target_pr['number']}"
            )
            paths = pull_files(target["repository"], target_pr["number"])
            checks = {
                "target_live_merged": bool(target_pull.get("merged_at"))
                and target_pull.get("state") == "closed",
                "target_live_url_matches": target_pull.get("html_url")
                == target_pr["url"],
                "target_live_branch_matches": target_pull.get("base", {}).get("ref")
                == target_pr["branch"],
                "target_live_timestamps_match": target_pull.get("created_at")
                == target_pr["created"]
                and target_pull.get("merged_at") == target_pr["submitted"],
                "target_live_head_matches": target_pull.get("head", {}).get("sha")
                == target["commit"],
                "target_live_paths_match": paths == sorted(target["changed_paths"]),
                "target_live_body_links_source": source_link
                in (target_pull.get("body") or "").lower(),
            }
            target_results.append({
                "repository": target["repository"],
                "pull_request": target_pr["number"],
                "checks": checks,
                "failure_reasons": checks_to_reasons(checks),
            })
        checks = {
            **source_checks,
            "all_target_live_checks_pass": bool(target_results)
            and all(all(item["checks"].values()) for item in target_results),
        }
        return {
            "live_status": "passed" if all(checks.values()) else "failed",
            "live_checks": checks,
            "live_failure_reasons": checks_to_reasons(checks),
            "target_live_audits": target_results,
        }
    except Exception as error:
        return {
            "live_status": "fetch_failed",
            "live_checks": {},
            "live_failure_reasons": ["live_api_failure"],
            "live_error": str(error),
            "target_live_audits": [],
        }


def select_verified(
    audit_rows: list[dict[str, Any]],
    candidate_order: list[str],
    preferred_order: list[str],
    quotas: dict[str, int],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    by_id = {item["case_id"]: item for item in audit_rows}
    preferred = set(preferred_order)
    ordered = [
        *[item for item in preferred_order if item in by_id],
        *[item for item in candidate_order if item not in preferred],
    ]
    selected: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    seen_sources: set[tuple[str, int]] = set()
    seen_targets: set[tuple[str, int]] = set()
    for case_id in ordered:
        row = by_id[case_id]
        project = row["project"]
        if row.get("verification_status") != "verified":
            continue
        if project not in quotas or counts[project] >= quotas[project]:
            continue
        source_key = target_key(row["source_repository"], row["source_pull_request"])
        relation_keys = {
            target_key(item["repository"], item["pull_request"])
            for item in row["target_local_audits"]
        }
        reasons = []
        if source_key in seen_sources:
            reasons.append("duplicate_source_pr_in_release")
        if relation_keys & seen_targets:
            reasons.append("duplicate_target_pr_in_release")
        if reasons:
            conflicts.append({"case_id": case_id, "reasons": reasons})
            continue
        selected.append(row)
        counts[project] += 1
        seen_sources.add(source_key)
        seen_targets.update(relation_keys)
    backfills = Counter(
        item["project"] for item in selected if item["case_id"] not in preferred
    )
    return selected, conflicts, dict(backfills)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-selection", type=Path, required=True)
    parser.add_argument("--preferred-selection", type=Path, required=True)
    parser.add_argument("--project-quota", action="append", type=parse_mapping, required=True)
    parser.add_argument("--project-split", action="append", type=parse_mapping, required=True)
    parser.add_argument("--dataset-dir", type=Path, default=ROOT)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--skip-live", action="store_true")
    args = parser.parse_args()

    started_at = dt.datetime.now(dt.timezone.utc).isoformat()
    quotas = {key: int(value) for key, value in args.project_quota}
    splits = dict(args.project_split)
    if set(quotas) != set(splits):
        raise SystemExit("--project-quota and --project-split projects must match")
    if len(quotas) != len(args.project_quota) or len(splits) != len(args.project_split):
        raise SystemExit("duplicate project mapping")
    candidate_selection = read_json(args.candidate_selection)
    preferred_selection = read_json(args.preferred_selection)
    candidates = candidate_selection["cases"]
    candidate_ids = [item["case_id"] for item in candidates]
    preferred_ids = [item["case_id"] for item in preferred_selection["cases"]]
    if not set(preferred_ids) <= set(candidate_ids):
        raise SystemExit("preferred selection is not a subset of candidate selection")

    evidence = load_evidence(args.dataset_dir.resolve())
    records: list[dict[str, Any]] = []
    live_jobs: list[tuple[int, dict[str, Any]]] = []
    for selected in candidates:
        record, case = local_case_audit(selected, evidence)
        records.append(record)
        if record["local_status"] == "passed" and case is not None and not args.skip_live:
            live_jobs.append((len(records) - 1, case))

    if args.skip_live:
        for record in records:
            record.update({
                "live_status": "not_assessed",
                "live_checks": {},
                "live_failure_reasons": [],
                "target_live_audits": [],
                "verification_status": (
                    "verified" if record["local_status"] == "passed" else "rejected"
                ),
            })
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
            results = list(executor.map(lambda item: live_case_audit(item[1]), live_jobs))
        for (index, _case), live_result in zip(live_jobs, results):
            records[index].update(live_result)
        for record in records:
            if "live_status" not in record:
                record.update({
                    "live_status": "not_run_due_to_local_failure",
                    "live_checks": {},
                    "live_failure_reasons": [],
                    "target_live_audits": [],
                })
            record["verification_status"] = (
                "verified"
                if record["local_status"] == "passed"
                and record["live_status"] == "passed"
                else "rejected"
            )

    selected, conflicts, backfills = select_verified(
        records, candidate_ids, preferred_ids, quotas
    )
    selected_ids = {item["case_id"] for item in selected}
    conflict_by_id = {item["case_id"]: item["reasons"] for item in conflicts}
    final_rows = [{
        "case_id": item["case_id"],
        "project": item["project"],
        "release_split": splits[item["project"]],
        "evidence_layer": "E1",
        "verification_status": "verified",
        "case_path": f"cases/{item['case_id']}.json",
        "audit_record_id": item["case_id"],
        "target_relation_count": item["target_relation_count"],
    } for item in selected]
    rejected_rows = []
    for item in records:
        if item["case_id"] in selected_ids:
            continue
        if item["verification_status"] != "verified":
            reasons = [
                *item["local_failure_reasons"], *item["live_failure_reasons"]
            ]
            disposition = "verification_failed"
        elif item["case_id"] in conflict_by_id:
            reasons = conflict_by_id[item["case_id"]]
            disposition = "duplicate_conflict"
        else:
            reasons = ["project_quota_filled"]
            disposition = "verified_reserve_not_selected"
        rejected_rows.append({
            "case_id": item["case_id"],
            "project": item["project"],
            "verification_status": item["verification_status"],
            "disposition": disposition,
            "reasons": reasons,
        })

    selected_counts = Counter(item["project"] for item in selected)
    verified_counts = Counter(
        item["project"] for item in records if item["verification_status"] == "verified"
    )
    status_counts = Counter(item["verification_status"] for item in records)
    live_counts = Counter(item["live_status"] for item in records)
    success = all(selected_counts[project] == count for project, count in quotas.items())
    metrics = {
        "schema_version": "1.0",
        "verification_mode": "local_only_smoke" if args.skip_live else "local_and_live",
        "candidate_cases_audited": len(records),
        "preferred_cases": len(preferred_ids),
        "verified_candidate_cases": status_counts["verified"],
        "rejected_candidate_cases": status_counts["rejected"],
        "verified_candidates_by_project": dict(sorted(verified_counts.items())),
        "live_statuses": dict(sorted(live_counts.items())),
        "final_case_count": len(final_rows),
        "final_project_counts": dict(sorted(selected_counts.items())),
        "final_split_counts": dict(sorted(Counter(item["release_split"] for item in final_rows).items())),
        "final_target_relation_count": sum(item["target_relation_count"] for item in final_rows),
        "backfills_by_project": dict(sorted(backfills.items())),
        "duplicate_conflicts": len(conflicts),
        "project_quotas": quotas,
        "success": success,
        "evidence_scope": "E1_historical_adaptation",
        "strict_E2_count_in_100_case_source_pool": 1,
        "strict_E2_count_in_final_50": 0,
        "marshal_execution_completed": False,
    }
    output_dir = args.output_dir.resolve()
    write_jsonl(output_dir / "candidate-audit.jsonl", records)
    write_jsonl(output_dir / "final-index.jsonl", final_rows)
    write_jsonl(output_dir / "rejected.jsonl", rejected_rows)
    write_json(output_dir / "metrics.json", metrics)
    write_json(output_dir / "run-manifest.json", {
        "schema_version": "1.0",
        "started_at": started_at,
        "completed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "command": sys.argv,
        "dataset_dir": str(args.dataset_dir.resolve()),
        "candidate_selection": str(args.candidate_selection.resolve()),
        "preferred_selection": str(args.preferred_selection.resolve()),
        "workers": args.workers,
        "live_checks_run": not args.skip_live,
        "outputs": [
            "candidate-audit.jsonl", "final-index.jsonl", "rejected.jsonl", "metrics.json"
        ],
    })
    print(json.dumps(metrics, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Validate cross-repository PR impact cases and print coverage statistics."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
CASE_KINDS = {"independent_positive", "hard_control", "config_regression"}
SPLITS = {"development", "validation", "test", "config-regression"}
EVIDENCE_LEVELS = {
    "executed", "ci_contrast_proven", "implementation_proven", "specification_proven",
    "coordination_proven", "config_derived",
}
IMPACT_KINDS = {
    "unclassified",
    "transaction_encoding", "shared_type_serialization", "specification_or_vector",
    "wire_format", "identifier_or_address_allocation", "dependency_or_build_interface",
    "runtime_api_contract", "data_schema", "deployment_configuration", "test_contract",
    "other_cross_repo_contract",
}


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def fail(message: str) -> None:
    raise SystemExit(f"validation failed: {message}")


def require(mapping: dict[str, Any], keys: tuple[str, ...], location: str) -> None:
    missing = [key for key in keys if key not in mapping]
    if missing:
        fail(f"{location} missing fields: {', '.join(missing)}")


def validate_url(value: Any, location: str) -> None:
    if not isinstance(value, str):
        fail(f"{location} must be a URL string")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        fail(f"{location} is not an HTTP(S) URL")


def validate_strings(values: Any, location: str, *, nonempty: bool = False) -> None:
    if not isinstance(values, list) or (nonempty and not values):
        fail(f"{location} must be{' a non-empty' if nonempty else ''} string list")
    if any(not isinstance(value, str) or not value for value in values):
        fail(f"{location} contains a non-string or empty value")
    if len(values) != len(set(values)):
        fail(f"{location} contains duplicate values")


def validate_commands(commands: Any, location: str) -> None:
    if not isinstance(commands, list):
        fail(f"{location} must be a command list")
    for index, command in enumerate(commands):
        if not isinstance(command, list) or not command or any(not isinstance(arg, str) for arg in command):
            fail(f"{location}[{index}] must be a non-empty argument array")


def validate_pull_request(record: Any, location: str) -> None:
    if not isinstance(record, dict):
        fail(f"{location} must be an object")
    require(record, ("provider", "number", "change_id", "url", "status", "subject", "branch", "created", "submitted"), location)
    if record["provider"] not in {"gerrit", "github"}:
        fail(f"{location}.provider is unsupported")
    if not isinstance(record["number"], int) or record["number"] < 1:
        fail(f"{location}.number must be positive")
    for key in ("change_id", "status", "subject", "branch", "created", "submitted"):
        if not isinstance(record[key], str) or not record[key]:
            fail(f"{location}.{key} must be a non-empty string")
    validate_url(record["url"], f"{location}.url")


def validate_case_shape(case: Any, location: str) -> None:
    if not isinstance(case, dict):
        fail(f"{location} must contain an object")
    require(case, ("schema_version", "case_id", "project", "split", "case_kind", "source", "relations", "targets", "label_source", "licenses", "provenance"), location)
    if case["schema_version"] != "1.1":
        fail(f"{location}.schema_version is unsupported")
    if case["split"] not in SPLITS or case["case_kind"] not in CASE_KINDS:
        fail(f"{location} has an unsupported split or case kind")
    source = case["source"]
    require(source, ("host", "repository", "pull_request", "base_commit", "candidate_commit", "changed_paths", "patch_url"), f"{location}.source")
    validate_pull_request(source["pull_request"], f"{location}.source.pull_request")
    if "/" not in source["repository"]:
        fail(f"{location}.source.repository must be owner/repo")
    for key in ("base_commit", "candidate_commit"):
        if not isinstance(source[key], str) or not SHA_PATTERN.fullmatch(source[key]):
            fail(f"{location}.source.{key} must be a full Git commit")
    validate_strings(source["changed_paths"], f"{location}.source.changed_paths", nonempty=True)
    validate_url(source["patch_url"], f"{location}.source.patch_url")
    if not isinstance(case["relations"], list) or not case["relations"]:
        fail(f"{location}.relations must be non-empty")
    for index, relation in enumerate(case["relations"]):
        where = f"{location}.relations[{index}]"
        require(relation, ("source_repository", "target_repository", "relation_kind", "evidence_url"), where)
        validate_url(relation["evidence_url"], f"{where}.evidence_url")
    if not isinstance(case["targets"], list) or not case["targets"]:
        fail(f"{location}.targets must be non-empty")
    for index, target in enumerate(case["targets"]):
        where = f"{location}.targets[{index}]"
        require(target, (
            "repository", "pull_request", "commit", "changed_paths", "label_scope",
            "impact_kind", "impact_kind_source", "expected_checks", "evidence",
        ), where)
        validate_pull_request(target["pull_request"], f"{where}.pull_request")
        if not SHA_PATTERN.fullmatch(target["commit"]):
            fail(f"{where}.commit must be a full Git commit")
        validate_strings(target["changed_paths"], f"{where}.changed_paths", nonempty=True)
        if target["label_scope"] not in {"known_coordination", "causal_impact"}:
            fail(f"{where}.label_scope is unsupported")
        if target["impact_kind"] not in IMPACT_KINDS:
            fail(f"{where}.impact_kind is unsupported")
        if target["impact_kind_source"] not in {"manual", "unclassified"}:
            fail(f"{where}.impact_kind_source is unsupported")
        if target["impact_kind_source"] == "unclassified" and target["impact_kind"] != "unclassified":
            fail(f"{where} has an automatic impact kind without a manual label")
        checks = target["expected_checks"]
        require(checks, ("label_kind", "paths", "symbols", "tests", "commands", "expected_result"), f"{where}.expected_checks")
        if checks["label_kind"] not in {"unavailable", "manually_curated", "ci_observed", "executed"}:
            fail(f"{where}.expected_checks.label_kind is unsupported")
        validate_strings(checks["paths"], f"{where}.expected_checks.paths")
        validate_strings(checks["symbols"], f"{where}.expected_checks.symbols")
        validate_strings(checks["tests"], f"{where}.expected_checks.tests")
        validate_commands(checks["commands"], f"{where}.expected_checks.commands")
        if checks["expected_result"] not in {
            "coordination_observed", "coordinated_change_required", "cross_repo_check_required",
            "no_cross_repo_impact", "pass", "fail",
            "fail_without_companion_pass_with_companion",
            "not_exercised_without_source_pass_with_source",
        }:
            fail(f"{where}.expected_checks.expected_result is unsupported")
        if checks["label_kind"] == "unavailable" and any(
            checks[key] for key in ("paths", "symbols", "tests", "commands")
        ):
            fail(f"{where} has inferred checks despite unavailable check labels")
        if target["label_scope"] == "known_coordination" and checks["label_kind"] != "unavailable":
            fail(f"{where} gives impact checks to a coordination-only target")
        if not isinstance(target["evidence"], list) or not target["evidence"]:
            fail(f"{where}.evidence must be non-empty")
        for evidence_index, evidence in enumerate(target["evidence"]):
            evidence_where = f"{where}.evidence[{evidence_index}]"
            require(evidence, ("level", "kind", "url", "statement"), evidence_where)
            if evidence["level"] not in EVIDENCE_LEVELS:
                fail(f"{evidence_where}.level is unsupported")
            validate_url(evidence["url"], f"{evidence_where}.url")
            if evidence.get("ci_url") is not None:
                validate_url(evidence["ci_url"], f"{evidence_where}.ci_url")
    label = case["label_source"]
    require(label, ("kind", "derived_from_marshal_config"), f"{location}.label_source")
    if not isinstance(label["derived_from_marshal_config"], bool):
        fail(f"{location}.label_source.derived_from_marshal_config must be boolean")
    if not isinstance(case["licenses"], list) or not case["licenses"]:
        fail(f"{location}.licenses must be non-empty")
    for index, license_record in enumerate(case["licenses"]):
        where = f"{location}.licenses[{index}]"
        require(license_record, ("repository", "spdx", "evidence_url"), where)
        validate_url(license_record["evidence_url"], f"{where}.evidence_url")
    require(case["provenance"], ("collector", "collected_at", "query"), f"{location}.provenance")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-count", type=int)
    args = parser.parse_args()

    licenses_document = read_json(ROOT / "licenses.json")
    license_by_repo = {item["repository"]: item for item in licenses_document["repositories"]}
    index = []
    with (ROOT / "index.jsonl").open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if line.strip():
                try:
                    index.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    fail(f"index line {line_number}: {exc}")

    if args.expected_count is not None and len(index) != args.expected_count:
        fail(f"expected {args.expected_count} index records, found {len(index)}")
    case_ids = [item["case_id"] for item in index]
    if len(case_ids) != len(set(case_ids)):
        fail("duplicate case_id in index")

    cases = []
    seen_sources = set()
    source_pr_keys = set()
    target_pr_keys = set()
    indexed_paths = set()
    for item in index:
        path = ROOT / item["path"]
        if not path.is_file():
            fail(f"missing case file {item['path']}")
        indexed_paths.add(path.resolve())
        case = read_json(path)
        validate_case_shape(case, item["path"])
        if case["case_id"] != item["case_id"]:
            fail(f"case_id mismatch in {item['path']}")
        source = case["source"]
        source_key = (source["host"], source["repository"], source["pull_request"]["number"])
        if source_key in seen_sources:
            fail(f"duplicate source PR {source_key}")
        seen_sources.add(source_key)
        source_pr_keys.add((source["host"], source["repository"], source["pull_request"]["number"]))
        relation_targets = {relation["target_repository"] for relation in case["relations"]}
        target_repositories = {target["repository"] for target in case["targets"]}
        if source["repository"] in target_repositories:
            fail(f"same-repository target in {case['case_id']}")
        if relation_targets != target_repositories:
            fail(f"relation/target mismatch in {case['case_id']}")
        if case["label_source"]["derived_from_marshal_config"]:
            if case["label_source"]["kind"] != "marshal_configuration":
                fail(f"configuration label mismatch in {case['case_id']}")
        elif case["case_kind"] == "independent_positive":
            if case["label_source"]["kind"] == "marshal_configuration":
                fail(f"independent case uses Marshal label in {case['case_id']}")
        case_license_repos = {item["repository"] for item in case["licenses"]}
        expected_license_repos = {source["repository"], *target_repositories}
        if case_license_repos != expected_license_repos:
            fail(f"license repository mismatch in {case['case_id']}")
        for repository in case_license_repos:
            if repository not in license_by_repo:
                fail(f"missing global license for {repository}")
        for target in case["targets"]:
            target_pr_keys.add((source["host"], target["repository"], target["pull_request"]["number"]))
            for evidence_item in target["evidence"]:
                if evidence_item["level"] not in {"executed", "ci_contrast_proven"}:
                    continue
                if not target["expected_checks"]["commands"]:
                    fail(f"executed evidence has no command in {case['case_id']}")
                result_path = evidence_item.get("result_path")
                if not result_path or not (ROOT / result_path).is_file():
                    fail(f"executed evidence has no result file in {case['case_id']}")
                result_rows = [
                    json.loads(line)
                    for line in (ROOT / result_path).read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
                commands = target["expected_checks"]["commands"]
                if evidence_item["level"] == "executed":
                    matching_results = [
                        row
                        for row in result_rows
                        if row.get("repository") == target["repository"]
                        and row.get("git_commit") == target["commit"]
                        and row.get("command") in commands
                        and row.get("matched") is True
                    ]
                else:
                    matching_results = [
                        row for row in result_rows
                        if row.get("case_id") == case["case_id"]
                        and row.get("repository") == target["repository"]
                        and row.get("matched") is True
                    ]
                    observed_contrast = {
                        (row.get("variant"), row.get("result"))
                        for row in matching_results
                    }
                    required_contrast = {
                        ("source_candidate_with_target_base", "fail"),
                        ("source_candidate_with_target_candidate", "pass"),
                    }
                    if not required_contrast <= observed_contrast:
                        fail(f"CI contrast lacks fail/pass variants in {case['case_id']}")
                if not matching_results:
                    fail(f"execution evidence does not match target in {case['case_id']}")
        cases.append(case)

    overlapping_prs = sorted(source_pr_keys & target_pr_keys)
    if overlapping_prs:
        fail(f"PRs appear as both source and target across cases: {overlapping_prs}")

    inputs = [
        json.loads(line)
        for line in (ROOT / "inputs.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    input_by_id = {item.get("case_id"): item for item in inputs}
    if len(input_by_id) != len(inputs) or set(input_by_id) != set(case_ids):
        fail("inputs.jsonl does not contain exactly one input for every indexed case")
    for case in cases:
        item = input_by_id[case["case_id"]]
        if set(item) != {
            "case_id", "observation_cutoff", "source", "candidate_repository_catalog",
            "candidate_repository_snapshots",
        }:
            fail(f"input has missing or unknown fields in {case['case_id']}")
        expected_catalog = f"candidate-repositories.json#{case['project']}"
        if item["candidate_repository_catalog"] != expected_catalog:
            fail(f"input references an unsupported repository catalog in {case['case_id']}")
        expected_snapshots = f"repository-snapshots.jsonl#{case['case_id']}"
        if item["candidate_repository_snapshots"] != expected_snapshots:
            fail(f"input references unsupported repository snapshots in {case['case_id']}")
        source = case["source"]
        expected_source = {
            "host": source["host"],
            "repository": source["repository"],
            "pull_request_number": source["pull_request"]["number"],
            "subject": source["pull_request"]["subject"],
            "base_commit": source["base_commit"],
            "candidate_commit": source["candidate_commit"],
            "changed_paths": source["changed_paths"],
            "patch_url": source["patch_url"],
        }
        if item["source"] != expected_source:
            fail(f"sanitized input/source mismatch in {case['case_id']}")
        if item["observation_cutoff"] != source["pull_request"]["created"]:
            fail(f"input cutoff mismatch in {case['case_id']}")

    repository_catalog = read_json(ROOT / "candidate-repositories.json")
    if set(repository_catalog) != {"schema_version", "catalogs"}:
        fail("candidate repository catalog has missing or unknown fields")
    if repository_catalog["schema_version"] != "2.0":
        fail("candidate repository catalog has unsupported schema version")
    catalogs = repository_catalog["catalogs"]
    if not isinstance(catalogs, dict) or not catalogs:
        fail("candidate repository catalogs must be a non-empty object")
    for name, catalog in catalogs.items():
        if set(catalog) != {"repositories"}:
            fail(f"candidate repository catalog {name} has unknown fields")
        validate_strings(catalog["repositories"], f"candidate-repositories.catalogs.{name}")
    for case in cases:
        catalog = catalogs.get(case["project"])
        if catalog is None:
            fail(f"missing candidate repository catalog for {case['project']}")
        required_targets = {target["repository"] for target in case["targets"]}
        if not required_targets <= set(catalog["repositories"]):
            fail(f"candidate repository catalog omits a target in {case['case_id']}")

    snapshot_rows = [
        json.loads(line)
        for line in (ROOT / "repository-snapshots.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    snapshot_by_id = {item["case_id"]: item for item in snapshot_rows}
    if len(snapshot_by_id) != len(snapshot_rows) or set(snapshot_by_id) != set(case_ids):
        fail("repository snapshots do not contain exactly one row per case")
    for case in cases:
        row = snapshot_by_id[case["case_id"]]
        cutoff = dt.datetime.fromisoformat(row["observation_cutoff"].replace("Z", "+00:00"))
        input_cutoff = dt.datetime.fromisoformat(
            case["source"]["pull_request"]["created"].replace("Z", "+00:00")
        )
        if input_cutoff.tzinfo is None:
            input_cutoff = input_cutoff.replace(tzinfo=dt.UTC)
        if cutoff != input_cutoff:
            fail(f"repository snapshot cutoff mismatch in {case['case_id']}")
        project_repositories = set(catalogs[case["project"]]["repositories"])
        snapshot_repositories = {item["repository"] for item in row["repositories"]}
        if snapshot_repositories != project_repositories:
            fail(f"repository snapshot/catalog mismatch in {case['case_id']}")
        available = {
            item["repository"] for item in row["repositories"] if item["status"] == "available"
        }
        target_repositories_for_case = {
            target["repository"] for target in case["targets"]
        }
        if not target_repositories_for_case <= available:
            fail(f"a scored target has no pre-cutoff snapshot in {case['case_id']}")
        if not (available - target_repositories_for_case):
            fail(f"case has no available non-target candidate in {case['case_id']}")
        for snapshot in row["repositories"]:
            if snapshot["status"] == "not_created_by_cutoff":
                continue
            if snapshot["status"] != "available":
                fail(f"repository snapshot fetch failed in {case['case_id']}")
            if not SHA_PATTERN.fullmatch(snapshot["commit"]):
                fail(f"repository snapshot has invalid commit in {case['case_id']}")
            committed_at = dt.datetime.fromisoformat(
                snapshot["committed_at"].replace("Z", "+00:00")
            )
            if committed_at > cutoff:
                fail(f"repository snapshot is newer than cutoff in {case['case_id']}")
            validate_url(snapshot["archive_url"], f"repository snapshot in {case['case_id']}")

    actual_case_paths = {path.resolve() for path in (ROOT / "cases").glob("*.json")}
    if actual_case_paths != indexed_paths:
        extra = sorted(str(path.relative_to(ROOT)) for path in actual_case_paths - indexed_paths)
        missing = sorted(str(path.relative_to(ROOT)) for path in indexed_paths - actual_case_paths)
        fail(f"case file/index mismatch: extra={extra}, missing={missing}")

    target_count = sum(len(case["targets"]) for case in cases)
    source_repositories = {case["source"]["repository"] for case in cases}
    target_repositories = {target["repository"] for case in cases for target in case["targets"]}
    edges = {
        (case["source"]["repository"], target["repository"])
        for case in cases
        for target in case["targets"]
    }
    evidence = Counter(
        item["level"]
        for case in cases
        for target in case["targets"]
        for item in target["evidence"]
    )
    impacts = Counter(target["impact_kind"] for case in cases for target in case["targets"])
    kinds = Counter(case["case_kind"] for case in cases)
    print(json.dumps({
        "cases": len(cases),
        "targets": target_count,
        "source_repositories": len(source_repositories),
        "target_repositories": len(target_repositories),
        "directed_repository_relations": len(edges),
        "case_kinds": kinds,
        "evidence_levels": evidence,
        "impact_kinds": impacts,
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

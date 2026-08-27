#!/usr/bin/env python3
"""Materialize the 100-case cross-repository impact discovery dataset."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
CASES = ROOT / "cases"
LEGACY_CASES = ROOT / "cases-spec-retrieval-v1"
COLLECTED_AT = "2026-08-23"
CHANGE_ID = re.compile(r"(?im)^Change-Id:\s*(I[0-9a-f]+)\s*$")

DISTRACTORS = {
    "ethereum": {
        "ChainSafe/lodestar", "Consensys/teku", "OffchainLabs/prysm",
        "besu-eth/besu", "erigontech/erigon", "ethereum/execution-apis",
        "ethereum/execution-specs", "ethereum/go-ethereum", "sigp/lighthouse",
        "status-im/nimbus-eth2",
    },
    "kubernetes": {
        "kubernetes/api", "kubernetes/apimachinery", "kubernetes/client-go",
        "kubernetes/kubernetes", "kubernetes-sigs/cluster-api",
        "kubernetes-sigs/controller-runtime", "kubernetes-sigs/gateway-api",
        "kubernetes-client/java", "kubernetes-client/python",
    },
    "opentelemetry": {
        "open-telemetry/opentelemetry-collector",
        "open-telemetry/opentelemetry-collector-contrib",
        "open-telemetry/opentelemetry-cpp", "open-telemetry/opentelemetry-dotnet",
        "open-telemetry/opentelemetry-erlang", "open-telemetry/opentelemetry-go",
        "open-telemetry/opentelemetry-java", "open-telemetry/opentelemetry-js",
        "open-telemetry/opentelemetry-php", "open-telemetry/opentelemetry-python",
        "open-telemetry/opentelemetry-rust", "open-telemetry/opentelemetry-swift",
    },
    "opencontainers-image": {
        "containerd/containerd", "containers/crun", "containers/image",
        "containers/storage", "moby/moby", "opencontainers/runc",
        "opencontainers/selinux", "oras-project/oras",
    },
    "opencontainers-runtime": {
        "containerd/containerd", "containers/crun", "containers/podman",
        "cri-o/cri-o", "moby/moby", "opencontainers/runc",
        "opencontainers/runtime-tools", "youki-dev/youki",
    },
    "python": {
        "pypa/pip", "pypa/setuptools", "python/cpython", "python/mypy",
        "python/typeshed", "python/typing", "python/typing_extensions",
    },
    "rust": {
        "rust-lang/cargo", "rust-lang/chalk", "rust-lang/miri",
        "rust-lang/polonius", "rust-lang/rust", "rust-lang/rust-analyzer",
        "rust-lang/rust-clippy", "rust-lang/rustfmt",
    },
    "openstack": {
        "openstack/cinder", "openstack/ceilometer", "openstack/glance",
        "openstack/keystone", "openstack/kolla", "openstack/kolla-ansible",
        "openstack/magnum", "openstack/neutron", "openstack/neutron-lib",
        "openstack/nova", "openstack/openstacksdk", "openstack/puppet-keystone",
        "openstack/python-magnumclient", "openstack/requirements",
    },
    "starlingx": {
        "starlingx/apt-ostree", "starlingx/clients", "starlingx/config",
        "starlingx/config-files", "starlingx/distcloud",
        "starlingx/distcloud-client", "starlingx/integ", "starlingx/monitoring",
        "starlingx/stx-puppet", "starlingx/update", "starlingx/utilities",
    },
    "zuul": {
        "opendev/system-config", "opendev/zuul-providers", "zuul/zuul",
        "zuul/zuul-jobs",
    },
    "drizzle": {
        "drizzle/drizzle", "drizzle/drizzle-test", "openstack/requirements",
        "zuul/zuul-jobs",
    },
    "wandertracks": {
        "wandertracks/wandertracks", "wandertracks/wandertracks-web",
        "opendev/zuul-providers", "zuul/zuul-jobs",
    },
}

INDEPENDENT_CATALOG_SOURCES = {
    "ethereum": "ethereum-protocol-specs-and-clients",
    "opentelemetry": "opentelemetry-language-sdks-and-collectors",
    "rust": "rust-governed-toolchain",
}

OPENDEV_IMPACT_KINDS = {
    "shared_runtime_metadata": "data_schema",
    "deployment_configuration": "deployment_configuration",
    "deployment_package": "dependency_or_build_interface",
    "service_activation": "deployment_configuration",
    "ci_configuration_contract": "dependency_or_build_interface",
    "client_server_validation": "runtime_api_contract",
    "dependency_and_deployment_configuration": "deployment_configuration",
    "shared_api_definition": "runtime_api_contract",
    "client_server_api": "runtime_api_contract",
    "generated_configuration_handoff": "deployment_configuration",
    "configuration_and_enforcement": "deployment_configuration",
    "shared_status_schema": "data_schema",
    "cross_repo_test_ownership": "test_contract",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def github_pr(repository: str, number: int, detail: dict[str, Any], branch: str) -> dict[str, Any]:
    return {
        "provider": "github",
        "number": number,
        "change_id": f"{repository}#{number}",
        "url": detail["url"],
        "status": "MERGED",
        "subject": detail["title"],
        "branch": branch,
        "created": detail["created_at"],
        "submitted": detail["merged_at"],
    }


def gerrit_change_id(message: str, number: int) -> str:
    match = CHANGE_ID.search(message)
    return match.group(1) if match else f"gerrit-change-{number}"


def gerrit_pr(
    repository: str,
    number: int,
    subject: str,
    branch: str,
    created: str,
    submitted: str,
    message: str,
) -> dict[str, Any]:
    return {
        "provider": "gerrit",
        "number": number,
        "change_id": gerrit_change_id(message, number),
        "url": f"https://review.opendev.org/c/{repository}/+/{number}",
        "status": "MERGED",
        "subject": subject,
        "branch": branch,
        "created": created,
        "submitted": submitted,
    }


def empty_checks() -> dict[str, Any]:
    return {
        "label_kind": "unavailable",
        "paths": [],
        "symbols": [],
        "tests": [],
        "commands": [],
        "expected_result": "coordinated_change_required",
    }


def license_record(repository: str, host: str) -> dict[str, str]:
    if host == "github.com":
        url = f"https://github.com/{repository}"
    else:
        url = f"https://opendev.org/{repository}"
    return {"repository": repository, "spdx": "NOASSERTION", "evidence_url": url}


def github_cases() -> list[dict[str, Any]]:
    selected = read_jsonl(ROOT / "candidates" / "github-multi-target-selected.jsonl")
    enriched = {
        (item["source_repository"], item["source_pull_request"]): item
        for item in read_jsonl(ROOT / "candidates" / "github-multi-target-review-enriched.jsonl")
    }
    reviews = {
        (item["source_repository"], item["source_pull_request"]): item
        for item in read_jsonl(ROOT / "candidates" / "github-multi-target-manual-review.jsonl")
    }
    snapshots = {
        (item["source_repository"], item["source_pull_request"]): item
        for item in read_jsonl(ROOT / "candidates" / "github-multi-target-opening-snapshots.jsonl")
        if item["status"] == "recovered"
    }
    audits = {
        (
            item["source_repository"], item["source_pull_request"],
            item["target_repository"], item["target_pull_request"],
        ): item
        for item in read_jsonl(ROOT / "candidates" / "github-multi-target-target-audit.jsonl")
        if item["status"] == "passed"
    }
    cases = []
    for choice in selected:
        key = (choice["source_repository"], choice["source_pull_request"])
        candidate = enriched[key]
        review = reviews[key]
        snapshot = snapshots[key]
        source = candidate["source"]
        accepted = [item for item in review["target_decisions"] if item["decision"] == "accept"]
        targets = []
        relations = []
        target_licenses = []
        for decision in accepted:
            target_key = (*key, decision["repository"], decision["pull_request"])
            audit = audits[target_key]["target"]
            target = {
                "repository": decision["repository"],
                "pull_request": github_pr(
                    decision["repository"], decision["pull_request"], audit, audit["base_branch"]
                ),
                "commit": audit["head_commit"],
                "changed_paths": audit["changed_paths"],
                "label_scope": "causal_impact",
                "impact_kind": "unclassified",
                "impact_kind_source": "unclassified",
                "expected_checks": empty_checks(),
                "evidence": [{
                    "level": "specification_proven",
                    "kind": "explicit_specification_to_implementation_reference",
                    "url": audit["url"],
                    "statement": decision["reason"],
                    "ci_url": None,
                }],
            }
            targets.append(target)
            relations.append({
                "source_repository": source["repository"],
                "target_repository": decision["repository"],
                "relation_kind": "specification_implementation",
                "evidence_url": audit["url"],
            })
            target_licenses.append(license_record(decision["repository"], "github.com"))
        case_id = f"github-{source['repository'].lower().replace('/', '-')}-{source['pull_request']}"
        source_detail = dict(source)
        source_detail["title"] = snapshot["subject"]
        cases.append({
            "schema_version": "1.1",
            "case_id": case_id,
            "project": candidate["ecosystem"],
            "split": "test",
            "case_kind": "independent_positive",
            "source": {
                "host": "github.com",
                "repository": source["repository"],
                "pull_request": github_pr(
                    source["repository"], source["pull_request"], source_detail, snapshot["branch"]
                ),
                "base_commit": snapshot["base_commit"],
                "candidate_commit": snapshot["candidate_commit"],
                "changed_paths": snapshot["changed_paths"],
                "patch_url": (
                    f"https://github.com/{source['repository']}/compare/"
                    f"{snapshot['base_commit']}...{snapshot['candidate_commit']}.patch"
                ),
            },
            "relations": relations,
            "targets": targets,
            "label_source": {
                "kind": "independent_project_evidence",
                "derived_from_marshal_config": False,
            },
            "licenses": [license_record(source["repository"], "github.com"), *target_licenses],
            "provenance": {
                "collector": "multi-target GitHub search, manual review, and opening snapshot recovery",
                "collected_at": COLLECTED_AT,
                "query": "merged implementation PR directly linking a source specification PR",
            },
        })
    return cases


def opendev_project(repository: str) -> str:
    owner = repository.split("/", 1)[0]
    return owner if owner in {"openstack", "starlingx", "zuul", "drizzle"} else "openstack"


def opendev_cases() -> list[dict[str, Any]]:
    rows = read_jsonl(ROOT / "candidates" / "opendev-semantic-revision-audit.jsonl")
    cases = []
    for row in rows:
        source = row["source"]
        project = opendev_project(source["repository"])
        targets = []
        relations = []
        target_licenses = []
        for target in row["targets"]:
            target_url = f"https://review.opendev.org/c/{target['repository']}/+/{target['change']}"
            targets.append({
                "repository": target["repository"],
                "pull_request": gerrit_pr(
                    target["repository"], target["change"], target["subject"],
                    target["branch"], target["created"], target["submitted"],
                    target["commit_message"],
                ),
                "commit": target["commit"],
                "changed_paths": target["changed_paths"],
                "label_scope": "causal_impact",
                "impact_kind": OPENDEV_IMPACT_KINDS[row["relation_family"]],
                "impact_kind_source": "manual",
                "expected_checks": empty_checks(),
                "evidence": [{
                    "level": "implementation_proven",
                    "kind": "companion_change_explains_cross_repository_semantics",
                    "url": target_url,
                    "statement": row["reason"],
                    "ci_url": None,
                }],
            })
            relations.append({
                "source_repository": source["repository"],
                "target_repository": target["repository"],
                "relation_kind": "semantic_companion_change",
                "evidence_url": target_url,
            })
            target_licenses.append(license_record(target["repository"], "review.opendev.org"))
        number = row["source_change"]
        cases.append({
            "schema_version": "1.1",
            "case_id": f"opendev-{number}-semantic-impact",
            "project": project,
            "split": "test",
            "case_kind": "independent_positive",
            "source": {
                "host": "review.opendev.org",
                "repository": source["repository"],
                "pull_request": gerrit_pr(
                    source["repository"], number, source["subject"], source["branch"],
                    source["created"], source["submitted"], source["opening_commit_message"],
                ),
                "base_commit": source["opening_parent"],
                "candidate_commit": source["opening_commit"],
                "changed_paths": source["opening_changed_paths"],
                "patch_url": (
                    f"https://review.opendev.org/changes/{number}/revisions/"
                    f"{source['opening_commit']}/patch"
                ),
            },
            "relations": relations,
            "targets": targets,
            "label_source": {
                "kind": "independent_project_evidence",
                "derived_from_marshal_config": False,
            },
            "licenses": [
                license_record(source["repository"], "review.opendev.org"), *target_licenses,
            ],
            "provenance": {
                "collector": "OpenDev semantic companion review and opening revision audit",
                "collected_at": COLLECTED_AT,
                "query": "merged companion changes with explicit cross-repository semantic rationale",
            },
        })
    return cases


def anchor_cases() -> list[dict[str, Any]]:
    return [
        json.loads((LEGACY_CASES / "opendev-1001023-cinder-impact.json").read_text(encoding="utf-8")),
        json.loads((LEGACY_CASES / "opendev-1001388.json").read_text(encoding="utf-8")),
    ]


def catalog_for(case: dict[str, Any]) -> str:
    return case["project"]


def main() -> int:
    cases = sorted([*github_cases(), *opendev_cases(), *anchor_cases()], key=lambda item: item["case_id"])
    if len(cases) != 100:
        raise SystemExit(f"expected 100 cases, found {len(cases)}")
    if len({item["case_id"] for item in cases}) != len(cases):
        raise SystemExit("duplicate case IDs")

    target_repositories: dict[str, set[str]] = {}
    for case in cases:
        target_repositories.setdefault(catalog_for(case), set()).update(
            target["repository"] for target in case["targets"]
        )
    source_snapshots = json.loads(
        (ROOT / "catalog-source-snapshots.json").read_text(encoding="utf-8")
    )["sources"]
    catalogs = {}
    for project, targets in sorted(target_repositories.items()):
        source_id = INDEPENDENT_CATALOG_SOURCES.get(project)
        if source_id:
            repositories = sorted(source_snapshots[source_id]["repositories"])
        else:
            repositories = sorted({*targets, *DISTRACTORS[project]})
        catalogs[project] = {"repositories": repositories}
        if not targets <= set(repositories):
            raise SystemExit(f"catalog {project} omits a target repository")
    write_json(ROOT / "candidate-repositories.json", {
        "schema_version": "2.0",
        "catalogs": catalogs,
    })

    for case in cases:
        write_json(CASES / f"{case['case_id']}.json", case)
    index = [{
        "case_id": case["case_id"],
        "case_kind": case["case_kind"],
        "path": f"cases/{case['case_id']}.json",
        "project": case["project"],
        "source_pr": case["source"]["pull_request"]["number"],
        "source_repository": case["source"]["repository"],
        "split": case["split"],
        "target_repositories": sorted({target["repository"] for target in case["targets"]}),
    } for case in cases]
    write_jsonl(ROOT / "index.jsonl", index)

    inputs = [{
        "case_id": case["case_id"],
        "observation_cutoff": case["source"]["pull_request"]["created"],
        "candidate_repository_catalog": f"candidate-repositories.json#{catalog_for(case)}",
        "candidate_repository_snapshots": f"repository-snapshots.jsonl#{case['case_id']}",
        "source": {
            "host": case["source"]["host"],
            "repository": case["source"]["repository"],
            "pull_request_number": case["source"]["pull_request"]["number"],
            "subject": case["source"]["pull_request"]["subject"],
            "base_commit": case["source"]["base_commit"],
            "candidate_commit": case["source"]["candidate_commit"],
            "changed_paths": case["source"]["changed_paths"],
            "patch_url": case["source"]["patch_url"],
        },
    } for case in cases]
    write_jsonl(ROOT / "inputs.jsonl", inputs)

    active_repositories = {
        license_item["repository"]
        for case in cases
        for license_item in case["licenses"]
    }
    license_by_repo = {
        item["repository"]: item
        for case in cases
        for item in case["licenses"]
    }
    write_json(ROOT / "licenses.json", {
        "schema_version": "1.1",
        "note": "只发布元数据和链接；运行时取得的第三方源码仍受各仓库许可证约束。NOASSERTION 表示未作统一许可证判断。",
        "repositories": [license_by_repo[repo] for repo in sorted(active_repositories)],
    })
    print(json.dumps({
        "formal_cases": len(cases),
        "github_specification_cases": len(github_cases()),
        "opendev_semantic_cases": len(opendev_cases()),
        "strong_evidence_anchor_cases": len(anchor_cases()),
        "target_labels": sum(len(case["targets"]) for case in cases),
        "catalogs": {key: len(value["repositories"]) for key, value in catalogs.items()},
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

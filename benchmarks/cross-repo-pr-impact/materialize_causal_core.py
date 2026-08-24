#!/usr/bin/env python3
"""Materialize the reviewed causal core without exposing target labels to inputs."""

from __future__ import annotations

import datetime as dt
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
CASES = ROOT / "cases"
ARCHIVE = ROOT / "candidates" / "known-coordination-cases"
LICENSES = {
    "ethereum/EIPs": ("NOASSERTION", "https://github.com/ethereum/EIPs"),
    "ethereum/go-ethereum": ("LGPL-3.0-only", "https://github.com/ethereum/go-ethereum/blob/master/COPYING"),
    "kubernetes/enhancements": ("Apache-2.0", "https://github.com/kubernetes/enhancements/blob/master/LICENSE"),
    "kubernetes/kubernetes": ("Apache-2.0", "https://github.com/kubernetes/kubernetes/blob/master/LICENSE"),
    "python/peps": ("NOASSERTION", "https://github.com/python/peps"),
    "python/cpython": ("PSF-2.0", "https://github.com/python/cpython/blob/main/LICENSE"),
    "rust-lang/rfcs": ("Apache-2.0 OR MIT", "https://github.com/rust-lang/rfcs"),
    "rust-lang/rust": ("Apache-2.0 OR MIT", "https://github.com/rust-lang/rust"),
}
STRONG_DISTRACTOR_REPOSITORIES = {
    "ChainSafe/lodestar",
    "Consensys/teku",
    "NethermindEth/nethermind",
    "OffchainLabs/prysm",
    "besu-eth/besu",
    "erigontech/erigon",
    "ethereum/execution-apis",
    "ethereum/execution-specs",
    "kubernetes/api",
    "kubernetes/apimachinery",
    "kubernetes/cli-runtime",
    "kubernetes/client-go",
    "kubernetes-client/csharp",
    "kubernetes-client/java",
    "kubernetes-client/javascript",
    "kubernetes-client/python",
    "kubernetes-sigs/cluster-api",
    "kubernetes-sigs/controller-runtime",
    "kubernetes-sigs/gateway-api",
    "pypa/pip",
    "pypa/setuptools",
    "python/mypy",
    "python/typeshed",
    "python/typing",
    "python/typing_extensions",
    "rust-lang/cargo",
    "rust-lang/chalk",
    "rust-lang/miri",
    "rust-lang/polonius",
    "rust-lang/rust-analyzer",
    "rust-lang/rust-clippy",
    "rust-lang/rustfmt",
    "sigp/lighthouse",
    "status-im/nimbus-eth2",
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


def license_record(repository: str) -> dict[str, str]:
    spdx, url = LICENSES[repository]
    return {"repository": repository, "spdx": spdx, "evidence_url": url}


def pr_record(
    repository: str,
    record: dict[str, Any],
    *,
    branch: str,
    subject: str | None = None,
) -> dict[str, Any]:
    return {
        "provider": "github",
        "number": record["number"],
        "change_id": f"{repository}#{record['number']}",
        "url": record["url"],
        "status": "MERGED",
        "subject": subject or record["title"],
        "branch": branch,
        "created": record["created_at"],
        "submitted": record["merged_at"],
    }


def make_case(
    candidate: dict[str, Any],
    review: dict[str, Any],
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    ecosystem = candidate["ecosystem"]
    source = candidate["source"]
    target = candidate["target"]
    source_slug = source["repository"].lower().replace("/", "-")
    case_id = f"github-{source_slug}-{source['number']}"
    return {
        "schema_version": "1.1",
        "case_id": case_id,
        "project": ecosystem,
        "split": "test",
        "case_kind": "independent_positive",
        "source": {
            "host": "github.com",
            "repository": source["repository"],
            "pull_request": pr_record(
                source["repository"], source,
                branch=snapshot["branch"], subject=snapshot["subject"],
            ),
            "base_commit": snapshot["base_commit"],
            "candidate_commit": snapshot["candidate_commit"],
            "changed_paths": snapshot["changed_paths"],
            "patch_url": (
                f"https://github.com/{source['repository']}/compare/"
                f"{snapshot['base_commit']}...{snapshot['candidate_commit']}.patch"
            ),
        },
        "relations": [{
            "source_repository": source["repository"],
            "target_repository": target["repository"],
            "relation_kind": "specification_implementation",
            "evidence_url": target["url"],
        }],
        "targets": [{
            "repository": target["repository"],
            "pull_request": pr_record(
                target["repository"], target, branch=snapshot["target_branch"]
            ),
            "commit": target["head_commit"],
            "changed_paths": target["changed_paths"],
            "label_scope": "causal_impact",
            "impact_kind": "unclassified",
            "impact_kind_source": "unclassified",
            "expected_checks": {
                "label_kind": "unavailable",
                "paths": [],
                "symbols": [],
                "tests": [],
                "commands": [],
                "expected_result": "coordinated_change_required",
            },
            "evidence": [{
                "level": "specification_proven",
                "kind": "explicit_specification_to_implementation_reference",
                "url": target["url"],
                "statement": review["reason"],
                "ci_url": None,
            }],
        }],
        "label_source": {
            "kind": "independent_project_evidence",
            "derived_from_marshal_config": False,
        },
        "licenses": [
            license_record(source["repository"]),
            license_record(target["repository"]),
        ],
        "provenance": {
            "collector": "collect_github_spec_candidates.py + manual review + opening snapshot recovery",
            "collected_at": dt.date.today().isoformat(),
            "query": "merged target PR explicitly linking a source specification PR",
        },
    }


def archive_coordination_cases() -> None:
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    for path in CASES.glob("*.json"):
        case = json.loads(path.read_text(encoding="utf-8"))
        if any(target["label_scope"] == "causal_impact" for target in case["targets"]):
            continue
        destination = ARCHIVE / path.name
        if destination.exists():
            destination.unlink()
        shutil.move(path, destination)


def main() -> int:
    candidates = read_jsonl(ROOT / "candidates" / "github-spec-candidates.jsonl")
    candidate_by_key = {
        (row["ecosystem"], row["source"]["number"], row["target"]["number"]): row
        for row in candidates
        if "source" in row and "target" in row
    }
    reviews = read_jsonl(ROOT / "candidates" / "github-spec-manual-review.jsonl")
    review_by_key = {
        (row["ecosystem"], row["source_number"], row["target_number"]): row
        for row in reviews if row["decision"] == "accept"
    }
    snapshots = read_jsonl(ROOT / "candidates" / "github-spec-opening-snapshots.jsonl")
    recovered_by_key = {
        (row["ecosystem"], row["source_number"], row["target_number"]): row
        for row in snapshots if row["status"] == "recovered"
    }
    usable_keys = sorted(review_by_key.keys() & recovered_by_key.keys())
    if len(usable_keys) != 95:
        raise SystemExit(f"expected 95 reviewed and time-safe GitHub cases, found {len(usable_keys)}")

    archive_coordination_cases()
    for key in usable_keys:
        case = make_case(candidate_by_key[key], review_by_key[key], recovered_by_key[key])
        write_json(CASES / f"{case['case_id']}.json", case)

    cases = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(CASES.glob("*.json"))
    ]
    if len(cases) != 99:
        raise SystemExit(f"expected 99 formal cases, found {len(cases)}")

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
        "candidate_repository_catalog": "candidate-repositories.json",
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

    catalog = json.loads((ROOT / "candidate-repositories.json").read_text(encoding="utf-8"))
    catalog["repositories"] = sorted({
        *catalog["repositories"],
        *STRONG_DISTRACTOR_REPOSITORIES,
        *(case["source"]["repository"] for case in cases),
        *(target["repository"] for case in cases for target in case["targets"]),
    })
    write_json(ROOT / "candidate-repositories.json", catalog)

    license_document = json.loads((ROOT / "licenses.json").read_text(encoding="utf-8"))
    by_repo = {row["repository"]: row for row in license_document["repositories"]}
    for repository in LICENSES:
        by_repo[repository] = license_record(repository)
    license_document["repositories"] = [by_repo[key] for key in sorted(by_repo)]
    write_json(ROOT / "licenses.json", license_document)

    print(json.dumps({
        "formal_cases": len(cases),
        "new_github_cases": len(usable_keys),
        "archived_coordination_cases": len(list(ARCHIVE.glob("*.json"))),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

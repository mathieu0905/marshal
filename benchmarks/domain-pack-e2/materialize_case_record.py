#!/usr/bin/env python3
"""Bind one source patch to a Domain Pack without consulting replay outcomes.

Change facts are parsed from the unified diff.  Candidate checks are the union
of public Pack routes.  They remain unjudged unless curator-side strict-E2
evidence later adds an explicit ``judged_e2_binding``.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from build_openstack_requirements_pack import (
    BuildError,
    _canonical_distribution,
    _requirement_entries,
)


CASE_SCHEMA_VERSION = "domain-pack-e2-case-1"
_DIFF_PATH_RE = re.compile(r"^(?:a|b)/(.*)$")


def _diff_path(value: str) -> str | None:
    value = value.split("\t", 1)[0].strip()
    if value == "/dev/null":
        return None
    match = _DIFF_PATH_RE.match(value)
    return match.group(1) if match else value


def _patch_change_facts(
    patch: str,
    constraint_paths: set[str],
    *,
    fact_vocabulary: str = "constraint",
) -> list[dict[str, Any]]:
    if fact_vocabulary not in {"constraint", "requirement"}:
        raise BuildError(f"unsupported source fact vocabulary: {fact_vocabulary}")
    old_path: str | None = None
    new_path: str | None = None
    changes: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: {"removed": [], "added": []}
    )
    for line in patch.splitlines():
        if line.startswith("--- "):
            old_path = _diff_path(line[4:])
            continue
        if line.startswith("+++ "):
            new_path = _diff_path(line[4:])
            continue
        if line.startswith("-") and not line.startswith("---"):
            path = old_path
            side = "removed"
        elif line.startswith("+") and not line.startswith("+++"):
            path = new_path
            side = "added"
        else:
            continue
        if path not in constraint_paths:
            continue
        entries = _requirement_entries(line[1:] + "\n", path)
        for entry in entries:
            changes[entry["key"]][side].append(
                {
                    "distribution": entry["distribution"],
                    "specifier": entry["specifier"],
                    "path": path,
                }
            )

    facts: list[dict[str, Any]] = []
    for key in sorted(changes):
        removed = changes[key]["removed"]
        added = changes[key]["added"]
        if removed and added:
            kind = f"{fact_vocabulary}-updated"
        elif added:
            kind = f"{fact_vocabulary}-added"
        else:
            kind = f"{fact_vocabulary}-removed"
        facts.append(
            {
                "kind": kind,
                "dependency_key": _canonical_distribution(key),
                "removed_entries": removed,
                "added_entries": added,
                "derivation": "unified-diff-requirement-lines-v1",
            }
        )
    return facts


def _fact_vocabulary(pack: dict[str, Any]) -> str:
    if "requirements_path_kinds" in pack.get("provenance", {}).get("source", {}):
        return "requirement"
    if any(
        route.get("trigger", {}).get("kind") == "requirement-entry-change"
        for route in pack.get("dependency_routes", [])
    ):
        return "requirement"
    return "constraint"


def materialize_case(pack: dict[str, Any], case_spec: dict[str, Any], patch: str) -> dict[str, Any]:
    for key in ("case_id", "source_event"):
        if key not in case_spec:
            raise BuildError(f"case specification is missing {key}")
    if case_spec["source_event"].get("repository") != "openstack/requirements":
        raise BuildError("case source_event.repository must be openstack/requirements")

    constraint_paths = set(pack["provenance"]["source"]["constraints_paths"])
    fact_vocabulary = _fact_vocabulary(pack)
    change_facts = _patch_change_facts(
        patch,
        constraint_paths,
        fact_vocabulary=fact_vocabulary,
    )
    routes_by_key = {route["dependency_key"]: route for route in pack["dependency_routes"]}

    candidate_route_ids: list[str] = []
    candidate_repositories: set[str] = set()
    candidate_check_ids: set[str] = set()
    unresolved_repositories: list[dict[str, str]] = []
    unresolved_dependency_keys: list[str] = []
    for fact in change_facts:
        route = routes_by_key.get(fact["dependency_key"])
        if not route:
            unresolved_dependency_keys.append(fact["dependency_key"])
            continue
        candidate_route_ids.append(route["id"])
        for repository_route in route["repositories"]:
            candidate_repositories.add(repository_route["repository"])
            candidate_check_ids.update(repository_route["focused_check_ids"])
            if repository_route["check_resolution"]["status"] == "unresolved":
                unresolved_repositories.append(
                    {
                        "route_id": route["id"],
                        "repository": repository_route["repository"],
                        "reason": repository_route["check_resolution"]["reason"],
                    }
                )

    known_check_ids = {check["id"] for check in pack["checks"]}
    missing_check_ids = candidate_check_ids - known_check_ids
    if missing_check_ids:
        raise BuildError(
            "pack routes reference undefined checks: " + ", ".join(sorted(missing_check_ids))
        )

    return {
        "schema_version": CASE_SCHEMA_VERSION,
        "case_id": case_spec["case_id"],
        "pack_family_id": pack["pack_family_id"],
        "pack_revision_id": pack["pack_revision_id"],
        "public": {
            "source_event": case_spec["source_event"],
            "change_facts": change_facts,
            "candidate_selection": {
                "method": f"changed-{fact_vocabulary}-to-pack-candidates-v1",
                "candidate_route_ids": sorted(candidate_route_ids),
                "candidate_repositories": sorted(candidate_repositories),
                "candidate_check_ids": sorted(candidate_check_ids),
                "unresolved_dependency_keys": sorted(unresolved_dependency_keys),
                "unresolved_repositories": sorted(
                    unresolved_repositories,
                    key=lambda row: (row["route_id"], row["repository"]),
                ),
            },
        },
        "curator": {
            "candidate_label_policy": "unjudged_unless_in_judged_e2_bindings",
            "judged_e2_bindings": [],
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--case-spec", type=Path, required=True)
    parser.add_argument("--patch", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pack = json.loads(args.pack.read_text(encoding="utf-8"))
    case_spec = json.loads(args.case_spec.read_text(encoding="utf-8"))
    case = materialize_case(pack, case_spec, args.patch.read_text(encoding="utf-8"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(case, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "case_id": case["case_id"],
                "change_facts": len(case["public"]["change_facts"]),
                "candidate_repositories": len(
                    case["public"]["candidate_selection"]["candidate_repositories"]
                ),
                "candidate_checks": len(
                    case["public"]["candidate_selection"]["candidate_check_ids"]
                ),
                "output": str(args.output),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

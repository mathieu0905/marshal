#!/usr/bin/env python3
"""Build a label-independent dependency-to-test Domain Pack from Git snapshots.

The builder reads only a constraints snapshot and a target repository snapshot.
It never reads replay logs, failure signatures, or maintainer repairs.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path


_CONSTRAINT_RE = re.compile(r"^([A-Za-z0-9_.-]+)={2,3}([^;\s]+)")


def _git(git_dir: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", f"--git-dir={git_dir}", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout


def _canonical(value: str) -> str:
    return re.sub(r"[-_.]+", "_", value).lower()


def _constraints(git_dir: Path, commit: str, path: str) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for raw in _git(git_dir, "show", f"{commit}:{path}").splitlines():
        match = _CONSTRAINT_RE.match(raw.strip())
        if not match:
            continue
        distribution, version = match.groups()
        rows[_canonical(distribution)] = {
            "distribution": distribution,
            "version": version,
        }
    return rows


def _test_files(git_dir: Path, commit: str, test_root: str) -> list[str]:
    output = _git(git_dir, "ls-tree", "-r", "--name-only", commit, test_root)
    return sorted(path for path in output.splitlines() if path.endswith(".py"))


def _imports(source: str) -> set[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".", 1)[0])
    return names


def _module_selector(path: str) -> str:
    module = path[:-3].replace("/", ".")
    return module[:-9] if module.endswith(".__init__") else module


def build_pack(args: argparse.Namespace) -> dict:
    constraints = _constraints(
        args.source_mirror, args.source_commit, args.constraints_path
    )
    by_distribution: dict[str, list[dict]] = defaultdict(list)
    for path in _test_files(args.target_mirror, args.target_commit, args.test_root):
        source = _git(args.target_mirror, "show", f"{args.target_commit}:{path}")
        for imported in sorted(_imports(source)):
            key = _canonical(imported)
            constraint = constraints.get(key)
            if not constraint:
                continue
            selector = _module_selector(path)
            invariant_id = (
                f"dependency-import.{args.target_repo.replace('/', '__')}."
                f"{key}.{selector}"
            )
            by_distribution[key].append(
                {
                    "id": invariant_id,
                    "domain": "dependency-compatibility",
                    "spec_ref": "derived:direct-test-import",
                    "executor_kind": "command",
                    "location_repo": args.target_repo,
                    "location_path": path,
                    "location_test": selector,
                    "severity": "high",
                    "run_command": [*args.command_prefix, selector],
                }
            )

    contracts = []
    invariants = []
    for key in sorted(by_distribution):
        rows = sorted(by_distribution[key], key=lambda row: row["id"])
        distribution = constraints[key]["distribution"]
        contracts.append(
            {
                "id": f"dependency-import:{key}",
                "trigger": {
                    "repo": args.source_repo,
                    "path_prefixes": [args.constraints_path],
                    "required_labels": [f"dependency:{key}"],
                },
                "verify_invariants": [row["id"] for row in rows],
            }
        )
        invariants.extend(rows)

    return {
        "schema_version": "marshal-domain-pack-1",
        "id": args.pack_id,
        "construction": {
            "method": "constraints-to-direct-test-imports-v1",
            "source_repository": args.source_repo,
            "source_commit": args.source_commit,
            "constraints_path": args.constraints_path,
            "target_repository": args.target_repo,
            "target_commit": args.target_commit,
            "test_root": args.test_root,
            "outcome_inputs_read": False,
            "rule_authoring_case": args.rule_authoring_case,
        },
        "default_tier": "low",
        "matched_tier": "high",
        "contracts": contracts,
        "invariants": invariants,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-mirror", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-repo", required=True)
    parser.add_argument("--constraints-path", required=True)
    parser.add_argument("--target-mirror", type=Path, required=True)
    parser.add_argument("--target-commit", required=True)
    parser.add_argument("--target-repo", required=True)
    parser.add_argument("--test-root", required=True)
    parser.add_argument("--pack-id", required=True)
    parser.add_argument("--command-prefix", nargs="+", required=True)
    parser.add_argument("--rule-authoring-case", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pack = build_pack(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(pack, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "pack_id": pack["id"],
                "contracts": len(pack["contracts"]),
                "invariants": len(pack["invariants"]),
                "output": str(args.output),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

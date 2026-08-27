#!/usr/bin/env python3
"""Inventory pre-existing target checks for revealed cross-repository relations."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from collect_formal_e2_candidate_mirrors import repository_path


RUNNER = re.compile(r"\b(stestr\s+run|pytest|python\s+-m\s+pytest|nosetests|ansible-test|molecule)\b")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def git(mirror: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "--git-dir", str(mirror), *arguments],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )


def test_path(path: str) -> bool:
    lowered = path.lower()
    return (
        "/test" in lowered
        or lowered.startswith("test")
        or Path(lowered).name.startswith("test_")
    ) and Path(lowered).suffix in {".py", ".sh", ".yaml", ".yml"}


def command_lines(text: str) -> list[str]:
    lines = []
    for raw in text.splitlines():
        value = raw.strip().lstrip("-").strip()
        if RUNNER.search(value) and value not in lines:
            lines.append(value)
    return lines


def inspect_relation(
    relation: dict[str, Any],
    source_repository: str,
    target: dict[str, Any],
    mirror_root: Path,
) -> dict[str, Any]:
    mirror = repository_path(mirror_root, target["repository"])
    tree = git(mirror, "ls-tree", "-r", "--name-only", target["base_commit"])
    paths = tree.stdout.splitlines() if tree.returncode == 0 else []
    tox_paths = sorted(path for path in paths if Path(path).name == "tox.ini")
    changed_tests = sorted(path for path in target["changed_paths"] if test_path(path))

    def affinity(path: str) -> tuple[int, int, str]:
        parent = str(Path(path).parent)
        covered = sum(
            parent == "." or changed == parent or changed.startswith(parent + "/")
            for changed in target["changed_paths"]
        )
        return (-covered, -len(Path(parent).parts), path)

    relevant_tox = sorted(tox_paths, key=affinity)[:5]
    commands = []
    for tox_path in relevant_tox:
        shown = git(mirror, "show", f"{target['base_commit']}:{tox_path}")
        if shown.returncode == 0:
            commands.extend({"config_path": tox_path, "command": value} for value in command_lines(shown.stdout))
    unique_commands = []
    seen = set()
    for item in commands:
        key = (item["config_path"], item["command"])
        if key not in seen:
            seen.add(key)
            unique_commands.append(item)
    replay_score = relation["triage_score"] + 20 * bool(changed_tests) + 20 * bool(unique_commands)
    return {
        **relation,
        "source_repository": source_repository,
        "cross_repository": source_repository != target["repository"],
        "target_base_commit": target["base_commit"],
        "target_head_commit": target["head_commit"],
        "target_changed_paths": target["changed_paths"],
        "changed_test_paths": changed_tests,
        "pre_existing_tox_paths": relevant_tox,
        "pre_existing_test_commands": unique_commands,
        "replay_score": replay_score,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-events", type=Path, required=True)
    parser.add_argument("--target-metadata", type=Path, required=True)
    parser.add_argument("--contract-triage", type=Path, required=True)
    parser.add_argument("--mirror-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args()
    sources = {row["candidate_id"]: row for row in read_jsonl(args.source_events)}
    metadata = {row["candidate_id"]: row for row in read_jsonl(args.target_metadata)}
    relations = read_jsonl(args.contract_triage)
    jobs = []
    for relation in relations:
        source_repository = sources[relation["candidate_id"]]["opening"]["repository"]
        if source_repository == relation["target_repository"]:
            continue
        target = next(
            row for row in metadata[relation["candidate_id"]]["targets"]
            if row["number"] == relation["target_change"]
        )
        jobs.append((relation, source_repository, target))
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        rows = list(executor.map(
            lambda item: inspect_relation(*item, args.mirror_root), jobs
        ))
    rows.sort(key=lambda row: (-row["replay_score"], -row["triage_score"], row["candidate_id"], row["target_change"]))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "replayability.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    metrics = {
        "schema_version": "1.0",
        "cross_repository_relation_count": len(rows),
        "changed_test_relation_count": sum(bool(row["changed_test_paths"]) for row in rows),
        "pre_existing_test_command_relation_count": sum(bool(row["pre_existing_test_commands"]) for row in rows),
        "both_test_and_command_relation_count": sum(
            bool(row["changed_test_paths"]) and bool(row["pre_existing_test_commands"])
            for row in rows
        ),
        "labels_assigned": False,
    }
    (args.output_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(metrics, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

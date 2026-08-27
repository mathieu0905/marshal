#!/usr/bin/env python3
"""Build a replay queue from revealed relations with existing Python tests."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

from collect_formal_e2_candidate_mirrors import repository_path


TEST_DEF = re.compile(r"^[ +\-]?\s*(?:async\s+)?def\s+(test_[A-Za-z0-9_]+)", re.MULTILINE)


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-events", type=Path, required=True)
    parser.add_argument("--target-metadata", type=Path, required=True)
    parser.add_argument("--replayability", type=Path, required=True)
    parser.add_argument("--target-patch-dir", type=Path, required=True)
    parser.add_argument("--snapshots", type=Path, required=True)
    parser.add_argument("--mirror-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--selector-mode", choices=("changed-def", "module"), default="changed-def")
    args = parser.parse_args()
    sources = {row["candidate_id"]: row for row in read_jsonl(args.source_events)}
    metadata = {row["candidate_id"]: row for row in read_jsonl(args.target_metadata)}
    snapshots = {row["case_id"]: row for row in read_jsonl(args.snapshots)}
    plans = []
    for relation in read_jsonl(args.replayability):
        tests = [
            path for path in relation["changed_test_paths"]
            if path.endswith(".py") and Path(path).name.startswith("test_")
        ]
        if not relation["source_repository"].startswith("openstack/") or not tests:
            continue
        if "tox.ini" not in relation["pre_existing_tox_paths"]:
            continue
        source = sources[relation["candidate_id"]]["opening"]
        source_mirror = repository_path(args.mirror_root, source["repository"])
        root = subprocess.run(
            ["git", "--git-dir", str(source_mirror), "ls-tree", "--name-only", source["base_commit"]],
            stdout=subprocess.PIPE, text=True, check=False,
        ).stdout.splitlines()
        if not {"setup.py", "setup.cfg", "pyproject.toml"} & set(root):
            continue
        target = next(
            item for item in metadata[relation["candidate_id"]]["targets"]
            if item["number"] == relation["target_change"]
        )
        patch = (args.target_patch_dir / f"{target['number']}.patch").read_text(
            encoding="utf-8", errors="replace"
        )
        names = list(dict.fromkeys(TEST_DEF.findall(patch)))
        module_selector = tests[0][:-3].replace("/", ".")
        selector = module_selector if args.selector_mode == "module" else (names[0] if names else module_selector)
        requirement_snapshot = next(
            (item for item in snapshots[relation["candidate_id"]]["repositories"]
             if item["repository"] == "openstack/requirements" and item["status"] == "available"),
            None,
        )
        if requirement_snapshot is None:
            continue
        requirements_mirror = repository_path(args.mirror_root, "openstack/requirements")
        historical = subprocess.run(
            [
                "git", "--git-dir", str(requirements_mirror), "rev-list", "-1",
                f"--before={target['created_at']}", "refs/heads/master",
            ],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
        ).stdout.strip()
        plans.append({
            "case_id": f"{relation['candidate_id']}--target-{target['number']}",
            "candidate_id": relation["candidate_id"],
            "source_repository": source["repository"],
            "source_base_commit": source["base_commit"],
            "source_head_commit": source["head_commit"],
            "source_subject": source["subject"],
            "target_repository": target["repository"],
            "target_change": target["number"],
            "target_base_commit": target["base_commit"],
            "target_head_commit": target["head_commit"],
            "target_subject": target["subject"],
            "target_test_path": tests[0],
            "test_selector": selector,
            "test_command": ["stestr", "run", selector],
            "command_config_path": "tox.ini",
            "requirements_commit": historical or requirement_snapshot["commit"],
            "requirements_cutoff": target["created_at"],
            "triage_score": relation["triage_score"],
        })
    plans.sort(key=lambda row: (-row["triage_score"], row["case_id"]))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in plans),
        encoding="utf-8",
    )
    print(json.dumps({"python_replay_plan_count": len(plans)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

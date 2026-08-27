#!/usr/bin/env python3
"""Replay a source checkout against a target's existing cross-repo command."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def mirror_path(root: Path, repository: str) -> Path:
    return root / f"{repository.replace('/', '__')}.git"


def clone_checkout(mirror: Path, destination: Path, commit: str) -> None:
    completed = subprocess.run(
        ["git", "clone", "--quiet", "--no-checkout", str(mirror), str(destination)],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    if completed.returncode:
        raise RuntimeError(completed.stdout)
    completed = subprocess.run(
        ["git", "checkout", "--quiet", "--detach", commit], cwd=destination,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    if completed.returncode:
        raise RuntimeError(completed.stdout)


def local_environment() -> dict[str, str]:
    environment = dict(os.environ)
    for key in list(environment):
        if key.lower() in {"http_proxy", "https_proxy", "all_proxy"}:
            environment.pop(key)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return environment


def parsed_check_count(output: str, pattern: re.Pattern[str]) -> int:
    return sum(1 for _ in pattern.finditer(output))


def python_executable(path: Path) -> str:
    # Keep a virtualenv's lexical interpreter path. Resolving the symlink to
    # its base interpreter drops pyvenv.cfg and therefore the replay deps.
    return str(path.absolute())


def command_provenance(
    plan: dict, sources: dict[str, Path], targets: dict[str, Path], target_base_commit: str
) -> dict[str, str]:
    side = plan.get("command_config_repository", "target")
    if side == "source":
        repository = plan["source_repository"]
        commit = plan["source_base_commit"]
        checkout = sources["A0"]
    elif side == "target":
        repository = plan["target_repository"]
        commit = target_base_commit
        checkout = targets["A0"]
    else:
        raise ValueError("command_config_repository must be source or target")
    path = plan["command_config_path"]
    if not isinstance(path, str) or not path or not (checkout / path).is_file():
        raise ValueError(f"command provenance path is absent at cutoff: {path}")
    return {"repository": repository, "commit": commit, "path": path}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--relation-id", required=True)
    parser.add_argument("--mirror-root", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--target-base-commit", required=True)
    parser.add_argument("--target-patch", type=Path, required=True)
    args = parser.parse_args()

    rows = [
        row for row in read_jsonl(args.plan)
        if row.get("relation_id", row.get("case_id")) == args.relation_id
    ]
    if len(rows) != 1:
        raise ValueError(f"relation must have exactly one plan row, got {len(rows)}")
    plan = rows[0]
    if plan.get("target_base_commit") != args.target_base_commit:
        raise ValueError("plan target base is not the public cutoff target commit")
    logical_command = plan.get("test_command")
    if (
        not isinstance(logical_command, list)
        or not logical_command
        or any(not isinstance(value, str) or not value for value in logical_command)
        or logical_command[0] not in {"python", "python3"}
    ):
        raise ValueError("cross-repo command must be a non-empty Python command list")
    count_expression = plan.get("check_count_regex")
    if not isinstance(count_expression, str) or not count_expression:
        raise ValueError("cross-repo command plan requires check_count_regex")
    count_pattern = re.compile(count_expression, re.MULTILINE)

    work = args.work_root / args.relation_id
    evidence = args.evidence_root / args.relation_id
    if work.exists() or evidence.exists():
        raise ValueError("relation work or evidence directory already exists")
    work.mkdir(parents=True)
    evidence.mkdir(parents=True)
    attempt = evidence / args.relation_id

    source_mirror = mirror_path(args.mirror_root, plan["source_repository"])
    target_mirror = mirror_path(args.mirror_root, plan["target_repository"])
    source_commits = {
        "A0": plan["source_base_commit"],
        "A1": plan["source_head_commit"],
        "A2": plan["source_head_commit"],
    }
    sources: dict[str, Path] = {}
    targets: dict[str, Path] = {}
    for arm in ("A0", "A1", "A2"):
        arm_root = work / arm.lower()
        sources[arm] = arm_root / "source"
        targets[arm] = arm_root / "target"
        clone_checkout(source_mirror, sources[arm], source_commits[arm])
        clone_checkout(target_mirror, targets[arm], args.target_base_commit)

    patch = args.target_patch.resolve()
    checked = subprocess.run(
        ["git", "apply", "--check", str(patch)], cwd=targets["A2"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    if checked.returncode:
        write_json(evidence / "rejection.json", {
            "case_id": args.relation_id,
            "reason": "maintainer_patch_does_not_apply_to_cutoff_target",
            "detail": checked.stdout[-2000:],
        })
        return 2
    applied = subprocess.run(
        ["git", "apply", str(patch)], cwd=targets["A2"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    if applied.returncode:
        raise RuntimeError(applied.stdout)
    patch_base = plan.get("target_patch_base_commit")
    if not isinstance(patch_base, str) or not patch_base:
        raise ValueError("cross-repo command plan requires target_patch_base_commit")
    maintainer_diff = subprocess.run(
        [
            "git", "--git-dir", str(target_mirror), "diff",
            patch_base, plan["target_head_commit"], "--",
        ],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if maintainer_diff.returncode or maintainer_diff.stdout != patch.read_bytes():
        write_json(evidence / "rejection.json", {
            "case_id": args.relation_id,
            "reason": "target_patch_is_not_exact_maintainer_diff",
            "target_patch_base_commit": patch_base,
            "target_head_commit": plan["target_head_commit"],
        })
        return 2
    shutil.copy2(patch, evidence / "target.patch")

    target_test_path = plan["target_test_path"]
    if not (targets["A0"] / target_test_path).is_file():
        raise ValueError(f"target check path is absent at cutoff: {target_test_path}")
    provenance = command_provenance(plan, sources, targets, args.target_base_commit)

    results: dict[str, tuple[int, str]] = {}
    check_counts: dict[str, int] = {}
    executable_command = [python_executable(args.python), *logical_command[1:]]
    for arm in ("A0", "A1", "A2"):
        completed = subprocess.run(
            executable_command, cwd=targets[arm], env=local_environment(),
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
        )
        arm_dir = attempt / arm.lower()
        arm_dir.mkdir(parents=True)
        (arm_dir / "command.log").write_text(completed.stdout, encoding="utf-8")
        check_counts[arm] = parsed_check_count(completed.stdout, count_pattern)
        write_json(arm_dir / "summary.json", {
            "arm": arm,
            "checks_run": check_counts[arm],
            "command": logical_command,
            "exit_code": completed.returncode,
        })
        results[arm] = (completed.returncode, completed.stdout)

    signature = plan["failure_signature"]
    exits = {arm: results[arm][0] for arm in results}
    strict = (
        exits["A0"] == 0 and exits["A1"] != 0 and exits["A2"] == 0
        and signature in results["A1"][1]
        and signature not in results["A0"][1]
        and signature not in results["A2"][1]
        and all(check_counts[arm] > 0 for arm in ("A0", "A1", "A2"))
    )
    with (evidence / "run-results.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=("arm", "exit_code", "checks_run"), delimiter="\t"
        )
        writer.writeheader()
        for arm in ("A0", "A1", "A2"):
            writer.writerow({
                "arm": arm, "exit_code": exits[arm], "checks_run": check_counts[arm]
            })
    if not strict:
        write_json(evidence / "rejection.json", {
            "case_id": args.relation_id,
            "reason": "strict_arm_signature_or_check_execution_gate_failed",
            "exit_codes": exits,
            "checks_run": check_counts,
            "failure_signature": signature,
        })
        return 1

    write_json(evidence / "contract.json", {
        "schema_version": "1.0",
        "case_id": args.relation_id,
        "candidate_id": plan["candidate_id"],
        "source_repository": plan["source_repository"],
        "source_base_commit": plan["source_base_commit"],
        "source_head_commit": plan["source_head_commit"],
        "source_application": "side_by_side_opening_checkout",
        "built_source_commits": source_commits,
        "target_repository": plan["target_repository"],
        "target_base_commit": args.target_base_commit,
        "target_head_commit": plan["target_head_commit"],
        "target_patch_base_commit": patch_base,
        "target_change": plan["target_change"],
        "target_a2_kind": "maintainer_patch_applied_to_cutoff_snapshot",
        "target_patch_evidence": "target.patch",
        "target_test_path": plan["target_test_path"],
        "test_command": logical_command,
        "command_config_path": plan["command_config_path"],
        "command_provenance": provenance,
        "selected_attempt_id": args.relation_id,
        "primary_result_channel": "project_build_or_test",
        "arms": {"A0": "pass", "A1": "fail", "A2": "pass"},
        "machine_arm_verification": "passed",
        "failure_signature": signature,
        "checks_run": check_counts,
    })
    print(json.dumps({"relation_id": args.relation_id, "strict_e2": True}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

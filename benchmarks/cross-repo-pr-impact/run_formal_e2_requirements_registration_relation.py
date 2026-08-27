#!/usr/bin/env python3
"""Replay one source-project to requirements-registration strict-E2 relation."""

from __future__ import annotations

import argparse
import csv
import json
import os
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


def run(command: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def clone_checkout(mirror: Path, destination: Path, commit: str) -> None:
    completed = run(["git", "clone", "--quiet", "--no-checkout", str(mirror), str(destination)])
    if completed.returncode:
        raise RuntimeError(completed.stdout)
    completed = run(["git", "checkout", "--quiet", "--detach", commit], cwd=destination)
    if completed.returncode:
        raise RuntimeError(completed.stdout)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--relation-id", required=True)
    parser.add_argument("--mirror-root", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--tox", type=Path, required=True)
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
    if plan["target_repository"] != "openstack/requirements":
        raise ValueError("requirements_registration requires openstack/requirements as target")

    work = args.work_root / args.relation_id
    evidence = args.evidence_root / args.relation_id
    if work.exists() or evidence.exists():
        raise ValueError("relation work or evidence directory already exists")
    work.mkdir(parents=True)
    evidence.mkdir(parents=True)

    source_mirror = mirror_path(args.mirror_root, plan["source_repository"])
    target_mirror = mirror_path(args.mirror_root, plan["target_repository"])
    if not source_mirror.is_dir() or not target_mirror.is_dir():
        raise ValueError("source or target mirror is missing")

    source_a0 = work / "source-a0"
    source_a1 = work / "source-a1"
    clone_checkout(source_mirror, source_a0, plan["source_base_commit"])
    clone_checkout(source_mirror, source_a1, plan["source_head_commit"])
    targets = {}
    for arm in ("a0", "a1", "a2"):
        targets[arm] = work / f"target-{arm}"
        clone_checkout(target_mirror, targets[arm], args.target_base_commit)

    patch_check = run(["git", "apply", "--check", str(args.target_patch)], cwd=targets["a2"])
    if patch_check.returncode:
        write_json(evidence / "rejection.json", {
            "case_id": args.relation_id,
            "reason": "maintainer_patch_does_not_apply_to_cutoff_target",
            "detail": patch_check.stdout[-2000:],
        })
        return 2
    applied = run(["git", "apply", str(args.target_patch)], cwd=targets["a2"])
    if applied.returncode:
        raise RuntimeError(applied.stdout)
    shutil.copy2(args.target_patch, evidence / "target.patch")

    venv = work / "runner"
    setup = run([str(args.python), "-m", "venv", str(venv)])
    if setup.returncode:
        (evidence / "environment-setup.log").write_text(setup.stdout, encoding="utf-8")
        return 2
    setup = run([
        str(venv / "bin" / "python"), "-m", "pip", "install", "-r",
        str(targets["a0"] / "requirements.txt"),
    ])
    (evidence / "environment-setup.log").write_text(setup.stdout, encoding="utf-8")
    if setup.returncode:
        write_json(evidence / "rejection.json", {
            "case_id": args.relation_id,
            "reason": "environment_setup_failed",
        })
        return 2

    logical_command = plan["test_command"]
    arm_inputs = {
        "A0": (source_a0, targets["a0"]),
        "A1": (source_a1, targets["a1"]),
        "A2": (source_a1, targets["a2"]),
    }
    summaries = {}
    for arm, (source, target) in arm_inputs.items():
        command = [
            str(venv / "bin" / "python"),
            str(target / "playbooks" / "files" / "project-requirements-change.py"),
            str(source), "master", "--reqs", str(target),
        ]
        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(target)
        for key in list(environment):
            if key.lower() in {"http_proxy", "https_proxy", "all_proxy"}:
                environment.pop(key)
        completed = run(command, cwd=target, env=environment)
        arm_dir = evidence / args.relation_id / arm.lower()
        arm_dir.mkdir(parents=True)
        (arm_dir / "command.log").write_text(completed.stdout, encoding="utf-8")
        summary = {"arm": arm, "command": logical_command, "exit_code": completed.returncode}
        write_json(arm_dir / "summary.json", summary)
        summaries[arm] = summary

    signature = "Requirement(package='hardware'"
    logs = {
        arm: (evidence / args.relation_id / arm.lower() / "command.log").read_text(
            encoding="utf-8", errors="replace"
        )
        for arm in arm_inputs
    }
    exits = {arm: summary["exit_code"] for arm, summary in summaries.items()}
    strict = (
        exits["A0"] == 0 and exits["A1"] != 0 and exits["A2"] == 0
        and signature in logs["A1"]
        and signature not in logs["A0"]
        and signature not in logs["A2"]
    )
    with (evidence / "run-results.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("arm", "exit_code"), delimiter="\t")
        writer.writeheader()
        for arm in ("A0", "A1", "A2"):
            writer.writerow({"arm": arm, "exit_code": exits[arm]})
    if not strict:
        write_json(evidence / "rejection.json", {
            "case_id": args.relation_id,
            "reason": "strict_arm_or_signature_gate_failed",
            "exit_codes": exits,
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
        "target_repository": plan["target_repository"],
        "target_base_commit": args.target_base_commit,
        "target_head_commit": plan["target_head_commit"],
        "target_change": plan["target_change"],
        "target_a2_kind": "maintainer_patch_applied_to_cutoff_snapshot",
        "target_patch_evidence": "target.patch",
        "requirements_commit": args.target_base_commit,
        "target_test_path": plan["target_test_path"],
        "test_command": logical_command,
        "command_config_path": plan["command_config_path"],
        "command_provenance": {
            "repository": plan["target_repository"],
            "commit": args.target_base_commit,
            "path": plan["command_config_path"],
        },
        "selected_attempt_id": args.relation_id,
        "primary_result_channel": "project_build_or_test",
        "arms": {"A0": "pass", "A1": "fail", "A2": "pass"},
        "machine_arm_verification": "passed",
        "failure_signature": signature,
    })
    print(json.dumps({"relation_id": args.relation_id, "strict_e2": True}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

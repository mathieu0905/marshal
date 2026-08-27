#!/usr/bin/env python3
"""Replay all maintainer-touched tests for one relation in one target environment."""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from collect_formal_e2_candidate_mirrors import repository_path
from run_formal_e2_python_replay import (
    RAN,
    clone_checkout,
    extract_failure_signature,
    normalize_failure_text,
    read_jsonl,
    run,
    write_arm,
)


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--relation-id", required=True)
    parser.add_argument("--mirror-root", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--tox", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--setuptools-version", default="75.6.0")
    parser.add_argument("--target-base-commit")
    parser.add_argument("--requirements-commit")
    parser.add_argument("--target-patch", type=Path)
    args = parser.parse_args()
    attempts = [
        row for row in read_jsonl(args.plan)
        if row.get("relation_id", row.get("case_id")) == args.relation_id
    ]
    if not attempts:
        raise SystemExit(f"relation is absent from plan: {args.relation_id}")
    plan = attempts[0]
    target_base_commit = args.target_base_commit or plan["target_base_commit"]
    requirements_commit = args.requirements_commit or plan["requirements_commit"]
    work = args.work_root / args.relation_id
    evidence = args.evidence_root / args.relation_id
    if work.exists() or evidence.exists():
        raise SystemExit(f"relation output already exists: {args.relation_id}")
    work.mkdir(parents=True)
    evidence.mkdir(parents=True)
    source_a0, source_a1 = work / "source-a0", work / "source-a1"
    target, requirements = work / "target", work / "requirements"
    clone_checkout(repository_path(args.mirror_root, plan["source_repository"]), source_a0, plan["source_base_commit"])
    clone_checkout(repository_path(args.mirror_root, plan["source_repository"]), source_a1, plan["source_head_commit"])
    clone_checkout(repository_path(args.mirror_root, plan["target_repository"]), target, target_base_commit)
    clone_checkout(repository_path(args.mirror_root, "openstack/requirements"), requirements, requirements_commit)
    pin = work / "pip-constraints.txt"
    pin.write_text(f"setuptools=={args.setuptools_version}\n", encoding="utf-8")
    environment = os.environ.copy()
    constraints_url = f"file://{(requirements / 'upper-constraints.txt').resolve()}"
    environment.update({
        "TOX_PYTHON": str(args.python.resolve()),
        "TOX_CONSTRAINTS_FILE": constraints_url,
        "UPPER_CONSTRAINTS_FILE": constraints_url,
        "PIP_CONSTRAINT": str(pin.resolve()),
    })
    setup_code, setup_output, _ = run([str(args.tox.resolve()), "-e", "py3", "--notest"], target, environment)
    (evidence / "environment-setup.log").write_text(setup_output, encoding="utf-8")
    pip, stestr = target / ".tox/py3/bin/pip", target / ".tox/py3/bin/stestr"
    if setup_code or not pip.exists() or not stestr.exists():
        write_json(evidence / "rejection.json", {
            "relation_id": args.relation_id, "reason": "target_environment_setup_failed", "exit_code": setup_code,
        })
        return 2

    results: dict[str, dict[str, tuple[int, str]]] = {row["case_id"]: {} for row in attempts}
    setup_logs = []
    for arm, source, target_commit in (
        ("A0", source_a0, target_base_commit),
        ("A1", source_a1, target_base_commit),
        ("A2", source_a1, target_base_commit if args.target_patch else plan["target_head_commit"]),
    ):
        subprocess.run(["git", "-C", str(target), "checkout", "-q", "--detach", target_commit], check=True)
        if arm == "A2" and args.target_patch:
            patch_result = subprocess.run(
                ["git", "-C", str(target), "apply", str(args.target_patch.resolve())],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            (evidence / "target-patch-apply.log").write_text(patch_result.stdout, encoding="utf-8")
            if patch_result.returncode:
                write_json(evidence / "rejection.json", {
                    "relation_id": args.relation_id,
                    "reason": "target_patch_does_not_apply_to_cutoff_snapshot",
                    "exit_code": patch_result.returncode,
                })
                return 2
        install_code, install_output, _ = run(
            [str(pip.resolve()), "install", "--no-deps", "-e", str(source.resolve())], target, environment
        )
        setup_logs.append(f"===== {arm} source install exit={install_code} =====\n{install_output}")
        for row in attempts:
            command = [str(stestr.resolve()), "run", row["test_selector"]]
            if install_code:
                code, output, elapsed = install_code, install_output, 0.0
            else:
                code, output, elapsed = run(command, target, environment)
            write_arm(evidence / row["case_id"], arm, ["stestr", "run", row["test_selector"]], code, output, elapsed)
            results[row["case_id"]][arm] = (code, output)
    (evidence / "arm-setup.log").write_text("\n".join(setup_logs), encoding="utf-8")

    adjudications = []
    strict_rows = []
    for row in attempts:
        arm_results = results[row["case_id"]]
        a0, a1, a2 = (arm_results[key] for key in ("A0", "A1", "A2"))
        signature = extract_failure_signature(a1[1])
        strict = (
            a0[0] == 0 and a1[0] != 0 and a2[0] == 0
            and RAN.search(a0[1]) is not None and RAN.search(a2[1]) is not None
            and signature is not None
            and signature not in normalize_failure_text(a0[1])
            and signature not in normalize_failure_text(a2[1])
        )
        adjudication = {
            "attempt_id": row["case_id"], "test_selector": row["test_selector"],
            "exit_codes": {key: arm_results[key][0] for key in ("A0", "A1", "A2")},
            "failure_signature": signature, "strict_e2": strict,
        }
        adjudications.append(adjudication)
        if strict:
            strict_rows.append((row, adjudication))
    (evidence / "attempts.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in adjudications), encoding="utf-8"
    )
    if not strict_rows:
        write_json(evidence / "rejection.json", {
            "relation_id": args.relation_id, "reason": "no_touched_test_satisfied_strict_e2",
            "attempt_count": len(attempts),
        })
        return 1
    selected, adjudication = strict_rows[0]
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter="\t", lineterminator="\n")
    writer.writerow(["arm", "exit_code", "result"])
    for arm in ("A0", "A1", "A2"):
        code = results[selected["case_id"]][arm][0]
        writer.writerow([arm, code, "pass" if code == 0 else "fail"])
    (evidence / "run-results.tsv").write_text(buffer.getvalue(), encoding="utf-8")
    if args.target_patch:
        (evidence / "target.patch").write_bytes(args.target_patch.read_bytes())
    write_json(evidence / "contract.json", {
        "schema_version": "1.0", **selected, "case_id": args.relation_id,
        "target_base_commit": target_base_commit,
        "requirements_commit": requirements_commit,
        "maintainer_target_base_commit": plan["target_base_commit"],
        "maintainer_target_head_commit": plan["target_head_commit"],
        "target_a2_kind": (
            "maintainer_patch_applied_to_cutoff_snapshot"
            if args.target_patch else "maintainer_target_revision"
        ),
        "target_patch_evidence": "target.patch" if args.target_patch else None,
        "selected_attempt_id": selected["case_id"],
        "primary_result_channel": "pre_existing_target_test",
        "command_provenance": {
            "repository": plan["target_repository"], "commit": target_base_commit, "path": "tox.ini",
        },
        "build_environment": {"setuptools_version": args.setuptools_version},
        "failure_signature": adjudication["failure_signature"],
        "arms": {"A0": "pass", "A1": "fail", "A2": "pass"},
        "machine_arm_verification": "passed",
        "strict_touched_test_count": len(strict_rows),
    })
    print(json.dumps({
        "relation_id": args.relation_id, "strict_e2": True,
        "selected_test": selected["test_selector"], "strict_touched_test_count": len(strict_rows),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

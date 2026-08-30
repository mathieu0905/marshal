#!/usr/bin/env python3
"""Execute one real pre-existing target Python test across strict A0/A1/A2."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any

from collect_formal_e2_candidate_mirrors import repository_path


FAILURE = re.compile(
    r"(?m)^\s*((?:[A-Za-z_]\w*\.)*[A-Za-z_]\w*"
    r"(?:Error|Exception|Forbidden|NotAuthorized):[^\n]+)"
)
BARE_FAILURE = re.compile(
    r"(?m)^\s*((?:[A-Za-z_]\w*\.)*[A-Za-z_]\w*"
    r"(?:Error|Exception|Forbidden|NotAuthorized))\s*$"
)
COMMAND_FAILURE = re.compile(r"(?m)^\s*([A-Za-z0-9_.-]+: error: [^\n]+)")
FAILED_SECTION = re.compile(r"(?m)^Failed [1-9][0-9]* tests? - output below:\s*$")
ADDRESS = re.compile(r"0x[0-9a-fA-F]+")
UUID = re.compile(
    r"(?<![0-9a-fA-F])[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}(?![0-9a-fA-F])"
)
RAN = re.compile(r"Ran:\s+([1-9][0-9]*)\s+tests?")


def normalize_failure_text(value: str) -> str:
    return UUID.sub("<uuid>", ADDRESS.sub("0x<address>", value))


def extract_failure_signature(output: str) -> str | None:
    failed = FAILED_SECTION.search(output)
    search_space = output[failed.end():] if failed else output
    patterns = (FAILURE, COMMAND_FAILURE, BARE_FAILURE) if failed else (
        FAILURE,
        COMMAND_FAILURE,
    )
    for pattern in patterns:
        match = pattern.search(search_space)
        if match:
            return normalize_failure_text(match.group(1).strip())
    return None


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def run(command: list[str], cwd: Path, environment: dict[str, str]) -> tuple[int, str, float]:
    started = time.monotonic()
    completed = subprocess.run(
        command, cwd=cwd, env=environment, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, errors="replace", check=False,
    )
    return completed.returncode, completed.stdout, time.monotonic() - started


def clone_checkout(mirror: Path, destination: Path, commit: str) -> None:
    subprocess.run(["git", "clone", "-q", "--no-checkout", str(mirror), str(destination)], check=True)
    subprocess.run(["git", "-C", str(destination), "checkout", "-q", "--detach", commit], check=True)


def write_arm(root: Path, arm: str, command: list[str], code: int, output: str, elapsed: float) -> None:
    destination = root / arm.lower()
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "command.log").write_text(output, encoding="utf-8")
    (destination / "summary.json").write_text(json.dumps({
        "schema_version": "1.0", "arm": arm, "command": command,
        "exit_code": code, "elapsed_seconds": elapsed,
        "finished_at": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--mirror-root", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--tox", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    args = parser.parse_args()
    plan = next(row for row in read_jsonl(args.plan) if row["case_id"] == args.case_id)
    work = args.work_root / args.case_id
    evidence = args.evidence_root / args.case_id
    if work.exists() or evidence.exists():
        raise SystemExit(f"case output already exists: {args.case_id}")
    work.mkdir(parents=True)
    evidence.mkdir(parents=True)
    source_a0 = work / "source-a0"
    source_a1 = work / "source-a1"
    target = work / "target"
    requirements = work / "requirements"
    clone_checkout(repository_path(args.mirror_root, plan["source_repository"]), source_a0, plan["source_base_commit"])
    clone_checkout(repository_path(args.mirror_root, plan["source_repository"]), source_a1, plan["source_head_commit"])
    clone_checkout(repository_path(args.mirror_root, plan["target_repository"]), target, plan["target_base_commit"])
    clone_checkout(repository_path(args.mirror_root, "openstack/requirements"), requirements, plan["requirements_commit"])
    pin = work / "pip-constraints.txt"
    pin.write_text("setuptools==75.6.0\n", encoding="utf-8")
    environment = os.environ.copy()
    environment.update({
        "TOX_PYTHON": str(args.python.resolve()),
        "TOX_CONSTRAINTS_FILE": f"file://{(requirements / 'upper-constraints.txt').resolve()}",
        "PIP_CONSTRAINT": str(pin.resolve()),
    })
    setup_code, setup_output, _ = run([str(args.tox.resolve()), "-e", "py3", "--notest"], target, environment)
    (evidence / "environment-setup.log").write_text(setup_output, encoding="utf-8")
    test_environment = target / ".tox/py3"
    pip = test_environment / "bin/pip"
    stestr = test_environment / "bin/stestr"
    if setup_code or not pip.exists() or not stestr.exists():
        (evidence / "rejection.json").write_text(json.dumps({
            "case_id": args.case_id, "reason": "target_environment_setup_failed", "exit_code": setup_code,
        }, indent=2) + "\n", encoding="utf-8")
        return 2

    setup_logs = []
    command = [str(stestr.resolve()), "run", plan["test_selector"]]
    results = []
    for arm, source, target_commit in (
        ("A0", source_a0, plan["target_base_commit"]),
        ("A1", source_a1, plan["target_base_commit"]),
        ("A2", source_a1, plan["target_head_commit"]),
    ):
        subprocess.run(["git", "-C", str(target), "checkout", "-q", "--detach", target_commit], check=True)
        install_code, install_output, _ = run(
            [str(pip.resolve()), "install", "--no-deps", "-e", str(source.resolve())],
            target, environment,
        )
        setup_logs.append(f"===== {arm} source install exit={install_code} =====\n{install_output}")
        if install_code:
            code, output, elapsed = install_code, install_output, 0.0
        else:
            code, output, elapsed = run(command, target, environment)
        write_arm(evidence, arm, ["stestr", "run", plan["test_selector"]], code, output, elapsed)
        results.append((arm, code, output))
    (evidence / "arm-setup.log").write_text("\n".join(setup_logs), encoding="utf-8")
    a0, a1, a2 = results
    signature = extract_failure_signature(a1[2])
    strict = (
        a0[1] == 0 and a1[1] != 0 and a2[1] == 0
        and RAN.search(a0[2]) is not None and RAN.search(a2[2]) is not None
        and signature is not None
        and signature not in normalize_failure_text(a0[2])
        and signature not in normalize_failure_text(a2[2])
    )
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter="\t", lineterminator="\n")
    writer.writerow(["arm", "exit_code", "result"])
    for arm, code, _output in results:
        writer.writerow([arm, code, "pass" if code == 0 else "fail"])
    (evidence / "run-results.tsv").write_text(buffer.getvalue(), encoding="utf-8")
    if strict:
        (evidence / "contract.json").write_text(json.dumps({
            "schema_version": "1.0", **plan,
            "primary_result_channel": "pre_existing_target_test",
            "command_provenance": {"repository": plan["target_repository"], "commit": plan["target_base_commit"], "path": "tox.ini"},
            "failure_signature": signature,
            "arms": {"A0": "pass", "A1": "fail", "A2": "pass"},
            "machine_arm_verification": "passed",
        }, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"case_id": args.case_id, "strict_e2": True, "signature": signature}, indent=2))
        return 0
    (evidence / "rejection.json").write_text(json.dumps({
        "case_id": args.case_id, "reason": "strict_arm_or_signature_gate_failed",
        "exit_codes": {arm: code for arm, code, _output in results},
        "a0_ran_tests": bool(RAN.search(a0[2])), "a2_ran_tests": bool(RAN.search(a2[2])),
        "failure_signature": signature,
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

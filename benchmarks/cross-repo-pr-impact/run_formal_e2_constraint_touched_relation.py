#!/usr/bin/env python3
"""Replay a one-pin global-constraints change across real target tests.

A0 uses the source opening base constraints and the target cutoff snapshot.
A1 changes only to the source opening head constraints.  A2 keeps those new
constraints and applies the maintainer target patch to the cutoff snapshot.
Each arm gets an independently created tox environment so dependency state
cannot leak between arms.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
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


PIN = re.compile(r"^([A-Za-z0-9_.-]+)===(\S+)$")


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def read_pins(path: Path) -> dict[str, str]:
    pins: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = PIN.match(line.strip())
        if match:
            pins[match.group(1).lower()] = match.group(2)
    return pins


def changed_pin_rows(
    old: Path, new: Path
) -> list[tuple[str, str | None, str | None]]:
    old_pins = read_pins(old)
    new_pins = read_pins(new)
    return [
        (name, old_pins.get(name), new_pins.get(name))
        for name in sorted(old_pins.keys() | new_pins.keys())
        if old_pins.get(name) != new_pins.get(name)
    ]


def changed_pin(old: Path, new: Path) -> tuple[str, str, str]:
    changed = changed_pin_rows(old, new)
    if len(changed) != 1 or changed[0][1] is None or changed[0][2] is None:
        raise ValueError(f"expected exactly one changed pinned distribution, got {changed}")
    name, old_version, new_version = changed[0]
    return name, old_version, new_version


def selected_changed_pin(
    old: Path, new: Path, distribution: str
) -> tuple[str, str, str]:
    """Select one routed pin while preserving every opening constraint change."""
    key = distribution.lower()
    changed = changed_pin_rows(old, new)
    matches = [row for row in changed if row[0] == key]
    if len(matches) != 1 or matches[0][1] is None or matches[0][2] is None:
        raise ValueError(
            f"selected distribution must have one old/new exact pin change: "
            f"distribution={distribution!r}, changed={changed}"
        )
    name, old_version, new_version = matches[0]
    return name, old_version, new_version


def constraint_source_application(
    changes: list[tuple[str, str | None, str | None]],
) -> str:
    return (
        "global_constraints_single_pin"
        if len(changes) == 1
        else "global_constraints_full_opening_diff"
    )


def installed_version(python: Path, distribution: str, cwd: Path, environment: dict[str, str]) -> tuple[int, str]:
    code, output, _ = run(
        [
            str(python.absolute()),
            "-c",
            "import importlib.metadata as m,sys; print(m.version(sys.argv[1]))",
            distribution,
        ],
        cwd,
        environment,
    )
    return code, output.strip()


PYTEST_RAN = re.compile(
    r"(?m)^=+ .*?\b([1-9][0-9]*) passed(?:,| in ).*?=+\s*$"
)
UNITTEST_RAN = re.compile(r"(?m)^Ran ([1-9][0-9]*) tests? in \S+")


def tests_ran(output: str) -> bool:
    return any(pattern.search(output) is not None for pattern in (RAN, PYTEST_RAN, UNITTEST_RAN))


def planned_test_command(
    row: dict[str, Any], test_environment: Path
) -> tuple[list[str], list[str]]:
    recorded = row.get("test_command") or ["stestr", "run", row["test_selector"]]
    if (
        not isinstance(recorded, list)
        or not recorded
        or any(not isinstance(item, str) or not item for item in recorded)
    ):
        raise ValueError(f"test_command must be a non-empty string list: {recorded!r}")
    if recorded[0] in {"stestr", "pytest"}:
        executable = test_environment / "bin" / recorded[0]
        if not executable.is_file():
            raise ValueError(f"test environment lacks {recorded[0]}: {executable}")
        return [str(executable.resolve()), *recorded[1:]], recorded
    if recorded[:2] == ["bash", "tools/unit_tests.sh"]:
        if len(recorded) >= 3 and recorded[2] == "python":
            python = test_environment / "bin" / "python"
            if not python.is_file():
                raise ValueError(
                    f"test environment lacks python required by tools/unit_tests.sh: {python}"
                )
            # Keep the virtualenv path itself. Resolving the python symlink to
            # the base interpreter drops virtualenv package discovery.
            return [*recorded[:2], str(python.absolute()), *recorded[3:]], recorded
        pytest = test_environment / "bin" / "pytest"
        if not pytest.is_file():
            raise ValueError(f"test environment lacks pytest required by tools/unit_tests.sh: {pytest}")
        return recorded.copy(), recorded
    raise ValueError(
        "test_command must invoke stestr, pytest, or the repository-native "
        f"bash tools/unit_tests.sh command: {recorded!r}"
    )


def without_proxy_environment(environment: dict[str, str]) -> dict[str, str]:
    return {
        key: value
        for key, value in environment.items()
        if key.lower() not in {"http_proxy", "https_proxy", "all_proxy"}
    }


def bootstrap_constraint_lines(
    values: list[str], base_constraint: str | None = "setuptools==75.6.0"
) -> list[str]:
    """Return deterministic, line-safe constraints for historical builds."""
    lines = [base_constraint] if base_constraint else []
    for value in values:
        if not isinstance(value, str) or not value.strip() or "\n" in value or "\r" in value:
            raise ValueError("bootstrap constraints must be non-empty single lines")
        constraint = value.strip()
        if constraint not in lines:
            lines.append(constraint)
    return lines


def parse_environment_overrides(values: list[str], option: str) -> dict[str, str]:
    overrides = {}
    for item in values:
        key, separator, value = item.partition("=")
        if not separator or not key:
            raise ValueError(f"{option} must use KEY=VALUE")
        overrides[key] = value
    return overrides


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
    parser.add_argument("--test-environment", action="append", default=[])
    parser.add_argument("--setup-environment", action="append", default=[])
    parser.add_argument("--bootstrap-constraint", action="append", default=[])
    parser.add_argument("--virtualenv-pip-version")
    parser.add_argument("--virtualenv-setuptools-version")
    args = parser.parse_args()

    if args.virtualenv_pip_version and not re.fullmatch(
        r"[A-Za-z0-9_.!+~-]+", args.virtualenv_pip_version
    ):
        raise SystemExit("--virtualenv-pip-version contains unsupported characters")
    if args.virtualenv_setuptools_version and not re.fullmatch(
        r"[A-Za-z0-9_.!+~-]+", args.virtualenv_setuptools_version
    ):
        raise SystemExit("--virtualenv-setuptools-version contains unsupported characters")

    try:
        test_environment_overrides = parse_environment_overrides(
            args.test_environment, "--test-environment"
        )
        setup_environment_overrides = parse_environment_overrides(
            args.setup_environment, "--setup-environment"
        )
    except ValueError as error:
        raise SystemExit(str(error)) from error

    attempts = [
        row for row in read_jsonl(args.plan)
        if row.get("relation_id", row.get("case_id")) == args.relation_id
    ]
    if not attempts:
        raise SystemExit(f"relation is absent from plan: {args.relation_id}")
    plan = attempts[0]
    if plan["source_repository"] != "openstack/requirements":
        raise SystemExit("constraint replay requires openstack/requirements as the source repository")
    work = args.work_root / args.relation_id
    evidence = args.evidence_root / args.relation_id
    if work.exists() or evidence.exists():
        raise SystemExit(f"relation output already exists: {args.relation_id}")
    work.mkdir(parents=True)
    evidence.mkdir(parents=True)

    requirements_a0 = work / "requirements-a0"
    requirements_a1 = work / "requirements-a1"
    clone_checkout(
        repository_path(args.mirror_root, plan["source_repository"]),
        requirements_a0,
        plan["source_base_commit"],
    )
    clone_checkout(
        repository_path(args.mirror_root, plan["source_repository"]),
        requirements_a1,
        plan["source_head_commit"],
    )
    old_constraints = requirements_a0 / "upper-constraints.txt"
    new_constraints = requirements_a1 / "upper-constraints.txt"
    constraint_changes = changed_pin_rows(old_constraints, new_constraints)
    selected_distribution = plan.get("changed_distribution")
    if selected_distribution:
        distribution, old_version, new_version = selected_changed_pin(
            old_constraints, new_constraints, selected_distribution
        )
        source_application = constraint_source_application(constraint_changes)
    else:
        distribution, old_version, new_version = changed_pin(
            old_constraints, new_constraints
        )
        source_application = "global_constraints_single_pin"
    a0_pins = read_pins(requirements_a0 / "upper-constraints.txt")
    a1_pins = read_pins(requirements_a1 / "upper-constraints.txt")
    historical_setuptools = a0_pins.get("setuptools")
    selected_setuptools = args.virtualenv_setuptools_version or (
        historical_setuptools
        if historical_setuptools and historical_setuptools == a1_pins.get("setuptools")
        else None
    )
    bootstrap_setuptools = (
        f"setuptools==={selected_setuptools}" if selected_setuptools else None
    )
    tox_environment = plan.get("tox_environment", "py3")
    if not isinstance(tox_environment, str) or not tox_environment.strip():
        raise SystemExit("tox_environment must be a non-empty string")

    pin = work / "bootstrap-constraints.txt"
    bootstrap_constraints = bootstrap_constraint_lines(
        args.bootstrap_constraint,
        bootstrap_setuptools or (
            None if distribution == "setuptools" else "setuptools==75.6.0"
        ),
    )
    pin.write_text("\n".join(bootstrap_constraints) + "\n", encoding="utf-8")
    arm_results: dict[str, dict[str, tuple[int, str]]] = {
        row["case_id"]: {} for row in attempts
    }
    setup_records = []
    installed_versions: dict[str, str] = {}
    for arm, constraints, expected_version in (
        ("A0", requirements_a0, old_version),
        ("A1", requirements_a1, new_version),
        ("A2", requirements_a1, new_version),
    ):
        target = work / f"target-{arm.lower()}"
        clone_checkout(
            repository_path(args.mirror_root, plan["target_repository"]),
            target,
            args.target_base_commit,
        )
        if arm == "A2":
            applied = subprocess.run(
                ["git", "-C", str(target), "apply", str(args.target_patch.resolve())],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            (evidence / "target-patch-apply.log").write_text(applied.stdout, encoding="utf-8")
            if applied.returncode:
                write_json(evidence / "rejection.json", {
                    "relation_id": args.relation_id,
                    "reason": "target_patch_does_not_apply_to_cutoff_snapshot",
                    "exit_code": applied.returncode,
                })
                return 2
        environment = os.environ.copy()
        constraints_url = f"file://{(constraints / 'upper-constraints.txt').resolve()}"
        environment.update({
            "TOX_PYTHON": str(args.python.resolve()),
            "TOX_CONSTRAINTS_FILE": constraints_url,
            "UPPER_CONSTRAINTS_FILE": constraints_url,
            "PIP_CONSTRAINT": str(pin.resolve()),
            "PIP_BUILD_CONSTRAINT": str(pin.resolve()),
        })
        environment.update(setup_environment_overrides)
        if args.virtualenv_pip_version:
            environment["VIRTUALENV_PIP"] = args.virtualenv_pip_version
        if selected_setuptools:
            environment["VIRTUALENV_SETUPTOOLS"] = selected_setuptools
        setup_code, setup_output, elapsed = run(
            [str(args.tox.resolve()), "-e", tox_environment, "--notest"], target, environment
        )
        setup_records.append({
            "arm": arm,
            "constraint_commit": plan["source_base_commit"] if arm == "A0" else plan["source_head_commit"],
            "expected_source_version": expected_version,
            "exit_code": setup_code,
            "elapsed_seconds": elapsed,
        })
        (evidence / f"environment-setup-{arm.lower()}.log").write_text(setup_output, encoding="utf-8")
        test_environment = target / ".tox" / tox_environment
        arm_python = test_environment / "bin/python"
        if setup_code or not arm_python.exists():
            write_json(evidence / "rejection.json", {
                "relation_id": args.relation_id,
                "reason": "target_environment_setup_failed",
                "arm": arm,
                "exit_code": setup_code,
            })
            write_json(evidence / "environment-setups.json", setup_records)
            return 2
        version_code, observed_version = installed_version(
            arm_python, distribution, target, environment
        )
        installed_versions[arm] = observed_version
        if version_code or observed_version != expected_version:
            write_json(evidence / "rejection.json", {
                "relation_id": args.relation_id,
                "reason": "source_constraint_not_consumed",
                "arm": arm,
                "distribution": distribution,
                "expected_version": expected_version,
                "observed_version": observed_version,
                "version_probe_exit_code": version_code,
            })
            write_json(evidence / "environment-setups.json", setup_records)
            return 2
        for row in attempts:
            command, recorded_command = planned_test_command(row, test_environment)
            command_environment = without_proxy_environment(environment)
            command_environment["PATH"] = os.pathsep.join([
                str((test_environment / "bin").resolve()),
                command_environment.get("PATH", ""),
            ])
            command_environment.update(test_environment_overrides)
            code, output, test_elapsed = run(command, target, command_environment)
            write_arm(
                evidence / row["case_id"], arm,
                recorded_command,
                code, output, test_elapsed,
            )
            arm_results[row["case_id"]][arm] = (code, output)
    write_json(evidence / "environment-setups.json", setup_records)

    adjudications = []
    strict_rows = []
    for row in attempts:
        results = arm_results[row["case_id"]]
        a0, a1, a2 = (results[key] for key in ("A0", "A1", "A2"))
        signature = extract_failure_signature(a1[1])
        strict = (
            a0[0] == 0 and a1[0] != 0 and a2[0] == 0
            and tests_ran(a0[1]) and tests_ran(a2[1])
            and signature is not None
            and signature not in normalize_failure_text(a0[1])
            and signature not in normalize_failure_text(a2[1])
        )
        adjudication = {
            "attempt_id": row["case_id"],
            "test_selector": row["test_selector"],
            "exit_codes": {key: results[key][0] for key in ("A0", "A1", "A2")},
            "failure_signature": signature,
            "strict_e2": strict,
        }
        adjudications.append(adjudication)
        if strict:
            strict_rows.append((row, adjudication))
    (evidence / "attempts.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in adjudications),
        encoding="utf-8",
    )
    if not strict_rows:
        write_json(evidence / "rejection.json", {
            "relation_id": args.relation_id,
            "reason": "no_touched_test_satisfied_strict_e2",
            "attempt_count": len(attempts),
        })
        return 1

    selected, adjudication = strict_rows[0]
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter="\t", lineterminator="\n")
    writer.writerow(["arm", "exit_code", "result"])
    for arm in ("A0", "A1", "A2"):
        code = arm_results[selected["case_id"]][arm][0]
        writer.writerow([arm, code, "pass" if code == 0 else "fail"])
    (evidence / "run-results.tsv").write_text(buffer.getvalue(), encoding="utf-8")
    (evidence / "target.patch").write_bytes(args.target_patch.read_bytes())
    write_json(evidence / "contract.json", {
        "schema_version": "1.0",
        **selected,
        "case_id": args.relation_id,
        "target_base_commit": args.target_base_commit,
        "requirements_commit": plan["source_base_commit"],
        "requirements_a1_commit": plan["source_head_commit"],
        "target_a2_kind": "maintainer_patch_applied_to_cutoff_snapshot",
        "target_patch_evidence": "target.patch",
        "selected_attempt_id": selected["case_id"],
        "primary_result_channel": "pre_existing_target_test",
        "command_provenance": {
            "repository": plan["target_repository"],
            "commit": args.target_base_commit,
            "path": "tox.ini",
        },
        "tox_environment": tox_environment,
        "source_application": source_application,
        "opening_constraint_changes": [
            {
                "distribution": name,
                "old_version": old,
                "new_version": new,
            }
            for name, old, new in constraint_changes
        ],
        "changed_distribution": distribution,
        "source_versions": {"A0": old_version, "A1": new_version, "A2": new_version},
        "installed_source_versions": installed_versions,
        "failure_signature": adjudication["failure_signature"],
        "arms": {"A0": "pass", "A1": "fail", "A2": "pass"},
        "machine_arm_verification": "passed",
        "strict_touched_test_count": len(strict_rows),
        "test_environment_keys": sorted(test_environment_overrides),
        "setup_environment_keys": sorted(setup_environment_overrides),
        "bootstrap_constraints": bootstrap_constraints,
        "virtualenv_pip_version": args.virtualenv_pip_version,
        "virtualenv_setuptools_version": selected_setuptools,
    })
    print(json.dumps({
        "relation_id": args.relation_id,
        "strict_e2": True,
        "selected_test": selected["test_selector"],
        "changed_distribution": distribution,
        "strict_touched_test_count": len(strict_rows),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

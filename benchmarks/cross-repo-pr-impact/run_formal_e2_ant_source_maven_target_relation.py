#!/usr/bin/env python3
"""Replay an Ant-built source opening against a Maven target at its cutoff."""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import zipfile
from pathlib import Path

from run_formal_e2_maven_source_relation import (
    clone_checkout,
    commit_patch_with_maintainer_metadata,
    java_environment,
    mirror_path,
    read_jsonl,
    run,
    successful_test_count,
    write_json,
)


def environment_overrides(values: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError("--environment values must use KEY=VALUE")
        key, item = value.split("=", 1)
        if not key or "\0" in key or "\0" in item:
            raise ValueError("--environment contains an invalid key or value")
        result[key] = item
    return result


def artifact_inventory(
    source: Path, artifacts: list[dict], side: str
) -> list[dict[str, object]]:
    inventory: list[dict[str, object]] = []
    for artifact in artifacts:
        jar = source / artifact["jar_path"]
        if not jar.is_file():
            raise ValueError(f"built source artifact is missing: {jar}")
        with zipfile.ZipFile(jar) as archive:
            entries = set(archive.namelist())
        required_entries = artifact.get(
            f"{side.lower()}_required_entries", artifact.get("required_entries", [])
        )
        forbidden_entries = artifact.get(
            f"{side.lower()}_forbidden_entries", artifact.get("forbidden_entries", [])
        )
        inventory.append({
            "artifact_id": artifact["artifact_id"],
            "jar_path": artifact["jar_path"],
            "size_bytes": jar.stat().st_size,
            "required_entries": {
                entry: entry in entries for entry in required_entries
            },
            "forbidden_entries": {
                entry: entry in entries for entry in forbidden_entries
            },
        })
    return inventory


def inventory_matches(inventory: list[dict[str, object]]) -> bool:
    return all(
        all(row["required_entries"].values())
        and not any(row["forbidden_entries"].values())
        for row in inventory
    )


def install_artifacts(
    source: Path,
    artifacts: list[dict],
    repository: Path,
    maven: Path,
    environment: dict[str, str],
    evidence: Path,
    side: str,
) -> None:
    for artifact in artifacts:
        jar = (source / artifact["jar_path"]).resolve()
        pom = Path(artifact["pom_template"]).resolve()
        completed = run(
            [
                str(maven), "--offline", f"-Dmaven.repo.local={repository}",
                "org.apache.maven.plugins:maven-install-plugin:3.1.3:install-file",
                f"-Dfile={jar}", f"-DpomFile={pom}",
            ],
            cwd=source,
            environment=environment,
        )
        (evidence / f"source-{side}.install-{artifact['artifact_id']}.log").write_text(
            completed.stdout, encoding="utf-8"
        )
        if completed.returncode:
            raise RuntimeError(
                f"source artifact install failed for {artifact['artifact_id']}"
            )


def apply_source_selection(
    target: Path,
    repository: Path,
    maven: Path,
    environment: dict[str, str],
    includes: str,
    version: str,
    log: Path,
) -> None:
    completed = run(
        [
            str(maven), "--offline", f"-Dmaven.repo.local={repository}",
            "org.codehaus.mojo:versions-maven-plugin:2.16.2:use-dep-version",
            f"-Dincludes={includes}", f"-DdepVersion={version}",
            "-DforceVersion=true", "-DgenerateBackupPoms=false",
        ],
        cwd=target,
        environment=environment,
    )
    log.write_text(completed.stdout, encoding="utf-8")
    if completed.returncode:
        raise RuntimeError("target source-artifact selection failed")


def commit_evaluator_setup(target: Path) -> None:
    """Make the trusted dependency-selection rewrite the A-arm baseline."""
    environment = dict(os.environ)
    environment.update(
        {
            "GIT_AUTHOR_NAME": "Marshal evaluator",
            "GIT_AUTHOR_EMAIL": "evaluator@marshal.invalid",
            "GIT_COMMITTER_NAME": "Marshal evaluator",
            "GIT_COMMITTER_EMAIL": "evaluator@marshal.invalid",
        }
    )
    staged = subprocess.run(
        ["git", "add", "--all"], cwd=target, env=environment,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    if staged.returncode:
        raise RuntimeError(staged.stdout)
    committed = subprocess.run(
        ["git", "commit", "--quiet", "--no-gpg-sign", "-m", "evaluator source selection"],
        cwd=target, env=environment, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False,
    )
    if committed.returncode:
        raise RuntimeError(committed.stdout)


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
    parser.add_argument("--maven", type=Path, required=True)
    parser.add_argument("--source-java-home", type=Path, required=True)
    parser.add_argument("--target-java-home", type=Path, required=True)
    parser.add_argument("--ant", type=Path, required=True)
    parser.add_argument("--junit", type=Path, required=True)
    parser.add_argument("--seed-repository", type=Path, required=True)
    parser.add_argument("--target-command-wrapper", type=Path)
    parser.add_argument("--environment", action="append", default=[])
    args = parser.parse_args()

    rows = [
        row for row in read_jsonl(args.plan)
        if row.get("relation_id", row.get("case_id")) == args.relation_id
    ]
    if len(rows) != 1:
        raise ValueError(f"relation must have exactly one plan row, got {len(rows)}")
    plan = rows[0]
    artifacts = plan.get("source_artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ValueError("source_artifacts must be a non-empty list")
    for artifact in artifacts:
        for key in ("artifact_id", "jar_path", "pom_template"):
            if not isinstance(artifact.get(key), str) or not artifact[key]:
                raise ValueError(f"source artifact is missing {key}")
        if not Path(artifact["pom_template"]).resolve().is_file():
            raise ValueError(f"source artifact POM is missing: {artifact['pom_template']}")

    work = args.work_root / args.relation_id
    evidence = args.evidence_root / args.relation_id
    if work.exists() or evidence.exists():
        raise ValueError("relation work or evidence directory already exists")
    work.mkdir(parents=True)
    evidence.mkdir(parents=True)

    overrides = environment_overrides(args.environment)
    source_environment = java_environment(dict(os.environ), args.source_java_home)
    target_environment = java_environment(dict(os.environ), args.target_java_home)
    source_environment.update(overrides)
    target_environment.update(overrides)
    source_mirror = mirror_path(args.mirror_root, plan["source_repository"])
    target_mirror = mirror_path(args.mirror_root, plan["target_repository"])

    sources = {"A0": work / "source-a0", "A1": work / "source-a1"}
    clone_checkout(source_mirror, sources["A0"], plan["source_base_commit"])
    clone_checkout(source_mirror, sources["A1"], plan["source_head_commit"])
    actual_parent = subprocess.check_output(
        ["git", "rev-parse", f"{plan['source_head_commit']}^"],
        cwd=sources["A1"], text=True,
    ).strip()
    if actual_parent != plan["source_base_commit"]:
        raise ValueError("source opening is not the planned direct parent/child pair")

    ant_targets = plan.get("source_build_targets", ["clobber", "buildsource", "buildjars"])
    if not isinstance(ant_targets, list) or not ant_targets or not all(
        isinstance(value, str) and value for value in ant_targets
    ):
        raise ValueError("source_build_targets must be a non-empty string list")
    inventories: dict[str, list[dict[str, object]]] = {}
    for side in ("A0", "A1"):
        command = [str(args.ant), "-quiet", f"-Djunit={args.junit.resolve()}", *ant_targets]
        completed = run(command, cwd=sources[side], environment=source_environment)
        (evidence / f"source-{side.lower()}.build.log").write_text(
            completed.stdout, encoding="utf-8"
        )
        if completed.returncode:
            raise RuntimeError(f"Ant source build failed for {side}")
        inventories[side] = artifact_inventory(sources[side], artifacts, side)
        if not inventory_matches(inventories[side]):
            write_json(evidence / "rejection.json", {
                "case_id": args.relation_id,
                "reason": "source_artifact_inventory_assertion_failed",
                "side": side,
                "inventory": inventories[side],
            })
            return 1

    repositories: dict[str, Path] = {}
    for arm in ("A0", "A1", "A2"):
        repositories[arm] = (work / f"m2-{arm.lower()}").resolve()
        shutil.copytree(args.seed_repository, repositories[arm])
        source_side = "A0" if arm == "A0" else "A1"
        install_artifacts(
            sources[source_side], artifacts, repositories[arm], args.maven,
            target_environment, evidence, arm.lower(),
        )

    targets: dict[str, Path] = {}
    version = plan["source_artifact_version"]
    includes = plan["source_dependency_includes"]
    for arm in ("A0", "A1", "A2"):
        target = work / f"target-{arm.lower()}"
        clone_checkout(target_mirror, target, args.target_base_commit)
        targets[arm] = target
        apply_source_selection(
            target, repositories[arm], args.maven, target_environment,
            includes, version, evidence / f"target-{arm.lower()}.source-selection.log",
        )
        commit_evaluator_setup(target)

    applied = subprocess.run(
        ["git", "apply", "--check", str(args.target_patch.resolve())],
        cwd=targets["A2"], text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False,
    )
    if applied.returncode:
        write_json(evidence / "rejection.json", {
            "case_id": args.relation_id,
            "reason": "maintainer_patch_does_not_apply_to_cutoff_target",
            "detail": applied.stdout[-2000:],
        })
        return 2
    applied = subprocess.run(
        ["git", "apply", str(args.target_patch.resolve())],
        cwd=targets["A2"], text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False,
    )
    if applied.returncode:
        raise RuntimeError(applied.stdout)
    shutil.copy2(args.target_patch, evidence / "target.patch")
    target_patch_commit = None
    if plan.get("commit_target_patch_with_maintainer_metadata"):
        target_patch_commit = commit_patch_with_maintainer_metadata(
            targets["A2"], plan["target_head_commit"]
        )

    logical_command = plan["test_command"]
    if not logical_command or logical_command[0] != "mvn":
        raise ValueError("Ant/Maven replay requires a target command beginning with mvn")
    results: dict[str, tuple[int, str]] = {}
    for arm in ("A0", "A1", "A2"):
        target_command = [
            str(args.maven), f"-Dmaven.repo.local={repositories[arm]}",
            *logical_command[1:],
        ]
        if args.target_command_wrapper is not None:
            target_command = [str(args.target_command_wrapper.resolve()), *target_command]
        completed = run(
            target_command,
            cwd=targets[arm], environment=target_environment,
        )
        arm_dir = evidence / args.relation_id / arm.lower()
        arm_dir.mkdir(parents=True)
        (arm_dir / "command.log").write_text(completed.stdout, encoding="utf-8")
        write_json(arm_dir / "summary.json", {
            "arm": arm, "command": logical_command, "exit_code": completed.returncode,
        })
        results[arm] = (completed.returncode, completed.stdout)

    signature = plan["failure_signature"]
    exits = {arm: result[0] for arm, result in results.items()}
    test_counts = {arm: successful_test_count(results[arm][1]) for arm in ("A0", "A2")}
    strict = (
        exits["A0"] == 0 and exits["A1"] != 0 and exits["A2"] == 0
        and signature in results["A1"][1]
        and signature not in results["A0"][1]
        and signature not in results["A2"][1]
        and test_counts["A0"] > 0 and test_counts["A2"] > 0
    )
    with (evidence / "run-results.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("arm", "exit_code"), delimiter="\t")
        writer.writeheader()
        for arm in ("A0", "A1", "A2"):
            writer.writerow({"arm": arm, "exit_code": exits[arm]})
    if not strict:
        write_json(evidence / "rejection.json", {
            "case_id": args.relation_id,
            "reason": "strict_arm_signature_or_test_execution_gate_failed",
            "exit_codes": exits,
            "failure_signature": signature,
            "tests_run": test_counts,
        })
        return 1

    ant_version = run([str(args.ant), "-version"], cwd=sources["A0"], environment=source_environment)
    java_version = run(
        [str(args.source_java_home / "bin" / "java"), "-version"],
        cwd=sources["A0"], environment=source_environment,
    )
    write_json(evidence / "contract.json", {
        "schema_version": "1.0",
        "case_id": args.relation_id,
        "candidate_id": plan["candidate_id"],
        "source_repository": plan["source_repository"],
        "source_base_commit": plan["source_base_commit"],
        "source_head_commit": plan["source_head_commit"],
        "source_application": "ant_built_maven_artifacts_from_opening_checkout",
        "source_artifact_versions": {arm: version for arm in ("A0", "A1", "A2")},
        "source_artifact_inventory": inventories,
        "source_build_targets": ant_targets,
        "source_toolchain": {
            "ant": ant_version.stdout.strip(),
            "java": java_version.stdout.strip(),
            "junit": str(args.junit.resolve()),
        },
        "built_source_commits": {
            "A0": plan["source_base_commit"],
            "A1": plan["source_head_commit"],
            "A2": plan["source_head_commit"],
        },
        "target_repository": plan["target_repository"],
        "target_base_commit": args.target_base_commit,
        "target_head_commit": plan["target_head_commit"],
        "target_change": plan["target_change"],
        "target_a2_kind": "maintainer_patch_applied_to_cutoff_snapshot",
        "target_patch_evidence": "target.patch",
        "target_patch_commit": target_patch_commit,
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
        "tests_run": test_counts,
    })
    print(json.dumps({"relation_id": args.relation_id, "strict_e2": True}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

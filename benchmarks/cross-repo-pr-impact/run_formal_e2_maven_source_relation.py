#!/usr/bin/env python3
"""Replay one Maven source-opening change against an opening-cutoff target."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run(command: list[str], *, cwd: Path, environment: dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def java_environment(base: dict[str, str], java_home: Path) -> dict[str, str]:
    environment = dict(base)
    resolved = java_home.resolve()
    environment["JAVA_HOME"] = str(resolved)
    environment["PATH"] = f"{resolved / 'bin'}:{environment['PATH']}"
    return environment


def mirror_path(root: Path, repository: str) -> Path:
    return root / f"{repository.replace('/', '__')}.git"


def clone_checkout(mirror: Path, destination: Path, commit: str) -> None:
    completed = subprocess.run(
        ["git", "clone", "--quiet", "--no-checkout", str(mirror), str(destination)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(completed.stdout)
    completed = subprocess.run(
        ["git", "checkout", "--quiet", "--detach", commit],
        cwd=destination,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(completed.stdout)


def commit_patch_with_maintainer_metadata(
    target: Path, maintainer_commit: str
) -> dict[str, str]:
    metadata = subprocess.run(
        [
            "git", "show", "-s",
            "--format=%an%x00%ae%x00%aI%x00%cn%x00%ce%x00%cI",
            maintainer_commit,
        ],
        cwd=target,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if metadata.returncode:
        raise RuntimeError(f"cannot read maintainer commit metadata: {metadata.stdout}")
    fields = metadata.stdout.strip().split("\0")
    if len(fields) != 6:
        raise ValueError("maintainer commit metadata is incomplete")
    author_name, author_email, author_date, committer_name, committer_email, committer_date = fields
    staged = subprocess.run(
        ["git", "add", "--all"], cwd=target, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    if staged.returncode:
        raise RuntimeError(staged.stdout)
    environment = dict(os.environ)
    environment.update({
        "GIT_AUTHOR_NAME": author_name,
        "GIT_AUTHOR_EMAIL": author_email,
        "GIT_AUTHOR_DATE": author_date,
        "GIT_COMMITTER_NAME": committer_name,
        "GIT_COMMITTER_EMAIL": committer_email,
        "GIT_COMMITTER_DATE": committer_date,
    })
    committed = subprocess.run(
        ["git", "commit", "--quiet", "--no-gpg-sign", "-C", maintainer_commit],
        cwd=target,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if committed.returncode:
        raise RuntimeError(committed.stdout)
    synthetic_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=target, text=True
    ).strip()
    return {
        "maintainer_commit": maintainer_commit,
        "maintainer_author_date": author_date,
        "maintainer_committer_date": committer_date,
        "replay_commit": synthetic_commit,
    }


def project_version(pom: Path) -> str:
    root = ET.parse(pom).getroot()
    namespace = root.tag.partition("}")[0] + "}" if "}" in root.tag else ""
    element = root.find(f"{namespace}version")
    if element is None or element.text is None or not element.text.strip():
        raise ValueError(f"cannot determine project version: {pom}")
    return element.text.strip()


def project_artifact_id(pom: Path) -> str:
    root = ET.parse(pom).getroot()
    namespace = root.tag.partition("}")[0] + "}" if "}" in root.tag else ""
    element = root.find(f"{namespace}artifactId")
    if element is None or element.text is None or not element.text.strip():
        raise ValueError(f"cannot determine project artifactId: {pom}")
    return element.text.strip()


def set_project_version(pom: Path, version: str) -> None:
    old = project_version(pom)
    text = pom.read_text(encoding="utf-8")
    # Maven permits the project-level <version> before or after <parent>.
    # The old implementation searched only after </parent>, which rejects
    # valid POMs such as Log4j's root POM where <version> precedes <parent>.
    # Locate all exact version elements and exclude the parent's version
    # element; requiring one remaining match prevents accidentally changing a
    # dependency/property version with the same value.
    needle = re.compile(r"<version>\s*" + re.escape(old) + r"\s*</version>")
    parent_start = text.find("<parent")
    parent_end = text.find("</parent>", parent_start)
    matches = [match for match in needle.finditer(text)]
    project_matches = [
        match
        for match in matches
        if not (
            parent_start >= 0
            and parent_end >= 0
            and parent_start <= match.start() <= parent_end + len("</parent>")
        )
    ]
    if len(project_matches) != 1:
        raise ValueError(f"project version is not uniquely replaceable: {pom}")
    match = project_matches[0]
    position = match.start()
    replacement = f"<version>{version}</version>"
    pom.write_text(
        text[:position] + replacement + text[match.end():],
        encoding="utf-8",
    )


def set_parent_version(pom: Path, version: str) -> None:
    text = pom.read_text(encoding="utf-8")
    start = text.find("<parent>")
    end = text.find("</parent>", start)
    if start < 0 or end < 0:
        raise ValueError(f"project parent is absent: {pom}")
    parent = text[start:end]
    match = re.search(r"<version>([^<]+)</version>", parent)
    if not match:
        raise ValueError(f"project parent version is absent: {pom}")
    absolute_start = start + match.start()
    absolute_end = start + match.end()
    pom.write_text(
        text[:absolute_start] + f"<version>{version}</version>" + text[absolute_end:],
        encoding="utf-8",
    )


def sync_reactor_parent_versions(
    source: Path, root_pom_relative: str, version: str, old_version: str | None = None
) -> list[str]:
    """Align child POM parent versions with a rewritten reactor root.

    A multi-module Maven checkout may keep the root project version in each
    child ``<parent>`` block.  Rewriting only the root makes ``-pl ... -am``
    resolve the children against the old snapshot and fail before compiling.
    Restrict replacements to POMs whose parent coordinates match the root and
    whose parent version is the old root version; unrelated dependency and
    property versions are left untouched.
    """
    root_pom = (source / root_pom_relative).resolve()
    root = ET.parse(root_pom).getroot()
    namespace = root.tag.partition("}")[0] + "}" if "}" in root.tag else ""
    group_element = root.find(f"{namespace}groupId")
    artifact_element = root.find(f"{namespace}artifactId")
    if (
        group_element is None
        or artifact_element is None
        or not group_element.text
        or not artifact_element.text
    ):
        raise ValueError(f"reactor root must declare groupId and artifactId: {root_pom}")
    parent_group = group_element.text.strip()
    parent_artifact = artifact_element.text.strip()
    old_version = old_version or project_version(root_pom)
    changed: list[str] = []
    for pom in sorted(source.rglob("pom.xml")):
        if pom.resolve() == root_pom:
            continue
        text = pom.read_text(encoding="utf-8")
        parent_match = re.search(
            r"<parent>(?P<body>.*?)</parent>", text, flags=re.DOTALL
        )
        if parent_match is None:
            continue
        body = parent_match.group("body")
        if not re.search(
            rf"<groupId>\s*{re.escape(parent_group)}\s*</groupId>", body
        ) or not re.search(
            rf"<artifactId>\s*{re.escape(parent_artifact)}\s*</artifactId>", body
        ):
            continue
        version_match = re.search(
            rf"<version>\s*{re.escape(old_version)}\s*</version>", body
        )
        if version_match is None:
            continue
        start = parent_match.start("body") + version_match.start()
        end = parent_match.start("body") + version_match.end()
        pom.write_text(
            text[:start] + f"<version>{version}</version>" + text[end:],
            encoding="utf-8",
        )
        changed.append(str(pom.relative_to(source)))
    return changed


def dependency_version(
    pom: Path, group: str, artifact: str, property_name: str | None = None
) -> str:
    text = pom.read_text(encoding="utf-8")
    if property_name:
        property_match = re.search(
            rf"<{re.escape(property_name)}>([^<]+)</{re.escape(property_name)}>",
            text,
        )
        if not property_match:
            raise ValueError(f"cannot find Maven property {property_name} in {pom}")
        return property_match.group(1)
    pattern = re.compile(
        rf"<dependency>\s*<groupId>{re.escape(group)}</groupId>\s*"
        rf"<artifactId>{re.escape(artifact)}</artifactId>\s*<version>([^<]+)</version>",
        re.MULTILINE,
    )
    match = pattern.search(text)
    if not match:
        raise ValueError(f"cannot find {group}:{artifact} dependency in {pom}")
    return match.group(1)


def install_source(
    source: Path,
    pom_relative: str,
    artifact_pom_relative: str,
    artifact_jar_relative: str | None,
    build_projects: list[str],
    version: str,
    repository: Path,
    maven: Path,
    environment: dict[str, str],
    log_prefix: Path,
    sync_reactor_parents: bool = False,
    build_pom_relative: str | None = None,
) -> Path:
    pom = (source / pom_relative).resolve()
    old_version = project_version(pom)
    set_project_version(pom, version)
    if sync_reactor_parents:
        sync_reactor_parent_versions(source, pom_relative, version, old_version)
    artifact_pom = (source / artifact_pom_relative).resolve()
    if not artifact_pom.is_file():
        raise ValueError(f"source artifact POM does not exist: {artifact_pom}")
    build_pom = (source / (build_pom_relative or pom_relative)).resolve()
    project_selector = []
    if build_projects and build_pom_relative is None:
        project_selector = ["-pl", ",".join(build_projects), "-am"]
    package = run(
        [
            str(maven), "-f", str(build_pom),
            f"-Dmaven.repo.local={repository}", "-Dmaven.test.skip=true",
            "-Dgpg.skip=true", "-Dmaven.javadoc.skip=true", "-Djacoco.skip=true",
            *project_selector,
            "package",
        ],
        cwd=source,
        environment=environment,
    )
    log_prefix.with_suffix(".package.log").write_text(package.stdout, encoding="utf-8")
    if package.returncode:
        raise RuntimeError(f"source package failed; see {log_prefix.with_suffix('.package.log')}")
    artifact_id = project_artifact_id(artifact_pom)
    jar = (
        source / artifact_jar_relative.format(version=version)
        if artifact_jar_relative is not None
        else artifact_pom.parent / "target" / f"{artifact_id}-{version}.jar"
    )
    if not jar.is_file():
        raise ValueError(f"expected main source artifact does not exist: {jar}")
    installed = run(
        [
            str(maven), f"-Dmaven.repo.local={repository}",
            "org.apache.maven.plugins:maven-install-plugin:3.1.3:install-file",
            f"-Dfile={jar}", f"-DpomFile={artifact_pom}",
        ],
        cwd=source,
        environment=environment,
    )
    log_prefix.with_suffix(".install.log").write_text(installed.stdout, encoding="utf-8")
    if installed.returncode:
        raise RuntimeError(f"source install failed; see {log_prefix.with_suffix('.install.log')}")
    return jar


def install_existing_jar(
    jar: Path,
    source: Path,
    pom_relative: str,
    artifact_pom_relative: str,
    version: str,
    repository: Path,
    maven: Path,
    environment: dict[str, str],
    log: Path,
    sync_reactor_parents: bool = False,
) -> None:
    pom = (source / pom_relative).resolve()
    old_version = project_version(pom)
    set_project_version(pom, version)
    if sync_reactor_parents:
        sync_reactor_parent_versions(source, pom_relative, version, old_version)
    artifact_pom = (source / artifact_pom_relative).resolve()
    if not artifact_pom.is_file():
        raise ValueError(f"source artifact POM does not exist: {artifact_pom}")
    installed = run(
        [
            str(maven), f"-Dmaven.repo.local={repository}",
            "org.apache.maven.plugins:maven-install-plugin:3.1.3:install-file",
            f"-Dfile={jar}", f"-DpomFile={artifact_pom}",
        ],
        cwd=source,
        environment=environment,
    )
    log.write_text(installed.stdout, encoding="utf-8")
    if installed.returncode:
        raise RuntimeError(f"source install failed; see {log}")


def install_parent_pom(
    pom: Path,
    repository: Path,
    maven: Path,
    environment: dict[str, str],
    log: Path,
) -> None:
    installed = run(
        [
            str(maven), f"-Dmaven.repo.local={repository}",
            "org.apache.maven.plugins:maven-install-plugin:3.1.3:install-file",
            f"-Dfile={pom}", f"-DpomFile={pom}", "-Dpackaging=pom",
        ],
        cwd=pom.parent,
        environment=environment,
    )
    log.write_text(installed.stdout, encoding="utf-8")
    if installed.returncode:
        raise RuntimeError(f"source parent POM install failed; see {log}")


TEST_SUMMARY = re.compile(
    r"Tests run: ([0-9]+), Failures: ([0-9]+), Errors: ([0-9]+), Skipped: ([0-9]+)"
)


def successful_test_count(output: str) -> int:
    return sum(
        int(match.group(1))
        for line in output.splitlines()
        if "Time elapsed:" in line
        for match in TEST_SUMMARY.finditer(line)
        if match.group(2) == "0" and match.group(3) == "0" and match.group(4) == "0"
    )


def planned_target_command(
    logical_command: list[str],
    target: Path,
    maven: Path,
    repository: Path,
) -> list[str]:
    if not logical_command:
        raise ValueError("Maven source replay requires a non-empty test_command")
    if logical_command[0] == "mvn":
        executable = maven
    elif logical_command[0] == "./mvnw":
        executable = (target / "mvnw").resolve()
        if not executable.is_file():
            raise ValueError(f"target Maven wrapper is missing: {executable}")
    else:
        raise ValueError(
            "Maven source replay requires a test_command beginning with mvn or ./mvnw"
        )
    return [
        str(executable),
        f"-Dmaven.repo.local={repository}",
        *logical_command[1:],
    ]


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
    parser.add_argument("--java-home", type=Path, required=True)
    parser.add_argument("--source-java-home", type=Path)
    parser.add_argument("--target-java-home", type=Path)
    parser.add_argument("--target-command-wrapper", type=Path)
    parser.add_argument("--seed-repository", type=Path, required=True)
    args = parser.parse_args()

    rows = [
        row for row in read_jsonl(args.plan)
        if row.get("relation_id", row.get("case_id")) == args.relation_id
    ]
    if len(rows) != 1:
        raise ValueError(f"relation must have exactly one plan row, got {len(rows)}")
    plan = rows[0]
    work = args.work_root / args.relation_id
    evidence = args.evidence_root / args.relation_id
    if work.exists() or evidence.exists():
        raise ValueError("relation work or evidence directory already exists")
    work.mkdir(parents=True)
    evidence.mkdir(parents=True)

    source_java_home = args.source_java_home or args.java_home
    target_java_home = args.target_java_home or args.java_home
    source_environment = java_environment(dict(os.environ), source_java_home)
    target_environment = java_environment(dict(os.environ), target_java_home)
    source_mirror = mirror_path(args.mirror_root, plan["source_repository"])
    target_mirror = mirror_path(args.mirror_root, plan["target_repository"])
    source_a0 = work / "source-a0"
    source_a1 = work / "source-a1"
    source_a2 = work / "source-a2"
    clone_checkout(source_mirror, source_a0, plan["source_base_commit"])
    clone_checkout(source_mirror, source_a1, plan["source_head_commit"])
    clone_checkout(source_mirror, source_a2, plan["source_head_commit"])
    target_a0_base_commit = plan.get("target_a0_base_commit", args.target_base_commit)
    if not isinstance(target_a0_base_commit, str) or not target_a0_base_commit:
        raise ValueError("target_a0_base_commit must be a non-empty string")
    targets = {}
    for arm in ("a0", "a1", "a2"):
        targets[arm] = work / f"target-{arm}"
        target_commit = (
            target_a0_base_commit if arm == "a0" else args.target_base_commit
        )
        clone_checkout(target_mirror, targets[arm], target_commit)
    applied = subprocess.run(
        ["git", "apply", "--check", str(args.target_patch.resolve())],
        cwd=targets["a2"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
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
        cwd=targets["a2"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if applied.returncode:
        raise RuntimeError(applied.stdout)
    shutil.copy2(args.target_patch, evidence / "target.patch")
    target_patch_commit = None
    if plan.get("commit_target_patch_with_maintainer_metadata"):
        target_patch_commit = commit_patch_with_maintainer_metadata(
            targets["a2"], plan["target_head_commit"]
        )

    source_group = plan.get("source_group_id", "org.assertj")
    source_artifact = plan.get("source_artifact_id", "assertj-core")
    target_pom_relative = plan.get("target_dependency_pom_path", "pom.xml")
    target_version_property = plan.get("target_version_property")
    source_pom_relative = plan.get("source_pom_path", "pom.xml")
    source_artifact_pom_relative = plan.get(
        "source_artifact_pom_path", source_pom_relative
    )
    source_artifact_jar_relative = plan.get("source_artifact_jar_path")
    source_build_projects = plan.get("source_build_projects", [])
    if (
        not isinstance(source_artifact_pom_relative, str)
        or not source_artifact_pom_relative
        or (
            source_artifact_jar_relative is not None
            and (
                not isinstance(source_artifact_jar_relative, str)
                or not source_artifact_jar_relative
            )
        )
        or not isinstance(source_build_projects, list)
        or any(not isinstance(value, str) or not value for value in source_build_projects)
    ):
        raise ValueError("source reactor artifact fields are invalid")
    source_parent_version = plan.get("source_parent_version_override")
    if source_parent_version is not None:
        if not isinstance(source_parent_version, str) or not source_parent_version.strip():
            raise ValueError("source_parent_version_override must be a non-empty string")
        for source in (source_a0, source_a1, source_a2):
            set_parent_version(source / source_pom_relative, source_parent_version)
    versions = {
        arm.upper(): dependency_version(
            target / target_pom_relative,
            source_group,
            source_artifact,
            target_version_property,
        )
        for arm, target in targets.items()
    }
    repositories = {}
    for arm in ("A0", "A1", "A2"):
        repositories[arm] = (work / f"m2-{arm.lower()}").resolve()
        shutil.copytree(args.seed_repository, repositories[arm])
    parent_pom_evidence = []
    parent_checkouts: dict[tuple[str, str], Path] = {}
    for index, entry in enumerate(plan.get("source_parent_poms", []), start=1):
        if not isinstance(entry, dict) or any(
            not isinstance(entry.get(key), str) or not entry[key]
            for key in ("repository", "commit", "pom_path")
        ):
            raise ValueError("source_parent_poms entries require repository, commit, and pom_path")
        identity = (entry["repository"], entry["commit"])
        checkout = parent_checkouts.get(identity)
        if checkout is None:
            checkout = work / f"source-parent-{len(parent_checkouts) + 1}"
            clone_checkout(
                mirror_path(args.mirror_root, entry["repository"]),
                checkout,
                entry["commit"],
            )
            parent_checkouts[identity] = checkout
        pom = (checkout / entry["pom_path"]).resolve()
        if not pom.is_file():
            raise ValueError(f"source parent POM is missing: {pom}")
        for arm in ("A0", "A1", "A2"):
            install_parent_pom(
                pom, repositories[arm], args.maven, source_environment,
                evidence / f"source-parent-{index}.{arm.lower()}.install.log",
            )
        parent_pom_evidence.append({
            "repository": entry["repository"],
            "commit": entry["commit"],
            "pom_path": entry["pom_path"],
        })
    install_source(
        source_a0, source_pom_relative, source_artifact_pom_relative,
        source_artifact_jar_relative, source_build_projects, versions["A0"],
        repositories["A0"], args.maven, source_environment,
        evidence / "source-a0",
        bool(plan.get("source_reactor_parent_version_sync", False)),
        plan.get("source_build_pom_path"),
    )
    head_jar = install_source(
        source_a1, source_pom_relative, source_artifact_pom_relative,
        source_artifact_jar_relative, source_build_projects, versions["A1"],
        repositories["A1"], args.maven, source_environment,
        evidence / "source-a1",
        bool(plan.get("source_reactor_parent_version_sync", False)),
        plan.get("source_build_pom_path"),
    )
    install_existing_jar(
        head_jar, source_a2, source_pom_relative, source_artifact_pom_relative,
        versions["A2"], repositories["A2"], args.maven, source_environment,
        evidence / "source-a2.install.log",
        bool(plan.get("source_reactor_parent_version_sync", False)),
    )

    results = {}
    logical_command = plan["test_command"]
    for arm in ("A0", "A1", "A2"):
        target = targets[arm.lower()]
        target_command = planned_target_command(
            logical_command, target, args.maven, repositories[arm]
        )
        if args.target_command_wrapper is not None:
            target_command = [str(args.target_command_wrapper.resolve()), *target_command]
        completed = run(
            target_command,
            cwd=target,
            environment=target_environment,
        )
        arm_dir = evidence / args.relation_id / arm.lower()
        arm_dir.mkdir(parents=True)
        (arm_dir / "command.log").write_text(completed.stdout, encoding="utf-8")
        write_json(arm_dir / "summary.json", {
            "arm": arm,
            "command": logical_command,
            "exit_code": completed.returncode,
        })
        results[arm] = (completed.returncode, completed.stdout)

    signature = plan.get(
        "failure_signature", "package org.assertj.core.internal.bytebuddy does not exist"
    )
    exits = {arm: results[arm][0] for arm in results}
    test_counts = {
        arm: successful_test_count(results[arm][1]) for arm in ("A0", "A2")
    }
    strict = (
        exits["A0"] == 0 and exits["A1"] != 0 and exits["A2"] == 0
        and signature in results["A1"][1]
        and signature not in results["A0"][1]
        and signature not in results["A2"][1]
        and test_counts["A0"] > 0
        and test_counts["A2"] > 0
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
        })
        return 1

    write_json(evidence / "contract.json", {
        "schema_version": "1.0",
        "case_id": args.relation_id,
        "candidate_id": plan["candidate_id"],
        "source_repository": plan["source_repository"],
        "source_base_commit": plan["source_base_commit"],
        "source_head_commit": plan["source_head_commit"],
        "source_application": "maven_local_artifact_from_opening_checkout",
        "source_artifact_versions": versions,
        "source_build_pom_path": source_pom_relative,
        "source_artifact_pom_path": source_artifact_pom_relative,
        "source_artifact_jar_path": source_artifact_jar_relative,
        "source_build_projects": source_build_projects,
        "source_parent_version_override": source_parent_version,
        "source_parent_poms": parent_pom_evidence,
        "build_java_homes": {
            "source": str(source_java_home.resolve()),
            "target": str(target_java_home.resolve()),
        },
        "built_source_commits": {
            "A0": plan["source_base_commit"],
            "A1": plan["source_head_commit"],
            "A2": plan["source_head_commit"],
        },
        "target_repository": plan["target_repository"],
        "target_a0_base_commit": target_a0_base_commit,
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

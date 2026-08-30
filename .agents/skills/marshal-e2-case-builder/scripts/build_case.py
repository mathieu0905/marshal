#!/usr/bin/env python3
"""Build and verify one candidate-bounded strict-E2 case package.

The blind ranker runs in a Docker container with an allowlist of read-only
mounts.  The private manifest is not opened until that container exits and is
never mounted into it.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import re
import tarfile
from pathlib import Path
from typing import Any


ALLOWED_CHANNELS = {
    "pre_existing_target_test",
    "maintainer_target_test",
    "project_build_or_test",
}
REPLAY_ADAPTERS = {
    "source_editable": "run_formal_e2_python_touched_relation.py",
    "requirements_constraint": "run_formal_e2_constraint_touched_relation.py",
    "requirements_registration": "run_formal_e2_requirements_registration_relation.py",
    "maven_source": "run_formal_e2_maven_source_relation.py",
    "ant_source_maven_target": "run_formal_e2_ant_source_maven_target_relation.py",
    "cross_repo_command": "run_formal_e2_cross_repo_command_relation.py",
}
MAVEN_REPLAY_ADAPTERS = {"maven_source", "ant_source_maven_target"}
NO_REQUIREMENTS_REPLAY_ADAPTERS = MAVEN_REPLAY_ADAPTERS | {"cross_repo_command"}
RUNNER_FILES = (
    "run_formal_e2_candidate_code_blind.py",
    "candidate_code_ranker.py",
    "collect_formal_e2_candidate_mirrors.py",
)
ADDRESS = re.compile(r"0x[0-9a-fA-F]+")
UUID = re.compile(
    r"(?<![0-9a-fA-F])[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}(?![0-9a-fA-F])"
)
MAVEN_TEST_SUMMARY = re.compile(
    r"Tests run: ([0-9]+), Failures: ([0-9]+), Errors: ([0-9]+), Skipped: ([0-9]+)"
)


def now() -> str:
    return dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def repository_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        raise ValueError(f"not in a Git checkout: {result.stderr.strip()}")
    return Path(result.stdout.strip()).resolve()


def resolve(root: Path, value: str) -> Path:
    path = Path(value).expanduser()
    return (root / path).resolve() if not path.is_absolute() else path.resolve()


def resolve_executable(root: Path, value: str) -> Path:
    """Make an executable absolute without dereferencing a virtualenv symlink."""
    path = Path(value).expanduser()
    return path.absolute() if path.is_absolute() else (root / path).absolute()


def repository_relative(root: Path, path: Path) -> str:
    # Keep repository-local interpreter symlinks lexical. Resolving them can
    # point at the external interpreter used to create the venv.
    return str(path.absolute().relative_to(root.resolve()))


def select_case(path: Path, case_id: str, kind: str) -> dict[str, Any]:
    rows = [row for row in read_jsonl(path) if row.get("case_id") == case_id]
    if len(rows) != 1:
        raise ValueError(f"{kind} must contain exactly one {case_id} row, got {len(rows)}")
    return rows[0]


def prepare_manifests(args: argparse.Namespace) -> int:
    """Materialize pending-review manifests from one existing replay-plan row."""
    root = repository_root()
    plan_path = resolve(root, args.plan)
    input_dir = resolve(root, args.input_dir)
    inputs_path = resolve(root, args.inputs) if args.inputs else input_dir / "inputs.jsonl"
    snapshots_path = (
        resolve(root, args.snapshots)
        if args.snapshots
        else input_dir / "repository-snapshots.jsonl"
    )
    catalogs_path = (
        resolve(root, args.catalogs)
        if args.catalogs
        else input_dir / "candidate-repositories.json"
    )
    source_patch_dir = resolve(root, args.source_patch_dir)
    target_patch_dir = resolve(root, args.target_patch_dir)
    output = resolve(root, args.output_dir)
    if output.exists():
        raise ValueError(f"manifest output directory already exists: {output}")
    plan = select_case(plan_path, args.case_id, "replay plan")
    candidate_id = plan["candidate_id"]
    target_change = str(plan["target_change"])
    source_patch = source_patch_dir / f"{candidate_id}.patch"
    target_patch = target_patch_dir / f"{target_change}.patch"
    for path in (
        inputs_path,
        snapshots_path,
        catalogs_path,
        source_patch,
        target_patch,
    ):
        if not path.is_file():
            raise ValueError(f"manifest input is missing: {path}")
    adapter = args.replay_adapter
    if adapter == "auto":
        adapter = (
            "requirements_constraint"
            if plan.get("source_repository") == "openstack/requirements"
            else "source_editable"
        )
    runner_dir = {
        "py310": "tox4-runner",
        "py313": "tox4-runner-py313",
        "tox3": "tox3-runner",
        "tox3-py38": "tox3-runner-py38",
        "tox3-py38-2021": "tox3-runner-py38-2021",
    }[args.runner]
    runner = root / "benchmarks" / "cross-repo-pr-impact" / ".work" / "formal-e2-strict-replays-2026-08-26" / runner_dir
    public = {
        "schema_version": "1.0",
        "candidate_id": candidate_id,
        "inputs": repository_relative(root, inputs_path),
        "snapshots": repository_relative(root, snapshots_path),
        "catalogs": repository_relative(root, catalogs_path),
        "patch_dir": repository_relative(root, source_patch_dir),
        "mirror_root": repository_relative(root, resolve(root, args.mirror_root)) if args.mirror_root else "benchmarks/cross-repo-pr-impact/.work/formal-e2-strict-wave2-candidate-mirrors-2026-08-26",
        "blind": {"container_image": "python:3.10", "top_k": 5, "workers": 8},
    }
    source_subject = plan.get("source_subject", candidate_id)
    target_subject = plan.get("target_subject", target_change)
    private = {
        "schema_version": "1.0",
        "candidate_id": candidate_id,
        "relation_id": plan.get("relation_id", plan["case_id"]),
        "target_repository": plan["target_repository"],
        "expected_check_paths": [plan["target_test_path"]],
        "source_change_family": f"opendev-change-{candidate_id.rsplit('-', 1)[-1]}-opening",
        "mechanism": args.mechanism or f"Pending semantic characterization: {source_subject} affects {target_subject}",
        "repair_template": args.repair_template or f"Pending semantic characterization of maintainer change {target_change}",
        "replay_adapter": adapter,
        "replay_plan": repository_relative(root, plan_path),
        "mirror_root": repository_relative(root, resolve(root, args.mirror_root)) if args.mirror_root else "benchmarks/cross-repo-pr-impact/.work/formal-e2-strict-wave2-candidate-mirrors-2026-08-26",
        "tox": repository_relative(root, runner / "bin" / "tox"),
        "python": repository_relative(root, runner / "bin" / "python"),
        "semantic_review": {
            "approved": False,
            "source_effect": f"Pending review of source opening: {source_subject}.",
            "a1_failure": "Pending full opening-cutoff replay confirmation.",
            "target_repair": f"Pending review of maintainer target change: {target_subject}.",
            "target_patch": repository_relative(root, target_patch),
            "reviewer_basis": "Machine three-arm replay and semantic adjudication are pending; this generated manifest is not an approval.",
        },
    }
    if args.bootstrap_constraint:
        private["bootstrap_constraints"] = args.bootstrap_constraint
    if args.virtualenv_pip_version:
        private["virtualenv_pip_version"] = args.virtualenv_pip_version
    if args.virtualenv_setuptools_version:
        private["virtualenv_setuptools_version"] = args.virtualenv_setuptools_version
    if adapter == "cross_repo_command":
        private["command_config_repository"] = plan.get(
            "command_config_repository", "target"
        )
        private["command_config_path"] = plan["command_config_path"]
    write_json(output / "public-case.json", public)
    write_json(output / "private-label.json", private)
    print(json.dumps({
        "case_id": private["relation_id"],
        "manifest_directory": repository_relative(root, output),
        "semantic_review_approved": False,
    }, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


def timestamp(value: str) -> dt.datetime:
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=dt.UTC) if parsed.tzinfo is None else parsed.astimezone(dt.UTC)


def mirror_path(mirror_root: Path, repository: str) -> Path:
    return mirror_root / f"{repository.replace('/', '__')}.git"


def validate_git_object(mirror: Path, commit: str) -> bool:
    result = subprocess.run(
        ["git", "--git-dir", str(mirror), "cat-file", "-e", f"{commit}^{{commit}}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def resolve_default_branch_snapshot(
    mirror_root: Path,
    repository: str,
    cutoff: str,
    host: str = "opendev.org",
    created_at: str | None = None,
) -> dict[str, Any]:
    if created_at is not None and timestamp(created_at) > timestamp(cutoff):
        return {"repository": repository, "host": host, "status": "not_created_by_cutoff"}
    mirror = mirror_path(mirror_root, repository)
    if not mirror.is_dir():
        raise ValueError(f"complete mirror is missing: {repository}")
    branch = "refs/heads/master" if host == "opendev.org" else subprocess.run(
        ["git", "--git-dir", str(mirror), "symbolic-ref", "HEAD"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    ).stdout.strip()
    if not branch.startswith("refs/heads/"):
        raise ValueError(f"cannot resolve {repository} default branch ref")
    result = subprocess.run(
        [
            "git", "--git-dir", str(mirror), "rev-list", "--first-parent", "-1",
            f"--before={cutoff}", branch,
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        raise ValueError(f"cannot resolve {repository} default branch: {result.stderr.strip()}")
    commit = result.stdout.strip()
    if not commit:
        return {
            "repository": repository,
            "host": host,
            "status": "not_created_by_cutoff",
        }
    committed_at = subprocess.run(
        ["git", "--git-dir", str(mirror), "show", "-s", "--format=%cI", commit],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout.strip()
    return {
        "repository": repository,
        "host": host,
        "status": "available",
        "commit": commit,
        "committed_at": committed_at,
        "archive_url": (
            f"https://github.com/{repository}/archive/{commit}.tar.gz"
            if host == "github.com"
            else f"https://opendev.org/api/v1/repos/{repository}/archive/{commit}.tar.gz"
        ),
    }


def prepare_public(root: Path, manifest: dict[str, Any], output: Path) -> dict[str, Any]:
    if manifest.get("schema_version") != "1.0":
        raise ValueError("unsupported public manifest schema")
    candidate_id = manifest["candidate_id"]
    inputs_path = resolve(root, manifest["inputs"])
    snapshots_path = resolve(root, manifest["snapshots"])
    catalogs_path = resolve(root, manifest["catalogs"])
    patch_dir = resolve(root, manifest["patch_dir"])
    archive_mode = "snapshot_archive_root" in manifest
    candidate_root = resolve(
        root,
        manifest["snapshot_archive_root"] if archive_mode else manifest["mirror_root"],
    )
    for path in (inputs_path, snapshots_path, catalogs_path, patch_dir, candidate_root):
        if not path.exists():
            raise ValueError(f"public input does not exist: {path}")

    input_rows = read_jsonl(inputs_path)
    selected_inputs = [row for row in input_rows if row.get("case_id") == candidate_id]
    if len(selected_inputs) != 1:
        raise ValueError(
            f"inputs must contain exactly one {candidate_id} row, got {len(selected_inputs)}"
        )
    input_row = selected_inputs[0]
    snapshot = select_case(snapshots_path, candidate_id, "snapshots")
    if input_row["candidate_repository_catalog"] != snapshot["candidate_repository_catalog"]:
        raise ValueError("input and snapshot catalog references disagree")
    if timestamp(input_row["observation_cutoff"]) != timestamp(snapshot["observation_cutoff"]):
        raise ValueError("input and snapshot observation cutoffs disagree")
    catalog_id = input_row["candidate_repository_catalog"].split("#", 1)[-1]
    catalogs_doc = read_json(catalogs_path)
    catalog = catalogs_doc.get("catalogs", {}).get(catalog_id)
    if catalog is None:
        raise ValueError(f"catalog is missing: {catalog_id}")
    membership_source = catalog.get("membership_source", {})
    source_provenance_complete = (
        isinstance(membership_source, dict)
        and (
            (
                bool(membership_source.get("repository"))
                and bool(membership_source.get("commit"))
                and bool(membership_source.get("path"))
            )
            or (
                membership_source.get("kind") == "github_organization_directory"
                and bool(membership_source.get("organization"))
                and bool(membership_source.get("endpoint"))
                and bool(membership_source.get("snapshot"))
                and bool(catalog.get("selection_rule"))
            )
            or (
                membership_source.get("kind") == "opendev_organization_directory"
                and bool(membership_source.get("organization"))
                and bool(membership_source.get("endpoint"))
                and bool(membership_source.get("snapshot"))
                and bool(catalog.get("selection_rule"))
            )
            or (
                membership_source.get("kind") == "ecosystem_package_dependency_index"
                and bool(membership_source.get("api_root"))
                and bool(membership_source.get("snapshot"))
                and bool(membership_source.get("query_slices"))
                and bool(membership_source.get("source_packages"))
                and bool(catalog.get("selection_rule"))
            )
        )
    )
    label_independent = catalog.get("membership_reads_labels") is False or (
        catalog.get("catalog_status") == "label_independent_reusable"
        and catalog.get("membership_reads_e2_targets") is False
        and source_provenance_complete
    )
    if not label_independent:
        raise ValueError("catalog membership is not label-independent")
    catalog_reference_count = sum(
        row.get("candidate_repository_catalog", "").split("#", 1)[-1] == catalog_id
        for row in input_rows
    )
    reusable = (
        catalog.get("reused_across_source_events") is True
        or catalog_reference_count >= 2
    )
    if not reusable:
        raise ValueError("catalog is not reusable across source events")
    members = set(catalog.get("repositories", []))
    if len(members) < 2:
        raise ValueError("catalog must contain at least two repositories")
    snapshot_repositories = {row["repository"] for row in snapshot["repositories"]}
    if not snapshot_repositories <= members:
        raise ValueError("snapshot contains repositories outside the catalog")
    open_dev_catalog = catalog.get("repository_host") == "opendev.org" or (
        catalog.get("membership_source", {}).get("repository") == "openstack/requirements"
        and all(repository.startswith(("openstack/", "starlingx/")) for repository in members)
    )
    github_catalog = catalog.get("repository_host") == "github.com"
    if not open_dev_catalog and not github_catalog:
        raise ValueError("single-case default-branch resolver supports OpenDev and GitHub catalogs")
    repository_host = "github.com" if github_catalog else "opendev.org"
    created_at = catalog.get("repository_created_at", {})
    if github_catalog and not archive_mode and (
        not isinstance(created_at, dict) or not members <= set(created_at)
    ):
        raise ValueError("GitHub catalog lacks repository creation provenance")
    original_by_repository = {row["repository"]: row for row in snapshot["repositories"]}
    if archive_mode:
        if set(original_by_repository) != members:
            raise ValueError("archive-backed snapshot must cover every catalog member")
        resolved_rows = [original_by_repository[repository] for repository in sorted(members)]
        repaired = 0
    else:
        resolved_rows = [
            resolve_default_branch_snapshot(
                candidate_root,
                repository,
                input_row["observation_cutoff"],
                repository_host,
                created_at.get(repository),
            )
            for repository in sorted(members)
        ]
        repaired = sum(
            original_by_repository.get(row["repository"], {}).get("commit") != row.get("commit")
            or original_by_repository.get(row["repository"], {}).get("status") != row.get("status")
            for row in resolved_rows
        )
    snapshot = {**snapshot, "repositories": resolved_rows}
    available = [row for row in resolved_rows if row["status"] == "available"]
    source_repository = input_row["source"]["repository"]
    if not any(row["repository"] != source_repository for row in available):
        raise ValueError("case has no available non-source candidate repository")
    missing_objects = []
    for row in available:
        if archive_mode:
            archive = (
                candidate_root / row["repository"].replace("/", "__")
                / f"{row['commit']}.tar.gz"
            )
            try:
                with tarfile.open(archive, "r:gz") as handle:
                    if handle.next() is None:
                        raise tarfile.ReadError("empty archive")
            except (OSError, tarfile.TarError):
                missing_objects.append(f"{row['repository']}@{row['commit']}")
        else:
            mirror = mirror_path(candidate_root, row["repository"])
            if not mirror.is_dir() or not validate_git_object(mirror, row["commit"]):
                missing_objects.append(f"{row['repository']}@{row['commit']}")
    if missing_objects:
        raise ValueError(
            f"cutoff Git objects missing for {len(missing_objects)} repositories; "
            f"first={missing_objects[0]}"
        )
    patch = patch_dir / f"{candidate_id}.patch"
    if not patch.is_file() or not patch.read_bytes().startswith(b"diff --git "):
        raise ValueError("source patch is missing or is not a code-only diff")

    public = output / "public"
    (public / "source-patches").mkdir(parents=True)
    write_jsonl(public / "inputs.jsonl", [input_row])
    write_jsonl(public / "repository-snapshots.jsonl", [snapshot])
    write_json(public / "candidate-repositories.json", {
        "schema_version": catalogs_doc.get("schema_version", "1.0"),
        "catalogs": {catalog_id: catalog},
    })
    shutil.copy2(patch, public / "source-patches" / patch.name)
    write_json(public / "manifest.json", packaged_public_manifest(manifest))
    write_json(public / "validation.json", {
        "schema_version": "1.0",
        "candidate_id": candidate_id,
        "snapshot_resolution": (
            "pre-audited exact-commit archives from the public cutoff snapshot"
            if archive_mode
            else "latest default-branch commit at or before observation cutoff"
        ),
        "input_snapshot_rows_replaced": repaired,
        "catalog_membership_reads_labels": False,
        "catalog_reused_across_source_events": True,
        "catalog_reference_count": catalog_reference_count,
        "available_repository_count": len(available),
    })
    return {
        "candidate_id": candidate_id,
        "catalog_id": catalog_id,
        "catalog_repository_count": len(members),
        "available_repository_count": len(available),
        "source_repository": source_repository,
        "candidate_root": candidate_root,
        "candidate_storage": "exact_commit_archive" if archive_mode else "git_mirror",
        "public_dir": public,
        "blind": manifest.get("blind", {}),
    }


def path_within(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def packaged_public_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Keep execution settings while removing host intake paths from blind input."""

    packaged = dict(manifest)
    packaged.update({
        "inputs": "inputs.jsonl",
        "snapshots": "repository-snapshots.jsonl",
        "catalogs": "candidate-repositories.json",
        "patch_dir": "source-patches",
    })
    return packaged


def public_manifest_leaks_relation(output: Path, private: dict[str, Any]) -> bool:
    serialized = json.dumps(
        read_json(output / "public" / "manifest.json"),
        ensure_ascii=False,
        sort_keys=True,
    )
    relation_id = private["relation_id"]
    forbidden = {relation_id}
    if "--target-" in relation_id:
        forbidden.add("target-" + relation_id.split("--target-", 1)[1])
    return any(token in serialized for token in forbidden)


def run_blind(
    root: Path,
    prepared: dict[str, Any],
    private_manifest_path: Path,
    output: Path,
) -> dict[str, Any]:
    benchmark = root / "benchmarks" / "cross-repo-pr-impact"
    public = prepared["public_dir"]
    candidate_root = prepared["candidate_root"]
    for visible in (public, candidate_root, benchmark):
        if path_within(private_manifest_path, visible):
            if visible == benchmark:
                # Only three individual runner files are mounted, not this directory.
                continue
            raise ValueError("private manifest is nested inside a blind-visible mount")
    blind = output / "blind"
    blind.mkdir(parents=True)
    config = prepared["blind"]
    image = config.get("container_image", "python:3.10")
    top_k = int(config.get("top_k", 5))
    workers = int(config.get("workers", 8))
    if top_k < 1 or workers < 1:
        raise ValueError("blind top_k and workers must be positive")
    inspect = subprocess.run(
        ["docker", "image", "inspect", "--format", "{{.Id}}", image],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if inspect.returncode:
        raise ValueError(f"blind container image is unavailable locally: {image}")
    command = [
        "docker", "run", "--rm", "--network", "none", "--read-only",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--pids-limit", "256", "--user", f"{os.getuid()}:{os.getgid()}",
        "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=64m",
        "-e", "PYTHONDONTWRITEBYTECODE=1",
        "-e", "MARSHAL_NETWORK_CONTROL=docker_network_none",
    ]
    for name in RUNNER_FILES:
        runner = benchmark / name
        if not runner.is_file():
            raise ValueError(f"blind runner is missing: {runner}")
        command.extend(["--mount", f"type=bind,src={runner},dst=/runner/{name},readonly"])
    command.extend([
        "--mount", f"type=bind,src={public},dst=/input,readonly",
        "--mount", f"type=bind,src={candidate_root},dst=/candidates,readonly",
        "--mount", f"type=bind,src={blind},dst=/output",
        image,
        "python", "/runner/run_formal_e2_candidate_code_blind.py",
        "--inputs", "/input/inputs.jsonl",
        "--patch-dir", "/input/source-patches",
        "--snapshots", "/input/repository-snapshots.jsonl",
        "--output-dir", "/output",
        "--case-id", prepared["candidate_id"],
        "--top-k", str(top_k),
        "--workers", str(workers),
    ])
    if prepared["candidate_storage"] == "git_mirror":
        command.extend(["--mirror-root", "/candidates"])
    else:
        command.extend(["--archive-root", "/candidates"])
    started_at = now()
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    completed_at = now()
    (blind / "container.log").write_text(result.stdout, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(f"blind container failed with exit {result.returncode}; see {blind / 'container.log'}")
    isolation = {
        "schema_version": "1.0",
        "mechanism": "docker_allowlist_mounts",
        "container_image": image,
        "network_mode": "none",
        "read_only_root": True,
        "capabilities_dropped": "ALL",
        "no_new_privileges": True,
        "label_store_mounted": False,
        "visible_mounts": [
            "runner_files", "public_case", prepared["candidate_storage"], "blind_output"
        ],
        "started_at": started_at,
        "completed_at": completed_at,
        "exit_code": result.returncode,
    }
    write_json(blind / "isolation.json", isolation)
    metrics = verify_blind(output)
    write_json(blind / "verification.json", metrics)
    return metrics


def verify_blind(output: Path) -> dict[str, Any]:
    public = output / "public"
    blind = output / "blind"
    inputs = read_jsonl(public / "inputs.jsonl")
    snapshots = read_jsonl(public / "repository-snapshots.jsonl")
    predictions = read_jsonl(blind / "predictions.jsonl")
    diagnostics = read_jsonl(blind / "diagnostics.jsonl")
    manifest = read_json(blind / "run-manifest.json")
    isolation = read_json(blind / "isolation.json")
    if not (len(inputs) == len(snapshots) == len(predictions) == len(diagnostics) == 1):
        raise ValueError("blind package must contain exactly one row per artifact")
    case_id = inputs[0]["case_id"]
    if {snapshots[0]["case_id"], predictions[0]["case_id"], diagnostics[0]["case_id"]} != {case_id}:
        raise ValueError("blind case ids disagree")
    if manifest.get("labels_read") is not False or manifest.get("network_used") is not False:
        raise ValueError("blind runner did not declare label/network isolation")
    if manifest.get("candidate_code_read") is not True:
        raise ValueError("blind runner did not read candidate code")
    if isolation.get("mechanism") != "docker_allowlist_mounts":
        raise ValueError("blind filesystem isolation is not Docker allowlist mounts")
    if isolation.get("network_mode") != "none" or isolation.get("label_store_mounted") is not False:
        raise ValueError("blind isolation does not exclude network and label store")
    if isolation.get("read_only_root") is not True or isolation.get("exit_code") != 0:
        raise ValueError("blind container isolation/run is incomplete")
    diagnostic = diagnostics[0]
    if diagnostic.get("label_inputs_read") is not False or diagnostic.get("candidate_code_read") is not True:
        raise ValueError("blind diagnostic isolation claims are invalid")
    available = {
        row["repository"]
        for row in snapshots[0]["repositories"]
        if row["status"] == "available" and row["repository"] != inputs[0]["source"]["repository"]
    }
    ranking = diagnostic.get("ranking", [])
    if {row["repository"] for row in ranking} != available:
        raise ValueError("blind ranker did not cover every available candidate")
    for row in ranking:
        tracked = row.get("tracked_file_count")
        selected = row.get("files_read")
        text = row.get("text_files_read")
        if not all(isinstance(value, int) and value >= 0 for value in (tracked, selected, text)):
            raise ValueError("blind ranker has invalid code-read counters")
        if selected > 24 or text > selected:
            raise ValueError("blind ranker exceeded its per-candidate code-read contract")
    total_text_reads = sum(row["text_files_read"] for row in ranking)
    if total_text_reads <= 0:
        raise ValueError("blind ranker has zero text-code reads across the candidate universe")
    predicted = [row["repository"] for row in predictions[0]["targets"]]
    if len(predicted) > 5 or len(predicted) != len(set(predicted)) or not set(predicted) <= available:
        raise ValueError("blind prediction is not a valid bounded top-5 list")
    return {
        "schema_version": "1.0",
        "blind_run_valid": True,
        "case_id": case_id,
        "candidate_repository_reads": len(ranking),
        "candidate_text_file_reads": total_text_reads,
        "candidate_snapshots_without_tracked_files": sum(
            row["tracked_file_count"] == 0 for row in ranking
        ),
        "labels_read": False,
        "network_mode": "none",
        "label_store_mounted": False,
    }


def validate_private(root: Path, private: dict[str, Any], candidate_id: str) -> dict[str, Any]:
    required = (
        "relation_id", "replay_plan", "target_repository", "expected_check_paths",
        "source_change_family", "mechanism", "repair_template",
        "semantic_review",
    )
    if private.get("schema_version") != "1.0" or private.get("candidate_id") != candidate_id:
        raise ValueError("private manifest schema or candidate id mismatch")
    missing = [key for key in required if key not in private]
    if missing:
        raise ValueError(f"private manifest missing: {', '.join(missing)}")
    plan_path = resolve(root, private["replay_plan"])
    relation_rows = [
        row for row in read_jsonl(plan_path)
        if row.get("relation_id", row.get("case_id")) == private["relation_id"]
    ]
    if not relation_rows:
        raise ValueError("relation is absent from replay plan")
    plan = relation_rows[0]
    if plan.get("candidate_id") != candidate_id:
        raise ValueError("replay plan candidate id mismatch")
    if plan.get("target_repository") != private["target_repository"]:
        raise ValueError("private target and replay plan disagree")
    replay_adapter = private.get("replay_adapter", "source_editable")
    if replay_adapter not in REPLAY_ADAPTERS:
        raise ValueError(f"unsupported replay adapter: {replay_adapter}")
    if replay_adapter == "requirements_constraint" and plan.get("source_repository") != "openstack/requirements":
        raise ValueError("requirements_constraint adapter requires openstack/requirements source")
    if replay_adapter == "requirements_registration" and plan.get("target_repository") != "openstack/requirements":
        raise ValueError("requirements_registration adapter requires openstack/requirements target")
    execution_keys = ("python",) if replay_adapter == "cross_repo_command" else ("tox", "python")
    missing_execution = [key for key in execution_keys if key not in private]
    if missing_execution:
        raise ValueError(f"private manifest missing replay executable: {', '.join(missing_execution)}")
    if not isinstance(private["expected_check_paths"], list) or not private["expected_check_paths"]:
        raise ValueError("private manifest has no expected check path")
    review = private["semantic_review"]
    required_review = ("approved", "source_effect", "a1_failure", "target_repair", "target_patch", "reviewer_basis")
    if any(key not in review for key in required_review):
        raise ValueError("semantic review is incomplete")
    for key in required_review[1:]:
        if not isinstance(review[key], str) or not review[key].strip():
            raise ValueError(f"semantic review field is empty: {key}")
    target_patch = resolve(root, review["target_patch"])
    if not target_patch.is_file() or not target_patch.read_bytes().startswith(b"diff --git "):
        raise ValueError("semantic review target patch is missing or not a code diff")
    tox = resolve_executable(root, private["tox"]) if "tox" in private else None
    python = resolve_executable(root, private["python"])
    mirror_root = resolve(root, private.get("mirror_root", "benchmarks/cross-repo-pr-impact/.work/formal-e2-strict-wave2-candidate-mirrors-2026-08-26"))
    for path in (plan_path, tox, python, mirror_root):
        if path is None:
            continue
        if not path.exists():
            raise ValueError(f"private replay input does not exist: {path}")
    return {"plan_path": plan_path, "plan": plan, "tox": tox, "python": python, "mirror_root": mirror_root}


def run_replay(root: Path, private: dict[str, Any], resolved: dict[str, Any], output: Path) -> int:
    replay_adapter = private.get("replay_adapter", "source_editable")
    replay = root / "benchmarks" / "cross-repo-pr-impact" / REPLAY_ADAPTERS[replay_adapter]
    snapshot = read_jsonl(output / "public" / "repository-snapshots.jsonl")[0]
    snapshot_by_repository = {row["repository"]: row for row in snapshot["repositories"]}
    target_snapshot = snapshot_by_repository.get(private["target_repository"])
    requirements_snapshot = snapshot_by_repository.get("openstack/requirements")
    if target_snapshot is None or target_snapshot.get("status") != "available":
        raise ValueError("target repository is unavailable at the source opening cutoff")
    if replay_adapter not in NO_REQUIREMENTS_REPLAY_ADAPTERS and (
        requirements_snapshot is None or requirements_snapshot.get("status") != "available"
    ):
        raise ValueError("openstack/requirements is unavailable at the source opening cutoff")
    target_patch = resolve(root, private["semantic_review"]["target_patch"])
    command = [
        sys.executable, str(replay),
        "--plan", str(resolved["plan_path"]),
        "--relation-id", private["relation_id"],
        "--mirror-root", str(resolved["mirror_root"]),
        "--work-root", str(output / "replay-work"),
        "--evidence-root", str(output / "evidence"),
        "--python", str(resolved["python"]),
        "--target-base-commit", target_snapshot["commit"],
        "--target-patch", str(target_patch),
    ]
    if replay_adapter != "cross_repo_command":
        command.extend(["--tox", str(resolved["tox"])])
    if replay_adapter == "source_editable":
        command.extend(["--requirements-commit", requirements_snapshot["commit"]])
        if private.get("setuptools_version"):
            command.extend(["--setuptools-version", private["setuptools_version"]])
    if replay_adapter == "requirements_constraint":
        replay_environment = private.get("replay_environment", {})
        if not isinstance(replay_environment, dict) or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in replay_environment.items()
        ):
            raise ValueError("replay_environment must be a string map")
        for key, value in sorted(replay_environment.items()):
            command.extend(["--test-environment", f"{key}={value}"])
        setup_environment = private.get("setup_environment", {})
        if not isinstance(setup_environment, dict) or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in setup_environment.items()
        ):
            raise ValueError("setup_environment must be a string map")
        for key, value in sorted(setup_environment.items()):
            expanded = value.replace("{repository_root}", str(root))
            command.extend(["--setup-environment", f"{key}={expanded}"])
        bootstrap_constraints = private.get("bootstrap_constraints", [])
        if not isinstance(bootstrap_constraints, list) or any(
            not isinstance(value, str)
            or not value.strip()
            or "\n" in value
            or "\r" in value
            for value in bootstrap_constraints
        ):
            raise ValueError("bootstrap_constraints must be a list of non-empty single-line strings")
        for value in bootstrap_constraints:
            command.extend(["--bootstrap-constraint", value])
        virtualenv_pip_version = private.get("virtualenv_pip_version")
        if virtualenv_pip_version is not None:
            if not isinstance(virtualenv_pip_version, str) or not re.fullmatch(
                r"[A-Za-z0-9_.!+~-]+", virtualenv_pip_version
            ):
                raise ValueError("virtualenv_pip_version is invalid")
            command.extend(["--virtualenv-pip-version", virtualenv_pip_version])
        virtualenv_setuptools_version = private.get("virtualenv_setuptools_version")
        if virtualenv_setuptools_version is not None:
            if not isinstance(virtualenv_setuptools_version, str) or not re.fullmatch(
                r"[A-Za-z0-9_.!+~-]+", virtualenv_setuptools_version
            ):
                raise ValueError("virtualenv_setuptools_version is invalid")
            command.extend([
                "--virtualenv-setuptools-version", virtualenv_setuptools_version
            ])
    if replay_adapter == "maven_source":
        for key in ("maven", "java_home", "maven_seed_repository"):
            if not isinstance(private.get(key), str) or not resolve(root, private[key]).exists():
                raise ValueError(f"maven_source replay input is missing: {key}")
        command.extend([
            "--maven", str(resolve(root, private["maven"])),
            "--java-home", str(resolve(root, private["java_home"])),
            "--seed-repository", str(resolve(root, private["maven_seed_repository"])),
        ])
        for key, option in (
            ("source_java_home", "--source-java-home"),
            ("target_java_home", "--target-java-home"),
        ):
            value = private.get(key)
            if value is not None:
                if not isinstance(value, str) or not resolve(root, value).exists():
                    raise ValueError(f"maven_source replay input is invalid: {key}")
                command.extend([option, str(resolve(root, value))])
    if replay_adapter == "ant_source_maven_target":
        for key in (
            "maven", "maven_seed_repository", "source_java_home", "target_java_home",
        ):
            if not isinstance(private.get(key), str) or not resolve(root, private[key]).exists():
                raise ValueError(f"ant_source_maven_target replay input is missing: {key}")
        command.extend([
            "--maven", str(resolve(root, private["maven"])),
            "--seed-repository", str(resolve(root, private["maven_seed_repository"])),
            "--source-java-home", str(resolve(root, private["source_java_home"])),
            "--target-java-home", str(resolve(root, private["target_java_home"])),
        ])
        for key, option in (
            ("ant", "--ant"),
            ("junit", "--junit"),
        ):
            if not isinstance(private.get(key), str) or not resolve(root, private[key]).exists():
                raise ValueError(f"ant_source_maven_target replay input is missing: {key}")
            command.extend([option, str(resolve(root, private[key]))])
        replay_environment = private.get("replay_environment", {})
        if not isinstance(replay_environment, dict) or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in replay_environment.items()
        ):
            raise ValueError("replay_environment must be a string map")
        for key, value in sorted(replay_environment.items()):
            command.extend(["--environment", f"{key}={value}"])
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    (output / "replay.log").write_text(result.stdout, encoding="utf-8")
    return result.returncode


def verify_constraint_source_application(contract: dict[str, Any]) -> None:
    application = contract.get("source_application")
    if application == "global_constraints_single_pin":
        changes = contract.get("opening_constraint_changes")
        if changes is not None and (not isinstance(changes, list) or len(changes) != 1):
            raise ValueError("single-pin constraint replay recorded a non-single opening diff")
        return
    if application != "global_constraints_full_opening_diff":
        raise ValueError("constraint replay did not record its source application")

    changes = contract.get("opening_constraint_changes")
    if not isinstance(changes, list) or len(changes) < 2:
        raise ValueError("full-opening constraint replay did not record every changed pin")
    normalized_changes: list[tuple[str, str | None, str | None]] = []
    for row in changes:
        if not isinstance(row, dict):
            raise ValueError("full-opening constraint replay contains an invalid change row")
        distribution = row.get("distribution")
        old_version = row.get("old_version")
        new_version = row.get("new_version")
        if (
            not isinstance(distribution, str)
            or not distribution
            or old_version == new_version
            or (old_version is not None and not isinstance(old_version, str))
            or (new_version is not None and not isinstance(new_version, str))
        ):
            raise ValueError("full-opening constraint replay contains an invalid change row")
        normalized_changes.append((distribution.casefold(), old_version, new_version))
    if len({distribution for distribution, _, _ in normalized_changes}) != len(normalized_changes):
        raise ValueError("full-opening constraint replay contains duplicate distributions")

    routed_distribution = contract.get("changed_distribution")
    source_versions = contract.get("source_versions")
    if not isinstance(routed_distribution, str) or not isinstance(source_versions, dict):
        raise ValueError("full-opening constraint replay did not identify its routed pin")
    routed = [
        row for row in normalized_changes if row[0] == routed_distribution.casefold()
    ]
    expected = (
        routed_distribution.casefold(),
        source_versions.get("A0"),
        source_versions.get("A1"),
    )
    if (
        len(routed) != 1
        or routed[0] != expected
        or source_versions.get("A1") != source_versions.get("A2")
    ):
        raise ValueError("full-opening constraint replay routed pin does not match old/new/new versions")


def verify_replay(output: Path, private: dict[str, Any]) -> dict[str, Any]:
    evidence = output / "evidence" / private["relation_id"]
    contract_path = evidence / "contract.json"
    if not contract_path.is_file():
        rejection = read_json(evidence / "rejection.json") if (evidence / "rejection.json").exists() else None
        raise ValueError(f"strict replay contract missing; rejection={rejection}")
    contract = read_json(contract_path)
    if contract.get("case_id") != private["relation_id"]:
        raise ValueError("replay contract relation mismatch")
    if contract.get("candidate_id") != private["candidate_id"]:
        raise ValueError("replay contract candidate mismatch")
    if contract.get("target_repository") != private["target_repository"]:
        raise ValueError("replay contract target mismatch")
    if contract.get("primary_result_channel") not in ALLOWED_CHANNELS:
        raise ValueError("replay did not use a real target task")
    if contract.get("arms") != {"A0": "pass", "A1": "fail", "A2": "pass"}:
        raise ValueError("replay contract arm direction is not pass/fail/pass")
    if contract.get("machine_arm_verification") != "passed":
        raise ValueError("replay machine verification did not pass")
    public_input = read_jsonl(output / "public" / "inputs.jsonl")[0]
    snapshot = read_jsonl(output / "public" / "repository-snapshots.jsonl")[0]
    catalogs = read_json(output / "public" / "candidate-repositories.json")["catalogs"]
    catalog_id = public_input["candidate_repository_catalog"].split("#", 1)[-1]
    if private["target_repository"] not in catalogs[catalog_id]["repositories"]:
        raise ValueError("revealed target is outside the label-independent catalog")
    snapshot_by_repository = {row["repository"]: row for row in snapshot["repositories"]}
    target_snapshot = snapshot_by_repository.get(private["target_repository"])
    requirements_snapshot = snapshot_by_repository.get("openstack/requirements")
    if target_snapshot is None or target_snapshot.get("status") != "available":
        raise ValueError("target repository is not available in the public cutoff snapshot")
    replay_adapter = private.get("replay_adapter", "source_editable")
    if replay_adapter not in NO_REQUIREMENTS_REPLAY_ADAPTERS and (
        requirements_snapshot is None or requirements_snapshot.get("status") != "available"
    ):
        raise ValueError("requirements repository is not available in the public cutoff snapshot")
    if contract.get("target_base_commit") != target_snapshot["commit"]:
        raise ValueError("A0/A1 target commit is not the public cutoff snapshot")
    if contract.get("source_base_commit") != public_input["source"]["base_commit"]:
        raise ValueError("A0 source commit is not the public opening base")
    if contract.get("source_head_commit") != public_input["source"]["candidate_commit"]:
        raise ValueError("A1/A2 source commit is not the public opening candidate")
    if contract.get("target_a2_kind") != "maintainer_patch_applied_to_cutoff_snapshot":
        raise ValueError("A2 is not the maintainer patch applied to the cutoff target snapshot")
    if replay_adapter == "requirements_constraint":
        if contract.get("requirements_commit") != public_input["source"]["base_commit"]:
            raise ValueError("A0 constraints are not the public opening base")
        verify_constraint_source_application(contract)
        if contract.get("requirements_a1_commit") != public_input["source"]["candidate_commit"]:
            raise ValueError("A1/A2 constraints are not the public opening candidate")
        source_versions = contract.get("source_versions")
        installed_versions = contract.get("installed_source_versions")
        if not isinstance(source_versions, dict) or installed_versions != source_versions:
            raise ValueError("constraint replay did not prove the installed source versions")
        if source_versions.get("A0") == source_versions.get("A1") or source_versions.get("A1") != source_versions.get("A2"):
            raise ValueError("constraint replay source versions do not encode old/new/new")
    elif replay_adapter in MAVEN_REPLAY_ADAPTERS:
        expected_application = {
            "maven_source": "maven_local_artifact_from_opening_checkout",
            "ant_source_maven_target": "ant_built_maven_artifacts_from_opening_checkout",
        }[replay_adapter]
        if contract.get("source_application") != expected_application:
            raise ValueError("Maven replay did not build the opening source checkouts")
        if contract.get("built_source_commits") != {
            "A0": public_input["source"]["base_commit"],
            "A1": public_input["source"]["candidate_commit"],
            "A2": public_input["source"]["candidate_commit"],
        }:
            raise ValueError("Maven replay source commits do not encode base/head/head")
        if replay_adapter == "ant_source_maven_target":
            inventories = contract.get("source_artifact_inventory")
            if not isinstance(inventories, dict) or set(inventories) != {"A0", "A1"}:
                raise ValueError("Ant replay source artifact inventory is incomplete")
            for side, rows in inventories.items():
                if not isinstance(rows, list) or not rows:
                    raise ValueError(f"Ant replay {side} artifact inventory is empty")
                for row in rows:
                    if not isinstance(row.get("artifact_id"), str) or row.get("size_bytes", 0) <= 0:
                        raise ValueError(f"Ant replay {side} artifact inventory row is invalid")
                    required = row.get("required_entries")
                    forbidden = row.get("forbidden_entries")
                    if not isinstance(required, dict) or not all(required.values()):
                        raise ValueError(f"Ant replay {side} required JAR entries are unproved")
                    if not isinstance(forbidden, dict) or any(forbidden.values()):
                        raise ValueError(f"Ant replay {side} forbidden JAR entries are present")
    elif replay_adapter == "cross_repo_command":
        if contract.get("source_application") != "side_by_side_opening_checkout":
            raise ValueError("cross-repo replay did not use side-by-side opening checkouts")
        if contract.get("built_source_commits") != {
            "A0": public_input["source"]["base_commit"],
            "A1": public_input["source"]["candidate_commit"],
            "A2": public_input["source"]["candidate_commit"],
        }:
            raise ValueError("cross-repo replay source commits do not encode base/head/head")
        provenance = contract.get("command_provenance")
        expected_repository = private.get("command_config_repository", "target")
        if expected_repository == "source":
            expected_provenance_repository = public_input["source"]["repository"]
            expected_provenance_commit = public_input["source"]["base_commit"]
        elif expected_repository == "target":
            expected_provenance_repository = private["target_repository"]
            expected_provenance_commit = target_snapshot["commit"]
        else:
            raise ValueError("cross-repo command_config_repository must be source or target")
        if provenance != {
            "repository": expected_provenance_repository,
            "commit": expected_provenance_commit,
            "path": private["command_config_path"],
        }:
            raise ValueError("cross-repo command provenance is not the declared cutoff file")
    elif contract.get("requirements_commit") != requirements_snapshot["commit"]:
        raise ValueError("replay requirements commit is not the public cutoff snapshot")
    target_patch_evidence = contract.get("target_patch_evidence")
    if not target_patch_evidence or not (evidence / target_patch_evidence).is_file():
        raise ValueError("A2 maintainer patch evidence is missing")
    attempt = evidence / contract["selected_attempt_id"]
    summaries = {arm: read_json(attempt / arm.lower() / "summary.json") for arm in ("A0", "A1", "A2")}
    exits = {arm: summaries[arm]["exit_code"] for arm in summaries}
    if exits["A0"] != 0 or exits["A1"] == 0 or exits["A2"] != 0:
        raise ValueError(f"parsed replay exits are not 0/nonzero/0: {exits}")
    commands = [summaries[arm]["command"] for arm in ("A0", "A1", "A2")]
    if commands[0] != commands[1] or commands[1] != commands[2] or commands[0] != contract["test_command"]:
        raise ValueError("three arms did not use the same target command")
    logs = {
        arm: (attempt / arm.lower() / "command.log").read_text(encoding="utf-8", errors="replace")
        for arm in ("A0", "A1", "A2")
    }
    signature = contract.get("failure_signature")
    normalized_logs = {
        arm: UUID.sub("<uuid>", ADDRESS.sub("0x<address>", value))
        for arm, value in logs.items()
    }
    if (
        not signature
        or signature not in normalized_logs["A1"]
        or signature in normalized_logs["A0"]
        or signature in normalized_logs["A2"]
    ):
        raise ValueError("failure signature is not exclusive to A1")
    parsed_maven_tests = None
    if replay_adapter in MAVEN_REPLAY_ADAPTERS:
        parsed_maven_tests = {
            arm: sum(
                int(match.group(1))
                for line in logs[arm].splitlines()
                if "Time elapsed:" in line
                for match in MAVEN_TEST_SUMMARY.finditer(line)
                if match.group(2) == "0"
                and match.group(3) == "0"
                and match.group(4) == "0"
            )
            for arm in ("A0", "A2")
        }
        if parsed_maven_tests["A0"] <= 0 or parsed_maven_tests["A2"] <= 0:
            raise ValueError("Maven A0/A2 logs do not contain a successful test-class summary")
    with (evidence / "run-results.tsv").open(encoding="utf-8", newline="") as handle:
        tsv = list(csv.DictReader(handle, delimiter="\t"))
    observed = {row["arm"]: int(row["exit_code"]) for row in tsv}
    if observed != exits:
        raise ValueError("run-results.tsv disagrees with parsed arm summaries")
    parsed_checks = None
    if replay_adapter == "cross_repo_command":
        parsed_checks = {arm: summaries[arm].get("checks_run") for arm in ("A0", "A1", "A2")}
        if any(not isinstance(value, int) or value <= 0 for value in parsed_checks.values()):
            raise ValueError("cross-repo command did not record positive check counts for every arm")
        if contract.get("checks_run") != parsed_checks:
            raise ValueError("cross-repo contract check counts disagree with arm summaries")
    result = {
        "schema_version": "1.0",
        "machine_strict_e2": True,
        "exit_codes": exits,
        "failure_signature": signature,
        "test_command": contract["test_command"],
        "target_test_path": contract.get("target_test_path"),
        "primary_result_channel": contract["primary_result_channel"],
        "target_cutoff_commit": target_snapshot["commit"],
        "target_a2_kind": contract["target_a2_kind"],
    }
    if replay_adapter == "requirements_constraint":
        result.update({
            "source_application": contract["source_application"],
            "source_base_commit": contract["source_base_commit"],
            "source_head_commit": contract["source_head_commit"],
            "source_versions": contract["source_versions"],
            "installed_source_versions": contract["installed_source_versions"],
            "catalog_source_snapshot_commit": requirements_snapshot["commit"],
        })
    elif replay_adapter in MAVEN_REPLAY_ADAPTERS:
        result.update({
            "source_application": contract["source_application"],
            "built_source_commits": contract["built_source_commits"],
            "source_artifact_versions": contract["source_artifact_versions"],
            "tests_run": parsed_maven_tests,
        })
        if replay_adapter == "ant_source_maven_target":
            result["source_artifact_inventory_verified"] = True
    elif replay_adapter == "cross_repo_command":
        result.update({
            "source_application": contract["source_application"],
            "built_source_commits": contract["built_source_commits"],
            "checks_run": parsed_checks,
        })
    else:
        result["requirements_cutoff_commit"] = requirements_snapshot["commit"]
    return result


def score_case(output: Path, private: dict[str, Any]) -> dict[str, Any]:
    prediction = read_jsonl(output / "blind" / "predictions.jsonl")[0]
    if prediction["case_id"] != private["candidate_id"]:
        raise ValueError("blind prediction candidate id mismatch")
    scored_prediction = {"case_id": private["relation_id"], "targets": prediction["targets"]}
    write_jsonl(output / "prediction-for-score.jsonl", [scored_prediction])
    ranked = [row["repository"] for row in scored_prediction["targets"]]
    target = private["target_repository"]
    rank = ranked.index(target) + 1 if target in ranked else None
    target_prediction = next((row for row in scored_prediction["targets"] if row["repository"] == target), None)
    expected_paths = set(private["expected_check_paths"])
    predicted_paths = set(target_prediction.get("paths", [])) if target_prediction else set()
    result = {
        "schema_version": "1.0",
        "evidence_layer": "E2",
        "dataset_status": "single_case_construction",
        "case_id": private["relation_id"],
        "target_repository": target,
        "repository_found": rank is not None,
        "rank": rank,
        "target_recall": 1.0 if rank is not None else 0.0,
        "mean_reciprocal_rank": 1.0 / rank if rank else 0.0,
        "recall_at_1": 1.0 if rank == 1 else 0.0,
        "recall_at_3": 1.0 if rank is not None and rank <= 3 else 0.0,
        "recall_at_5": 1.0 if rank is not None and rank <= 5 else 0.0,
        "expected_check_paths": sorted(expected_paths),
        "predicted_check_paths": sorted(predicted_paths),
        "check_position_found": bool(expected_paths & predicted_paths),
        "runnable_check_proposed": bool(target_prediction and target_prediction.get("commands")),
        "execution_result": target_prediction.get("execution_result", "not_assessed") if target_prediction else "not_assessed",
        "non_target_predictions": "unjudged",
        "precision_f1_specificity_reported": False,
    }
    write_json(output / "score.json", result)
    return result


def build_report(output: Path, private: dict[str, Any], revealed_at: str) -> dict[str, Any]:
    blind = verify_blind(output)
    replay = verify_replay(output, private)
    score = score_case(output, private)
    isolation = read_json(output / "blind" / "isolation.json")
    prediction = read_jsonl(output / "blind" / "predictions.jsonl")[0]
    chronology_ok = timestamp(isolation["completed_at"]) <= timestamp(revealed_at)
    semantic = private["semantic_review"]
    blockers = []
    if public_manifest_leaks_relation(output, private):
        blockers.append("public_manifest_leaks_relation_label")
    if not chronology_ok:
        blockers.append("label_revealed_before_blind_completion")
    if semantic.get("approved") is not True:
        blockers.append("semantic_review_not_approved")
    report = {
        "schema_version": "1.0",
        "case_id": private["relation_id"],
        "candidate_id": private["candidate_id"],
        "evidence_layer": "E2",
        "status": "case_ready_for_formal_pool" if not blockers else "not_ready",
        "case_ready_for_formal_pool": not blockers,
        "formal_benchmark": False,
        "formal_benchmark_reason": "grouped dataset split and collection release are separate",
        "source_change_family": private["source_change_family"],
        "directed_relation": [
            read_jsonl(output / "public" / "inputs.jsonl")[0]["source"]["repository"],
            private["target_repository"],
        ],
        "mechanism": private["mechanism"],
        "repair_template": private["repair_template"],
        "blind_prediction_created_at": prediction["created_at"],
        "blind_completed_at": isolation["completed_at"],
        "label_revealed_at": revealed_at,
        "blind": blind,
        "replay": replay,
        "semantic_review": semantic,
        "score": score,
        "blockers": blockers,
    }
    write_json(output / "case-report.json", report)
    return report


def reveal_and_replay(
    root: Path,
    private_path: Path,
    output: Path,
    candidate_id: str,
) -> int:
    """Reveal one private label only after a completed blind package exists."""

    revealed_at = now()
    private = read_json(private_path)
    resolved = validate_private(root, private, candidate_id)
    (output / "private").mkdir()
    write_json(output / "private" / "label.json", private)
    write_json(output / "private" / "reveal.json", {
        "schema_version": "1.0",
        "candidate_id": candidate_id,
        "revealed_at": revealed_at,
        "blind_container_exited": True,
    })
    replay_code = run_replay(root, private, resolved, output)
    if replay_code:
        report = {
            "schema_version": "1.0",
            "case_id": private["relation_id"],
            "status": "rejected_or_replay_failed",
            "case_ready_for_formal_pool": False,
            "replay_exit_code": replay_code,
            "blockers": ["strict_replay_failed"],
        }
        write_json(output / "case-report.json", report)
        print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
        return 1
    report = build_report(output, private, revealed_at)
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if report["case_ready_for_formal_pool"] else 1


def run(args: argparse.Namespace) -> int:
    root = repository_root()
    public_path = resolve(root, args.public_manifest)
    private_path = resolve(root, args.private_manifest)
    output = resolve(root, args.output_dir)
    if output.exists():
        raise ValueError(f"output directory already exists: {output}")
    public_manifest = read_json(public_path)
    output.mkdir(parents=True)
    (output / ".gitignore").write_text("replay-work/\n", encoding="utf-8")
    prepared = prepare_public(root, public_manifest, output)
    run_blind(root, prepared, private_path, output)

    # This is the first read of the private manifest.  The isolated blind
    # container has already exited and never received this path as a mount.
    return reveal_and_replay(
        root, private_path, output, prepared["candidate_id"]
    )


def resume_after_blind(args: argparse.Namespace) -> int:
    """Continue an untouched, verifier-clean blind output at private reveal."""

    root = repository_root()
    public_path = resolve(root, args.public_manifest)
    private_path = resolve(root, args.private_manifest)
    output = resolve(root, args.output_dir)
    if not output.is_dir():
        raise ValueError(f"blind output directory does not exist: {output}")
    if (output / "private").exists():
        raise ValueError("cannot resume after the private label has been revealed")
    supplied_public = read_json(public_path)
    stored_public = read_json(output / "public" / "manifest.json")
    if packaged_public_manifest(supplied_public) != stored_public:
        raise ValueError("stored public package does not match the supplied manifest")
    candidate_id = supplied_public["candidate_id"]
    inputs = read_jsonl(output / "public" / "inputs.jsonl")
    if len(inputs) != 1 or inputs[0].get("case_id") != candidate_id:
        raise ValueError("stored public package candidate id mismatch")
    metrics = verify_blind(output)
    write_json(output / "blind" / "verification.json", metrics)
    return reveal_and_replay(root, private_path, output, candidate_id)


def verify(args: argparse.Namespace) -> int:
    root = repository_root()
    output = resolve(root, args.output_dir)
    private = read_json(output / "private" / "label.json")
    reveal = read_json(output / "private" / "reveal.json")
    try:
        report = build_report(output, private, reveal["revealed_at"])
    except (ValueError, RuntimeError, OSError, KeyError, json.JSONDecodeError) as exc:
        report = {
            "schema_version": "1.0",
            "case_id": private.get("relation_id"),
            "status": "not_ready",
            "case_ready_for_formal_pool": False,
            "formal_benchmark": False,
            "blockers": [str(exc)],
        }
        write_json(output / "case-report.json", report)
        print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
        return 1
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if report["case_ready_for_formal_pool"] else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--plan", required=True)
    prepare_parser.add_argument("--case-id", required=True)
    prepare_parser.add_argument("--input-dir", required=True)
    prepare_parser.add_argument("--inputs")
    prepare_parser.add_argument("--snapshots")
    prepare_parser.add_argument("--catalogs")
    prepare_parser.add_argument("--source-patch-dir", required=True)
    prepare_parser.add_argument("--target-patch-dir", required=True)
    prepare_parser.add_argument("--mirror-root")
    prepare_parser.add_argument("--output-dir", required=True)
    prepare_parser.add_argument(
        "--replay-adapter",
        choices=("auto", *REPLAY_ADAPTERS),
        default="auto",
    )
    prepare_parser.add_argument(
        "--runner",
        choices=("py310", "py313", "tox3", "tox3-py38", "tox3-py38-2021"),
        default="py310",
    )
    prepare_parser.add_argument("--bootstrap-constraint", action="append", default=[])
    prepare_parser.add_argument("--virtualenv-pip-version")
    prepare_parser.add_argument("--virtualenv-setuptools-version")
    prepare_parser.add_argument("--mechanism")
    prepare_parser.add_argument("--repair-template")
    prepare_parser.set_defaults(function=prepare_manifests)
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--public-manifest", required=True)
    run_parser.add_argument("--private-manifest", required=True)
    run_parser.add_argument("--output-dir", required=True)
    run_parser.set_defaults(function=run)
    resume_parser = subparsers.add_parser("resume-after-blind")
    resume_parser.add_argument("--public-manifest", required=True)
    resume_parser.add_argument("--private-manifest", required=True)
    resume_parser.add_argument("--output-dir", required=True)
    resume_parser.set_defaults(function=resume_after_blind)
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--output-dir", required=True)
    verify_parser.set_defaults(function=verify)
    args = parser.parse_args()
    try:
        return args.function(args)
    except (ValueError, RuntimeError, OSError, KeyError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

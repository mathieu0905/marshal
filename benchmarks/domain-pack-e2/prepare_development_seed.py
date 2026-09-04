#!/usr/bin/env python3
"""Convert one existing strict-E2 replay into a self-contained development case.

The source event chooses only the Pack revision and the explicitly disclosed
development materialization subset. Project membership still comes from the
source-opening ``projects.txt``; replay results never change membership or
routes. The importer verifies arm summaries, commands, failure signature, and
target patch while copying the evidence into the case package.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from build_openstack_requirements_pack import (
    BuildError,
    _canonical_distribution,
    _materialize_command_template,
    _project_members,
    build_pack,
)
from materialize_case_record import materialize_case
from verify_case_record import verification_errors


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise BuildError(f"expected a JSON object in {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _repo_path(repo_root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else repo_root / path


def _relative_to_repo(repo_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve()))
    except ValueError as exc:
        raise BuildError(f"development output must be inside repository: {path}") from exc


def _copy(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise BuildError(f"missing evidence artifact: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _git_has_commit(git_dir: Path, commit: str) -> bool:
    process = subprocess.run(
        ["git", f"--git-dir={git_dir}", "cat-file", "-e", f"{commit}^{{commit}}"],
        check=False,
        capture_output=True,
        text=True,
    )
    return process.returncode == 0


def prepare(seed_path: Path, output_dir: Path, repo_root: Path) -> dict[str, Any]:
    seed = _load_json(seed_path)
    authoring_case_ids = {seed["case_id"]}
    if seed.get("authoring_registry"):
        authoring_registry = _load_json(
            _repo_path(repo_root, seed["authoring_registry"])
        )
        authoring_case_ids.update(authoring_registry.get("source_change_ids", []))
    case_dir = _repo_path(repo_root, seed["existing_case_dir"])
    public_dir = case_dir / "public"
    evidence_root = case_dir / "evidence" / seed["case_id"]
    contract = _load_json(evidence_root / "contract.json")
    label = _load_json(case_dir / "private" / "label.json")
    public_input = _load_json(public_dir / "inputs.jsonl")
    snapshots = _load_json(public_dir / "repository-snapshots.jsonl")
    public_manifest = _load_json(public_dir / "manifest.json")
    snapshot_overrides: dict[str, dict[str, Any]] = {}
    if seed.get("snapshot_overrides"):
        override_payload = _load_json(_repo_path(repo_root, seed["snapshot_overrides"]))
        if override_payload.get("observation_cutoff") != public_input.get(
            "observation_cutoff"
        ):
            raise BuildError("snapshot override cutoff differs from source event cutoff")
        for row in override_payload.get("repositories", []):
            repository = row.get("repository")
            if not repository or repository in snapshot_overrides:
                raise BuildError("snapshot overrides contain an invalid or duplicate row")
            snapshot_overrides[repository] = row

    if public_input.get("case_id") != contract.get("candidate_id"):
        raise BuildError("public input and replay contract identify different source events")
    if contract.get("case_id") != seed["case_id"]:
        raise BuildError("seed case_id and replay contract do not match")

    source_patch_candidates = sorted((public_dir / "source-patches").glob("*.patch"))
    if len(source_patch_candidates) != 1:
        raise BuildError("development seed requires exactly one public source patch")
    source_patch = source_patch_candidates[0]
    mirror_root = _repo_path(repo_root, public_manifest["mirror_root"])
    source_mirror = mirror_root / "openstack__requirements.git"
    if not _git_has_commit(source_mirror, contract["source_base_commit"]):
        raise BuildError("requirements mirror lacks source-opening base commit")

    target_repository = contract["target_repository"]
    repositories = snapshots.get("repositories")
    if not isinstance(repositories, list):
        raise BuildError("public repository snapshots lack repositories list")
    source_members = _project_members(
        {
            "git_dir": str(source_mirror),
            "commit": contract["source_base_commit"],
            "projects_path": "projects.txt",
        }
    )
    unknown_overrides = set(snapshot_overrides) - set(source_members)
    if unknown_overrides:
        raise BuildError(
            "snapshot overrides are outside source-opening projects.txt: "
            + ", ".join(sorted(unknown_overrides))
        )
    manifest_by_repository = {
        row["repository"]: dict(snapshot_overrides.get(row["repository"], row))
        for row in repositories
        if row.get("repository") in source_members
    }
    for repository in source_members:
        manifest_by_repository.setdefault(
            repository,
            dict(
                snapshot_overrides.get(
                    repository,
                    {
                        "repository": repository,
                        "status": "not_assessed",
                        "reason": "absent_from_legacy_snapshot_catalog",
                    },
                )
            ),
        )

    materialization_setting = seed["materialize_repositories"]
    if materialization_setting == "all_available":
        materialize_repositories = {
            repository
            for repository, row in manifest_by_repository.items()
            if row.get("status") == "available"
        }
    elif isinstance(materialization_setting, list) and all(
        isinstance(repository, str) for repository in materialization_setting
    ):
        materialize_repositories = set(materialization_setting)
    else:
        raise BuildError(
            "materialize_repositories must be a repository list or all_available"
        )
    if target_repository not in materialize_repositories:
        raise BuildError("development materialization must include the judged target")

    manifest_rows: list[dict[str, Any]] = []
    seen_materialized: set[str] = set()
    for repository in sorted(source_members):
        row = manifest_by_repository[repository]
        if repository in materialize_repositories:
            if row.get("status") != "available" or not row.get("commit"):
                raise BuildError(f"selected repository has no available snapshot: {repository}")
            git_dir = mirror_root / f"{repository.replace('/', '__')}.git"
            if not _git_has_commit(git_dir, row["commit"]):
                raise BuildError(f"mirror lacks cutoff commit for {repository}")
            row["materialize"] = True
            row["git_dir"] = _relative_to_repo(repo_root, git_dir)
            seen_materialized.add(repository)
        else:
            row.pop("materialize", None)
            row.pop("git_dir", None)
        manifest_rows.append(row)
    missing_materialized = materialize_repositories - seen_materialized
    if missing_materialized:
        raise BuildError(
            "materialized repositories absent from snapshot catalog: "
            + ", ".join(sorted(missing_materialized))
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    snapshot_manifest = {
        "observation_cutoff": public_input["observation_cutoff"],
        "repositories": manifest_rows,
    }
    snapshot_manifest_path = output_dir / "snapshot-manifest.json"
    _write_json(snapshot_manifest_path, snapshot_manifest)
    build_spec = {
        "pack_family_id": seed["pack_family_id"],
        "pack_revision_id": seed["pack_revision_id"],
        "project": "openstack",
        "authoring_case_ids": sorted(authoring_case_ids),
        "source": {
            "repository": "openstack/requirements",
            "git_dir": _relative_to_repo(repo_root, source_mirror),
            "commit": contract["source_base_commit"],
            "projects_path": "projects.txt",
            "constraints_paths": public_input["source"]["changed_paths"],
        },
        "snapshot_manifest": {
            "manifest_id": f"{seed['case_id']}-public-cutoff-snapshots",
            "path": _relative_to_repo(repo_root, snapshot_manifest_path),
            "format": "project-snapshots-json",
        },
    }
    if seed.get("scan_workers") is not None:
        build_spec["scan_workers"] = seed["scan_workers"]
    _write_json(output_dir / "build-spec.json", build_spec)
    pack = build_pack(build_spec)
    _write_json(output_dir / "domain-pack.json", pack)

    evidence_dir = output_dir / "evidence"
    _copy(source_patch, evidence_dir / "source.patch")
    _copy(evidence_root / "target.patch", evidence_dir / "target.patch")
    _copy(evidence_root / "contract.json", evidence_dir / "contract.json")
    selected_attempt = evidence_root / contract["selected_attempt_id"]
    for arm_id in ("A0", "A1", "A2"):
        source_arm = selected_attempt / arm_id.lower()
        _copy(
            source_arm / "summary.json",
            evidence_dir / arm_id.lower() / "summary.json",
        )
        _copy(
            source_arm / "command.log",
            evidence_dir / arm_id.lower() / "command.log",
        )

    source_event = dict(public_input["source"])
    source_event["observation_cutoff"] = public_input["observation_cutoff"]
    source_event["patch_ref"] = "evidence/source.patch"
    case_spec = {"case_id": seed["case_id"], "source_event": source_event}
    _write_json(output_dir / "case-spec.json", case_spec)
    case = materialize_case(pack, case_spec, source_patch.read_text(encoding="utf-8"))

    dependency = _canonical_distribution(contract["changed_distribution"])
    route_id = f"requirements-constraint:{dependency}"
    routes = {route["id"]: route for route in pack["dependency_routes"]}
    if route_id not in routes:
        raise BuildError(f"materialized Pack has no route for {route_id}")
    candidate_check_ids = case["public"]["candidate_selection"]["candidate_check_ids"]
    check_candidates = [
        check
        for check in pack["checks"]
        if check["id"] in candidate_check_ids
        and check["location_repo"] == target_repository
        and check["definition"]["path"] == contract["target_test_path"]
    ]
    if len(check_candidates) != 1:
        raise BuildError(
            "expected exactly one Pack check matching replay target path; found "
            f"{len(check_candidates)}"
        )
    check = check_candidates[0]
    command_text = " ".join(contract["test_command"])
    templates_by_id = {
        template["id"]: template for template in pack["execution_templates"]
    }
    command_candidates = []
    for execution_binding in check["execution_bindings"]:
        template = templates_by_id[execution_binding["template_id"]]
        specialized = _materialize_command_template(
            template["command_template"],
            contract["test_selector"],
        )
        if specialized != command_text:
            continue
        command_candidates.append(
            {
                "base_template_id": template["id"],
                "provenance": {
                    "repository": check["location_repo"],
                    "commit": template["provenance"]["commit"],
                    "test_path": check["definition"]["path"],
                    "ci_definition": template["definition"],
                },
                "template": specialized,
            }
        )
    if len(command_candidates) != 1:
        raise BuildError(
            "expected exactly one Pack command matching replay command; found "
            f"{len(command_candidates)}"
        )
    if command_candidates[0]["provenance"].get("commit") != contract["target_base_commit"]:
        raise BuildError("Pack command and replay use different target cutoff commits")

    arms: dict[str, Any] = {}
    expected_status = {"A0": "pass", "A1": "fail", "A2": "pass"}
    signature = contract["failure_signature"]
    for arm_id, status in expected_status.items():
        arm_ref = f"evidence/{arm_id.lower()}"
        summary = _load_json(output_dir / arm_ref / "summary.json")
        log = (output_dir / arm_ref / "command.log").read_text(
            encoding="utf-8",
            errors="replace",
        )
        if summary.get("arm") != arm_id:
            raise BuildError(f"{arm_id} summary identifies a different arm")
        if summary.get("command") != contract["test_command"]:
            raise BuildError(f"{arm_id} did not execute the contracted command")
        exit_code = summary.get("exit_code")
        if (status == "pass" and exit_code != 0) or (
            status == "fail" and (not isinstance(exit_code, int) or exit_code == 0)
        ):
            raise BuildError(f"{arm_id} exit code violates strict-E2 direction")
        if bool(signature in log) != (arm_id == "A1"):
            raise BuildError(f"failure signature is not exclusive to A1: {arm_id}")
        arms[arm_id] = {
            "status": status,
            "exit_code": exit_code,
            "artifact_refs": [
                f"{arm_ref}/summary.json",
                f"{arm_ref}/command.log",
            ],
            "summary_ref": f"{arm_ref}/summary.json",
            "command_log_ref": f"{arm_ref}/command.log",
        }

    case["curator"]["judged_e2_bindings"].append(
        {
            "binding_id": f"e2:{seed['case_id']}",
            "relation_id": label["relation_id"],
            "route_id": route_id,
            "check_id": check["id"],
            "location_repo": target_repository,
            "selector": contract["test_selector"],
            "command": command_candidates[0],
            "arms": arms,
            "failure_signature": {
                "value": signature,
                "exclusive_to": "A1",
                "artifact_refs": [
                    "evidence/a0/command.log",
                    "evidence/a1/command.log",
                    "evidence/a2/command.log",
                ],
            },
            "target_repair": {
                "repository": target_repository,
                "change_id": contract["target_change"],
                "patch_ref": "evidence/target.patch",
            },
            "mechanism": label["mechanism"],
        }
    )
    _write_json(output_dir / "case-record.json", case)
    errors = verification_errors(pack, case, output_dir)
    not_assessed = pack["coverage"]["snapshot_status_counts"]["not_assessed"]
    release_blockers = [
        "Pack materialization includes a known target used during authoring",
    ]
    if not pack["coverage"]["materialization_complete"]:
        release_blockers.append(
            "Pack materialization is incomplete for the projects.txt universe"
        )
    if not_assessed:
        release_blockers.append(
            f"{not_assessed} candidate repositories lack assessed cutoff snapshots"
        )
    verification = {
        "valid": not errors,
        "artifact_verification": "performed",
        "errors": errors,
        "release_status": "development",
        "release_blockers": release_blockers,
    }
    _write_json(output_dir / "verification.json", verification)
    if errors:
        raise BuildError("generated package failed verification: " + "; ".join(errors))
    return {
        "case_id": seed["case_id"],
        "release_status": "development",
        "candidate_repositories": pack["coverage"]["projects_txt_candidates"],
        "materialized_repositories": pack["coverage"]["materialized_candidates"],
        "candidate_checks": len(candidate_check_ids),
        "judged_e2_bindings": 1,
        "output": str(output_dir),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = prepare(args.seed, args.output_dir, args.repo_root)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

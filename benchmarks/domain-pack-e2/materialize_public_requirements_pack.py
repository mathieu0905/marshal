#!/usr/bin/env python3
"""Materialize an OpenStack requirements Domain Pack from public opening data.

This entry point accepts one label-blind source-opening event and local public
Git mirrors.  It never accepts a target relation, replay result, private label,
or maintainer repair.  Project membership comes from ``projects.txt`` at the
opening base commit, and every member receives an explicit snapshot row at the
opening ``created_at`` cutoff.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from build_openstack_requirements_pack import (
    GENERATOR_ID,
    GENERATOR_VERSION,
    SOURCE_REQUIREMENTS_PATHS,
    BuildError,
    _git,
    _project_members,
    build_pack,
)
from prepare_development_seed import _git_has_commit, _write_json


REQUIRED_GENERATOR_VERSION = "1.4.0"
PACK_FAMILY_ID = "openstack-requirements-python-consumers"
SOURCE_REPOSITORY = "openstack/requirements"
AUTHORING_INFLUENCE = Path(__file__).resolve().with_name("authoring-influence.json")

_EVENT_FIELDS = {
    "schema_version",
    "source_change_id",
    "candidate_id",
    "source_change_family",
    "candidate_repository_catalog",
    "catalog_selected_at",
    "label_review_state",
    "discovery",
    "opening",
}
_OPENING_FIELDS = {
    "provider",
    "repository",
    "number",
    "change_id",
    "url",
    "created_at",
    "branch",
    "subject",
    "base_commit",
    "head_commit",
    "changed_paths",
}
_FORBIDDEN_FIELD_NAMES = {
    "a0",
    "a1",
    "a2",
    "arms",
    "expected_check_paths",
    "failure_signature",
    "hidden_impact_label",
    "impact_label",
    "judged_e2_bindings",
    "label",
    "labels",
    "maintainer_patch",
    "outcome",
    "outcomes",
    "private",
    "private_label",
    "replay",
    "replay_plan",
    "result",
    "results",
    "target",
    "target_change",
    "target_change_id",
    "target_id",
    "target_patch",
    "target_repo",
    "target_repository",
}


def _normalized_field(value: str) -> str:
    return value.strip().lower().replace("-", "_")


def _reject_forbidden_fields(value: Any, location: str = "source_event") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if not isinstance(key, str):
                raise BuildError(f"{location} contains a non-string field name")
            normalized = _normalized_field(key)
            if (
                normalized in _FORBIDDEN_FIELD_NAMES
                or normalized.startswith("target_")
                or normalized.startswith("private_")
                or normalized.startswith("outcome_")
                or normalized.startswith("replay_")
            ):
                raise BuildError(f"forbidden public event field: {location}.{key}")
            _reject_forbidden_fields(nested, f"{location}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_forbidden_fields(nested, f"{location}[{index}]")


def _validate_exact_fields(
    value: dict[str, Any],
    *,
    allowed: set[str],
    required: set[str],
    location: str,
) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise BuildError(
            f"unsupported {location} field(s): " + ", ".join(sorted(unknown))
        )
    missing = required - set(value)
    if missing:
        raise BuildError(
            f"missing {location} field(s): " + ", ".join(sorted(missing))
        )


def _rfc3339(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BuildError("opening.created_at must be a non-empty timestamp")
    timestamp = value.strip().replace("Z", "+00:00")
    try:
        parsed = dt.datetime.fromisoformat(timestamp)
    except ValueError as exc:
        raise BuildError(f"invalid opening.created_at: {value!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.UTC)
    return parsed.astimezone(dt.UTC).isoformat().replace("+00:00", "Z")


def _authoring_case_ids(source_change_id: str) -> list[str]:
    try:
        registry = json.loads(AUTHORING_INFLUENCE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise BuildError(f"cannot read authoring influence registry: {exc}") from exc
    if not isinstance(registry, dict):
        raise BuildError("authoring influence registry must be one JSON object")
    source_change_ids = registry.get("source_change_ids")
    if (
        not isinstance(source_change_ids, list)
        or not all(
            isinstance(case_id, str) and case_id for case_id in source_change_ids
        )
        or len(set(source_change_ids)) != len(source_change_ids)
    ):
        raise BuildError(
            "authoring influence source_change_ids must be a unique string list"
        )
    return [source_change_id] if source_change_id in source_change_ids else []


def _validate_source_event(source_event: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(source_event, dict):
        raise BuildError("source event must be one JSON object")
    _reject_forbidden_fields(source_event)
    _validate_exact_fields(
        source_event,
        allowed=_EVENT_FIELDS,
        required={"source_change_id", "opening"},
        location="source event",
    )
    source_change_id = source_event.get("source_change_id")
    candidate_id = source_event.get("candidate_id")
    if not isinstance(source_change_id, str) or not source_change_id.strip():
        raise BuildError("source_change_id must be a non-empty string")
    if candidate_id is not None and (
        not isinstance(candidate_id, str) or not candidate_id.strip()
    ):
        raise BuildError("candidate_id must be a non-empty string")
    if candidate_id is not None and (
        source_change_id.strip() != candidate_id.strip()
    ):
        raise BuildError("source_change_id and candidate_id must be identical")
    if source_event.get("label_review_state", "not_started") != "not_started":
        raise BuildError("label_review_state must remain not_started")
    discovery = source_event.get("discovery")
    if discovery is not None and not isinstance(discovery, dict):
        raise BuildError("discovery must be a JSON object")

    opening = source_event["opening"]
    if not isinstance(opening, dict):
        raise BuildError("opening must be a JSON object")
    _validate_exact_fields(
        opening,
        allowed=_OPENING_FIELDS,
        required={
            "provider",
            "repository",
            "number",
            "created_at",
            "branch",
            "base_commit",
            "head_commit",
            "changed_paths",
        },
        location="opening",
    )
    if opening["provider"] != "gerrit":
        raise BuildError("opening.provider must be gerrit")
    if opening["repository"] != SOURCE_REPOSITORY:
        raise BuildError(f"opening.repository must be {SOURCE_REPOSITORY}")
    if not isinstance(opening["number"], int) or isinstance(opening["number"], bool):
        raise BuildError("opening.number must be an integer")
    canonical_id = f"formal-opendev-{opening['number']}"
    if source_change_id.strip() != canonical_id:
        raise BuildError(
            "source_change_id must equal formal-opendev-<opening.number>"
        )
    if candidate_id is not None and candidate_id.strip() != canonical_id:
        raise BuildError("candidate_id must equal formal-opendev-<opening.number>")
    for key in ("branch", "base_commit", "head_commit"):
        if not isinstance(opening[key], str) or not opening[key]:
            raise BuildError(f"opening.{key} must be a non-empty string")
    changed_paths = opening["changed_paths"]
    if (
        not isinstance(changed_paths, list)
        or not changed_paths
        or not all(isinstance(path, str) and path for path in changed_paths)
        or len(set(changed_paths)) != len(changed_paths)
    ):
        raise BuildError("opening.changed_paths must be a non-empty unique string list")
    relevant_paths = sorted(set(changed_paths) & SOURCE_REQUIREMENTS_PATHS)
    if not relevant_paths:
        raise BuildError(
            "requirements Pack openings must change global-requirements.txt "
            "or upper-constraints.txt"
        )

    normalized = dict(source_event)
    normalized["source_change_id"] = canonical_id
    normalized["candidate_id"] = canonical_id
    normalized["opening"] = dict(opening)
    normalized["opening"]["created_at"] = _rfc3339(opening["created_at"])
    normalized["opening"]["changed_paths"] = sorted(changed_paths)
    normalized["requirements_paths"] = relevant_paths
    return normalized


def _mirror_git_dir(mirror_root: Path, repository: str) -> Path:
    return mirror_root / f"{repository.replace('/', '__')}.git"


def _run_git(git_dir: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", f"--git-dir={git_dir}", *args],
        check=False,
        capture_output=True,
        text=True,
    )


def _opening_patch(
    source_git_dir: Path,
    base_commit: str,
    head_commit: str,
    declared_paths: list[str],
) -> str:
    if not _git_has_commit(source_git_dir, base_commit):
        raise BuildError("requirements mirror lacks source-opening base commit")
    if not _git_has_commit(source_git_dir, head_commit):
        raise BuildError("requirements mirror lacks source-opening head commit")
    ancestor = _run_git(
        source_git_dir,
        "merge-base",
        "--is-ancestor",
        base_commit,
        head_commit,
    )
    if ancestor.returncode:
        raise BuildError("source-opening base commit is not an ancestor of head commit")
    actual_paths = _git(
        source_git_dir,
        "diff",
        "--name-only",
        "--no-renames",
        base_commit,
        head_commit,
        "--",
    ).splitlines()
    if sorted(actual_paths) != sorted(declared_paths):
        raise BuildError(
            "opening.changed_paths differs from the source-opening Git diff"
        )
    patch = _git(
        source_git_dir,
        "diff",
        "--binary",
        "--full-index",
        "--no-ext-diff",
        "--no-renames",
        base_commit,
        head_commit,
        "--",
    )
    if not patch:
        raise BuildError("source-opening patch is empty")
    return patch


def _default_branch_ref(git_dir: Path) -> str | None:
    symbolic = _run_git(git_dir, "symbolic-ref", "HEAD")
    if symbolic.returncode == 0 and symbolic.stdout.strip():
        ref = symbolic.stdout.strip()
        exists = _run_git(git_dir, "show-ref", "--verify", "--quiet", ref)
        if exists.returncode == 0:
            return ref
    for ref in ("refs/heads/master", "refs/heads/main"):
        exists = _run_git(git_dir, "show-ref", "--verify", "--quiet", ref)
        if exists.returncode == 0:
            return ref
    return None


def _snapshot_row(
    repository: str,
    mirror_root: Path,
    cutoff: str,
    *,
    source_base_commit: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "repository": repository,
        "observation_cutoff": cutoff,
    }
    git_dir = _mirror_git_dir(mirror_root, repository)
    if not git_dir.is_dir():
        return {
            **row,
            "status": "not_assessed",
            "reason": "candidate Git mirror is absent",
        }
    if source_base_commit is not None:
        if not _git_has_commit(git_dir, source_base_commit):
            return {
                **row,
                "status": "not_assessed",
                "reason": "source mirror lacks the opening base commit",
            }
        commit = source_base_commit
        resolution = "source_opening_base_commit"
        branch_ref = None
    else:
        branch_ref = _default_branch_ref(git_dir)
        if branch_ref is None:
            return {
                **row,
                "status": "not_assessed",
                "reason": "candidate mirror has no resolvable default branch",
            }
        resolved = _run_git(
            git_dir,
            "rev-list",
            "--first-parent",
            "-1",
            f"--before={cutoff}",
            branch_ref,
        )
        if resolved.returncode:
            detail = resolved.stderr.strip() or resolved.stdout.strip()
            return {
                **row,
                "status": "not_assessed",
                "reason": f"cutoff commit resolution failed: {detail}",
                "branch_ref": branch_ref,
            }
        commit = resolved.stdout.strip()
        if not commit:
            return {
                **row,
                "status": "not_created_by_cutoff",
                "reason": "default branch has no commit at or before cutoff",
                "branch_ref": branch_ref,
            }
        resolution = "default_branch_first_parent_at_or_before_cutoff"

    try:
        committed_at = _git(git_dir, "show", "-s", "--format=%cI", commit).strip()
    except BuildError as exc:
        return {
            **row,
            "status": "not_assessed",
            "reason": f"cutoff commit metadata unavailable: {exc}",
        }
    available = {
        **row,
        "status": "available",
        "materialize": True,
        "git_dir": str(git_dir.resolve()),
        "commit": commit,
        "committed_at": _rfc3339(committed_at),
        "cutoff_resolution": resolution,
    }
    if branch_ref is not None:
        available["branch_ref"] = branch_ref
    return available


def materialize(
    source_event: dict[str, Any],
    mirror_root: Path,
    output_dir: Path,
    *,
    scan_workers: int = 1,
) -> dict[str, Any]:
    """Build all public artifacts for one requirements source opening."""

    event = _validate_source_event(source_event)
    if GENERATOR_VERSION != REQUIRED_GENERATOR_VERSION:
        raise BuildError(
            "public materializer requires build_openstack_requirements_pack.py "
            f"{REQUIRED_GENERATOR_VERSION}, found {GENERATOR_VERSION}"
        )
    if not isinstance(scan_workers, int) or not 1 <= scan_workers <= 32:
        raise BuildError("scan_workers must be an integer between 1 and 32")
    mirror_root = mirror_root.resolve()
    source_git_dir = _mirror_git_dir(mirror_root, SOURCE_REPOSITORY)
    opening = event["opening"]
    patch = _opening_patch(
        source_git_dir,
        opening["base_commit"],
        opening["head_commit"],
        opening["changed_paths"],
    )
    members = _project_members(
        {
            "git_dir": str(source_git_dir),
            "commit": opening["base_commit"],
            "projects_path": "projects.txt",
        }
    )
    cutoff = opening["created_at"]
    authoring_case_ids = _authoring_case_ids(event["source_change_id"])
    rows = [
        _snapshot_row(
            repository,
            mirror_root,
            cutoff,
            source_base_commit=(
                opening["base_commit"]
                if repository == SOURCE_REPOSITORY
                else None
            ),
        )
        for repository in sorted(members)
    ]

    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    public_source = {
        "schema_version": "1.0",
        "source_change_id": event["source_change_id"],
        "candidate_id": event["candidate_id"],
        "source_change_family": event.get("source_change_family"),
        "discovery": event.get("discovery"),
        "observation_cutoff": cutoff,
        "opening": opening,
        "input_policy": {
            "labels_read": False,
            "targets_read": False,
            "outcomes_read": False,
            "membership_source": "projects.txt at source-opening base commit",
        },
    }
    _write_json(output_dir / "public-source.json", public_source)
    (output_dir / "source.patch").write_text(patch, encoding="utf-8")
    snapshot_manifest = {
        "observation_cutoff": cutoff,
        "repositories": rows,
    }
    snapshot_path = output_dir / "snapshot-manifest.json"
    _write_json(snapshot_path, snapshot_manifest)

    revision_id = f"{PACK_FAMILY_ID}@{event['candidate_id']}-opening"
    build_spec = {
        "pack_family_id": PACK_FAMILY_ID,
        "pack_revision_id": revision_id,
        "project": "openstack",
        "authoring_case_ids": authoring_case_ids,
        "source": {
            "repository": SOURCE_REPOSITORY,
            "git_dir": str(source_git_dir.resolve()),
            "commit": opening["base_commit"],
            "projects_path": "projects.txt",
            "constraints_paths": event["requirements_paths"],
        },
        "snapshot_manifest": {
            "manifest_id": f"{event['candidate_id']}-opening-cutoff-snapshots",
            "path": str(snapshot_path),
            "format": "project-snapshots-json",
        },
        "scan_workers": scan_workers,
    }
    _write_json(output_dir / "build-spec.json", build_spec)

    # Call the fixed generator version; do not duplicate its route/check logic.
    pack = build_pack(build_spec)
    if pack.get("generator") != {
        "id": GENERATOR_ID,
        "version": REQUIRED_GENERATOR_VERSION,
    }:
        raise BuildError("Domain Pack was not produced by the required generator")
    snapshot_incomplete = not pack["coverage"]["materialization_complete"]
    expected_development_only = bool(authoring_case_ids) or snapshot_incomplete
    if (
        pack["construction_policy"]["development_only"]
        != expected_development_only
    ):
        raise BuildError(
            "development_only must reflect authoring influence or snapshot "
            "incompleteness"
        )
    _write_json(output_dir / "domain-pack.json", pack)

    return {
        "candidate_id": event["candidate_id"],
        "generator_version": REQUIRED_GENERATOR_VERSION,
        "projects_txt_candidates": len(members),
        "materialized_candidates": pack["coverage"]["materialized_candidates"],
        "materialization_complete": not snapshot_incomplete,
        "authoring_case_ids": authoring_case_ids,
        "development_only": pack["construction_policy"]["development_only"],
        "output": str(output_dir),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-event", type=Path, required=True)
    parser.add_argument("--mirror-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--scan-workers", type=int, default=1)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        source_event = json.loads(args.source_event.read_text(encoding="utf-8"))
        summary = materialize(
            source_event,
            args.mirror_root,
            args.output_dir,
            scan_workers=args.scan_workers,
        )
    except (BuildError, json.JSONDecodeError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

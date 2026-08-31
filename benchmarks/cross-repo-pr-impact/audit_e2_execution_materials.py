#!/usr/bin/env python3
"""Audit whether each released E2 label can be replayed, not merely inspected.

Historical command logs are evidence, but they are not counted as runnable
materials.  Readiness requires the adapter, replay plan, target patch, runtime,
Git mirrors, and referenced commits needed to create fresh A0/A1/A2 arms.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any


BENCHMARK_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = BENCHMARK_ROOT.parents[1]
ADAPTERS = {
    "requirements_constraint": "run_formal_e2_constraint_touched_relation.py",
    "source_editable": "run_formal_e2_python_touched_relation.py",
    "maven_source": "run_formal_e2_maven_source_relation.py",
    "cross_repo_command": "run_formal_e2_cross_repo_command_relation.py",
    "ant_source_maven_target": "run_formal_e2_ant_source_maven_target_relation.py",
    "requirements_registration": "run_formal_e2_requirements_registration_relation.py",
}
COMMON_PATH_FIELDS = ("replay_plan", "mirror_root", "python")
ADAPTER_PATH_FIELDS = {
    "requirements_constraint": ("tox",),
    "source_editable": ("tox",),
    "maven_source": ("tox", "maven", "java_home", "maven_seed_repository"),
    "cross_repo_command": (),
    "ant_source_maven_target": (
        "tox", "maven", "source_java_home", "target_java_home", "ant", "junit",
        "maven_seed_repository",
    ),
    "requirements_registration": ("tox",),
}
SYSTEM_PREFIXES = (Path("/usr"), Path("/bin"), Path("/lib"), Path("/lib64"))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def resolve(reference: str) -> Path:
    path = Path(reference)
    return path if path.is_absolute() else PROJECT_ROOT / path


def allowed_location(path: Path) -> bool:
    resolved = path.resolve(strict=False)
    project = PROJECT_ROOT.resolve()
    return resolved == project or project in resolved.parents or any(
        resolved == prefix or prefix in resolved.parents for prefix in SYSTEM_PREFIXES
    )


def mirror_path(root: Path, repository: str) -> Path:
    return root / f"{repository.replace('/', '__')}.git"


def git_has_commit(mirror: Path, commit: str) -> bool:
    if not mirror.is_dir() or not commit:
        return False
    completed = subprocess.run(
        ["git", "--git-dir", str(mirror), "cat-file", "-e", f"{commit}^{{commit}}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return completed.returncode == 0


def select_plan(rows: list[dict[str, Any]], relation_id: str) -> dict[str, Any] | None:
    matches = [
        row for row in rows
        if row.get("relation_id", row.get("case_id")) == relation_id
    ]
    if not matches:
        return None
    return matches[0]


def audit_case(case_dir: Path) -> dict[str, Any]:
    label = read_json(case_dir / "private" / "label.json")
    relation_id = label["relation_id"]
    adapter = label.get("replay_adapter")
    blockers: list[str] = []
    assets = []
    runner_name = ADAPTERS.get(adapter)
    runner = BENCHMARK_ROOT / runner_name if runner_name else None
    if runner is None or not runner.is_file():
        blockers.append(f"adapter_unavailable:{adapter}")
    else:
        assets.append({"kind": "adapter", "path": runner.relative_to(PROJECT_ROOT).as_posix(), "exists": True})

    for field in (*COMMON_PATH_FIELDS, *ADAPTER_PATH_FIELDS.get(adapter, ())):
        reference = label.get(field)
        if not isinstance(reference, str) or not reference:
            blockers.append(f"missing_reference:{field}")
            continue
        path = resolve(reference)
        exists = path.exists()
        location_ok = allowed_location(path)
        assets.append({
            "kind": field,
            "reference": reference,
            "exists": exists,
            "project_or_system_local": location_ok,
        })
        if not exists:
            blockers.append(f"path_missing:{field}")
        elif not location_ok:
            blockers.append(f"path_outside_project_or_system:{field}")

    published_patch = case_dir / "evidence" / relation_id / "target.patch"
    if not published_patch.is_file() or not published_patch.read_bytes().startswith(b"diff --git "):
        blockers.append("published_target_patch_missing")
    assets.append({"kind": "target_patch", "path": published_patch.relative_to(PROJECT_ROOT).as_posix(), "exists": published_patch.is_file()})

    plan = None
    plan_reference = label.get("replay_plan")
    if isinstance(plan_reference, str) and resolve(plan_reference).is_file():
        try:
            plan = select_plan(read_jsonl(resolve(plan_reference)), relation_id)
        except (KeyError, ValueError, json.JSONDecodeError):
            blockers.append("replay_plan_unparseable")
        if plan is None:
            blockers.append("relation_absent_from_replay_plan")

    commit_checks = []
    mirror_reference = label.get("mirror_root")
    if plan is not None and isinstance(mirror_reference, str) and resolve(mirror_reference).is_dir():
        root = resolve(mirror_reference)
        for side in ("source", "target"):
            repository = plan.get(f"{side}_repository")
            commits = [
                plan.get(f"{side}_base_commit"),
                plan.get(f"{side}_head_commit"),
            ]
            if not isinstance(repository, str):
                blockers.append(f"plan_missing:{side}_repository")
                continue
            mirror = mirror_path(root, repository)
            if not mirror.is_dir():
                blockers.append(f"mirror_missing:{side}")
            for commit in commits:
                if not isinstance(commit, str) or not git_has_commit(mirror, commit):
                    blockers.append(f"commit_unavailable:{side}")
                    available = False
                else:
                    available = True
                commit_checks.append({"side": side, "repository": repository, "commit": commit, "available": available})

    standalone_paths = []
    release_root = case_dir.parents[1].resolve()
    for asset in assets:
        reference = asset.get("reference") or asset.get("path")
        if reference:
            path = resolve(reference)
            standalone_paths.append(path == release_root or release_root in path.resolve(strict=False).parents)
    return {
        "schema_version": "1.0",
        "case_id": relation_id,
        "replay_adapter": adapter,
        "project_local_fresh_replay_ready": not blockers,
        "standalone_release_fresh_replay_ready": not blockers and all(standalone_paths),
        "blockers": sorted(set(blockers)),
        "assets": assets,
        "commit_checks": commit_checks,
    }


def audit(release_dir: Path) -> dict[str, Any]:
    case_dirs = sorted(path for path in (release_dir / "cases").iterdir() if (path / "private" / "label.json").is_file())
    records = [audit_case(path) for path in case_dirs]
    adapter_counts = Counter(row["replay_adapter"] for row in records)
    blocker_counts = Counter(blocker.split(":", 1)[0] for row in records for blocker in row["blockers"])
    return {
        "schema_version": "1.0",
        "release_dir": release_dir.relative_to(PROJECT_ROOT).as_posix(),
        "case_count": len(records),
        "adapter_counts": dict(sorted(adapter_counts.items())),
        "project_local_fresh_replay_ready_count": sum(row["project_local_fresh_replay_ready"] for row in records),
        "standalone_release_fresh_replay_ready_count": sum(row["standalone_release_fresh_replay_ready"] for row in records),
        "blocker_category_counts": dict(sorted(blocker_counts.items())),
        "records": records,
        "interpretation": (
            "Existing A0/A1/A2 logs remain valid label evidence. This audit asks the different question of whether a fresh execution can be created from currently distributed materials."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("release_dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.release_dir.resolve())
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in (
        "case_count", "adapter_counts", "project_local_fresh_replay_ready_count",
        "standalone_release_fresh_replay_ready_count", "blocker_category_counts",
    )}, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

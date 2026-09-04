from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from build_openstack_requirements_pack import BuildError  # noqa: E402
from collect_public_requirements_sources import public_source_row  # noqa: E402
from materialize_public_requirements_pack import (  # noqa: E402
    AUTHORING_INFLUENCE,
    REQUIRED_GENERATOR_VERSION,
    materialize,
)
from materialize_case_record import materialize_case  # noqa: E402


def _repository(
    path: Path,
    files: dict[str, str],
    *,
    message: str = "cutoff snapshot",
) -> tuple[Path, str]:
    path.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "master", str(path)], check=True)
    subprocess.run(
        ["git", "-C", str(path), "config", "user.email", "dataset@example.invalid"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(path), "config", "user.name", "Dataset Test"],
        check=True,
    )
    for relative_path, content in files.items():
        destination = path / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(path), "commit", "-q", "-m", message],
        check=True,
    )
    commit = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return path, commit


def _commit_files(path: Path, files: dict[str, str]) -> str:
    for relative_path, content in files.items():
        destination = path / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", *sorted(files)], check=True)
    subprocess.run(
        ["git", "-C", str(path), "commit", "-q", "-m", "opening revision"],
        check=True,
    )
    return subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _mirror(repository: Path, mirror_root: Path, name: str) -> Path:
    destination = mirror_root / f"{name.replace('/', '__')}.git"
    subprocess.run(
        ["git", "clone", "-q", "--mirror", str(repository), str(destination)],
        check=True,
    )
    return destination


def _fixture(
    tmp_path: Path,
    *,
    include_missing_repository: bool,
    changed_paths: tuple[str, ...] = ("upper-constraints.txt",),
    number: int = 123,
) -> tuple[dict, Path]:
    projects = ["openstack/consumer", "openstack/requirements"]
    if include_missing_repository:
        projects.append("openstack/unavailable-consumer")
    requirements, base_commit = _repository(
        tmp_path / "requirements",
        {
            "projects.txt": "".join(f"{repository}\n" for repository in projects),
            "global-requirements.txt": "alembic>=1.8\n",
            "upper-constraints.txt": "alembic===1.15.0\n",
            "README.rst": "Requirements catalog\n",
        },
    )
    revised_contents = {
        "global-requirements.txt": "alembic>=1.9\n",
        "upper-constraints.txt": "alembic===1.16.0\n",
        "README.rst": "Requirements catalog documentation\n",
    }
    head_commit = _commit_files(
        requirements,
        {path: revised_contents[path] for path in changed_paths},
    )
    consumer, _ = _repository(
        tmp_path / "consumer",
        {
            "requirements.txt": "alembic>=1.8\n",
            "consumer/api.py": "import alembic\n",
            "consumer/tests/test_api.py": "from consumer import api\n",
            "tox.ini": "[testenv]\ncommands = pytest {posargs}\n",
        },
    )
    mirror_root = tmp_path / "mirrors"
    mirror_root.mkdir()
    _mirror(requirements, mirror_root, "openstack/requirements")
    _mirror(consumer, mirror_root, "openstack/consumer")
    event = public_source_row(
        {
            "provider": "gerrit",
            "repository": "openstack/requirements",
            "number": number,
            "change_id": "Ipublic",
            "url": f"https://review.opendev.org/c/openstack/requirements/+/{number}",
            "created_at": "2030-01-01T00:00:00Z",
            "branch": "master",
            "subject": "Update alembic constraint",
            "base_commit": base_commit,
            "head_commit": head_commit,
            "changed_paths": list(changed_paths),
        }
    )
    return event, mirror_root


def test_public_materializer_preserves_universe_and_marks_incomplete_snapshots(
    tmp_path: Path,
) -> None:
    event, mirror_root = _fixture(tmp_path, include_missing_repository=True)
    output_dir = tmp_path / "output"

    summary = materialize(event, mirror_root, output_dir, scan_workers=2)

    assert summary["generator_version"] == REQUIRED_GENERATOR_VERSION == "1.4.0"
    assert summary["candidate_id"] == event["source_change_id"]
    for name in (
        "public-source.json",
        "source.patch",
        "snapshot-manifest.json",
        "build-spec.json",
        "domain-pack.json",
    ):
        assert (output_dir / name).is_file()
    assert "-alembic===1.15.0" in (output_dir / "source.patch").read_text()
    assert "+alembic===1.16.0" in (output_dir / "source.patch").read_text()

    snapshots = json.loads((output_dir / "snapshot-manifest.json").read_text())
    assert snapshots["observation_cutoff"] == event["opening"]["created_at"]
    by_repository = {
        row["repository"]: row for row in snapshots["repositories"]
    }
    assert set(by_repository) == {
        "openstack/consumer",
        "openstack/requirements",
        "openstack/unavailable-consumer",
    }
    assert all(
        row["observation_cutoff"] == event["opening"]["created_at"]
        for row in by_repository.values()
    )
    assert by_repository["openstack/consumer"]["status"] == "available"
    assert by_repository["openstack/consumer"]["materialize"] is True
    assert by_repository["openstack/requirements"]["commit"] == event["opening"][
        "base_commit"
    ]
    assert by_repository["openstack/unavailable-consumer"]["status"] == (
        "not_assessed"
    )

    spec = json.loads((output_dir / "build-spec.json").read_text())
    pack = json.loads((output_dir / "domain-pack.json").read_text())
    public_source = json.loads((output_dir / "public-source.json").read_text())
    assert public_source["source_change_id"] == "formal-opendev-123"
    assert public_source["candidate_id"] == "formal-opendev-123"
    assert public_source["discovery"] == event["discovery"]
    assert spec["authoring_case_ids"] == []
    assert pack["generator"]["version"] == "1.4.0"
    assert pack["coverage"]["projects_txt_candidates"] == 3
    assert pack["coverage"]["not_in_snapshot_manifest"] == 0
    assert pack["coverage"]["materialization_complete"] is False
    assert pack["construction_policy"]["development_only"] is True
    assert pack["construction_policy"]["authoring_case_ids"] == []


def test_complete_public_snapshots_are_not_development_only(tmp_path: Path) -> None:
    event, mirror_root = _fixture(tmp_path, include_missing_repository=False)
    output_dir = tmp_path / "output"

    materialize(event, mirror_root, output_dir)

    pack = json.loads((output_dir / "domain-pack.json").read_text())
    assert pack["coverage"]["materialization_complete"] is True
    assert pack["construction_policy"]["development_only"] is False
    assert pack["construction_policy"]["event_independent"] is True
    assert pack["construction_policy"]["authoring_case_ids"] == []


def test_global_requirements_only_derives_source_facts_routes_checks_and_commands(
    tmp_path: Path,
) -> None:
    event, mirror_root = _fixture(
        tmp_path,
        include_missing_repository=False,
        changed_paths=("global-requirements.txt",),
    )
    output_dir = tmp_path / "output"

    materialize(event, mirror_root, output_dir)

    spec = json.loads((output_dir / "build-spec.json").read_text())
    pack = json.loads((output_dir / "domain-pack.json").read_text())
    assert spec["source"]["constraints_paths"] == ["global-requirements.txt"]
    assert pack["provenance"]["source"]["constraints_paths"] == [
        "global-requirements.txt"
    ]
    assert pack["provenance"]["source"]["requirements_path_kinds"] == [
        {"kind": "global-requirements", "path": "global-requirements.txt"}
    ]

    route = next(
        route for route in pack["dependency_routes"] if route["dependency_key"] == "alembic"
    )
    assert route["trigger"]["kind"] == "requirement-entry-change"
    assert route["trigger"]["paths"] == ["global-requirements.txt"]
    assert route["trigger"]["path_kinds"] == [
        {"kind": "global-requirements", "path": "global-requirements.txt"}
    ]
    assert route["trigger"]["source_entries"] == [
        {
            "distribution": "alembic",
            "line": 1,
            "path": "global-requirements.txt",
            "source_kind": "global-requirements",
            "specifier": ">=1.8",
        }
    ]
    assert route["repositories"][0]["repository"] == "openstack/consumer"
    assert route["repositories"][0]["focused_check_ids"] == [
        "python-test.openstack__consumer.consumer.tests.test_api"
    ]
    check = next(
        check
        for check in pack["checks"]
        if check["id"] == route["repositories"][0]["focused_check_ids"][0]
    )
    assert check["execution_bindings"]
    assert any(
        template["command_template"] == "pytest {posargs}"
        for template in pack["execution_templates"]
    )

    case = materialize_case(
        pack,
        {
            "case_id": event["source_change_id"],
            "source_event": {"repository": "openstack/requirements"},
        },
        (output_dir / "source.patch").read_text(),
    )
    assert case["public"]["change_facts"] == [
        {
            "kind": "requirement-updated",
            "dependency_key": "alembic",
            "removed_entries": [
                {
                    "distribution": "alembic",
                    "specifier": ">=1.8",
                    "path": "global-requirements.txt",
                }
            ],
            "added_entries": [
                {
                    "distribution": "alembic",
                    "specifier": ">=1.9",
                    "path": "global-requirements.txt",
                }
            ],
            "derivation": "unified-diff-requirement-lines-v1",
        }
    ]
    assert case["public"]["candidate_selection"]["candidate_repositories"] == [
        "openstack/consumer"
    ]
    assert case["public"]["candidate_selection"]["method"] == (
        "changed-requirement-to-pack-candidates-v1"
    )
    assert case["public"]["candidate_selection"]["candidate_check_ids"] == [
        "python-test.openstack__consumer.consumer.tests.test_api"
    ]


def test_global_and_upper_requirements_paths_are_both_preserved(tmp_path: Path) -> None:
    event, mirror_root = _fixture(
        tmp_path,
        include_missing_repository=False,
        changed_paths=("global-requirements.txt", "upper-constraints.txt"),
    )
    output_dir = tmp_path / "output"

    materialize(event, mirror_root, output_dir)

    spec = json.loads((output_dir / "build-spec.json").read_text())
    pack = json.loads((output_dir / "domain-pack.json").read_text())
    expected_paths = ["global-requirements.txt", "upper-constraints.txt"]
    assert spec["source"]["constraints_paths"] == expected_paths
    assert pack["provenance"]["source"]["constraints_paths"] == expected_paths
    route = next(
        route for route in pack["dependency_routes"] if route["dependency_key"] == "alembic"
    )
    assert route["trigger"]["paths"] == expected_paths
    assert {entry["path"] for entry in route["trigger"]["source_entries"]} == set(
        expected_paths
    )

    case = materialize_case(
        pack,
        {
            "case_id": event["source_change_id"],
            "source_event": {"repository": "openstack/requirements"},
        },
        (output_dir / "source.patch").read_text(),
    )
    fact = case["public"]["change_facts"][0]
    assert {entry["path"] for entry in fact["removed_entries"]} == set(expected_paths)
    assert {entry["path"] for entry in fact["added_entries"]} == set(expected_paths)


def test_opening_without_supported_requirements_path_is_rejected(tmp_path: Path) -> None:
    event, mirror_root = _fixture(
        tmp_path,
        include_missing_repository=False,
        changed_paths=("README.rst",),
    )

    with pytest.raises(
        BuildError,
        match="must change global-requirements.txt or upper-constraints.txt",
    ):
        materialize(event, mirror_root, tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_authoring_source_event_is_automatically_development_only(
    tmp_path: Path,
) -> None:
    registry = json.loads(AUTHORING_INFLUENCE.read_text(encoding="utf-8"))
    assert registry["generator_version"] == "1.4.0"
    assert "formal-opendev-849284" in registry["source_change_ids"]
    event, mirror_root = _fixture(
        tmp_path,
        include_missing_repository=False,
        changed_paths=("global-requirements.txt",),
        number=849284,
    )
    output_dir = tmp_path / "output"

    summary = materialize(event, mirror_root, output_dir)

    spec = json.loads((output_dir / "build-spec.json").read_text())
    pack = json.loads((output_dir / "domain-pack.json").read_text())
    expected_authoring_ids = ["formal-opendev-849284"]
    assert summary["materialization_complete"] is True
    assert summary["authoring_case_ids"] == expected_authoring_ids
    assert summary["development_only"] is True
    assert spec["authoring_case_ids"] == expected_authoring_ids
    assert pack["construction_policy"]["authoring_case_ids"] == expected_authoring_ids
    assert pack["construction_policy"]["development_only"] is True
    assert pack["construction_policy"]["event_independent"] is False


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("target_repository", "openstack/consumer"),
        ("private_label", {"relation": "hidden"}),
        ("outcome", "A1 failed"),
        ("A0", {"exit_code": 0}),
    ],
)
def test_function_rejects_target_private_and_outcome_fields(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    event, mirror_root = _fixture(tmp_path, include_missing_repository=False)
    tainted = copy.deepcopy(event)
    tainted["opening"][field] = value

    with pytest.raises(BuildError, match="forbidden public event field"):
        materialize(tainted, mirror_root, tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_cli_rejects_private_fields_before_writing(tmp_path: Path) -> None:
    event, mirror_root = _fixture(tmp_path, include_missing_repository=False)
    event["private"] = {"target_id": "hidden"}
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event), encoding="utf-8")
    output_dir = tmp_path / "output"

    process = subprocess.run(
        [
            sys.executable,
            str(ROOT / "materialize_public_requirements_pack.py"),
            "--source-event",
            str(event_path),
            "--mirror-root",
            str(mirror_root),
            "--output-dir",
            str(output_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert process.returncode == 2
    assert "forbidden public event field" in process.stderr
    assert not output_dir.exists()


@pytest.mark.parametrize(
    "mutate",
    [
        lambda event: event.update(source_change_id="formal-opendev-124"),
        lambda event: event.update(candidate_id="formal-opendev-124"),
        lambda event: event.pop("source_change_id"),
    ],
)
def test_source_identity_must_match_opening_number(
    tmp_path: Path,
    mutate,
) -> None:
    event, mirror_root = _fixture(tmp_path, include_missing_repository=False)
    mutate(event)

    with pytest.raises(
        BuildError,
        match="must (?:equal|be identical)|missing source event field",
    ):
        materialize(event, mirror_root, tmp_path / "output")

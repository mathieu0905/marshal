from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from build_openstack_requirements_pack import (  # noqa: E402
    GENERATOR_ID,
    GENERATOR_VERSION,
    BuildError,
    build_pack,
)
from materialize_case_record import materialize_case  # noqa: E402
from verify_case_record import verification_errors  # noqa: E402


def _git_repository(path: Path, files: dict[str, str]) -> tuple[Path, str]:
    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True)
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
        ["git", "-C", str(path), "commit", "-q", "-m", "cutoff snapshot"],
        check=True,
    )
    commit = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return path / ".git", commit


@pytest.fixture()
def built_pack(tmp_path: Path) -> dict:
    requirements_git, requirements_commit = _git_repository(
        tmp_path / "requirements",
        {
            "projects.txt": (
                "openstack/cinder\n"
                "openstack/nova\n"
                "openstack/requirements\n"
                "openstack/swift\n"
            ),
            "upper-constraints.txt": (
                "alembic===1.15.0\n"
                "oslo.concurrency===7.2.0\n"
                "unconsumed-package===1.0\n"
            ),
        },
    )
    cinder_git, cinder_commit = _git_repository(
        tmp_path / "cinder",
        {
            "requirements.txt": "alembic>=1.8\n",
            "cinder/db/api.py": "import alembic\n",
            "cinder/tests/unit/fixtures.py": "import alembic\n",
            "cinder/tests/unit/test_migrations.py": "import alembic\n",
            "tox.ini": (
                "[testenv]\ncommands =\n"
                "  stestr run {posargs}\n"
                "  stestr slowest\n"
            ),
            "zuul.d/project.yaml": "- job:\n    name: cinder-unit\n",
        },
    )
    nova_git, nova_commit = _git_repository(
        tmp_path / "nova",
        {
            "test-requirements.txt": "oslo.concurrency>=6\n",
            "nova/tests/unit/test_coordination.py": "import oslo_concurrency\n",
            "tox.ini": "[testenv:unit]\ncommands = pytest {posargs}\n",
        },
    )
    snapshot_manifest = tmp_path / "openstack-snapshots.json"
    snapshot_manifest.write_text(
        json.dumps(
            {
                "observation_cutoff": "2026-08-15T12:56:38Z",
                "repositories": [
                    {
                        "repository": "openstack/cinder",
                        "status": "available",
                        "materialize": True,
                        "git_dir": str(cinder_git),
                        "commit": cinder_commit,
                    },
                    {
                        "repository": "openstack/nova",
                        "status": "available",
                        "materialize": True,
                        "git_dir": str(nova_git),
                        "commit": nova_commit,
                    },
                    {"repository": "openstack/requirements", "status": "unavailable"},
                    {"repository": "openstack/swift", "status": "unavailable"},
                ],
            }
        ),
        encoding="utf-8",
    )
    spec = {
        "pack_family_id": "openstack-requirements-python-consumers",
        "pack_revision_id": "openstack-requirements-python-consumers@2026-08-15",
        "project": "openstack",
        "authoring_case_ids": ["development-seed"],
        "source": {
            "repository": "openstack/requirements",
            "git_dir": str(requirements_git),
            "commit": requirements_commit,
            "projects_path": "projects.txt",
            "constraints_paths": ["upper-constraints.txt"],
        },
        "snapshot_manifest": {
            "manifest_id": "openstack-project-cutoff-2026-08-15",
            "path": str(snapshot_manifest),
            "format": "project-snapshots-json",
        },
    }
    return build_pack(spec)


def _case_spec(case_id: str) -> dict:
    return {
        "case_id": case_id,
        "source_event": {
            "repository": "openstack/requirements",
            "base_commit": "base",
            "candidate_commit": "candidate",
        },
    }


def _alembic_patch() -> str:
    return """\
diff --git a/upper-constraints.txt b/upper-constraints.txt
--- a/upper-constraints.txt
+++ b/upper-constraints.txt
@@ -1 +1 @@
-alembic===1.15.0
+alembic===1.16.0
"""


def test_project_pack_uses_projects_txt_and_ci_only_as_command_provenance(
    built_pack: dict,
) -> None:
    pack = built_pack
    assert pack["pack_family_id"] == "openstack-requirements-python-consumers"
    assert pack["generator"] == {"id": GENERATOR_ID, "version": GENERATOR_VERSION}
    assert pack["coverage"]["projects_txt_candidates"] == 4
    assert pack["coverage"]["materialized_candidates"] == 2
    assert pack["coverage"]["materialization_complete"] is True
    assert pack["construction_policy"]["development_only"] is True
    assert pack["construction_policy"]["authoring_case_ids"] == ["development-seed"]

    routes = {route["dependency_key"]: route for route in pack["dependency_routes"]}
    assert set(routes) == {"alembic", "oslo_concurrency"}
    assert [row["repository"] for row in routes["alembic"]["repositories"]] == [
        "openstack/cinder"
    ]
    assert all(
        repository_route["repository"] != "openstack/requirements"
        for route in routes.values()
        for repository_route in route["repositories"]
    )
    assert routes["alembic"]["repositories"][0]["focused_check_ids"] == [
        "python-test.openstack__cinder.cinder.tests.unit.test_migrations"
    ]
    assert all(
        "repository_check_ids" not in row
        for route in routes.values()
        for row in route["repositories"]
    )
    assert not any(
        check["definition"]["path"].endswith("fixtures.py")
        for check in pack["checks"]
    )
    assert any(
        template["command_template"] == "stestr slowest"
        for template in pack["execution_templates"]
    )

    serialized = json.dumps(pack)
    for marshal_field in ("default_tier", "matched_tier", "verdict", "executor_kind"):
        assert f'"{marshal_field}"' not in serialized


def test_case_candidates_are_complete_but_non_targets_remain_unjudged(
    built_pack: dict,
) -> None:
    case = materialize_case(built_pack, _case_spec("alembic-update"), _alembic_patch())
    selection = case["public"]["candidate_selection"]
    assert selection["candidate_repositories"] == ["openstack/cinder"]
    assert selection["candidate_check_ids"] == [
        "python-test.openstack__cinder.cinder.tests.unit.test_migrations"
    ]
    assert case["curator"] == {
        "candidate_label_policy": "unjudged_unless_in_judged_e2_bindings",
        "judged_e2_bindings": [],
    }
    assert not verification_errors(built_pack, case)

    narrowed = copy.deepcopy(case)
    narrowed["public"]["candidate_selection"]["candidate_check_ids"].clear()
    assert (
        "public.candidate_selection.candidate_check_ids is not the complete derived set"
        in verification_errors(built_pack, narrowed)
    )


def test_relation_level_e2_binding_does_not_label_other_candidates(
    built_pack: dict,
    tmp_path: Path,
) -> None:
    case = materialize_case(built_pack, _case_spec("alembic-update"), _alembic_patch())
    route_id = case["public"]["candidate_selection"]["candidate_route_ids"][0]
    check_id = case["public"]["candidate_selection"]["candidate_check_ids"][0]
    check = next(row for row in built_pack["checks"] if row["id"] == check_id)
    execution_binding = check["execution_bindings"][0]
    command_template = next(
        row
        for row in built_pack["execution_templates"]
        if row["id"] == execution_binding["template_id"]
    )
    command = {
        "base_template_id": command_template["id"],
        "template": command_template["command_template"].replace(
            "{posargs}", check["selector"]
        ),
        "provenance": {
            "repository": check["location_repo"],
            "commit": command_template["provenance"]["commit"],
            "test_path": check["definition"]["path"],
            "ci_definition": command_template["definition"],
        },
    }
    case["curator"]["judged_e2_bindings"].append(
        {
            "binding_id": "e2-cinder-alembic",
            "relation_id": "openstack/requirements->openstack/cinder:alembic",
            "route_id": route_id,
            "check_id": check_id,
            "location_repo": "openstack/cinder",
            "selector": check["selector"],
            "command": command,
            "arms": {
                "A0": {
                    "status": "pass",
                    "exit_code": 0,
                    "artifact_refs": ["a0.json", "a0.log"],
                    "summary_ref": "a0.json",
                    "command_log_ref": "a0.log",
                },
                "A1": {
                    "status": "fail",
                    "exit_code": 1,
                    "artifact_refs": ["a1.json", "a1.log"],
                    "summary_ref": "a1.json",
                    "command_log_ref": "a1.log",
                },
                "A2": {
                    "status": "pass",
                    "exit_code": 0,
                    "artifact_refs": ["a2.json", "a2.log"],
                    "summary_ref": "a2.json",
                    "command_log_ref": "a2.log",
                },
            },
            "failure_signature": {
                "value": "example failure",
                "exclusive_to": "A1",
                "artifact_refs": ["a0.log", "a1.log", "a2.log"],
            },
            "target_repair": {
                "repository": "openstack/cinder",
                "change_id": "123",
                "patch_ref": "target.patch",
            },
            "mechanism": "The dependency change breaks the pre-existing target check.",
        }
    )
    assert not verification_errors(built_pack, case)

    case["public"]["source_event"]["patch_ref"] = "source.patch"
    (tmp_path / "source.patch").write_text(_alembic_patch(), encoding="utf-8")
    (tmp_path / "target.patch").write_text("target repair\n", encoding="utf-8")
    for arm_id, exit_code in (("A0", 0), ("A1", 1), ("A2", 0)):
        arm_name = arm_id.lower()
        (tmp_path / f"{arm_name}.json").write_text(
            json.dumps(
                {
                    "arm": arm_id,
                    "command": command["template"].split(),
                    "exit_code": exit_code,
                }
            ),
            encoding="utf-8",
        )
        (tmp_path / f"{arm_name}.log").write_text(
            "example failure\n" if arm_id == "A1" else "passed\n",
            encoding="utf-8",
        )
    assert not verification_errors(built_pack, case, tmp_path)

    missing_semantic_review = copy.deepcopy(case)
    missing_semantic_review["curator"]["judged_e2_bindings"][0][
        "semantic_adjudication_ref"
    ] = "missing-semantic-adjudication.json"
    assert any(
        "cannot read judged binding e2-cinder-alembic semantic adjudication" in error
        for error in verification_errors(
            built_pack, missing_semantic_review, tmp_path
        )
    )

    bad = copy.deepcopy(case)
    bad["curator"]["judged_e2_bindings"][0]["arms"]["A1"]["exit_code"] = 0
    assert "judged binding e2-cinder-alembic A1 must exit nonzero" in (
        verification_errors(built_pack, bad)
    )


def test_optional_runtime_evidence_is_cross_checked(
    built_pack: dict,
    tmp_path: Path,
) -> None:
    case = materialize_case(built_pack, _case_spec("alembic-update"), _alembic_patch())
    route_id = case["public"]["candidate_selection"]["candidate_route_ids"][0]
    check_id = case["public"]["candidate_selection"]["candidate_check_ids"][0]
    check = next(row for row in built_pack["checks"] if row["id"] == check_id)
    template_id = check["execution_bindings"][0]["template_id"]
    template = next(
        row for row in built_pack["execution_templates"] if row["id"] == template_id
    )
    command_text = template["command_template"].replace(
        "{posargs}", check["selector"]
    )
    command = command_text.split()
    binding = {
        "binding_id": "e2-runtime-evidence",
        "relation_id": "requirements->cinder:alembic",
        "route_id": route_id,
        "check_id": check_id,
        "location_repo": check["location_repo"],
        "selector": check["selector"],
        "command": {
            "base_template_id": template_id,
            "template": command_text,
            "provenance": {"repository": check["location_repo"]},
        },
        "failure_signature": {
            "value": "example failure",
            "exclusive_to": "A1",
            "artifact_refs": ["a1.log"],
        },
        "target_repair": {
            "repository": check["location_repo"],
            "change_id": "repair",
            "patch_ref": "target.patch",
        },
        "mechanism": "exact constraint change breaks a pre-existing check",
        "arms": {},
    }
    expected_versions = {"A0": "1.15.0", "A1": "1.16.0", "A2": "1.16.0"}
    for arm_id, exit_code in (("A0", 0), ("A1", 1), ("A2", 0)):
        lower = arm_id.lower()
        summary_ref = f"{lower}.json"
        log_ref = f"{lower}.log"
        actual_ref = f"{lower}-actual.json"
        binding["arms"][arm_id] = {
            "status": "pass" if exit_code == 0 else "fail",
            "exit_code": exit_code,
            "check_count": 7,
            "installed_source_version": expected_versions[arm_id],
            "summary_ref": summary_ref,
            "command_log_ref": log_ref,
            "actual_command_ref": actual_ref,
            "artifact_refs": [summary_ref, log_ref, actual_ref],
        }
        (tmp_path / summary_ref).write_text(
            json.dumps(
                {
                    "arm": arm_id,
                    "command": command,
                    "exit_code": exit_code,
                    "check_count": 7,
                    "installed_source_version": expected_versions[arm_id],
                }
            ),
            encoding="utf-8",
        )
        (tmp_path / log_ref).write_text(
            ("example failure\n" if arm_id == "A1" else "")
            + "Ran: 7 tests in 0.1 sec.\n",
            encoding="utf-8",
        )
        (tmp_path / actual_ref).write_text(
            json.dumps({"recorded_command": command}), encoding="utf-8"
        )
    (tmp_path / "target.patch").write_text("repair\n", encoding="utf-8")
    (tmp_path / "source.patch").write_text(_alembic_patch(), encoding="utf-8")
    case["public"]["source_event"]["patch_ref"] = "source.patch"
    case["curator"]["judged_e2_bindings"] = [binding]
    assert not verification_errors(built_pack, case, tmp_path)

    bad_count = copy.deepcopy(case)
    bad_count["curator"]["judged_e2_bindings"][0]["arms"]["A2"][
        "check_count"
    ] = 6
    assert any(
        "A2 command log check_count mismatch" in error
        for error in verification_errors(built_pack, bad_count, tmp_path)
    )

    bad_version = copy.deepcopy(case)
    bad_version["curator"]["judged_e2_bindings"][0]["arms"]["A1"][
        "installed_source_version"
    ] = "9.9.9"
    assert any(
        "A1 installed source version differs from source patch" in error
        for error in verification_errors(built_pack, bad_version, tmp_path)
    )


def test_emitted_records_match_schemas(built_pack: dict) -> None:
    jsonschema = pytest.importorskip("jsonschema")
    pack_schema = json.loads((ROOT / "domain-pack.schema.json").read_text())
    case_schema = json.loads((ROOT / "case-record.schema.json").read_text())
    jsonschema.validate(built_pack, pack_schema)
    case = materialize_case(built_pack, _case_spec("schema"), "")
    jsonschema.validate(case, case_schema)


def test_legacy_1_3_3_pack_shape_remains_schema_and_case_verifiable(
    built_pack: dict,
) -> None:
    jsonschema = pytest.importorskip("jsonschema")
    legacy_pack = copy.deepcopy(built_pack)
    legacy_pack["generator"]["version"] = "1.3.3"
    legacy_pack["provenance"]["source"].pop("requirements_path_kinds", None)
    for route in legacy_pack["dependency_routes"]:
        route["trigger"]["kind"] = "constraint-entry-change"
        route["trigger"].pop("path_kinds", None)
        for entry in route["trigger"]["source_entries"]:
            entry.pop("source_kind", None)

    schema = json.loads((ROOT / "domain-pack.schema.json").read_text())
    jsonschema.validate(legacy_pack, schema)
    case = materialize_case(
        legacy_pack,
        _case_spec("legacy-alembic-update"),
        _alembic_patch(),
    )
    assert not verification_errors(legacy_pack, case)


def test_projects_txt_rejects_duplicates(tmp_path: Path) -> None:
    requirements_git, requirements_commit = _git_repository(
        tmp_path / "requirements",
        {
            "projects.txt": "openstack/cinder\nopenstack/cinder\n",
            "upper-constraints.txt": "alembic===1.15.0\n",
        },
    )
    snapshot_manifest = tmp_path / "snapshots.json"
    snapshot_manifest.write_text(
        json.dumps(
            {"observation_cutoff": "2026-08-15T12:56:38Z", "repositories": []}
        ),
        encoding="utf-8",
    )
    spec = {
        "pack_family_id": "family",
        "pack_revision_id": "revision",
        "project": "openstack",
        "source": {
            "repository": "openstack/requirements",
            "git_dir": str(requirements_git),
            "commit": requirements_commit,
            "projects_path": "projects.txt",
            "constraints_paths": ["upper-constraints.txt"],
        },
        "snapshot_manifest": {
            "path": str(snapshot_manifest),
            "format": "project-snapshots-json",
        },
    }
    with pytest.raises(BuildError, match="duplicate projects.txt repository"):
        build_pack(spec)


def test_alias_string_and_transitive_consumers_are_derived_from_cutoff_code(
    tmp_path: Path,
) -> None:
    requirements_git, requirements_commit = _git_repository(
        tmp_path / "requirements",
        {
            "projects.txt": (
                "openstack/consumer\n"
                "openstack/python-widget\n"
                "openstack/requirements\n"
            ),
            "upper-constraints.txt": "python-widget===2.0\n",
        },
    )
    provider_git, provider_commit = _git_repository(
        tmp_path / "python-widget",
        {
            "setup.cfg": "[metadata]\nname = python-widget\n",
            "widget/__init__.py": "",
            "widget/client.py": "def call():\n    return True\n",
        },
    )
    consumer_git, consumer_commit = _git_repository(
        tmp_path / "consumer",
        {
            "requirements.txt": "python-widget>=1\n",
            "consumer/__init__.py": "",
            "consumer/api.py": "import widget\n",
            "consumer/tests/__init__.py": "",
            "consumer/tests/test_api.py": "from consumer import api\n",
            "consumer/tests/test_mock.py": "TARGET = 'widget.client.call'\n",
            "tox.ini": "[testenv]\ncommands = pytest {posargs}\n",
        },
    )
    snapshot_manifest = tmp_path / "snapshots.json"
    snapshot_manifest.write_text(
        json.dumps(
            {
                "observation_cutoff": "2025-01-01T00:00:00Z",
                "repositories": [
                    {
                        "repository": "openstack/consumer",
                        "status": "available",
                        "materialize": True,
                        "git_dir": str(consumer_git),
                        "commit": consumer_commit,
                    },
                    {
                        "repository": "openstack/python-widget",
                        "status": "available",
                        "materialize": True,
                        "git_dir": str(provider_git),
                        "commit": provider_commit,
                    },
                    {"repository": "openstack/requirements", "status": "unavailable"},
                ],
            }
        ),
        encoding="utf-8",
    )
    pack = build_pack(
        {
            "pack_family_id": "alias-test",
            "pack_revision_id": "alias-test@cutoff",
            "project": "openstack",
            "authoring_case_ids": ["development-alias-test"],
            "source": {
                "repository": "openstack/requirements",
                "git_dir": str(requirements_git),
                "commit": requirements_commit,
                "projects_path": "projects.txt",
                "constraints_paths": ["upper-constraints.txt"],
            },
            "snapshot_manifest": {
                "path": str(snapshot_manifest),
                "format": "project-snapshots-json",
            },
        }
    )

    alias = next(
        row
        for row in pack["dependency_aliases"]
        if row["dependency_key"] == "python_widget" and row["import_root"] == "widget"
    )
    assert alias == {
        "dependency_key": "python_widget",
        "import_root": "widget",
        "provider_repositories": ["openstack/python-widget"],
        "status": "available",
    }
    route = next(
        row for row in pack["dependency_routes"] if row["dependency_key"] == "python_widget"
    )
    assert route["trigger"]["import_roots"] == ["python_widget", "widget"]
    consumer = next(
        row for row in route["repositories"] if row["repository"] == "openstack/consumer"
    )
    assert all(
        row["repository"] != "openstack/python-widget"
        for row in route["repositories"]
    )
    assert consumer["focused_check_ids"] == [
        "python-test.openstack__consumer.consumer.tests.test_api",
        "python-test.openstack__consumer.consumer.tests.test_mock",
    ]
    assert consumer["consumption_evidence"]["focused_check_derivation_counts"] == {
        "python_string_reference": 1,
        "transitive_python_import": 1,
    }

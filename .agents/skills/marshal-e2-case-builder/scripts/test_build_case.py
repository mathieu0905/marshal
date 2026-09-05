import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).with_name("build_case.py")
SPEC = importlib.util.spec_from_file_location("marshal_e2_build_case", MODULE_PATH)
assert SPEC and SPEC.loader
build_case = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build_case)

BENCHMARK = MODULE_PATH.parents[4] / "benchmarks" / "cross-repo-pr-impact"
sys.path.insert(0, str(BENCHMARK))
CONSTRAINT_MODULE_PATH = BENCHMARK / "run_formal_e2_constraint_touched_relation.py"
CONSTRAINT_SPEC = importlib.util.spec_from_file_location(
    "marshal_e2_constraint_replay", CONSTRAINT_MODULE_PATH
)
assert CONSTRAINT_SPEC and CONSTRAINT_SPEC.loader
constraint_replay = importlib.util.module_from_spec(CONSTRAINT_SPEC)
CONSTRAINT_SPEC.loader.exec_module(constraint_replay)
MAVEN_MODULE_PATH = BENCHMARK / "run_formal_e2_maven_source_relation.py"
MAVEN_SPEC = importlib.util.spec_from_file_location(
    "marshal_e2_maven_replay", MAVEN_MODULE_PATH
)
assert MAVEN_SPEC and MAVEN_SPEC.loader
maven_replay = importlib.util.module_from_spec(MAVEN_SPEC)
MAVEN_SPEC.loader.exec_module(maven_replay)
ANT_MAVEN_MODULE_PATH = BENCHMARK / "run_formal_e2_ant_source_maven_target_relation.py"
ANT_MAVEN_SPEC = importlib.util.spec_from_file_location(
    "marshal_e2_ant_maven_replay", ANT_MAVEN_MODULE_PATH
)
assert ANT_MAVEN_SPEC and ANT_MAVEN_SPEC.loader
ant_maven_replay = importlib.util.module_from_spec(ANT_MAVEN_SPEC)
ANT_MAVEN_SPEC.loader.exec_module(ant_maven_replay)
CROSS_REPO_MODULE_PATH = BENCHMARK / "run_formal_e2_cross_repo_command_relation.py"
CROSS_REPO_SPEC = importlib.util.spec_from_file_location(
    "marshal_e2_cross_repo_replay", CROSS_REPO_MODULE_PATH
)
assert CROSS_REPO_SPEC and CROSS_REPO_SPEC.loader
cross_repo_replay = importlib.util.module_from_spec(CROSS_REPO_SPEC)
CROSS_REPO_SPEC.loader.exec_module(cross_repo_replay)
RELEASE_MODULE_PATH = MODULE_PATH.with_name("release_formal_pool.py")
RELEASE_SPEC = importlib.util.spec_from_file_location(
    "marshal_e2_release_formal_pool", RELEASE_MODULE_PATH
)
assert RELEASE_SPEC and RELEASE_SPEC.loader
release_formal_pool = importlib.util.module_from_spec(RELEASE_SPEC)
RELEASE_SPEC.loader.exec_module(release_formal_pool)
CATALOG_MODULE_PATH = MODULE_PATH.with_name("build_component_catalog.py")
CATALOG_SPEC = importlib.util.spec_from_file_location(
    "marshal_e2_component_catalog", CATALOG_MODULE_PATH
)
assert CATALOG_SPEC and CATALOG_SPEC.loader
component_catalog = importlib.util.module_from_spec(CATALOG_SPEC)
CATALOG_SPEC.loader.exec_module(component_catalog)


class DefaultBranchSnapshotTests(unittest.TestCase):
    def test_replay_environment_roots_are_absolute_and_case_local(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "case-output"
            environment = build_case.replay_process_environment(output)
            for variable in ("TMPDIR", "HOME", "XDG_CACHE_HOME"):
                value = Path(environment[variable])
                self.assertTrue(value.is_absolute())
                self.assertTrue(value.is_relative_to((output / "process-runtime").resolve()))

    def test_resolve_executable_preserves_virtualenv_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "base-python"
            base.touch()
            executable = root / "venv" / "bin" / "python"
            executable.parent.mkdir(parents=True)
            executable.symlink_to(base)

            selected = build_case.resolve_executable(root, "venv/bin/python")

        self.assertEqual(executable.absolute(), selected)

    def test_ignores_newer_commit_that_is_not_on_master(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            mirrors = root / "mirrors"
            mirror = mirrors / "org__repo.git"
            subprocess.run(["git", "init", "-q", "-b", "master", str(source)], check=True)
            subprocess.run(["git", "-C", str(source), "config", "user.name", "test"], check=True)
            subprocess.run(["git", "-C", str(source), "config", "user.email", "test@example.test"], check=True)
            environment = os.environ.copy()
            environment.update({
                "GIT_AUTHOR_DATE": "2024-01-01T00:00:00Z",
                "GIT_COMMITTER_DATE": "2024-01-01T00:00:00Z",
            })
            (source / "value.txt").write_text("master\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(source), "add", "value.txt"], check=True)
            subprocess.run(["git", "-C", str(source), "commit", "-qm", "master"], env=environment, check=True)
            master = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
            subprocess.run(["git", "-C", str(source), "checkout", "-qb", "review"], check=True)
            environment.update({
                "GIT_AUTHOR_DATE": "2024-01-02T00:00:00Z",
                "GIT_COMMITTER_DATE": "2024-01-02T00:00:00Z",
            })
            (source / "value.txt").write_text("review\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(source), "commit", "-qam", "review"], env=environment, check=True)
            mirrors.mkdir()
            subprocess.run(["git", "clone", "-q", "--mirror", str(source), str(mirror)], check=True)
            subprocess.run(["git", "--git-dir", str(mirror), "branch", "-f", "master", master], check=True)

            snapshot = build_case.resolve_default_branch_snapshot(
                mirrors, "org/repo", "2024-01-03T00:00:00Z"
            )

        self.assertEqual(master, snapshot["commit"])
        self.assertEqual("available", snapshot["status"])


class FormalPoolReleaseTests(unittest.TestCase):
    def test_catalog_merge_ignores_only_rebuild_timestamp(self) -> None:
        left = {
            "catalog_id": "shared",
            "repositories": ["org/a", "org/b"],
            "constructed_at": "2026-08-26T04:03:14Z",
        }
        right = {
            "catalog_id": "shared",
            "repositories": ["org/a", "org/b"],
            "constructed_at": "2026-08-29T16:30:07Z",
        }

        merged = release_formal_pool.merge_catalog_definitions(left, right)

        self.assertEqual(left, merged)

    def test_catalog_merge_rejects_membership_difference(self) -> None:
        with self.assertRaisesRegex(ValueError, "beyond constructed_at"):
            release_formal_pool.merge_catalog_definitions(
                {
                    "catalog_id": "shared",
                    "repositories": ["org/a"],
                    "constructed_at": "2026-08-26T04:03:14Z",
                },
                {
                    "catalog_id": "shared",
                    "repositories": ["org/a", "org/b"],
                    "constructed_at": "2026-08-29T16:30:07Z",
                },
            )

    def test_grouped_split_is_exact_and_keeps_all_four_axes_isolated(self) -> None:
        reports = []
        for number in range(50):
            family = "shared-three" if number < 3 else f"family-{number}"
            reports.append({
                "case_id": f"case-{number:02d}",
                "directed_relation": [f"source-{number}", f"target-{number}"],
                "source_change_family": family,
                "mechanism": f"mechanism-{number}",
                "repair_template": f"repair-{number}",
            })

        assignments, groups = release_formal_pool.assign_grouped_splits(reports)

        self.assertEqual({"development": 30, "evaluation": 10, "holdout": 10}, dict(Counter(assignments.values())))
        self.assertEqual(1, len({assignments[f"case-{number:02d}"] for number in range(3)}))
        self.assertEqual(48, len(groups))

    def test_excludes_review_commit_merged_after_cutoff(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            mirrors = root / "mirrors"
            mirror = mirrors / "org__repo.git"
            subprocess.run(["git", "init", "-q", "-b", "master", str(source)], check=True)
            subprocess.run(["git", "-C", str(source), "config", "user.name", "test"], check=True)
            subprocess.run(["git", "-C", str(source), "config", "user.email", "test@example.test"], check=True)
            environment = os.environ.copy()
            environment.update({
                "GIT_AUTHOR_DATE": "2024-01-01T00:00:00Z",
                "GIT_COMMITTER_DATE": "2024-01-01T00:00:00Z",
            })
            (source / "value.txt").write_text("master\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(source), "add", "value.txt"], check=True)
            subprocess.run(["git", "-C", str(source), "commit", "-qm", "master"], env=environment, check=True)
            master = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
            subprocess.run(["git", "-C", str(source), "checkout", "-qb", "review"], check=True)
            environment.update({
                "GIT_AUTHOR_DATE": "2024-01-02T00:00:00Z",
                "GIT_COMMITTER_DATE": "2024-01-02T00:00:00Z",
            })
            (source / "review.txt").write_text("review\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(source), "add", "review.txt"], check=True)
            subprocess.run(["git", "-C", str(source), "commit", "-qm", "review"], env=environment, check=True)
            subprocess.run(["git", "-C", str(source), "checkout", "-q", "master"], check=True)
            environment.update({
                "GIT_AUTHOR_DATE": "2024-01-04T00:00:00Z",
                "GIT_COMMITTER_DATE": "2024-01-04T00:00:00Z",
            })
            subprocess.run(
                ["git", "-C", str(source), "merge", "--no-ff", "-qm", "merge later", "review"],
                env=environment, check=True,
            )
            mirrors.mkdir()
            subprocess.run(["git", "clone", "-q", "--mirror", str(source), str(mirror)], check=True)

            snapshot = build_case.resolve_default_branch_snapshot(
                mirrors, "org/repo", "2024-01-03T00:00:00Z"
            )

        self.assertEqual(master, snapshot["commit"])


class BlindVerificationTests(unittest.TestCase):
    def test_packaged_manifest_does_not_expose_host_intake_paths(self) -> None:
        source = {
            "schema_version": "1.0",
            "candidate_id": "public-case",
            "inputs": "old/formal-source--target-123/inputs.jsonl",
            "snapshots": "old/formal-source--target-123/snapshots.jsonl",
            "catalogs": "old/formal-source--target-123/catalogs.json",
            "patch_dir": "old/formal-source--target-123/source-patches",
            "mirror_root": "benchmarks/shared-candidate-mirrors",
            "blind": {"top_k": 5, "workers": 8},
        }

        packaged = build_case.packaged_public_manifest(source)

        self.assertEqual("inputs.jsonl", packaged["inputs"])
        self.assertEqual("repository-snapshots.jsonl", packaged["snapshots"])
        self.assertEqual("candidate-repositories.json", packaged["catalogs"])
        self.assertEqual("source-patches", packaged["patch_dir"])
        self.assertNotIn("target-123", str(packaged))
        self.assertEqual(source["mirror_root"], packaged["mirror_root"])

    def test_detects_relation_label_in_blind_visible_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "public").mkdir()
            build_case.write_json(output / "public" / "manifest.json", {
                "inputs": "old/formal-source--target-123/inputs.jsonl",
            })

            leaked = build_case.public_manifest_leaks_relation(output, {
                "relation_id": "formal-source--target-123",
            })

        self.assertTrue(leaked)

    def test_accepts_target_neutral_public_manifest_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "public").mkdir()
            build_case.write_json(output / "public" / "manifest.json", {
                "inputs": "public-formal-source/inputs.jsonl",
            })

            leaked = build_case.public_manifest_leaks_relation(output, {
                "relation_id": "formal-source--target-123",
            })

        self.assertFalse(leaked)

    def test_accepts_a_real_empty_cutoff_snapshot_when_universe_has_text_reads(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            public = output / "public"
            blind = output / "blind"
            public.mkdir()
            blind.mkdir()
            build_case.write_jsonl(public / "inputs.jsonl", [{
                "case_id": "case-1",
                "source": {"repository": "org/source"},
            }])
            build_case.write_jsonl(public / "repository-snapshots.jsonl", [{
                "case_id": "case-1",
                "repositories": [
                    {"repository": "org/empty", "status": "available"},
                    {"repository": "org/text", "status": "available"},
                ],
            }])
            build_case.write_jsonl(blind / "predictions.jsonl", [{
                "case_id": "case-1",
                "targets": [{"repository": "org/text"}],
            }])
            build_case.write_jsonl(blind / "diagnostics.jsonl", [{
                "case_id": "case-1",
                "label_inputs_read": False,
                "candidate_code_read": True,
                "ranking": [
                    {
                        "repository": "org/empty", "tracked_file_count": 0,
                        "files_read": 0, "text_files_read": 0,
                    },
                    {
                        "repository": "org/text", "tracked_file_count": 2,
                        "files_read": 1, "text_files_read": 1,
                    },
                ],
            }])
            build_case.write_json(blind / "run-manifest.json", {
                "labels_read": False, "network_used": False,
                "candidate_code_read": True,
            })
            build_case.write_json(blind / "isolation.json", {
                "mechanism": "docker_allowlist_mounts", "network_mode": "none",
                "label_store_mounted": False, "read_only_root": True,
                "exit_code": 0,
            })

            result = build_case.verify_blind(output)

        self.assertEqual(1, result["candidate_text_file_reads"])
        self.assertEqual(1, result["candidate_snapshots_without_tracked_files"])


class ConstraintReplayTests(unittest.TestCase):
    def test_write_arm_supports_python_310_utc_timestamp(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            constraint_replay.write_arm(
                root, "A0", ["stestr", "run", "example.test"], 0, "ok", 0.1
            )

            summary = build_case.read_json(root / "a0" / "summary.json")

        self.assertTrue(summary["finished_at"].endswith("Z"))

    def test_requires_exactly_one_changed_pin(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = root / "old.txt"
            new = root / "new.txt"
            old.write_text("alpha===1.0\ntooz===8.1.0\n", encoding="utf-8")
            new.write_text("alpha===1.0\ntooz===9.0.0\n", encoding="utf-8")

            self.assertEqual(
                ("tooz", "8.1.0", "9.0.0"),
                constraint_replay.changed_pin(old, new),
            )

    def test_rejects_multi_pin_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = root / "old.txt"
            new = root / "new.txt"
            old.write_text("alpha===1.0\ntooz===8.1.0\n", encoding="utf-8")
            new.write_text("alpha===2.0\ntooz===9.0.0\n", encoding="utf-8")

            with self.assertRaises(ValueError):
                constraint_replay.changed_pin(old, new)

    def test_selects_routed_pin_while_preserving_full_opening_diff(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = root / "old.txt"
            new = root / "new.txt"
            old.write_text(
                "SQLAlchemy===1.4.41\nsqlalchemy-migrate===0.13.0\n",
                encoding="utf-8",
            )
            new.write_text("SQLAlchemy===2.0.9\n", encoding="utf-8")

            self.assertEqual(
                ("sqlalchemy", "1.4.41", "2.0.9"),
                constraint_replay.selected_changed_pin(
                    old, new, "SQLAlchemy"
                ),
            )
            self.assertEqual(
                [
                    ("sqlalchemy", "1.4.41", "2.0.9"),
                    ("sqlalchemy-migrate", "0.13.0", None),
                ],
                constraint_replay.changed_pin_rows(old, new),
            )

    def test_routed_single_pin_is_still_recorded_as_single_pin(self) -> None:
        self.assertEqual(
            "global_constraints_single_pin",
            constraint_replay.constraint_source_application(
                [("oslo.service", "4.2.2", "4.3.0")]
            ),
        )

    def test_routed_multi_pin_records_the_full_opening_diff(self) -> None:
        self.assertEqual(
            "global_constraints_full_opening_diff",
            constraint_replay.constraint_source_application(
                [
                    ("sqlalchemy", "1.4.41", "2.0.9"),
                    ("sqlalchemy-migrate", "0.13.0", None),
                ]
            ),
        )

    def test_full_constraints_adapter_is_explicit_and_uses_existing_runner(self) -> None:
        self.assertEqual(
            "run_formal_e2_constraint_touched_relation.py",
            build_case.REPLAY_ADAPTERS["requirements_full_constraints"],
        )

    def test_counts_selected_pytest_check_in_pass_and_failure(self) -> None:
        self.assertEqual(
            1,
            constraint_replay.tests_run_count(
                "============================== 1 passed in 0.22s ==============================\n"
            ),
        )

    def test_extracts_pytest_error_line_for_full_constraints_replay(self) -> None:
        self.assertEqual(
            "AttributeError: 'LogCaptureHandler' object has no attribute 'address'",
            constraint_replay.pytest_failure_signature(
                "E   AttributeError: 'LogCaptureHandler' object has no attribute 'address'\n"
            ),
        )
        self.assertEqual(
            1,
            constraint_replay.tests_run_count(
                "============================== 1 failed in 0.31s ==============================\n"
            ),
        )

    def test_full_constraints_contract_records_versions_and_checks(self) -> None:
        contract = {
            "source_application": "global_constraints_full_opening_diff",
            "changed_distribution": "pytest",
            "source_versions": {"A0": "9.0.3", "A1": "9.1.1", "A2": "9.1.1"},
            "opening_constraint_changes": [
                {"distribution": "pytest", "old_version": "9.0.3", "new_version": "9.1.1"},
                {"distribution": "coverage", "old_version": "7.14.3", "new_version": "7.15.0"},
            ],
        }
        build_case.verify_constraint_source_application(contract)
        command = ["pytest", "test/unit/test_proxy_logging.py::test_handler"]
        installed = {
            "A0": {"pytest": "9.0.3", "coverage": "7.14.3"},
            "A1": {"pytest": "9.1.1", "coverage": "7.15.0"},
            "A2": {"pytest": "9.1.1", "coverage": "7.15.0"},
        }
        evidence = constraint_replay.full_constraints_evidence(
            {"source_base_commit": "requirements-base", "source_head_commit": "requirements-head"},
            "swift-cutoff",
            command,
            installed,
            {"A0": 1, "A1": 1, "A2": 1},
        )
        self.assertEqual(
            {"A0": "requirements-base", "A1": "requirements-head", "A2": "requirements-head"},
            evidence["constraint_commits_by_arm"],
        )
        self.assertEqual(
            {"A0": "swift-cutoff", "A1": "swift-cutoff", "A2": "swift-cutoff"},
            evidence["target_base_commits_by_arm"],
        )
        self.assertEqual({"A0": command, "A1": command, "A2": command}, evidence["test_commands_by_arm"])
        self.assertEqual(installed, evidence["installed_versions_by_distribution"])
        self.assertEqual({"A0": 1, "A1": 1, "A2": 1}, evidence["checks_run"])

    def test_verifier_accepts_a_recorded_full_opening_diff(self) -> None:
        build_case.verify_constraint_source_application({
            "source_application": "global_constraints_full_opening_diff",
            "changed_distribution": "sqlalchemy",
            "source_versions": {"A0": "1.4.41", "A1": "2.0.9", "A2": "2.0.9"},
            "opening_constraint_changes": [
                {
                    "distribution": "sqlalchemy",
                    "old_version": "1.4.41",
                    "new_version": "2.0.9",
                },
                {
                    "distribution": "sqlalchemy-migrate",
                    "old_version": "0.13.0",
                    "new_version": None,
                },
            ],
        })

    def test_verifier_rejects_full_opening_diff_without_all_changes(self) -> None:
        with self.assertRaisesRegex(ValueError, "did not record every changed pin"):
            build_case.verify_constraint_source_application({
                "source_application": "global_constraints_full_opening_diff",
                "changed_distribution": "sqlalchemy",
                "source_versions": {"A0": "1.4.41", "A1": "2.0.9", "A2": "2.0.9"},
                "opening_constraint_changes": [{
                    "distribution": "sqlalchemy",
                    "old_version": "1.4.41",
                    "new_version": "2.0.9",
                }],
            })

    def test_verifier_rejects_full_opening_diff_with_wrong_routed_versions(self) -> None:
        with self.assertRaisesRegex(ValueError, "routed pin does not match"):
            build_case.verify_constraint_source_application({
                "source_application": "global_constraints_full_opening_diff",
                "changed_distribution": "sqlalchemy",
                "source_versions": {"A0": "1.4.41", "A1": "2.0.8", "A2": "2.0.8"},
                "opening_constraint_changes": [
                    {
                        "distribution": "sqlalchemy",
                        "old_version": "1.4.41",
                        "new_version": "2.0.9",
                    },
                    {
                        "distribution": "sqlalchemy-migrate",
                        "old_version": "0.13.0",
                        "new_version": None,
                    },
                ],
            })

    def test_failure_signature_comes_from_stestr_failed_section(self) -> None:
        output = """RuntimeError: incidental at 0x1234
Failed 2 tests - output below:
case.name
AssertionError: expected call not found.
"""

        self.assertEqual(
            "AssertionError: expected call not found.",
            constraint_replay.extract_failure_signature(output),
        )

    def test_failure_signature_normalizes_addresses(self) -> None:
        output = """Failed 1 tests - output below:
RuntimeError: object at 0x7f00 failed for req-4e1552ea-d189-4577-93c8-511f0370d4a8
"""

        self.assertEqual(
            "RuntimeError: object at 0x<address> failed for req-<uuid>",
            constraint_replay.extract_failure_signature(output),
        )

    def test_failure_signature_accepts_bare_timeout_in_failed_section(self) -> None:
        output = """Failed 1 tests - output below:
test.case
    fixtures._fixtures.timeout.TimeoutException
"""

        self.assertEqual(
            "fixtures._fixtures.timeout.TimeoutException",
            constraint_replay.extract_failure_signature(output),
        )

    def test_constraint_replay_preserves_planned_stestr_options(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            environment = Path(directory)
            (environment / "bin").mkdir()
            (environment / "bin/stestr").touch()
            executable, recorded = constraint_replay.planned_test_command(
                {
                    "test_selector": "nova.tests.functional.test_report_client",
                    "test_command": [
                        "stestr",
                        "--test-path=./nova/tests/functional",
                        "run",
                        "nova.tests.functional.test_report_client",
                    ],
                },
                environment,
            )

        self.assertEqual(recorded[1:], executable[1:])
        self.assertEqual("stestr", recorded[0])

    def test_constraint_replay_preserves_repository_native_pytest_wrapper(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            environment = Path(directory)
            (environment / "bin").mkdir()
            (environment / "bin/pytest").touch()
            executable, recorded = constraint_replay.planned_test_command(
                {
                    "test_selector": "openstack_auth/tests/unit/test_policy.py",
                    "test_command": [
                        "bash",
                        "tools/unit_tests.sh",
                        ".",
                        "openstack_auth/tests/unit/test_policy.py",
                    ],
                },
                environment,
            )

        self.assertEqual(recorded, executable)

    def test_constraint_replay_uses_tox_python_for_legacy_horizon_wrapper(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            environment = Path(directory)
            (environment / "bin").mkdir()
            (environment / "bin/python").touch()
            executable, recorded = constraint_replay.planned_test_command(
                {
                    "test_selector": "openstack_dashboard.test.unit.api.test_nova",
                    "test_command": [
                        "bash",
                        "tools/unit_tests.sh",
                        "python",
                        ".",
                        "openstack_dashboard.test.unit.api.test_nova",
                    ],
                },
                environment,
            )

        self.assertEqual(recorded[:2], executable[:2])
        self.assertEqual(recorded[3:], executable[3:])
        self.assertEqual((environment / "bin/python").absolute(), Path(executable[2]))

    def test_constraint_replay_accepts_pytest_terminal_summary(self) -> None:
        self.assertTrue(
            constraint_replay.tests_ran(
                "================ 19 passed, 2 warnings in 1.25s ================\n"
            )
        )

    def test_constraint_replay_accepts_unittest_terminal_summary(self) -> None:
        self.assertTrue(constraint_replay.tests_ran("Ran 1 test in 0.123s\n\nOK\n"))

    def test_constraint_replay_does_not_leak_host_proxy_into_tests(self) -> None:
        cleaned = constraint_replay.without_proxy_environment(
            {
                "PATH": "/bin",
                "http_proxy": "http://proxy",
                "HTTPS_PROXY": "http://proxy",
                "ALL_PROXY": "socks://proxy",
                "NO_PROXY": "localhost",
            }
        )

        self.assertEqual({"PATH": "/bin", "NO_PROXY": "localhost"}, cleaned)

    def test_constraint_replay_extends_historical_build_constraints(self) -> None:
        self.assertEqual(
            ["setuptools==75.6.0", "Cython<3"],
            constraint_replay.bootstrap_constraint_lines(["Cython<3", "Cython<3"]),
        )

    def test_constraint_replay_uses_source_era_setuptools_constraint(self) -> None:
        self.assertEqual(
            ["setuptools===56.0.0", "Cython<3"],
            constraint_replay.bootstrap_constraint_lines(
                ["Cython<3"], "setuptools===56.0.0"
            ),
        )

    def test_constraint_replay_rejects_multiline_build_constraint(self) -> None:
        with self.assertRaises(ValueError):
            constraint_replay.bootstrap_constraint_lines(["Cython<3\nrequests<3"])

    def test_constraint_replay_parses_setup_environment(self) -> None:
        self.assertEqual(
            {"CFLAGS": "-I/tmp/include", "LIBRARY_PATH": "/tmp/lib"},
            constraint_replay.parse_environment_overrides(
                ["CFLAGS=-I/tmp/include", "LIBRARY_PATH=/tmp/lib"],
                "--setup-environment",
            ),
        )

    def test_constraint_replay_rejects_invalid_setup_environment(self) -> None:
        with self.assertRaisesRegex(ValueError, "KEY=VALUE"):
            constraint_replay.parse_environment_overrides(
                ["CFLAGS"], "--setup-environment"
            )


class MavenSourceReplayTests(unittest.TestCase):
    def test_clone_checkout_detaches_at_requested_commit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            destination = root / "destination"
            subprocess.run(["git", "init", "-q", str(source)], check=True)
            subprocess.run(["git", "-C", str(source), "config", "user.name", "Test"], check=True)
            subprocess.run(["git", "-C", str(source), "config", "user.email", "test@example.test"], check=True)
            value = source / "value.txt"
            value.write_text("first\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(source), "add", "value.txt"], check=True)
            subprocess.run(["git", "-C", str(source), "commit", "-qm", "first"], check=True)
            first = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
            value.write_text("second\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(source), "commit", "-qam", "second"], check=True)

            maven_replay.clone_checkout(source, destination, first)

            self.assertEqual(
                first,
                subprocess.check_output(
                    ["git", "-C", str(destination), "rev-parse", "HEAD"], text=True
                ).strip(),
            )
            self.assertEqual("first\n", (destination / "value.txt").read_text(encoding="utf-8"))

    def test_build_sides_can_have_distinct_java_environments(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            java_home = Path(directory) / "jdk"
            environment = maven_replay.java_environment(
                {"PATH": "/usr/bin", "KEEP": "yes"}, java_home
            )

        self.assertEqual(str(java_home.resolve()), environment["JAVA_HOME"])
        self.assertEqual(f"{java_home.resolve() / 'bin'}:/usr/bin", environment["PATH"])
        self.assertEqual("yes", environment["KEEP"])

    def test_target_maven_wrapper_preserves_recorded_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target"
            target.mkdir()
            wrapper = target / "mvnw"
            wrapper.touch()
            repository = root / "m2"

            command = maven_replay.planned_target_command(
                ["./mvnw", "-B", "clean", "test"],
                target,
                root / "mvn",
                repository,
            )

        self.assertEqual(str(wrapper), command[0])
        self.assertEqual(f"-Dmaven.repo.local={repository}", command[1])
        self.assertEqual(["-B", "clean", "test"], command[2:])

    def test_commits_patch_with_recorded_maintainer_dates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            subprocess.run(["git", "init", "-q", str(repository)], check=True)
            subprocess.run(["git", "-C", str(repository), "config", "user.name", "Test"], check=True)
            subprocess.run(["git", "-C", str(repository), "config", "user.email", "test@example.test"], check=True)
            value = repository / "value.txt"
            value.write_text("old\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repository), "add", "value.txt"], check=True)
            base_environment = os.environ.copy()
            base_environment.update({
                "GIT_AUTHOR_DATE": "2020-01-01T00:00:00Z",
                "GIT_COMMITTER_DATE": "2020-01-01T00:00:00Z",
            })
            subprocess.run(["git", "-C", str(repository), "commit", "-qm", "base"], env=base_environment, check=True)
            base = subprocess.check_output(["git", "-C", str(repository), "rev-parse", "HEAD"], text=True).strip()
            value.write_text("new\n", encoding="utf-8")
            maintainer_environment = os.environ.copy()
            maintainer_environment.update({
                "GIT_AUTHOR_DATE": "2023-05-06T07:08:09Z",
                "GIT_COMMITTER_DATE": "2023-05-06T07:08:09Z",
            })
            subprocess.run(["git", "-C", str(repository), "commit", "-qam", "maintainer repair"], env=maintainer_environment, check=True)
            maintainer = subprocess.check_output(["git", "-C", str(repository), "rev-parse", "HEAD"], text=True).strip()
            subprocess.run(["git", "-C", str(repository), "checkout", "-q", "--detach", base], check=True)
            value.write_text("new\n", encoding="utf-8")

            recorded = maven_replay.commit_patch_with_maintainer_metadata(
                repository, maintainer
            )

            self.assertEqual(maintainer, recorded["maintainer_commit"])
            self.assertEqual("2023-05-06T07:08:09+00:00", recorded["maintainer_author_date"])
            self.assertEqual("new\n", value.read_text(encoding="utf-8"))
            self.assertEqual(
                "2023-05-06T07:08:09+00:00",
                subprocess.check_output(
                    ["git", "-C", str(repository), "show", "-s", "--format=%cI", "HEAD"],
                    text=True,
                ).strip(),
            )

    def test_reads_parentless_project_coordinates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pom = Path(directory) / "pom.xml"
            pom.write_text(
                "<project><modelVersion>4.0.0</modelVersion>"
                "<groupId>com.h2database</groupId><artifactId>h2</artifactId>"
                "<version>1.4.200-SNAPSHOT</version></project>",
                encoding="utf-8",
            )

            self.assertEqual("h2", maven_replay.project_artifact_id(pom))
            self.assertEqual("1.4.200-SNAPSHOT", maven_replay.project_version(pom))

    def test_updates_direct_project_version_without_touching_parent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pom = Path(directory) / "pom.xml"
            pom.write_text(
                '<project xmlns="http://maven.apache.org/POM/4.0.0">'
                '<modelVersion>4.0.0</modelVersion>'
                '<parent><groupId>com.example</groupId><artifactId>base</artifactId>'
                '<version>2.11.0-SNAPSHOT</version></parent>'
                '<groupId>com.example</groupId><artifactId>core</artifactId>'
                '<name>Core</name><version>2.11.0-SNAPSHOT</version></project>',
                encoding="utf-8",
            )

            maven_replay.set_project_version(pom, "2.8.0")

            self.assertEqual("2.8.0", maven_replay.project_version(pom))
            self.assertIn(
                '<artifactId>base</artifactId><version>2.11.0-SNAPSHOT</version>',
                pom.read_text(encoding="utf-8"),
            )

    def test_updates_parent_version_without_touching_project_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pom = Path(directory) / "pom.xml"
            pom.write_text(
                '<project><modelVersion>4.0.0</modelVersion><parent>'
                '<groupId>com.example</groupId><artifactId>base</artifactId>'
                '<version>2.11.0-SNAPSHOT</version></parent>'
                '<artifactId>core</artifactId><version>2.11.0-SNAPSHOT</version></project>',
                encoding="utf-8",
            )

            maven_replay.set_parent_version(pom, "2.11.0")

            text = pom.read_text(encoding="utf-8")
            self.assertIn('<artifactId>base</artifactId><version>2.11.0</version>', text)
            self.assertEqual("2.11.0-SNAPSHOT", maven_replay.project_version(pom))

    def test_reads_dependency_version_property(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pom = Path(directory) / "pom.xml"
            pom.write_text(
                "<project><properties><h2.version>1.4.199</h2.version>"
                "</properties></project>",
                encoding="utf-8",
            )

            self.assertEqual(
                "1.4.199",
                maven_replay.dependency_version(
                    pom, "com.h2database", "h2", "h2.version"
                ),
            )

    def test_counts_only_successful_unskipped_maven_tests(self) -> None:
        output = (
            "Tests run: 2, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 1 s - in GoodTest\n"
            "Tests run: 1, Failures: 0, Errors: 0, Skipped: 1, Time elapsed: 1 s - in SkippedTest\n"
            "Tests run: 3, Failures: 1, Errors: 0, Skipped: 0, Time elapsed: 1 s - in FailedTest\n"
            "Tests run: 2, Failures: 0, Errors: 0, Skipped: 0\n"
        )

        self.assertEqual(2, maven_replay.successful_test_count(output))


class AntSourceMavenTargetReplayTests(unittest.TestCase):
    def test_parses_environment_overrides(self) -> None:
        self.assertEqual(
            {"JAVA_TOOL_OPTIONS": "-XX:UseAVX=2"},
            ant_maven_replay.environment_overrides(
                ["JAVA_TOOL_OPTIONS=-XX:UseAVX=2"]
            ),
        )

    def test_rejects_invalid_environment_override(self) -> None:
        with self.assertRaisesRegex(ValueError, "KEY=VALUE"):
            ant_maven_replay.environment_overrides(["JAVA_TOOL_OPTIONS"])

    def test_inventory_enforces_required_and_forbidden_entries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            jar = root / "artifact.jar"
            import zipfile
            with zipfile.ZipFile(jar, "w") as archive:
                archive.writestr("new/Driver.class", b"class")
            inventory = ant_maven_replay.artifact_inventory(root, [{
                "artifact_id": "artifact",
                "jar_path": "artifact.jar",
                "required_entries": ["new/Driver.class"],
                "forbidden_entries": ["old/Driver.class"],
            }], "A1")

        self.assertTrue(ant_maven_replay.inventory_matches(inventory))


class CrossRepoCommandReplayTests(unittest.TestCase):
    def test_python_executable_preserves_virtualenv_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "base-python"
            base.touch()
            venv_python = root / "venv-python"
            venv_python.symlink_to(base)

            selected = cross_repo_replay.python_executable(venv_python)

        self.assertEqual(str(venv_python.absolute()), selected)

    def test_command_provenance_can_come_from_source_opening_base(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            target = root / "target"
            source.mkdir()
            target.mkdir()
            (source / "tox.ini").write_text("[testenv]\n", encoding="utf-8")
            provenance = cross_repo_replay.command_provenance(
                {
                    "source_repository": "org/source",
                    "source_base_commit": "source-base",
                    "target_repository": "org/target",
                    "command_config_repository": "source",
                    "command_config_path": "tox.ini",
                },
                {"A0": source},
                {"A0": target},
                "target-base",
            )

        self.assertEqual({
            "repository": "org/source", "commit": "source-base", "path": "tox.ini"
        }, provenance)

    def test_counts_each_native_check_result(self) -> None:
        pattern = __import__("re").compile(
            r"^(?:ok:|style\.json: vendored asset differs)", __import__("re").MULTILINE
        )
        output = "ok: first.json\nok: second.json\nstyle.json: vendored asset differs\n"

        self.assertEqual(3, cross_repo_replay.parsed_check_count(output, pattern))

    def test_removes_proxy_variables_from_native_check(self) -> None:
        with mock.patch.dict(os.environ, {
            "PATH": "/bin", "http_proxy": "http://proxy", "HTTPS_PROXY": "http://proxy"
        }, clear=True):
            environment = cross_repo_replay.local_environment()

        self.assertEqual("/bin", environment["PATH"])
        self.assertNotIn("http_proxy", environment)
        self.assertNotIn("HTTPS_PROXY", environment)


class ComponentCatalogTests(unittest.TestCase):
    def test_collects_all_pages_without_labels(self) -> None:
        pages = {
            1: [{
                "repository_url": "https://github.com/example/one",
                "repo_metadata": {"created_at": "2010-01-01T00:00:00Z"},
            }],
            2: [{
                "repository_url": "git+https://github.com/example/two.git",
                "repo_metadata": {"created_at": "2011-01-01T00:00:00Z"},
            }],
            3: [],
        }

        def fetcher(url: str):
            from urllib.parse import parse_qs, urlparse
            return pages[int(parse_qs(urlparse(url).query)["page"][0])]

        snapshots = component_catalog.collect_pages(
            "repo1.maven.org", "org.example:source", 1, fetcher
        )
        document = component_catalog.catalog_document(
            "catalog", "repo1.maven.org", "org.example:source", snapshots,
            "2026-08-27T00:00:00Z",
        )

        catalog = document["catalogs"]["catalog"]
        self.assertEqual(["example/one", "example/two"], catalog["repositories"])
        self.assertFalse(catalog["membership_reads_e2_targets"])
        self.assertEqual(3, len(snapshots))


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Build ten command-scoped E3 cases from retained multi-arm executions.

The builder does not turn green builds into negatives by declaration.  It reads
the retained per-repetition result records, checks the actual A0/A1 direction,
version probes, and test execution, then emits deliberately narrow claims.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream, delimiter="\t"))


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def bundle_evidence(output_dir: Path, cases: list[dict[str, Any]]) -> None:
    """Copy only the raw files parsed by the verifier into the release."""
    for case in cases:
        destination = output_dir / "evidence" / case["e3_id"]
        destination.mkdir(parents=True, exist_ok=True)
        evidence = case["evidence"]
        for key in ("result_tables", "exit_codes", "logs"):
            if key not in evidence:
                continue
            bundled = []
            for index, reference in enumerate(evidence[key], start=1):
                source = ROOT / reference
                target = destination / f"{key}-{index}{source.suffix}"
                shutil.copy2(source, target)
                bundled.append(target.relative_to(output_dir).as_posix())
            evidence[key] = bundled
        for key in ("command", "summary"):
            if key not in evidence:
                continue
            source = ROOT / evidence[key]
            target = destination / f"{key}{source.suffix}"
            shutil.copy2(source, target)
            evidence[key] = target.relative_to(output_dir).as_posix()


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def requirements_cases() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    base = RESULTS / "requirements-formal-repetitions-2026-08-24"
    repositories = ("heat", "ironic", "keystone", "nova", "placement")
    tables = [base / f"repeat-{repeat}" / "run-results.tsv" for repeat in range(1, 4)]
    all_rows = [row for table in tables for row in read_tsv(table)]
    cases = []
    for repository in repositories:
        selected = [
            row for row in all_rows
            if row["repository"] == repository and row["config"] in {"a0", "a1"}
        ]
        if len(selected) != 6:
            raise ValueError(f"requirements/{repository}: expected six A0/A1 rows")
        for row in selected:
            expected_version = "1.18.5" if row["config"] == "a0" else "1.19.1"
            if (
                row["expected_version"] != expected_version
                or row["actual_version"] != expected_version
                or row["exit_code"] != "0"
                or row["expected_result"] != "pass"
                or row["test_executed"] != "true"
                or row["version_ok"] != "true"
                or row["direction_ok"] != "true"
            ):
                raise ValueError(f"requirements/{repository}: invalid retained result {row}")
        command_path = base / "repeat-1" / "runs" / "a0" / repository / "command.txt"
        command = command_path.read_text(encoding="utf-8").strip()
        selector = command.rsplit(" -- ", 1)[-1]
        cases.append({
            "schema_version": "1.0",
            "e3_id": f"e3-restraint-requirements-{repository}",
            "pack_id": "restraint-requirements-alembic-1.19.1",
            "evidence_layer": "E3",
            "source_repository": "openstack/requirements",
            "source_change": {"distribution": "alembic", "a0": "1.18.5", "a1": "1.19.1"},
            "target_repository": f"openstack/{repository}",
            "target_commit": (
                base / "repeat-1" / "runs" / "a0" / repository / "consumer-commit.txt"
            ).read_text(encoding="utf-8").strip(),
            "command_scope": {"test_selector": selector, "logical_executor": "tox"},
            "observations": {"repetitions": 3, "a0_exit_codes": [0, 0, 0], "a1_exit_codes": [0, 0, 0]},
            "consumption_surface": "the target's native MySQL model/migration synchronization check executes Alembic-backed schema reflection and comparison",
            "claim_ceiling": "No breakage was observed for this one MySQL model-sync selector; no repository-wide compatibility claim is made.",
            "semantic_review": {
                "approved": True,
                "basis": "Same target commit and selector in three isolated A0/A1 repetitions; the table records exact Alembic versions, test execution, and zero exits in both arms.",
            },
            "evidence": {
                "result_tables": [relative(path) for path in tables],
                "command": relative(command_path),
            },
        })
    pack = {
        "schema_version": "1.0",
        "pack_id": "restraint-requirements-alembic-1.19.1",
        "source_repository": "openstack/requirements",
        "source_change": "Alembic constraint 1.18.5 to 1.19.1",
        "candidate_repositories": [
            "openstack/cinder", "openstack/heat", "openstack/ironic",
            "openstack/keystone", "openstack/nova", "openstack/placement",
        ],
        "breakage_repositories": ["openstack/cinder"],
        "bounded_negative_repositories": [case["target_repository"] for case in cases],
        "bounded_universe_complete": True,
        "interpretation": "All six candidates were run under the same five-arm project-package protocol; the five E3 labels remain command-scoped.",
    }
    return pack, cases


def snakeyaml_cases() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    base = RESULTS / "snakeyaml-formal-repetitions-2026-08-24"
    summary = read_json(base / "summary.json")
    if summary["aggregate"] != {
        "repository_commands": 60,
        "expected_direction_matches": 60,
        "version_inputs_verified": 60,
        "pass_commands_with_tests_executed": 54,
        "expected_compile_failures": 6,
        "unexpected_nonzero_exits": 0,
        "by_arm": {
            "a0": {"commands": 12, "passed": 12},
            "a1": {"commands": 12, "passed": 6, "expected_compile_failures": 6},
            "a2": {"commands": 12, "passed": 12},
            "a3_before": {"commands": 12, "passed": 12},
            "a3_after": {"commands": 12, "passed": 12},
        },
    }:
        raise ValueError("SnakeYAML aggregate no longer matches the accepted repetition frame")
    specifications = {
        "xlate": ("xlate/yaml-json", "78 default plus 60 YAML 1.1 and 60 YAML 1.2 tests"),
        "xvik": ("xvik/yaml-updater", "146 tests in the yaml-config-updater module"),
    }
    cases = []
    for slug, (repository, test_scope) in specifications.items():
        evidence = []
        commits = set()
        commands = set()
        for repeat in range(1, 4):
            for arm in ("a0", "a1"):
                run = base / f"repeat-{repeat}" / "runs" / arm / slug
                if (run / "exit-code.txt").read_text(encoding="utf-8").strip() != "0":
                    raise ValueError(f"SnakeYAML/{slug}: {arm} repeat {repeat} did not pass")
                commits.add((run / "consumer-commit.txt").read_text(encoding="utf-8").strip())
                commands.add((run / "command.txt").read_text(encoding="utf-8").strip())
                evidence.append(relative(run / "exit-code.txt"))
        if len(commits) != 1:
            raise ValueError(f"SnakeYAML/{slug}: target commit changed across arms")
        cases.append({
            "schema_version": "1.0",
            "e3_id": f"e3-restraint-snakeyaml-{slug}",
            "pack_id": "restraint-snakeyaml-2.0",
            "evidence_layer": "E3",
            "source_repository": "snakeyaml/snakeyaml",
            "source_change": {"distribution": "org.yaml:snakeyaml", "a0": "1.32", "a1": "2.0"},
            "target_repository": repository,
            "target_commit": next(iter(commits)),
            "command_scope": {"native_test_scope": test_scope, "recorded_command_variants": len(commands)},
            "observations": {"repetitions": 3, "a0_exit_codes": [0, 0, 0], "a1_exit_codes": [0, 0, 0]},
            "consumption_surface": "native parsing, reading, writing, and generation tests execute the SnakeYAML-backed consumer path",
            "claim_ceiling": "Only the recorded native parser/module tests are E3; other modules, configurations, and YAML inputs remain unjudged.",
            "semantic_review": {
                "approved": True,
                "basis": "Three isolated repetitions used the same fixed consumer commit; all A0/A1 commands passed and the formal aggregate records all source-version probes.",
            },
            "evidence": {"exit_codes": evidence, "summary": relative(base / "summary.json")},
        })
    pack = {
        "schema_version": "1.0",
        "pack_id": "restraint-snakeyaml-2.0",
        "source_repository": "snakeyaml/snakeyaml",
        "source_change": "SnakeYAML 1.32 to 2.0",
        "candidate_repositories": ["apache/jclouds", "zio/zio-json", "xlate/yaml-json", "xvik/yaml-updater"],
        "breakage_repositories": ["apache/jclouds", "zio/zio-json"],
        "bounded_negative_repositories": [case["target_repository"] for case in cases],
        "bounded_universe_complete": True,
        "interpretation": "All four candidates were run under the same repeated project-package protocol; negative claims are limited to each recorded command.",
    }
    return pack, cases


def slf4j_cases() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    base = RESULTS / "slf4j-formal-repetitions-2026-08-24"
    summary = read_json(base / "summary.json")
    aggregate = summary["aggregate"]
    if (
        aggregate["repository_commands"] != 60
        or aggregate["expected_direction_matches"] != 60
        or aggregate["version_inputs_verified"] != 60
        or aggregate["unexpected_nonzero_exits"] != 0
    ):
        raise ValueError("SLF4J aggregate no longer matches the accepted repetition frame")
    specifications = {
        "password4j": ("Password4j/password4j", "all 206 native tests", "a0.log", "a1.log", "BUILD SUCCESS"),
        "spotless": ("diffplug/spotless", "three targeted FreshMarkStepTest/SortPomTest methods", "a0.targeted.log", "a1.targeted.log", "Executed 3 tests"),
        "rabbit": ("rabbitmq/rabbitmq-jms-client", "114 native unit tests", "a0.log", "a1.log", "Tests run: 114"),
    }
    cases = []
    for slug, (repository, test_scope, a0_name, a1_name, success_marker) in specifications.items():
        logs = []
        for repeat in range(1, 4):
            for arm, filename in (("a0", a0_name), ("a1", a1_name)):
                path = base / f"rep{repeat}" / slug / filename
                text = path.read_text(encoding="utf-8", errors="replace")
                if success_marker not in text:
                    raise ValueError(f"SLF4J/{slug}: missing pass marker in {path}")
                logs.append(relative(path))
        cases.append({
            "schema_version": "1.0",
            "e3_id": f"e3-restraint-slf4j-{slug}",
            "pack_id": "restraint-slf4j-2.0.0",
            "evidence_layer": "E3",
            "source_repository": "qos-ch/slf4j",
            "source_change": {"distribution": "org.slf4j:slf4j-api", "a0": "1.7.36", "a1": "2.0.0"},
            "target_repository": repository,
            "command_scope": {"native_test_scope": test_scope},
            "observations": {"repetitions": 3, "a0_exit_codes": [0, 0, 0], "a1_exit_codes": [0, 0, 0]},
            "consumption_surface": summary["consumer_results"][repository]["boundary"],
            "claim_ceiling": summary["consumer_results"][repository]["boundary"],
            "semantic_review": {
                "approved": True,
                "basis": "All six A0/A1 logs contain the command-specific success marker; the project aggregate records exact source-version probes and no unexpected nonzero exits.",
            },
            "evidence": {"logs": logs, "summary": relative(base / "summary.json")},
        })
    pack = {
        "schema_version": "1.0",
        "pack_id": "restraint-slf4j-2.0.0",
        "source_repository": "qos-ch/slf4j",
        "source_change": "SLF4J API 1.7.36 to 2.0.0",
        "candidate_repositories": [
            "jadler-mocking/jadler", "Password4j/password4j",
            "diffplug/spotless", "rabbitmq/rabbitmq-jms-client",
        ],
        "breakage_repositories": ["jadler-mocking/jadler"],
        "bounded_negative_repositories": [case["target_repository"] for case in cases],
        "bounded_universe_complete": True,
        "interpretation": "All four candidates were run under the same repeated project-package protocol; each negative label retains its explicit logging/provider ceiling.",
    }
    return pack, cases


def build(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    packs = []
    cases = []
    for collector in (requirements_cases, snakeyaml_cases, slf4j_cases):
        pack, collected = collector()
        packs.append(pack)
        cases.extend(collected)
    if len(cases) != 10 or len({row["e3_id"] for row in cases}) != 10:
        raise ValueError("restraint release requires exactly ten unique E3 cases")
    bundle_evidence(output_dir, cases)
    write_jsonl(output_dir / "e3-cases.jsonl", sorted(cases, key=lambda row: row["e3_id"]))
    write_jsonl(output_dir / "project-packs.jsonl", sorted(packs, key=lambda row: row["pack_id"]))
    report = {
        "schema_version": "1.0",
        "evidence_layer": "E3",
        "case_count": len(cases),
        "project_pack_count": len(packs),
        "source_event_count": len({row["pack_id"] for row in cases}),
        "a0_a1_repetition_count": sum(row["observations"]["repetitions"] for row in cases),
        "machine_verified_a0_pass_a1_pass_count": len(cases),
        "semantic_approval_count": sum(row["semantic_review"]["approved"] for row in cases),
        "bounded_universe_complete_pack_count": sum(row["bounded_universe_complete"] for row in packs),
        "claim_scope": "command_scoped_bounded_negative",
        "formal_main_set_precision_supported": False,
        "restraint_pack_precision_specificity_supported": True,
    }
    write_json(output_dir / "verification.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report = build(args.output_dir)
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

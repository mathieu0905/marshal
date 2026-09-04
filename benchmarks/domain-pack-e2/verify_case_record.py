#!/usr/bin/env python3
"""Verify public candidates and any curator-judged strict-E2 bindings."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


_STESTR_CHECK_COUNT = re.compile(r"(?m)^Ran: ([1-9][0-9]*) tests?\b")
_UNITTEST_CHECK_COUNT = re.compile(r"(?m)^Ran ([1-9][0-9]*) tests? in \S+")
_PYTEST_CHECK_COUNT = re.compile(
    r"(?m)^=+ .*?\b([1-9][0-9]*) passed(?:,| in ).*?=+\s*$"
)


def _check_count(log: str) -> int | None:
    for pattern in (_STESTR_CHECK_COUNT, _UNITTEST_CHECK_COUNT, _PYTEST_CHECK_COUNT):
        matches = pattern.findall(log)
        if matches:
            return int(matches[-1])
    return None


def _exact_source_versions(
    public: dict[str, Any], dependency_key: str
) -> dict[str, str] | None:
    facts = [
        fact
        for fact in public.get("change_facts", [])
        if fact.get("dependency_key") == dependency_key
    ]
    if len(facts) != 1:
        return None
    fact = facts[0]

    def exact(entries: Any) -> str | None:
        if not isinstance(entries, list) or len(entries) != 1:
            return None
        specifier = entries[0].get("specifier")
        if not isinstance(specifier, str) or not specifier.startswith("==="):
            return None
        return specifier[3:]

    old = exact(fact.get("removed_entries"))
    new = exact(fact.get("added_entries"))
    if old is None or new is None:
        return None
    return {"A0": old, "A1": new, "A2": new}


def _artifact_path(package_root: Path, reference: str) -> Path | None:
    candidate = package_root / reference
    try:
        candidate.resolve().relative_to(package_root.resolve())
    except (ValueError, OSError):
        return None
    return candidate


def _read_json_artifact(
    package_root: Path,
    reference: str,
    label: str,
    errors: list[str],
) -> dict[str, Any] | None:
    path = _artifact_path(package_root, reference)
    if path is None:
        errors.append(f"{label} escapes package root")
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"cannot read {label}: {exc}")
        return None
    if not isinstance(payload, dict):
        errors.append(f"{label} must contain a JSON object")
        return None
    return payload


def _read_text_artifact(
    package_root: Path,
    reference: str,
    label: str,
    errors: list[str],
) -> str | None:
    path = _artifact_path(package_root, reference)
    if path is None:
        errors.append(f"{label} escapes package root")
        return None
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        errors.append(f"cannot read {label}: {exc}")
        return None


def verification_errors(
    pack: dict[str, Any],
    case: dict[str, Any],
    package_root: Path | None = None,
) -> list[str]:
    errors: list[str] = []
    if case.get("pack_family_id") != pack.get("pack_family_id"):
        errors.append("pack_family_id does not match referenced pack")
    if case.get("pack_revision_id") != pack.get("pack_revision_id"):
        errors.append("pack_revision_id does not match referenced pack")

    routes_by_key = {
        route["dependency_key"]: route for route in pack.get("dependency_routes", [])
    }
    routes_by_id = {
        route["id"]: route for route in pack.get("dependency_routes", [])
    }
    expected_route_ids: set[str] = set()
    expected_repositories: set[str] = set()
    expected_check_ids: set[str] = set()
    expected_unresolved: set[str] = set()
    expected_unresolved_repositories: set[tuple[str, str, str]] = set()
    public = case.get("public", {})
    from materialize_case_record import _fact_vocabulary

    fact_vocabulary = _fact_vocabulary(pack)
    if package_root is not None:
        source_event = public.get("source_event", {})
        source_patch_ref = source_event.get("patch_ref")
        if not source_patch_ref:
            errors.append("public.source_event lacks patch_ref")
        else:
            source_patch = _read_text_artifact(
                package_root,
                source_patch_ref,
                "public source patch",
                errors,
            )
            if source_patch is not None:
                from materialize_case_record import _patch_change_facts

                constraint_paths = set(
                    pack.get("provenance", {})
                    .get("source", {})
                    .get("constraints_paths", [])
                )
                derived_facts = _patch_change_facts(
                    source_patch,
                    constraint_paths,
                    fact_vocabulary=fact_vocabulary,
                )
                if derived_facts != public.get("change_facts", []):
                    errors.append("public.change_facts do not match packaged source patch")
    for fact in public.get("change_facts", []):
        route = routes_by_key.get(fact.get("dependency_key"))
        if route is None:
            expected_unresolved.add(fact.get("dependency_key"))
            continue
        expected_route_ids.add(route["id"])
        for repository_route in route["repositories"]:
            expected_repositories.add(repository_route["repository"])
            expected_check_ids.update(repository_route["focused_check_ids"])
            if repository_route["check_resolution"]["status"] == "unresolved":
                expected_unresolved_repositories.add(
                    (
                        route["id"],
                        repository_route["repository"],
                        repository_route["check_resolution"]["reason"],
                    )
                )

    selection = public.get("candidate_selection", {})
    expected_method = f"changed-{fact_vocabulary}-to-pack-candidates-v1"
    if selection.get("method") != expected_method:
        errors.append("public.candidate_selection.method does not match the pack")
    comparisons = (
        ("candidate_route_ids", expected_route_ids),
        ("candidate_repositories", expected_repositories),
        ("candidate_check_ids", expected_check_ids),
        ("unresolved_dependency_keys", expected_unresolved),
    )
    for field, expected in comparisons:
        actual_rows = selection.get(field, [])
        if len(actual_rows) != len(set(actual_rows)):
            errors.append(f"public.candidate_selection.{field} contains duplicates")
        if set(actual_rows) != expected:
            errors.append(
                f"public.candidate_selection.{field} is not the complete derived set"
            )

    unresolved_rows = selection.get("unresolved_repositories", [])
    actual_unresolved_repositories = {
        (row.get("route_id"), row.get("repository"), row.get("reason"))
        for row in unresolved_rows
    }
    if len(unresolved_rows) != len(actual_unresolved_repositories):
        errors.append("public.candidate_selection.unresolved_repositories has duplicates")
    if actual_unresolved_repositories != expected_unresolved_repositories:
        errors.append(
            "public.candidate_selection.unresolved_repositories is not the complete derived set"
        )

    check_ids_in_pack = {check["id"] for check in pack.get("checks", [])}
    if not expected_check_ids <= check_ids_in_pack:
        errors.append("selected routes reference checks absent from the pack")

    checks_by_id = {check["id"]: check for check in pack.get("checks", [])}
    binding_ids: set[str] = set()
    judged = case.get("curator", {}).get("judged_e2_bindings", [])
    for binding in judged:
        binding_id = binding.get("binding_id")
        if binding_id in binding_ids:
            errors.append(f"duplicate judged E2 binding: {binding_id}")
        binding_ids.add(binding_id)
        route = routes_by_id.get(binding.get("route_id"))
        check = checks_by_id.get(binding.get("check_id"))
        if route is None:
            errors.append(f"judged binding {binding_id} references unknown route")
            continue
        if check is None:
            errors.append(f"judged binding {binding_id} references unknown check")
            continue
        if route["id"] not in expected_route_ids or check["id"] not in expected_check_ids:
            errors.append(f"judged binding {binding_id} is outside this patch's candidates")
        route_check_ids = {
            check_id
            for repository_route in route["repositories"]
            for check_id in repository_route["focused_check_ids"]
        }
        if binding["check_id"] not in route_check_ids:
            errors.append(f"judged binding {binding_id} check is outside its route")
        if binding.get("location_repo") != check["location_repo"]:
            errors.append(f"judged binding {binding_id} location_repo mismatch")
        binding_selector = binding.get("selector")
        selector_is_within_check = isinstance(binding_selector, str) and (
            binding_selector == check.get("selector")
            or binding_selector.startswith(f"{check.get('selector')}.")
        )
        if not selector_is_within_check:
            errors.append(f"judged binding {binding_id} selector is outside Pack check")
        command_matches = False
        if selector_is_within_check:
            from build_openstack_requirements_pack import _materialize_command_template

            templates_by_id = {
                template["id"]: template
                for template in pack.get("execution_templates", [])
            }
            base_template_id = binding.get("command", {}).get("base_template_id")
            allowed_template_ids = {
                row["template_id"] for row in check.get("execution_bindings", [])
            }
            template = templates_by_id.get(base_template_id)
            command_matches = (
                base_template_id in allowed_template_ids
                and template is not None
                and _materialize_command_template(
                    template["command_template"], binding_selector
                )
                == binding.get("command", {}).get("template")
            )
        if not command_matches:
            errors.append(f"judged binding {binding_id} command differs from Pack check")
        command_provenance = binding.get("command", {}).get("provenance", {})
        if command_provenance.get("repository") != check["location_repo"]:
            errors.append(f"judged binding {binding_id} command provenance repo mismatch")
        if not binding.get("relation_id"):
            errors.append(f"judged binding {binding_id} lacks relation_id")
        if not binding.get("mechanism"):
            errors.append(f"judged binding {binding_id} lacks mechanism")
        semantic_ref = binding.get("semantic_adjudication_ref") or binding.get(
            "semantic_review_ref"
        )
        if package_root is not None and semantic_ref:
            _read_json_artifact(
                package_root,
                semantic_ref,
                f"judged binding {binding_id} semantic adjudication",
                errors,
            )
        signature = binding.get("failure_signature", {})
        if (
            not signature.get("value")
            or signature.get("exclusive_to") != "A1"
            or not signature.get("artifact_refs")
        ):
            errors.append(f"judged binding {binding_id} lacks an A1-exclusive signature")
        repair = binding.get("target_repair", {})
        if (
            repair.get("repository") != check["location_repo"]
            or repair.get("change_id") in {None, ""}
            or not repair.get("patch_ref")
        ):
            errors.append(f"judged binding {binding_id} target repair is incomplete")

        arms = binding.get("arms", {})
        if set(arms) != {"A0", "A1", "A2"}:
            errors.append(f"judged binding {binding_id} must define A0, A1, and A2")
            continue
        expected_status = {"A0": "pass", "A1": "fail", "A2": "pass"}
        expected_source_versions = _exact_source_versions(
            public, route["dependency_key"]
        )
        for arm_id, status in expected_status.items():
            arm = arms[arm_id]
            if arm.get("status") != status:
                errors.append(
                    f"judged binding {binding_id} {arm_id} must have status {status}"
                )
            exit_code = arm.get("exit_code")
            if status == "pass" and exit_code != 0:
                errors.append(f"judged binding {binding_id} {arm_id} must exit 0")
            if status == "fail" and (not isinstance(exit_code, int) or exit_code == 0):
                errors.append(f"judged binding {binding_id} {arm_id} must exit nonzero")

            summary_ref = arm.get("summary_ref")
            command_log_ref = arm.get("command_log_ref")
            if not summary_ref or not command_log_ref:
                errors.append(
                    f"judged binding {binding_id} {arm_id} lacks structured artifact refs"
                )
            if package_root is None or not summary_ref or not command_log_ref:
                continue
            summary = _read_json_artifact(
                package_root,
                summary_ref,
                f"judged binding {binding_id} {arm_id} summary",
                errors,
            )
            log = _read_text_artifact(
                package_root,
                command_log_ref,
                f"judged binding {binding_id} {arm_id} command log",
                errors,
            )
            if summary is not None:
                if summary.get("arm") != arm_id:
                    errors.append(
                        f"judged binding {binding_id} {arm_id} summary arm mismatch"
                    )
                if summary.get("exit_code") != exit_code:
                    errors.append(
                        f"judged binding {binding_id} {arm_id} summary exit mismatch"
                    )
                summary_command = summary.get("command")
                if not isinstance(summary_command, list) or not all(
                    isinstance(part, str) for part in summary_command
                ):
                    errors.append(
                        f"judged binding {binding_id} {arm_id} summary command is invalid"
                    )
                elif " ".join(summary_command) != binding["command"].get("template"):
                    errors.append(
                        f"judged binding {binding_id} {arm_id} summary command mismatch"
                    )
                check_count = arm.get("check_count")
                if check_count is not None:
                    if not isinstance(check_count, int) or check_count <= 0:
                        errors.append(
                            f"judged binding {binding_id} {arm_id} check_count is invalid"
                        )
                    if summary.get("check_count") != check_count:
                        errors.append(
                            f"judged binding {binding_id} {arm_id} summary check_count mismatch"
                        )
                installed_version = arm.get("installed_source_version")
                if installed_version is not None:
                    if (
                        not isinstance(installed_version, str)
                        or not installed_version
                        or summary.get("installed_source_version") != installed_version
                    ):
                        errors.append(
                            f"judged binding {binding_id} {arm_id} installed source version mismatch"
                        )
                    if (
                        expected_source_versions is not None
                        and installed_version != expected_source_versions[arm_id]
                    ):
                        errors.append(
                            f"judged binding {binding_id} {arm_id} installed source version differs from source patch"
                        )
            if log is not None:
                signature_value = signature.get("value", "")
                expected_presence = arm_id == "A1"
                if bool(signature_value in log) != expected_presence:
                    errors.append(
                        f"judged binding {binding_id} signature exclusivity failed in {arm_id}"
                    )
                check_count = arm.get("check_count")
                if check_count is not None and _check_count(log) != check_count:
                    errors.append(
                        f"judged binding {binding_id} {arm_id} command log check_count mismatch"
                    )

            actual_command_ref = arm.get("actual_command_ref")
            if package_root is not None and actual_command_ref:
                actual_command = _read_json_artifact(
                    package_root,
                    actual_command_ref,
                    f"judged binding {binding_id} {arm_id} actual command",
                    errors,
                )
                if actual_command is not None:
                    recorded = actual_command.get("recorded_command")
                    if (
                        not isinstance(recorded, list)
                        or not all(isinstance(part, str) for part in recorded)
                        or " ".join(recorded) != binding["command"].get("template")
                    ):
                        errors.append(
                            f"judged binding {binding_id} {arm_id} actual command mismatch"
                        )

        if package_root is not None and repair.get("patch_ref"):
            patch = _read_text_artifact(
                package_root,
                repair["patch_ref"],
                f"judged binding {binding_id} target repair patch",
                errors,
            )
            if patch is not None and not patch.strip():
                errors.append(f"judged binding {binding_id} target repair patch is empty")
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument(
        "--package-root",
        type=Path,
        help="read arm summaries, command logs, and repair patch from this directory",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pack = json.loads(args.pack.read_text(encoding="utf-8"))
    case = json.loads(args.case.read_text(encoding="utf-8"))
    errors = verification_errors(pack, case, args.package_root)
    print(
        json.dumps(
            {
                "valid": not errors,
                "artifact_verification": (
                    "performed" if args.package_root is not None else "not_requested"
                ),
                "errors": errors,
            },
            indent=2,
        )
    )
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

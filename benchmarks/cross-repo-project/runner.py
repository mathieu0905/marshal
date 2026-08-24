#!/usr/bin/env python3
"""校验、准备并运行项目级跨仓评测数据。"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "index.jsonl"
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class DatasetError(RuntimeError):
    pass


def load_projects(index_path: Path = INDEX) -> list[dict[str, Any]]:
    projects: list[dict[str, Any]] = []
    seen: set[str] = set()
    root = index_path.resolve().parent
    for line_number, raw in enumerate(index_path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        entry = json.loads(raw)
        path = (root / entry["path"]).resolve()
        if root not in path.parents:
            raise DatasetError(f"索引第 {line_number} 行指向数据集目录之外")
        project = json.loads(path.read_text(encoding="utf-8"))
        if entry["project_id"] != project.get("project_id"):
            raise DatasetError(f"索引与 {path.name} 的 project_id 不一致")
        if entry["split"] != project.get("split"):
            raise DatasetError(f"索引与 {path.name} 的 split 不一致")
        if entry["project_id"] in seen:
            raise DatasetError(f"项目标识重复：{entry['project_id']}")
        seen.add(entry["project_id"])
        projects.append(project)
    if not projects:
        raise DatasetError("索引中没有项目")
    return projects


def require(mapping: dict[str, Any], keys: tuple[str, ...], location: str) -> None:
    missing = [key for key in keys if key not in mapping]
    if missing:
        raise DatasetError(f"{location} 缺少字段：{', '.join(missing)}")


def validate_repository(repository: dict[str, Any], location: str) -> None:
    require(
        repository,
        ("full_name", "url", "license", "license_file", "prepare_commands"),
        location,
    )
    full_name = repository["full_name"]
    if full_name.count("/") != 1 or any(not part for part in full_name.split("/")):
        raise DatasetError(f"{location}.full_name 必须是完整的 owner/repo")
    commands = repository["prepare_commands"]
    require(commands, ("clone", "checkout"), f"{location}.prepare_commands")
    for name in ("clone", "checkout"):
        if not isinstance(commands[name], list) or not commands[name]:
            raise DatasetError(f"{location}.prepare_commands.{name} 必须是非空参数数组")


def validate_projects(projects: list[dict[str, Any]]) -> dict[str, int]:
    case_ids: set[str] = set()
    repository_names: set[str] = set()
    scenario_count = 0
    for project in projects:
        project_id = project.get("project_id", "<unknown>")
        require(
            project,
            (
                "schema_version",
                "project_id",
                "title",
                "split",
                "scenario_kind",
                "source",
                "provider",
                "consumers",
            ),
            project_id,
        )
        if project["schema_version"] != "1.0":
            raise DatasetError(f"{project_id} 使用了不支持的格式版本")
        if not ID_PATTERN.fullmatch(project_id):
            raise DatasetError(f"项目标识不合法：{project_id}")
        if project["split"] not in {"train", "development", "test"}:
            raise DatasetError(f"{project_id}.split 不合法")
        source = project["source"]
        require(source, ("dataset", "dataset_repository", "dataset_revision", "license"), f"{project_id}.source")
        if not SHA_PATTERN.fullmatch(source["dataset_revision"]):
            raise DatasetError(f"{project_id}.source.dataset_revision 不是完整 Git 提交")

        provider = project["provider"]
        require(provider, ("repository", "artifact", "variants", "change"), f"{project_id}.provider")
        validate_repository(provider["repository"], f"{project_id}.provider.repository")
        repository_names.add(provider["repository"]["full_name"])
        variants: set[str] = set()
        for variant in provider["variants"]:
            require(variant, ("variant_id", "version", "git_ref", "git_commit"), f"{project_id}.provider.variant")
            if variant["variant_id"] in variants:
                raise DatasetError(f"{project_id} 的上游版本标识重复：{variant['variant_id']}")
            if not SHA_PATTERN.fullmatch(variant["git_commit"]):
                raise DatasetError(f"{project_id} 的上游 Git 提交不完整")
            variants.add(variant["variant_id"])

        consumers = project["consumers"]
        minimum_consumers = 2 if project["scenario_kind"] == "released_dependency_fanout" else 1
        if not isinstance(consumers, list) or len(consumers) < minimum_consumers:
            raise DatasetError(f"{project_id} 至少需要 {minimum_consumers} 个消费仓")
        for consumer in consumers:
            require(
                consumer,
                ("case_id", "repository", "dependency", "change", "variants", "test", "source_record_url"),
                f"{project_id}.consumer",
            )
            case_id = consumer["case_id"]
            if not ID_PATTERN.fullmatch(case_id) or case_id in case_ids:
                raise DatasetError(f"案例标识不合法或重复：{case_id}")
            case_ids.add(case_id)
            scenario_count += 1
            validate_repository(consumer["repository"], f"{project_id}.{case_id}.repository")
            repository_names.add(consumer["repository"]["full_name"])
            dependency = consumer["dependency"]
            require(
                dependency,
                ("direction", "coordinate", "from_provider_variant", "to_provider_variant", "manifest_path"),
                f"{project_id}.{case_id}.dependency",
            )
            if dependency["direction"] != "provider_to_consumer":
                raise DatasetError(f"{case_id} 的依赖方向不合法")
            if dependency["coordinate"] != provider["artifact"]["coordinate"]:
                raise DatasetError(f"{case_id} 的依赖坐标与上游产物不一致")
            for key in ("from_provider_variant", "to_provider_variant"):
                if dependency[key] not in variants:
                    raise DatasetError(f"{case_id}.{key} 未指向上游版本")
            for variant_name in ("before", "after"):
                state = consumer["variants"].get(variant_name, {})
                require(state, ("git_commit", "expected"), f"{case_id}.{variant_name}")
                if not SHA_PATTERN.fullmatch(state["git_commit"]):
                    raise DatasetError(f"{case_id}.{variant_name}.git_commit 不是完整 Git 提交")
                outcome = state["expected"].get("outcome")
                if outcome not in {"pass", "fail"}:
                    raise DatasetError(f"{case_id}.{variant_name} 的预期结果不合法")
                if outcome == "fail" and not state["expected"].get("failure_category"):
                    raise DatasetError(f"{case_id}.{variant_name} 缺少预期失败类别")
            test = consumer["test"]
            require(test, ("working_directory", "command", "timeout_seconds", "environment"), f"{case_id}.test")
            if not isinstance(test["command"], list) or not test["command"]:
                raise DatasetError(f"{case_id}.test.command 必须是非空参数数组")
            runtime_keys = {"java_major", "node_major"} & set(test["environment"])
            if len(runtime_keys) != 1:
                raise DatasetError(f"{case_id}.test.environment 必须且只能声明一种运行时")
    return {
        "projects": len(projects),
        "consumer_cases": scenario_count,
        "repositories": len(repository_names),
    }


def selected_projects(projects: list[dict[str, Any]], selected: list[str]) -> list[dict[str, Any]]:
    if not selected:
        return projects
    requested = set(selected)
    found = [project for project in projects if project["project_id"] in requested]
    missing = requested - {project["project_id"] for project in found}
    if missing:
        raise DatasetError(f"找不到项目：{', '.join(sorted(missing))}")
    return found


def run_process(
    argv: list[str],
    cwd: Path | None = None,
    timeout: int | None = None,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        env=environment,
        check=False,
    )


def checked(argv: list[str], cwd: Path | None = None, attempts: int = 1) -> str:
    for attempt in range(attempts):
        result = run_process(argv, cwd=cwd)
        if result.returncode == 0:
            return result.stdout
        if attempt + 1 < attempts:
            time.sleep(min(2**attempt, 8))
    raise DatasetError(f"命令失败：{' '.join(argv)}\n{result.stdout[-2000:]}")


def source_path(workspace: Path, full_name: str) -> Path:
    return workspace / "sources" / full_name.replace("/", "__")


def ensure_source(workspace: Path, repository: dict[str, Any]) -> Path:
    path = source_path(workspace, repository["full_name"])
    if path.exists():
        actual = checked(["git", "-C", str(path), "remote", "get-url", "origin"]).strip()
        if actual != repository["url"]:
            raise DatasetError(f"{path} 的远程地址与数据记录不一致")
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    checked(["git", "clone", "--quiet", "--filter=blob:none", "--no-checkout", repository["url"], str(path)])
    return path


def ensure_commit(source: Path, commit: str) -> None:
    exists = run_process(["git", "-C", str(source), "cat-file", "-e", f"{commit}^{{commit}}"])
    if exists.returncode != 0:
        checked(["git", "-C", str(source), "fetch", "--quiet", "origin", commit], attempts=3)
    resolved = checked(["git", "-C", str(source), "rev-parse", f"{commit}^{{commit}}"]).strip()
    if resolved != commit:
        raise DatasetError(f"无法解析 Git 提交：{commit}")


def ensure_worktree(source: Path, target: Path, commit: str) -> None:
    if target.exists():
        actual = checked(["git", "-C", str(target), "rev-parse", "HEAD"]).strip()
        if actual != commit:
            raise DatasetError(f"{target} 已存在，但版本不是 {commit}")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    checked(
        ["git", "-C", str(source), "worktree", "add", "--quiet", "--detach", str(target), commit],
        attempts=3,
    )


def prepare_projects(projects: list[dict[str, Any]], workspace: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for project in projects:
        project_root = workspace / "projects" / project["project_id"]
        provider = project["provider"]
        provider_source = ensure_source(workspace, provider["repository"])
        for variant in provider["variants"]:
            commit = variant["git_commit"]
            ensure_commit(provider_source, commit)
            target = project_root / "provider" / variant["variant_id"]
            ensure_worktree(provider_source, target, commit)
            records.append(
                {
                    "project_id": project["project_id"],
                    "role": "provider",
                    "repository": provider["repository"]["full_name"],
                    "variant": variant["variant_id"],
                    "git_commit": commit,
                    "status": "prepared",
                }
            )
        for consumer in project["consumers"]:
            consumer_source = ensure_source(workspace, consumer["repository"])
            for variant_name in ("before", "after"):
                commit = consumer["variants"][variant_name]["git_commit"]
                ensure_commit(consumer_source, commit)
                target = project_root / "consumers" / consumer["case_id"] / variant_name
                ensure_worktree(consumer_source, target, commit)
                records.append(
                    {
                        "project_id": project["project_id"],
                        "case_id": consumer["case_id"],
                        "role": "consumer",
                        "repository": consumer["repository"]["full_name"],
                        "variant": variant_name,
                        "git_commit": commit,
                        "status": "prepared",
                    }
                )
    write_jsonl(workspace / "prepare-results.jsonl", records)
    return records


def classify_failure(output: str, timed_out: bool) -> str | None:
    if timed_out:
        return "timeout"
    lower = output.lower()
    if "dependencies differ" in lower or "dependency-lock-maven-plugin" in lower and "actual dependencies" in lower:
        return "dependency_lock_failure"
    if "compilation error" in lower or "compilation failure" in lower or "cannot find symbol" in lower or "class file for" in lower and "not found" in lower:
        return "compilation_failure"
    if "there are test failures" in lower or re.search(r"tests run: .* (failures|errors): [1-9]", lower):
        return "test_failure"
    return "unclassified_failure"


def java_environment(major: str) -> dict[str, str]:
    candidates = [
        os.environ.get(f"JAVA_HOME_{major}"),
        os.environ.get(f"JDK_{major}_HOME"),
        f"/usr/lib/jvm/java-{major}-openjdk-amd64",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        java_home = Path(candidate)
        java = java_home / "bin" / "java"
        if not java.is_file():
            continue
        result = run_process([str(java), "-version"], timeout=30)
        first_line = result.stdout.splitlines()[0] if result.stdout else ""
        if result.returncode == 0 and re.search(rf' version "{re.escape(major)}(?:[.\"]|$)', first_line):
            environment = os.environ.copy()
            environment["JAVA_HOME"] = str(java_home)
            environment["PATH"] = f"{java_home / 'bin'}{os.pathsep}{environment.get('PATH', '')}"
            return environment
    raise DatasetError(f"找不到案例要求的 Java {major} 运行时")


def node_environment(major: str) -> dict[str, str]:
    candidates: list[Path] = []
    configured = os.environ.get(f"NODE_HOME_{major}")
    if configured:
        candidates.append(Path(configured) / "bin" / "node")
    current = shutil.which("node")
    if current:
        candidates.append(Path(current))
    candidates.extend(sorted((Path.home() / ".nvm" / "versions" / "node").glob(f"v{major}*/bin/node"), reverse=True))
    for node in candidates:
        if not node.is_file():
            continue
        result = run_process([str(node), "--version"], timeout=30)
        if result.returncode == 0 and re.match(rf"^v{re.escape(major)}(?:\.|$)", result.stdout.strip()):
            environment = os.environ.copy()
            environment["PATH"] = f"{node.parent}{os.pathsep}{environment.get('PATH', '')}"
            return environment
    raise DatasetError(f"找不到案例要求的 Node.js {major} 运行时")


def runtime_environment(specification: dict[str, Any]) -> tuple[str, dict[str, str]]:
    if "java_major" in specification:
        major = specification["java_major"]
        return f"java:{major}", java_environment(major)
    major = specification["node_major"]
    return f"node:{major}", node_environment(major)


def tool_version(argv: list[str], environment: dict[str, str]) -> str:
    try:
        result = run_process(argv, timeout=30, environment=environment)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return "unavailable"
    return result.stdout.splitlines()[0] if result.stdout else "unknown"


def run_projects(
    projects: list[dict[str, Any]], workspace: Path, results_path: Path
) -> tuple[list[dict[str, Any]], int]:
    results: list[dict[str, Any]] = []
    mismatches = 0
    environments: dict[str, tuple[dict[str, str], dict[str, str]]] = {}
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_root = workspace / "logs" / run_id
    for project in projects:
        project_root = workspace / "projects" / project["project_id"]
        for consumer in project["consumers"]:
            for variant_name in ("before", "after"):
                state = consumer["variants"][variant_name]
                test = consumer["test"]
                environment_spec = test["environment"]
                runtime_key, process_environment = runtime_environment(environment_spec)
                if runtime_key not in environments:
                    if runtime_key.startswith("java:"):
                        versions = {
                            "java": tool_version(["java", "-version"], process_environment),
                            "maven": tool_version(["mvn", "-version"], process_environment),
                            "git": tool_version(["git", "--version"], process_environment),
                        }
                    else:
                        versions = {
                            "node": tool_version(["node", "--version"], process_environment),
                            "npm": tool_version(["npm", "--version"], process_environment),
                            "git": tool_version(["git", "--version"], process_environment),
                        }
                    environments[runtime_key] = (
                        process_environment,
                        versions,
                    )
                process_environment, recorded_environment = environments[runtime_key]
                checkout = project_root / "consumers" / consumer["case_id"] / variant_name
                cwd = checkout / test["working_directory"]
                if not cwd.is_dir():
                    raise DatasetError(f"尚未准备运行目录：{cwd}")
                provider_variant = consumer["dependency"][
                    "from_provider_variant" if variant_name == "before" else "to_provider_variant"
                ]
                provider_checkout = project_root / "provider" / provider_variant
                process_environment = process_environment.copy()
                for name, value in environment_spec.get("variables", {}).items():
                    process_environment[name] = value.format(provider_checkout=provider_checkout)
                started = time.monotonic()
                timed_out = False
                try:
                    preparation = None
                    if test.get("prepare_command"):
                        preparation = run_process(
                            test["prepare_command"],
                            cwd=cwd,
                            timeout=test["timeout_seconds"],
                            environment=process_environment,
                        )
                    if preparation is not None and preparation.returncode != 0:
                        completed = preparation
                        output = preparation.stdout
                    else:
                        completed = run_process(
                            test["command"],
                            cwd=cwd,
                            timeout=test["timeout_seconds"],
                            environment=process_environment,
                        )
                        output = (preparation.stdout if preparation is not None else "") + completed.stdout
                    exit_code: int | None = completed.returncode
                except subprocess.TimeoutExpired as exc:
                    timed_out = True
                    exit_code = None
                    output = exc.stdout or ""
                    if isinstance(output, bytes):
                        output = output.decode(errors="replace")
                duration = round(time.monotonic() - started, 3)
                actual_outcome = "pass" if exit_code == 0 else "fail"
                failure_category = None if actual_outcome == "pass" else classify_failure(output, timed_out)
                expected = state["expected"]
                matched = expected["outcome"] == actual_outcome
                if actual_outcome == "fail":
                    matched = matched and expected.get("failure_category") == failure_category
                output_checks = {
                    expected_text: expected_text in output
                    for expected_text in expected.get("output_contains", [])
                }
                matched = matched and all(output_checks.values())
                if not matched:
                    mismatches += 1
                log_path = log_root / project["project_id"] / f"{consumer['case_id']}-{variant_name}.log"
                log_path.parent.mkdir(parents=True, exist_ok=True)
                log_path.write_text(output, encoding="utf-8")
                results.append(
                    {
                        "schema_version": "1.0",
                        "run_id": run_id,
                        "project_id": project["project_id"],
                        "case_id": consumer["case_id"],
                        "repository": consumer["repository"]["full_name"],
                        "variant": variant_name,
                        "git_commit": state["git_commit"],
                        "provider_variant": provider_variant,
                        "execution_mode": project["scenario_kind"],
                        "command": test["command"],
                        "expected": expected,
                        "actual": {
                            "outcome": actual_outcome,
                            "exit_code": exit_code,
                            "failure_category": failure_category,
                            "timed_out": timed_out,
                            "output_checks": output_checks,
                        },
                        "matched": matched,
                        "duration_seconds": duration,
                        "environment": recorded_environment,
                        "log_path": str(log_path.relative_to(workspace)),
                    }
                )
                write_jsonl(results_path, results)
    return results, mismatches


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records)
    path.write_text(text, encoding="utf-8")


def assert_fresh_workspace(workspace: Path) -> None:
    if workspace.exists() and any(workspace.iterdir()):
        raise DatasetError(f"端到端运行要求空目录：{workspace}")
    workspace.mkdir(parents=True, exist_ok=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Marshal 项目级跨仓评测数据工具")
    parser.add_argument("--index", type=Path, default=INDEX, help="数据索引")
    subparsers = parser.add_subparsers(dest="action", required=True)
    subparsers.add_parser("validate", help="校验数据格式和跨记录关系")
    for name in ("prepare", "run", "all"):
        command = subparsers.add_parser(name)
        command.add_argument("--workspace", type=Path, required=True)
        command.add_argument("--project", action="append", default=[])
        if name in {"run", "all"}:
            command.add_argument("--results", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        projects = load_projects(args.index)
        counts = validate_projects(projects)
        if args.action == "validate":
            print(json.dumps({"status": "valid", **counts}, ensure_ascii=False))
            return 0
        projects = selected_projects(projects, args.project)
        workspace = args.workspace.resolve()
        if args.action == "all":
            assert_fresh_workspace(workspace)
            prepare_projects(projects, workspace)
            results, mismatches = run_projects(projects, workspace, args.results.resolve())
            print(json.dumps({"status": "finished", "results": len(results), "mismatches": mismatches}, ensure_ascii=False))
            return 1 if mismatches else 0
        if args.action == "prepare":
            records = prepare_projects(projects, workspace)
            print(json.dumps({"status": "prepared", "records": len(records)}, ensure_ascii=False))
            return 0
        results, mismatches = run_projects(projects, workspace, args.results.resolve())
        print(json.dumps({"status": "finished", "results": len(results), "mismatches": mismatches}, ensure_ascii=False))
        return 1 if mismatches else 0
    except (DatasetError, OSError, json.JSONDecodeError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

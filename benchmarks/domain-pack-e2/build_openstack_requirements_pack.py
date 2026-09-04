#!/usr/bin/env python3
"""Materialize a project-level OpenStack requirements Domain Pack.

The generator is deliberately event- and outcome-independent.  It reads
``projects.txt`` and the dependency catalogs from the requirements snapshot visible
when a source change opens, plus candidate repositories at their observation
cutoffs.  It does not accept a source event, an impacted-repository label,
replay output, failure signature, or repair patch.
"""

from __future__ import annotations

import argparse
import ast
import configparser
import json
import re
import subprocess
import tomllib
import warnings
from collections import defaultdict
from collections import deque
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "domain-pack-e2-1"
GENERATOR_ID = "openstack-requirements-project-pack"
GENERATOR_VERSION = "1.4.0"
SOURCE_REQUIREMENTS_PATHS = frozenset(
    {"global-requirements.txt", "upper-constraints.txt"}
)

_DISTRIBUTION_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9_.-]*[A-Za-z0-9])?")
_PROJECT_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_TEST_RUNNER_RE = re.compile(
    r"(?:^|\s)(?:stestr|pytest|ostestr|nosetests|python\s+-m\s+unittest|"
    r"(?:bash\s+)?[^\s]*tools/(?:unit_)?tests?\.sh|[^\s]*manage\.py\s+test)(?:\s|$)"
)
_PYTHON_REFERENCE_RE = re.compile(r"^([A-Za-z_]\w*)(?:\.|$)")
_NON_PACKAGE_ROOTS = {
    "doc",
    "docs",
    "examples",
    "playbooks",
    "releasenotes",
    "roles",
    "test",
    "tests",
    "tools",
}


class BuildError(ValueError):
    """Raised when public, cutoff-time inputs cannot form a materialization."""


def _git(git_dir: Path, *args: str) -> str:
    process = subprocess.run(
        ["git", f"--git-dir={git_dir}", *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if process.returncode:
        detail = process.stderr.strip() or process.stdout.strip()
        raise BuildError(f"git {' '.join(args)} failed for {git_dir}: {detail}")
    return process.stdout


def _show(git_dir: Path, commit: str, path: str) -> str:
    return _git(git_dir, "show", f"{commit}:{path}")


def _show_many(git_dir: Path, commit: str, paths: list[str]) -> dict[str, str]:
    """Read many blobs through one cat-file process instead of one Git per file."""

    process = subprocess.Popen(
        ["git", f"--git-dir={git_dir}", "cat-file", "--batch"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if process.stdin is None or process.stdout is None:
        process.kill()
        raise BuildError(f"could not open git cat-file pipes for {git_dir}")
    contents: dict[str, str] = {}
    try:
        for path in paths:
            process.stdin.write(f"{commit}:{path}\n".encode())
            process.stdin.flush()
            header = process.stdout.readline().decode("utf-8", errors="replace").strip()
            fields = header.rsplit(" ", 2)
            if len(fields) != 3 or fields[1] != "blob" or not fields[2].isdigit():
                raise BuildError(f"git cat-file failed for {commit}:{path}: {header}")
            size = int(fields[2])
            blob = process.stdout.read(size)
            if process.stdout.read(1) != b"\n":
                raise BuildError(f"git cat-file framing failed for {commit}:{path}")
            contents[path] = blob.decode("utf-8", errors="replace")
    finally:
        process.stdin.close()
        return_code = process.wait()
    if return_code:
        detail = process.stderr.read().decode("utf-8", errors="replace").strip()
        raise BuildError(f"git cat-file failed for {git_dir}: {detail}")
    return contents


def _paths(git_dir: Path, commit: str) -> list[str]:
    output = _git(git_dir, "ls-tree", "-r", "--name-only", commit)
    return sorted(path for path in output.splitlines() if path)


def _canonical_distribution(value: str) -> str:
    return re.sub(r"[-_.]+", "_", value).lower()


def _safe_id(value: str) -> str:
    return re.sub(r"[^a-z0-9_.-]+", "_", value.lower()).strip("_")


def _source_requirement_kind(path: str) -> str:
    if path == "global-requirements.txt":
        return "global-requirements"
    if path == "upper-constraints.txt":
        return "upper-constraints"
    raise BuildError(f"unsupported requirements source path: {path}")


def _requirement_entries(text: str, path: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith(("#", "-", "http://", "https://")):
            continue
        match = _DISTRIBUTION_RE.match(stripped)
        if not match:
            continue
        distribution = match.group(0)
        remainder = stripped[match.end() :].strip()
        if remainder.startswith("["):
            closing = remainder.find("]")
            if closing < 0:
                continue
            remainder = remainder[closing + 1 :].strip()
        specifier = remainder.split("#", 1)[0].strip()
        entries.append(
            {
                "distribution": distribution,
                "key": _canonical_distribution(distribution),
                "specifier": specifier,
                "path": path,
                "line": line_number,
            }
        )
    return entries


def _project_members(source: dict[str, Any]) -> dict[str, int]:
    """Parse the requirements contract universe from cutoff ``projects.txt``."""

    path = source["projects_path"]
    text = _show(Path(source["git_dir"]), source["commit"], path)
    members: dict[str, int] = {}
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        repository = raw_line.strip()
        if not repository or repository.startswith("#"):
            continue
        if not _PROJECT_REPOSITORY_RE.fullmatch(repository):
            raise BuildError(
                f"invalid projects.txt repository at {path}:{line_number}: "
                f"{repository!r}"
            )
        if repository in members:
            raise BuildError(
                f"duplicate projects.txt repository at {path}:{line_number}: "
                f"{repository}"
            )
        members[repository] = line_number
    if not members:
        raise BuildError("source-opening projects.txt yielded no candidate repositories")
    return members


def _python_analysis(text: str) -> tuple[set[str], set[str], set[str]]:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return set(), set(), set()
    imported_modules: set[str] = set()
    string_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
            imported_modules.update(
                f"{node.module}.{alias.name}"
                for alias in node.names
                if alias.name != "*"
            )
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            match = _PYTHON_REFERENCE_RE.match(node.value)
            if match:
                string_roots.add(_canonical_distribution(match.group(1)))
    import_roots = {
        _canonical_distribution(module.split(".", 1)[0])
        for module in imported_modules
    }
    return imported_modules, import_roots, string_roots


def _python_imports(text: str) -> set[str]:
    """Compatibility wrapper retained for focused unit callers."""

    return _python_analysis(text)[1]


def _is_collectable_test_module(path: str) -> bool:
    filename = path.rsplit("/", 1)[-1]
    return (
        filename == "tests.py"
        or filename.startswith("test_")
        or filename.endswith("_test.py")
    )


def _test_selector(path: str) -> str:
    module = path[:-3].replace("/", ".")
    return module[:-9] if module.endswith(".__init__") else module


def _module_name(path: str) -> str:
    module = path[:-3].replace("/", ".")
    return module[:-9] if module.endswith(".__init__") else module


def _is_requirement_path(path: str) -> bool:
    filename = path.rsplit("/", 1)[-1]
    return (
        filename == "requirements.txt"
        or filename.endswith("-requirements.txt")
        or ("/requirements/" in f"/{path}" and filename.endswith(".txt"))
    )


def _tox_commands(text: str) -> list[dict[str, Any]]:
    parser = configparser.RawConfigParser(strict=False)
    try:
        parser.read_string(text)
    except configparser.Error:
        return []
    commands: list[dict[str, Any]] = []
    for section in parser.sections():
        if section != "testenv" and not section.startswith("testenv:"):
            continue
        if not parser.has_option(section, "commands"):
            continue
        value = parser.get(section, "commands", raw=True)
        for index, raw_command in enumerate(value.splitlines(), start=1):
            command = raw_command.strip()
            if not command or command.startswith("#"):
                continue
            commands.append(
                {
                    "section": section,
                    "index": index,
                    "command_template": command,
                    "supports_posargs": "{posargs}" in command,
                    "kind": "test" if _TEST_RUNNER_RE.search(command) else "task",
                }
            )
    return commands


def _materialize_command_template(command: str, selector: str) -> str:
    materialized = command.replace("{posargs}", selector)
    materialized = materialized.replace("{envpython}", "python")
    materialized = materialized.replace("{toxinidir}/", "")
    materialized = materialized.replace("{toxinidir}", ".")
    return materialized


def _target_identity(config: dict[str, Any]) -> dict[str, Any]:
    repository = config["repository"]
    git_dir = Path(config["git_dir"])
    commit = config["commit"]
    paths = _paths(git_dir, commit)
    metadata_paths = [
        path for path in ("setup.cfg", "pyproject.toml", "setup.py") if path in paths
    ]
    contents = _show_many(git_dir, commit, metadata_paths)
    distributions: set[str] = set()

    setup_cfg = contents.get("setup.cfg")
    if setup_cfg:
        parser = configparser.RawConfigParser(strict=False)
        try:
            parser.read_string(setup_cfg)
            if parser.has_option("metadata", "name"):
                distributions.add(
                    _canonical_distribution(parser.get("metadata", "name").strip())
                )
        except configparser.Error:
            pass

    pyproject = contents.get("pyproject.toml")
    if pyproject:
        try:
            project = tomllib.loads(pyproject).get("project", {})
            if isinstance(project.get("name"), str):
                distributions.add(_canonical_distribution(project["name"]))
        except (tomllib.TOMLDecodeError, TypeError):
            pass

    setup_py = contents.get("setup.py", "")
    setup_name = re.search(r"\bname\s*=\s*['\"]([^'\"]+)['\"]", setup_py)
    if setup_name:
        distributions.add(_canonical_distribution(setup_name.group(1)))

    package_roots = {
        _canonical_distribution(path.split("/", 1)[0])
        for path in paths
        if path.count("/") >= 1
        and path.endswith("/__init__.py")
        and path.split("/", 1)[0] not in _NON_PACKAGE_ROOTS
        and not path.split("/", 1)[0].startswith(".")
    }
    return {
        "repository": repository,
        "commit": commit,
        "distributions": sorted(distributions),
        "package_roots": sorted(package_roots),
    }


def _target_scan(
    config: dict[str, Any],
    constraint_keys: set[str],
    import_aliases: dict[str, set[str]] | None = None,
) -> dict[str, Any]:
    repository = config["repository"]
    git_dir = Path(config["git_dir"])
    commit = config["commit"]
    paths = _paths(git_dir, commit)
    content_paths = sorted(
        path
        for path in paths
        if path.endswith(".py") or _is_requirement_path(path) or path == "tox.ini"
    )
    contents = _show_many(git_dir, commit, content_paths)

    declarations: dict[str, list[dict[str, Any]]] = defaultdict(list)
    import_aliases = import_aliases or {key: {key} for key in constraint_keys}
    import_surfaces: dict[str, list[dict[str, Any]]] = defaultdict(list)
    string_surfaces: dict[str, list[dict[str, Any]]] = defaultdict(list)
    test_surfaces: dict[str, list[dict[str, Any]]] = defaultdict(list)
    analyses: dict[str, tuple[set[str], set[str], set[str]]] = {}
    direct_dependencies: dict[str, set[str]] = defaultdict(set)
    direct_kinds: dict[tuple[str, str], str] = {}

    for path in paths:
        if _is_requirement_path(path):
            for entry in _requirement_entries(contents[path], path):
                if entry["key"] in constraint_keys:
                    declarations[entry["key"]].append(
                        {
                            "path": path,
                            "line": entry["line"],
                            "distribution": entry["distribution"],
                            "specifier": entry["specifier"],
                        }
                    )
        if path.endswith(".py"):
            analysis = _python_analysis(contents[path])
            analyses[path] = analysis
            imported_modules, import_roots, string_roots = analysis
            del imported_modules
            import_keys = {
                key for root in import_roots for key in import_aliases.get(root, set())
            }
            string_keys = {
                key for root in string_roots for key in import_aliases.get(root, set())
            }
            for key in import_keys:
                surface = {"path": path, "kind": "direct_python_import"}
                import_surfaces[key].append(surface)
                direct_dependencies[path].add(key)
                direct_kinds[(path, key)] = "direct_python_import"
            for key in string_keys - import_keys:
                surface = {"path": path, "kind": "python_string_reference"}
                string_surfaces[key].append(surface)
                direct_dependencies[path].add(key)
                direct_kinds[(path, key)] = "python_string_reference"

    module_paths = {
        _module_name(path): path for path in analyses
    }
    edges: dict[str, set[str]] = defaultdict(set)
    reverse_edges: dict[str, set[str]] = defaultdict(set)
    for path, (imported_modules, _, _) in analyses.items():
        for imported_module in imported_modules:
            candidate = imported_module
            while candidate:
                imported_path = module_paths.get(candidate)
                if imported_path is not None and imported_path != path:
                    edges[path].add(imported_path)
                    reverse_edges[imported_path].add(path)
                    break
                candidate = candidate.rpartition(".")[0]

    reachable_dependencies = {
        path: set(keys) for path, keys in direct_dependencies.items()
    }
    queue = deque(sorted(reachable_dependencies))
    while queue:
        dependency_path = queue.popleft()
        dependency_keys = reachable_dependencies[dependency_path]
        for importer in sorted(reverse_edges.get(dependency_path, set())):
            before = len(reachable_dependencies.setdefault(importer, set()))
            reachable_dependencies[importer].update(dependency_keys)
            if len(reachable_dependencies[importer]) != before:
                queue.append(importer)

    def evidence_path(test_path: str, dependency_key: str) -> tuple[str, list[str]]:
        if dependency_key in direct_dependencies.get(test_path, set()):
            return direct_kinds[(test_path, dependency_key)], [test_path]
        pending: deque[tuple[str, list[str]]] = deque([(test_path, [test_path])])
        visited = {test_path}
        while pending:
            current, chain = pending.popleft()
            for imported_path in sorted(edges.get(current, set())):
                if imported_path in visited:
                    continue
                next_chain = [*chain, imported_path]
                if dependency_key in direct_dependencies.get(imported_path, set()):
                    return "transitive_python_import", next_chain
                visited.add(imported_path)
                pending.append((imported_path, next_chain))
        return "transitive_python_import", [test_path]

    for path in sorted(analyses):
        if not _is_collectable_test_module(path):
            continue
        for key in sorted(reachable_dependencies.get(path, set())):
            kind, chain = evidence_path(path, key)
            test_surfaces[key].append(
                {
                    "path": path,
                    "kind": kind,
                    "selector": _test_selector(path),
                    "collection_rule": "python-test-filename-v1",
                    "reference_chain": chain,
                }
            )

    execution_templates: list[dict[str, Any]] = []
    ci_sources: list[str] = []
    if "tox.ini" in paths:
        ci_sources.append("tox.ini")
        for command in _tox_commands(contents["tox.ini"]):
            template_id = (
                f"command.tox.{_safe_id(repository.replace('/', '__'))}."
                f"{_safe_id(command['section'])}.{command['index']}"
            )
            execution_templates.append(
                {
                    "id": template_id,
                    "location_repo": repository,
                    "kind": "tox-command-template",
                    "definition": {
                        "path": "tox.ini",
                        "section": command["section"],
                        "command_index": command["index"],
                    },
                    "command_template": command["command_template"],
                    "command_kind": command["kind"],
                    "supports_posargs": command["supports_posargs"],
                    "provenance": {
                        "repository": repository,
                        "commit": commit,
                        "path": "tox.ini",
                        "section": command["section"],
                        "command_index": command["index"],
                    },
                }
            )
    for path in (".zuul.yaml", "zuul.yaml"):
        if path in paths:
            ci_sources.append(path)

    return {
        "repository": repository,
        "commit": commit,
        "declarations": declarations,
        "import_surfaces": import_surfaces,
        "string_surfaces": string_surfaces,
        "test_surfaces": test_surfaces,
        "execution_templates": execution_templates,
        "ci_sources": sorted(ci_sources),
    }


def _load_snapshot_manifest(config: dict[str, Any]) -> tuple[str, dict[str, dict[str, Any]]]:
    if config.get("format") != "project-snapshots-json":
        raise BuildError(f"unsupported snapshot manifest format: {config.get('format')}")
    payload = json.loads(Path(config["path"]).read_text(encoding="utf-8"))
    cutoff = payload.get("observation_cutoff")
    rows = payload.get("repositories")
    if not isinstance(cutoff, str) or not cutoff:
        raise BuildError("snapshot manifest must declare observation_cutoff")
    if not isinstance(rows, list):
        raise BuildError("snapshot manifest must contain a repositories list")
    snapshots: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("repository"), str):
            raise BuildError(f"invalid snapshot manifest row: {row!r}")
        repository = row["repository"]
        if repository in snapshots:
            raise BuildError(f"duplicate repository in snapshot manifest: {repository}")
        status = row.get("status")
        if status not in {
            "available",
            "not_assessed",
            "not_created_by_cutoff",
            "unavailable",
        }:
            raise BuildError(f"invalid snapshot status for {repository}: {status!r}")
        if status == "available" and not row.get("commit"):
            raise BuildError(f"available snapshot for {repository} requires commit")
        if bool(row.get("git_dir")) != bool(row.get("materialize", False)):
            raise BuildError(
                f"snapshot {repository} must provide git_dir exactly when materialize is true"
            )
        snapshots[repository] = row
    return cutoff, snapshots


def _validate_spec(spec: dict[str, Any]) -> None:
    for key in (
        "pack_family_id",
        "pack_revision_id",
        "project",
        "source",
        "snapshot_manifest",
    ):
        if key not in spec:
            raise BuildError(f"missing build specification field: {key}")
    if spec["project"] != "openstack":
        raise BuildError("this generator only materializes the OpenStack project domain")
    source = spec["source"]
    for key in (
        "repository",
        "git_dir",
        "commit",
        "projects_path",
        "constraints_paths",
    ):
        if key not in source:
            raise BuildError(f"missing source field: {key}")
    if source["repository"] != "openstack/requirements":
        raise BuildError("source.repository must be openstack/requirements")
    constraint_paths = source["constraints_paths"]
    if (
        not isinstance(constraint_paths, list)
        or not constraint_paths
        or not all(isinstance(path, str) and path for path in constraint_paths)
        or len(set(constraint_paths)) != len(constraint_paths)
    ):
        raise BuildError(
            "source.constraints_paths must be a non-empty unique string list"
        )
    unsupported_paths = set(constraint_paths) - SOURCE_REQUIREMENTS_PATHS
    if unsupported_paths:
        raise BuildError(
            "source.constraints_paths contains unsupported requirements path(s): "
            + ", ".join(sorted(unsupported_paths))
        )
    authoring_case_ids = spec.get("authoring_case_ids", [])
    if not isinstance(authoring_case_ids, list) or not all(
        isinstance(case_id, str) and case_id for case_id in authoring_case_ids
    ):
        raise BuildError("authoring_case_ids must be a list of non-empty strings")
    snapshot_manifest = spec["snapshot_manifest"]
    for key in ("path", "format"):
        if key not in snapshot_manifest:
            raise BuildError(f"missing snapshot_manifest field: {key}")
    scan_workers = spec.get("scan_workers", 1)
    if not isinstance(scan_workers, int) or not 1 <= scan_workers <= 32:
        raise BuildError("scan_workers must be an integer between 1 and 32")


def build_pack(spec: dict[str, Any]) -> dict[str, Any]:
    _validate_spec(spec)
    source = spec["source"]
    member_lines = _project_members(source)
    members = set(member_lines)
    observation_cutoff, manifest_snapshots = _load_snapshot_manifest(spec["snapshot_manifest"])

    constraints: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in sorted(set(source["constraints_paths"])):
        text = _show(Path(source["git_dir"]), source["commit"], path)
        for entry in _requirement_entries(text, path):
            constraints[entry["key"]].append(entry)
    if not constraints:
        raise BuildError("constraints snapshots yielded no dependency entries")

    target_configs: dict[str, dict[str, Any]] = {}
    for repository in sorted(members):
        target = manifest_snapshots.get(repository)
        if target and target["status"] == "available" and target.get("materialize"):
            target_configs[repository] = target

    materialization_complete = all(
        repository in manifest_snapshots
        and (
            manifest_snapshots[repository]["status"]
            in {"not_created_by_cutoff", "unavailable"}
            or (
                manifest_snapshots[repository]["status"] == "available"
                and manifest_snapshots[repository].get("materialize") is True
            )
        )
        for repository in members
    )

    target_rows = [target_configs[repository] for repository in sorted(target_configs)]
    with ThreadPoolExecutor(max_workers=spec.get("scan_workers", 1)) as executor:
        identities = list(executor.map(_target_identity, target_rows))

    alias_claims: dict[str, set[str]] = defaultdict(set)
    alias_providers: dict[tuple[str, str], set[str]] = defaultdict(set)
    for identity in identities:
        for distribution in identity["distributions"]:
            if distribution not in constraints:
                continue
            for root in identity["package_roots"]:
                alias_claims[root].add(distribution)
                alias_providers[(distribution, root)].add(identity["repository"])
    import_aliases: dict[str, set[str]] = {
        key: {key} for key in constraints
    }
    for root, dependency_keys in alias_claims.items():
        if len(dependency_keys) == 1:
            import_aliases.setdefault(root, set()).update(dependency_keys)

    with ThreadPoolExecutor(max_workers=spec.get("scan_workers", 1)) as executor:
        scans = list(
            executor.map(
                lambda target: _target_scan(
                    target,
                    set(constraints),
                    import_aliases,
                ),
                target_rows,
            )
        )

    execution_templates: dict[str, dict[str, Any]] = {}
    checks: dict[str, dict[str, Any]] = {}
    for scan in scans:
        for template in scan["execution_templates"]:
            execution_templates[template["id"]] = template
        for key, surfaces in scan["test_surfaces"].items():
            for surface in surfaces:
                check_id = (
                    f"python-test.{_safe_id(scan['repository'].replace('/', '__'))}."
                    f"{_safe_id(surface['selector'])}"
                )
                bindings = [
                    {
                        "template_id": template["id"],
                        "placeholder": "{posargs}",
                        "value": surface["selector"],
                    }
                    for template in scan["execution_templates"]
                    if template["supports_posargs"]
                    and template["command_kind"] == "test"
                ]
                if not bindings:
                    continue
                checks[check_id] = {
                    "id": check_id,
                    "location_repo": scan["repository"],
                    "kind": "python-test-module",
                    "definition": {
                        "path": surface["path"],
                        "collection_rule": surface["collection_rule"],
                    },
                    "selector": surface["selector"],
                    "execution_bindings": bindings,
                }

    routes: list[dict[str, Any]] = []
    for dependency_key in sorted(constraints):
        repositories: list[dict[str, Any]] = []
        dependency_provider_repositories = {
            repository
            for (provided_dependency, _), provider_repositories in alias_providers.items()
            if provided_dependency == dependency_key
            for repository in provider_repositories
        }
        for scan in scans:
            if scan["repository"] == source["repository"]:
                continue
            if scan["repository"] in dependency_provider_repositories:
                continue
            declarations = sorted(
                scan["declarations"].get(dependency_key, []),
                key=lambda row: (row["path"], row["line"]),
            )
            imports = sorted(
                scan["import_surfaces"].get(dependency_key, []),
                key=lambda row: row["path"],
            )
            string_references = sorted(
                scan["string_surfaces"].get(dependency_key, []),
                key=lambda row: row["path"],
            )
            focused_surfaces = sorted(
                scan["test_surfaces"].get(dependency_key, []),
                key=lambda row: row["path"],
            )
            if not declarations and not imports and not string_references:
                continue
            focused_check_ids = sorted(
                {
                    f"python-test.{_safe_id(scan['repository'].replace('/', '__'))}."
                    f"{_safe_id(surface['selector'])}"
                    for surface in focused_surfaces
                    if (
                        f"python-test.{_safe_id(scan['repository'].replace('/', '__'))}."
                        f"{_safe_id(surface['selector'])}"
                    )
                    in checks
                }
            )
            resolution = (
                {"status": "available"}
                if focused_check_ids
                else {
                    "status": "unresolved",
                    "reason": "no_collectable_direct_import_test_with_cutoff_command",
                }
            )
            repositories.append(
                {
                    "repository": scan["repository"],
                    "consumption_evidence": {
                        "dependency_declarations": declarations,
                        "direct_python_imports": imports,
                        "python_string_references": string_references,
                        "focused_check_derivation_counts": dict(
                            sorted(Counter(row["kind"] for row in focused_surfaces).items())
                        ),
                    },
                    "focused_check_ids": focused_check_ids,
                    "check_resolution": resolution,
                }
            )
        if not repositories:
            continue
        source_entries = sorted(
            (
                {
                    "distribution": entry["distribution"],
                    "specifier": entry["specifier"],
                    "path": entry["path"],
                    "source_kind": _source_requirement_kind(entry["path"]),
                    "line": entry["line"],
                }
                for entry in constraints[dependency_key]
            ),
            key=lambda row: (row["path"], row["line"]),
        )
        routes.append(
            {
                "id": f"requirements-constraint:{dependency_key}",
                "dependency_key": dependency_key,
                "trigger": {
                    "repository": source["repository"],
                    "kind": "requirement-entry-change",
                    "paths": sorted(set(source["constraints_paths"])),
                    "path_kinds": [
                        {
                            "path": path,
                            "kind": _source_requirement_kind(path),
                        }
                        for path in sorted(set(source["constraints_paths"]))
                    ],
                    "source_entries": source_entries,
                    "import_roots": sorted(
                        root
                        for root, dependency_keys in import_aliases.items()
                        if dependency_key in dependency_keys
                    ),
                },
                "repositories": repositories,
            }
        )

    candidates = []
    for repository in sorted(members):
        target = target_configs.get(repository)
        manifest_row = manifest_snapshots.get(repository)
        if target:
            snapshot = {
                "status": "materialized",
                "commit": target["commit"],
                "source_status": target["status"],
            }
        elif manifest_row:
            snapshot = {
                "status": (
                    "available_not_materialized"
                    if manifest_row["status"] == "available"
                    else manifest_row["status"]
                ),
                "source_status": manifest_row["status"],
            }
            if manifest_row.get("commit"):
                snapshot["commit"] = manifest_row["commit"]
        else:
            snapshot = {"status": "not_in_snapshot_manifest"}
        if manifest_row:
            for field in ("archive_url", "committed_at", "host", "reason"):
                if manifest_row.get(field) is not None:
                    snapshot[field] = manifest_row[field]
        candidates.append(
            {
                "repository": repository,
                "membership_source": {
                    "repository": source["repository"],
                    "commit": source["commit"],
                    "path": source["projects_path"],
                    "line": member_lines[repository],
                },
                "inclusion_basis": "requirements_contract",
                "contract_exception": repository
                in {
                    "openstack/hacking",
                    "openstack/pbr",
                    "openstack/requirements",
                },
                "snapshot": snapshot,
            }
        )

    target_provenance = []
    scan_by_repository = {scan["repository"]: scan for scan in scans}
    for repository in sorted(target_configs):
        scan = scan_by_repository[repository]
        target_provenance.append(
            {
                "repository": repository,
                "commit": scan["commit"],
                "dependency_files": sorted(
                    {row["path"] for rows in scan["declarations"].values() for row in rows}
                ),
                "ci_files": scan["ci_sources"],
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "pack_family_id": spec["pack_family_id"],
        "pack_revision_id": spec["pack_revision_id"],
        "project": "openstack",
        "materialization": {"observation_cutoff": observation_cutoff},
        "generator": {"id": GENERATOR_ID, "version": GENERATOR_VERSION},
        "construction_policy": {
            "event_independent": not spec.get("authoring_case_ids")
            and materialization_complete,
            "route_derivation_outcome_independent": True,
            "development_only": bool(spec.get("authoring_case_ids"))
            or not materialization_complete,
            "authoring_case_ids": sorted(set(spec.get("authoring_case_ids", []))),
            "allowed_inputs": [
                "source_opening_projects_txt",
                "source_opening_requirement_catalogs",
                "target_cutoff_dependency_declarations",
                "target_cutoff_python_source_and_tests",
                "target_cutoff_ci_configuration",
                "target_cutoff_python_package_metadata",
            ],
            "excluded_inputs": [
                "a1_replay_log",
                "failure_signature",
                "target_repair",
                "hidden_impact_label",
            ],
        },
        "provenance": {
            "source": {
                "repository": source["repository"],
                "commit": source["commit"],
                "commit_time": _git(
                    Path(source["git_dir"]),
                    "show",
                    "-s",
                    "--format=%cI",
                    source["commit"],
                ).strip(),
                "projects_path": source["projects_path"],
                "membership_epoch_commit": _git(
                    Path(source["git_dir"]),
                    "rev-list",
                    "-1",
                    source["commit"],
                    "--",
                    source["projects_path"],
                ).strip(),
                "constraints_paths": sorted(set(source["constraints_paths"])),
                "requirements_path_kinds": [
                    {
                        "path": path,
                        "kind": _source_requirement_kind(path),
                    }
                    for path in sorted(set(source["constraints_paths"]))
                ],
            },
            "snapshot_manifest": {
                "manifest_id": spec["snapshot_manifest"].get("manifest_id"),
                "format": spec["snapshot_manifest"]["format"],
                "observation_cutoff": observation_cutoff,
            },
            "targets": target_provenance,
        },
        "coordination_repositories": [source["repository"]],
        "candidate_repositories": candidates,
        "dependency_routes": routes,
        "dependency_aliases": [
            {
                "dependency_key": dependency_key,
                "import_root": root,
                "provider_repositories": sorted(
                    alias_providers.get((dependency_key, root), set())
                ),
                "status": (
                    "available"
                    if dependency_key in import_aliases.get(root, set())
                    else "ambiguous"
                ),
            }
            for root in sorted(alias_claims)
            for dependency_key in sorted(alias_claims[root])
        ],
        "execution_templates": [
            execution_templates[template_id]
            for template_id in sorted(execution_templates)
        ],
        "checks": [checks[check_id] for check_id in sorted(checks)],
        "coverage": {
            "projects_txt_candidates": len(members),
            "snapshot_manifest_candidates": len(manifest_snapshots),
            "materialized_candidates": len(target_configs),
            "materialization_complete": materialization_complete,
            "snapshot_status_counts": {
                status: sum(
                    1
                    for repository in members
                    if manifest_snapshots.get(repository, {}).get("status") == status
                )
                for status in (
                    "available",
                    "not_assessed",
                    "not_created_by_cutoff",
                    "unavailable",
                )
            },
            "not_in_snapshot_manifest": sum(
                1 for repository in members if repository not in manifest_snapshots
            ),
            "dependencies_with_routes": len(routes),
            "execution_templates": len(execution_templates),
            "checks": len(checks),
            "known_limits": [
                "Python requirement declarations and direct imports only",
                "distribution/import aliases require an unambiguous candidate package provider",
                "Python propagation follows static import and dotted-string reference edges only",
                "executable command templates are discovered from tox.ini only",
                "collectable tests require test_*.py, *_test.py, or tests.py filenames",
                "available_not_materialized projects.txt members have no code-derived routes",
            ],
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    pack = build_pack(spec)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(pack, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "pack_family_id": pack["pack_family_id"],
                "pack_revision_id": pack["pack_revision_id"],
                "candidates": pack["coverage"]["projects_txt_candidates"],
                "materialized": pack["coverage"]["materialized_candidates"],
                "routes": pack["coverage"]["dependencies_with_routes"],
                "checks": pack["coverage"]["checks"],
                "output": str(args.output),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

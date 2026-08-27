#!/usr/bin/env python3
"""Rank cutoff candidate repositories by reading their pinned code snapshots.

This adapter is intentionally label-blind. It consumes only public opening
inputs, code-only source patches, catalog-derived cutoff snapshots, and local
complete Git mirrors or exact-commit source archives prepared before label
review.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import json
import math
import os
import re
import subprocess
import tarfile
from functools import lru_cache
from collections import Counter
from pathlib import Path
from typing import Any, Callable

from candidate_code_ranker import IGNORED_PARTS, STOP_WORDS, tokens
from collect_formal_e2_candidate_mirrors import repository_path


EXTRA_STOP_WORDS = {
    "assert", "branch", "commit", "copyright", "description", "example",
    "license", "openstack", "project", "release", "repository", "source",
    "subject", "todo", "ubuntu", "unit", "utils",
}
CODE_SUFFIXES = {
    ".c", ".cc", ".cfg", ".conf", ".cpp", ".cs", ".go", ".gradle",
    ".h", ".hpp", ".ini", ".java", ".js", ".json", ".kt", ".kts",
    ".md", ".php", ".properties", ".py", ".rb", ".rs", ".rst", ".sh",
    ".swift", ".toml", ".ts", ".tsx", ".txt", ".xml", ".yaml", ".yml",
}
CODE_NAMES = {
    "Dockerfile", "Gemfile", "Makefile", "Pipfile", "SConstruct", "go.mod",
    "package.json", "pom.xml", "pyproject.toml", "requirements.txt", "setup.cfg",
    "setup.py", "tox.ini",
}
SURFACE_PARTS = {
    "api", "build", "client", "clients", "config", "driver", "drivers",
    "interface", "interfaces", "manager", "models", "plugin", "plugins",
    "requirements", "service", "services", "test", "tests",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def select_query_terms(input_item: dict[str, Any], patch_text: str, limit: int = 24) -> list[str]:
    source = input_item["source"]
    visible_context = "\n".join([
        source.get("subject", ""),
        *source.get("changed_paths", []),
    ])
    context_counts = Counter(tokens(visible_context))
    patch_counts = Counter(tokens(patch_text))
    candidates = set(context_counts) | set(patch_counts)
    ignored = STOP_WORDS | EXTRA_STOP_WORDS

    def priority(term: str) -> tuple[float, str]:
        context_boost = 1.0 if context_counts[term] else 0.0
        identifier_boost = min(len(term), 32) / 4.0
        compound_boost = 2.0 if "_" in term else 0.0
        repetition = min(patch_counts[term], 8)
        return (
            -(context_boost + identifier_boost + compound_boost + math.log1p(repetition)),
            term,
        )

    eligible = [
        term for term in candidates
        if len(term) >= 4 and term not in ignored and not term.isdigit()
    ]
    return sorted(eligible, key=priority)[:limit]


def local_git_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.update({
        "GIT_ALLOW_PROTOCOL": "file",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
        "http_proxy": "http://127.0.0.1:9",
        "https_proxy": "http://127.0.0.1:9",
        "HTTP_PROXY": "http://127.0.0.1:9",
        "HTTPS_PROXY": "http://127.0.0.1:9",
        "NO_PROXY": "",
        "no_proxy": "",
    })
    return environment


def run_git(
    arguments: list[str],
    runner: Callable[..., subprocess.CompletedProcess[bytes]] = subprocess.run,
    input_data: bytes | None = None,
) -> subprocess.CompletedProcess[bytes]:
    return runner(
        arguments,
        input=input_data,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=local_git_environment(),
        check=False,
    )


@lru_cache(maxsize=512)
def cached_tree_read(mirror: str, commit: str) -> tuple[int, bytes, bytes]:
    result = run_git(["git", "--git-dir", mirror, "ls-tree", "-r", "-l", "-z", commit])
    return result.returncode, result.stdout, result.stderr


def parse_tree(payload: bytes) -> list[tuple[str, str, int]]:
    entries = []
    for raw in payload.split(b"\0"):
        if not raw:
            continue
        metadata, separator, path = raw.partition(b"\t")
        fields = metadata.split()
        if not separator or len(fields) != 4 or fields[1] != b"blob" or fields[3] == b"-":
            continue
        entries.append((
            path.decode(errors="replace"),
            fields[2].decode("ascii"),
            int(fields[3]),
        ))
    return entries


def selected_blobs(
    entries: list[tuple[str, str, int]], query: set[str], limit: int = 24
) -> list[tuple[str, str, int, int]]:
    eligible = []
    fallback = []
    for path, object_id, size in entries:
        value = Path(path)
        if size > 512 * 1024 or any(part in IGNORED_PARTS for part in value.parts):
            continue
        fallback.append((0, 0, path, object_id, size))
        if value.suffix.lower() not in CODE_SUFFIXES and value.name not in CODE_NAMES:
            continue
        path_tokens = set(tokens(path))
        overlap = len(query & path_tokens)
        surface = len(SURFACE_PARTS & path_tokens)
        eligible.append((overlap, surface, path, object_id, size))
    eligible.sort(key=lambda row: (-row[0], -row[1], row[2]))
    selected = eligible[:limit]
    selected_paths = {row[2] for row in selected}
    if len(selected) < limit:
        selected.extend(
            row for row in fallback
            if row[2] not in selected_paths
        )
        selected = selected[:limit]
    return [
        (path, object_id, size, overlap)
        for overlap, _surface, path, object_id, size in selected
    ]


def parse_batch_objects(payload: bytes, expected: int) -> list[bytes]:
    objects = []
    offset = 0
    while offset < len(payload) and len(objects) < expected:
        end = payload.find(b"\n", offset)
        if end < 0:
            break
        header = payload[offset:end]
        offset = end + 1
        if header.endswith(b" missing"):
            objects.append(b"")
            continue
        fields = header.rsplit(b" ", 2)
        if len(fields) != 3 or not fields[2].isdigit():
            break
        size = int(fields[2])
        objects.append(payload[offset:offset + size])
        offset += size + 1
    return objects


def scan_commit(
    mirror: Path,
    commit: str,
    query_terms: list[str],
    runner: Callable[..., subprocess.CompletedProcess[bytes]] = subprocess.run,
) -> dict[str, Any]:
    if runner is subprocess.run:
        returncode, tree_stdout, tree_stderr = cached_tree_read(str(mirror), commit)
    else:
        tree = run_git(
            ["git", "--git-dir", str(mirror), "ls-tree", "-r", "-l", "-z", commit],
            runner,
        )
        returncode, tree_stdout, tree_stderr = tree.returncode, tree.stdout, tree.stderr
    if returncode != 0:
        return {"status": "commit_or_tree_missing", "error": tree_stderr.decode(errors="replace")[-1000:]}
    entries = parse_tree(tree_stdout)
    query = set(query_terms)
    selected = selected_blobs(entries, query)
    batch = run_git(
        ["git", "--git-dir", str(mirror), "cat-file", "--batch"],
        runner,
        "".join(f"{object_id}\n" for _path, object_id, _size, _overlap in selected).encode(),
    )
    if batch.returncode != 0:
        return {"status": "code_read_failed", "error": batch.stderr.decode(errors="replace")[-1000:]}
    contents = parse_batch_objects(batch.stdout, len(selected))
    if len(contents) != len(selected):
        return {"status": "code_read_failed", "error": "incomplete git cat-file batch output"}
    term_counts: Counter[str] = Counter()
    path_counts: list[tuple[int, int, str]] = []
    bytes_read = 0
    text_files_read = 0
    for (path, _object_id, _size, path_overlap), content in zip(selected, contents):
        if b"\0" in content[:4096]:
            continue
        text_files_read += 1
        bytes_read += len(content)
        matches = Counter(term for term in tokens(content.decode(errors="replace")) if term in query)
        term_counts.update(matches)
        match_count = sum(min(count, 20) for count in matches.values())
        if path_overlap or match_count:
            path_counts.append((path_overlap, match_count, path))
    path_counts.sort(key=lambda row: (-row[0], -row[1], row[2]))
    return {
        "status": "available",
        "tracked_file_count": len(entries),
        "files_read": len(selected),
        "text_files_read": text_files_read,
        "bytes_read": bytes_read,
        "matched_query_terms": len(term_counts),
        "matching_token_count": sum(term_counts.values()),
        "paths": [row[2] for row in path_counts[:5]],
        "path_query_overlap": sum(row[0] for row in path_counts[:5]),
    }


def archive_path(root: Path, repository: str, commit: str) -> Path:
    return root / repository.replace("/", "__") / f"{commit}.tar.gz"


def scan_archive(
    archive: Path,
    _commit: str,
    query_terms: list[str],
) -> dict[str, Any]:
    try:
        with tarfile.open(archive, "r:gz") as handle:
            members = [member for member in handle.getmembers() if member.isfile()]
            entries: list[tuple[str, str, int]] = []
            member_by_path: dict[str, tarfile.TarInfo] = {}
            for member in members:
                parts = Path(member.name).parts
                if len(parts) < 2:
                    continue
                relative = str(Path(*parts[1:]))
                entries.append((relative, relative, member.size))
                member_by_path[relative] = member
            query = set(query_terms)
            selected = selected_blobs(entries, query)
            # Gzip seeks backwards by restarting decompression from the
            # beginning.  selected_blobs orders by relevance, so reading in
            # that order can inflate one archive scan into as many as 24 full
            # decompression passes.  Preserve the same selected set and final
            # scoring, but visit members in monotonically increasing archive
            # offset order after the one metadata pass above.
            selected_for_read = sorted(
                selected,
                key=lambda row: member_by_path[row[0]].offset_data,
            )
            term_counts: Counter[str] = Counter()
            path_counts: list[tuple[int, int, str]] = []
            bytes_read = 0
            text_files_read = 0
            for path, _identifier, _size, path_overlap in selected_for_read:
                stream = handle.extractfile(member_by_path[path])
                if stream is None:
                    return {"status": "code_read_failed", "error": f"archive member unreadable: {path}"}
                content = stream.read()
                if b"\0" in content[:4096]:
                    continue
                text_files_read += 1
                bytes_read += len(content)
                matches = Counter(
                    term for term in tokens(content.decode(errors="replace")) if term in query
                )
                term_counts.update(matches)
                match_count = sum(min(count, 20) for count in matches.values())
                if path_overlap or match_count:
                    path_counts.append((path_overlap, match_count, path))
    except (OSError, tarfile.TarError) as error:
        return {"status": "archive_missing_or_invalid", "error": str(error)[-1000:]}
    path_counts.sort(key=lambda row: (-row[0], -row[1], row[2]))
    return {
        "status": "available",
        "tracked_file_count": len(entries),
        "files_read": len(selected),
        "text_files_read": text_files_read,
        "bytes_read": bytes_read,
        "matched_query_terms": len(term_counts),
        "matching_token_count": sum(term_counts.values()),
        "paths": [row[2] for row in path_counts[:5]],
        "path_query_overlap": sum(row[0] for row in path_counts[:5]),
    }


def score_scan(scan: dict[str, Any]) -> float:
    return (
        2.0 * scan["matched_query_terms"]
        + math.log1p(scan["matching_token_count"])
        + 2.0 * scan.get("path_query_overlap", 0)
    )


def rank_case(
    input_item: dict[str, Any],
    snapshot: dict[str, Any],
    patch_dir: Path,
    candidate_root: Path,
    top_k: int,
    workers: int,
    scanner: Callable[[Path, str, list[str]], dict[str, Any]] = scan_commit,
    candidate_storage: str = "git_mirror",
) -> tuple[dict[str, Any], dict[str, Any]]:
    patch_text = (patch_dir / f"{input_item['case_id']}.patch").read_text(
        encoding="utf-8", errors="replace"
    )
    query_terms = select_query_terms(input_item, patch_text)
    source_repository = input_item["source"]["repository"]
    available = [
        row for row in snapshot["repositories"]
        if row["status"] == "available" and row["repository"] != source_repository
    ]
    scans: dict[str, dict[str, Any]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                scanner,
                (
                    repository_path(candidate_root, row["repository"])
                    if candidate_storage == "git_mirror"
                    else archive_path(candidate_root, row["repository"], row["commit"])
                ),
                row["commit"],
                query_terms,
            ): row["repository"]
            for row in available
        }
        for future in concurrent.futures.as_completed(futures):
            scans[futures[future]] = future.result()
    failures = [
        {"repository": repository, **scan}
        for repository, scan in sorted(scans.items())
        if scan["status"] != "available"
    ]
    if failures:
        raise RuntimeError(
            f"{input_item['case_id']}: candidate code unavailable for "
            f"{len(failures)} repositories; first={failures[0]}"
        )
    ranking = [
        {
            "repository": repository,
            "score": score_scan(scan),
            "paths": scan["paths"],
            "tracked_file_count": scan["tracked_file_count"],
            "files_read": scan["files_read"],
            "text_files_read": scan["text_files_read"],
            "bytes_read": scan["bytes_read"],
            "matched_query_terms": scan["matched_query_terms"],
            "matching_token_count": scan["matching_token_count"],
        }
        for repository, scan in scans.items()
    ]
    ranking.sort(key=lambda row: (-row["score"], row["repository"]))
    selected = ranking[:top_k]
    prediction = {
        "case_id": input_item["case_id"],
        "targets": [{
            "repository": row["repository"],
            "paths": row["paths"],
            "tests": [],
            "commands": [],
            "execution_result": "not_assessed",
        } for row in selected],
    }
    diagnostic = {
        "case_id": input_item["case_id"],
        "method": f"cutoff_{candidate_storage}_targeted_24_code_overlap_v1",
        "label_inputs_read": False,
        "candidate_code_read": True,
        "candidate_repositories_read": len(scans),
        "maximum_code_files_read_per_candidate": 24,
        "query_terms": query_terms,
        "source_repository_excluded": source_repository,
        "ranking": ranking,
    }
    return prediction, diagnostic


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--patch-dir", type=Path, required=True)
    parser.add_argument("--snapshots", type=Path, required=True)
    candidates = parser.add_mutually_exclusive_group(required=True)
    candidates.add_argument("--mirror-root", type=Path)
    candidates.add_argument("--archive-root", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--case-workers", type=int, default=1)
    parser.add_argument("--case-id", action="append", dest="case_ids")
    parser.add_argument("--shard-index", type=int)
    parser.add_argument("--shard-count", type=int)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Keep already checkpointed label-blind cases and compute only missing cases.",
    )
    args = parser.parse_args()
    if args.top_k < 1 or args.workers < 1 or args.case_workers < 1:
        raise SystemExit("--top-k, --workers, and --case-workers must be positive")
    inputs = read_jsonl(args.inputs)
    if args.case_ids:
        requested = set(args.case_ids)
        inputs = [item for item in inputs if item["case_id"] in requested]
        found = {item["case_id"] for item in inputs}
        unknown = sorted(requested - found)
        if unknown:
            raise SystemExit(f"unknown case id: {unknown[0]}")
    if (args.shard_index is None) != (args.shard_count is None):
        raise SystemExit("--shard-index and --shard-count must be supplied together")
    if args.shard_count is not None:
        if args.shard_count < 1 or not 0 <= args.shard_index < args.shard_count:
            raise SystemExit("invalid shard index/count")
        inputs = [
            item for index, item in enumerate(inputs)
            if index % args.shard_count == args.shard_index
        ]
    snapshots = {row["case_id"]: row for row in read_jsonl(args.snapshots)}
    missing = [item["case_id"] for item in inputs if item["case_id"] not in snapshots]
    if missing:
        raise SystemExit(f"missing cutoff snapshots for {len(missing)} cases; first={missing[0]}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    prediction_path = args.output_dir / "predictions.jsonl"
    diagnostic_path = args.output_dir / "diagnostics.jsonl"
    predictions_by_case: dict[str, dict[str, Any]] = {}
    diagnostics_by_case: dict[str, dict[str, Any]] = {}
    if args.resume and prediction_path.exists() and diagnostic_path.exists():
        predictions_by_case = {row["case_id"]: row for row in read_jsonl(prediction_path)}
        diagnostics_by_case = {row["case_id"]: row for row in read_jsonl(diagnostic_path)}
        if set(predictions_by_case) != set(diagnostics_by_case):
            raise SystemExit("resume prediction/diagnostic checkpoints disagree")
        unknown = set(predictions_by_case) - {item["case_id"] for item in inputs}
        if unknown:
            raise SystemExit(f"resume checkpoint contains unknown case: {sorted(unknown)[0]}")
    prior_times = {row.get("created_at") for row in predictions_by_case.values()}
    prior_times.discard(None)
    if len(prior_times) > 1:
        raise SystemExit("resume checkpoint contains multiple creation times")
    created_at = next(
        iter(prior_times),
        dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
    )
    pending_inputs = [item for item in inputs if item["case_id"] not in predictions_by_case]
    candidate_storage = "git_mirror" if args.mirror_root is not None else "exact_commit_archive"
    candidate_root = args.mirror_root if args.mirror_root is not None else args.archive_root
    scanner = scan_commit if args.mirror_root is not None else scan_archive
    assert candidate_root is not None
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.case_workers) as executor:
        futures = {
            executor.submit(
                rank_case,
                item,
                snapshots[item["case_id"]],
                args.patch_dir,
                candidate_root,
                args.top_k,
                args.workers,
                scanner,
                candidate_storage,
            ): item["case_id"]
            for item in pending_inputs
        }
        for future in concurrent.futures.as_completed(futures):
            case_id = futures[future]
            prediction, diagnostic = future.result()
            prediction["created_at"] = created_at
            predictions_by_case[case_id] = prediction
            diagnostics_by_case[case_id] = diagnostic
            completed_ids = [
                item["case_id"] for item in inputs
                if item["case_id"] in predictions_by_case
            ]
            write_jsonl(
                prediction_path,
                [predictions_by_case[key] for key in completed_ids],
            )
            write_jsonl(
                diagnostic_path,
                [diagnostics_by_case[key] for key in completed_ids],
            )
    predictions = [predictions_by_case[item["case_id"]] for item in inputs]
    diagnostics = [diagnostics_by_case[item["case_id"]] for item in inputs]
    write_jsonl(prediction_path, predictions)
    write_jsonl(diagnostic_path, diagnostics)
    manifest = {
        "schema_version": "1.0",
        "system": "Marshal cutoff candidate-code lexical adapter v1",
        "created_at": created_at,
        "started_at": created_at,
        "completed_at": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "case_count": len(predictions),
        "labels_read": False,
        "network_used": False,
        "network_enforcement": os.environ.get("MARSHAL_NETWORK_CONTROL", "environment_only"),
        "candidate_code_read": True,
        "candidate_code_source": (
            "complete local Git mirrors at catalog cutoff commits"
            if args.mirror_root is not None
            else "local source archives named by catalog cutoff commits"
        ),
        "network_controls": [
            "Git transport restricted to file protocol",
            "proxy environment forced to closed loopback endpoint",
            "ranker reads only the mounted local candidate snapshots",
        ],
    }
    write_json(args.output_dir / "run-manifest.json", manifest)
    print(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

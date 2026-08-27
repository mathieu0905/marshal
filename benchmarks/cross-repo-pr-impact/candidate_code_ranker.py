#!/usr/bin/env python3
"""Rank prepared candidate repositories by source-change/code lexical overlap.

This development adapter reads only the visible source patch, input metadata, and
observation-time candidate code. It does not read case labels or target changes.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any


TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")
CAMEL = re.compile(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|[0-9]+")
IGNORED_PARTS = {
    ".git", ".gradle", ".idea", ".mypy_cache", ".pytest_cache", ".tox",
    ".venv", "__pycache__", "build", "coverage", "dist", "node_modules",
    "target", "vendor", "vendors",
}
STOP_WORDS = {
    "add", "added", "after", "also", "and", "before", "bool", "build",
    "change", "changed", "class", "const", "data", "default", "delete",
    "else", "false", "file", "from", "function", "import", "include",
    "int", "into", "json", "list", "main", "new", "none", "null", "object",
    "package", "path", "private", "public", "remove", "removed", "return",
    "self", "static", "string", "test", "tests", "that", "this", "true",
    "type", "update", "updated", "using", "value", "version", "void", "with",
}


def tokens(text: str) -> list[str]:
    result = []
    for match in TOKEN.findall(text):
        lowered = match.lower()
        if lowered not in STOP_WORDS and len(lowered) >= 3:
            result.append(lowered)
        for piece in CAMEL.findall(match.replace("_", " ")):
            piece = piece.lower()
            if piece not in STOP_WORDS and len(piece) >= 3 and piece != lowered:
                result.append(piece)
    return result


def visible_file(path: Path) -> bool:
    return (
        path.is_file()
        and path.stat().st_size <= 512 * 1024
        and not any(part in IGNORED_PARTS for part in path.parts)
    )


def read_text(path: Path) -> str | None:
    try:
        payload = path.read_bytes()
    except OSError:
        return None
    if b"\0" in payload[:4096]:
        return None
    return payload.decode("utf-8", errors="ignore")


def scan_repository(repository_root: Path, query: set[str]) -> dict[str, Any]:
    term_counts: Counter[str] = Counter()
    path_scores: list[tuple[int, int, str]] = []
    files_read = 0
    bytes_read = 0
    for path in sorted(repository_root.rglob("*")):
        if not visible_file(path):
            continue
        content = read_text(path)
        if content is None:
            continue
        files_read += 1
        bytes_read += path.stat().st_size
        relative = str(path.relative_to(repository_root))
        path_hits = len(query & set(tokens(relative)))
        content_counts = Counter(token for token in tokens(content) if token in query)
        term_counts.update(content_counts)
        content_hits = sum(min(value, 5) for value in content_counts.values())
        if path_hits or content_hits:
            path_scores.append((path_hits, content_hits, relative))
    ranked_paths = [
        item[2]
        for item in sorted(path_scores, key=lambda item: (-item[0], -item[1], item[2]))[:5]
    ]
    return {
        "term_counts": term_counts,
        "paths": ranked_paths,
        "files_read": files_read,
        "bytes_read": bytes_read,
    }


def normalize_score(raw_score: float, files_read: int, mode: str) -> float:
    if mode == "none":
        return raw_score
    if mode == "sqrt_files":
        return raw_score / math.sqrt(max(files_read, 1))
    raise ValueError(f"unsupported size normalization: {mode}")


def rank_case(
    case_dir: Path, top_k: int, size_normalization: str = "none"
) -> tuple[dict[str, Any], dict[str, Any]]:
    input_item = json.loads((case_dir / "input.json").read_text(encoding="utf-8"))
    patch_text = (case_dir / "source.patch").read_text(encoding="utf-8", errors="ignore")
    query_counts = Counter(tokens(patch_text))
    query = set(query_counts)
    repositories_root = case_dir / "repositories"
    source_repository = input_item.get("source", {}).get("repository")
    scans = {
        path.name.replace("__", "/", 1): scan_repository(path, query)
        for path in sorted(repositories_root.iterdir())
        if path.is_dir() and path.name.replace("__", "/", 1) != source_repository
    }
    document_frequency = Counter({
        term: sum(scan["term_counts"][term] > 0 for scan in scans.values())
        for term in query
    })
    repository_count = len(scans)
    scored = []
    for repository, scan in scans.items():
        score = 0.0
        matched_terms = 0
        for term, count in scan["term_counts"].items():
            if not count:
                continue
            matched_terms += 1
            inverse_frequency = math.log(
                (repository_count + 1) / (document_frequency[term] + 1)
            ) + 1.0
            query_weight = 1.0 + math.log1p(min(query_counts[term], 8))
            score += inverse_frequency * query_weight * (1.0 + math.log1p(min(count, 20)))
        raw_score = score
        scored.append({
            "repository": repository,
            "score": normalize_score(
                raw_score, scan["files_read"], size_normalization
            ),
            "raw_score": raw_score,
            "matched_query_terms": matched_terms,
            "paths": scan["paths"],
            "files_read": scan["files_read"],
            "bytes_read": scan["bytes_read"],
        })
    scored.sort(key=lambda item: (-item["score"], item["repository"]))
    selected = scored[:top_k]
    prediction = {
        "case_id": input_item["case_id"],
        "targets": [{
            "repository": item["repository"],
            "paths": item["paths"],
            "tests": [],
            "commands": [],
            "execution_result": "not_assessed",
        } for item in selected],
    }
    diagnostics = {
        "case_id": input_item["case_id"],
        "method": (
            "candidate_code_lexical_overlap_v1"
            if size_normalization == "none"
            else f"candidate_code_lexical_overlap_{size_normalization}_v1"
        ),
        "label_inputs_read": False,
        "source_repository_excluded": source_repository,
        "query_term_count": len(query),
        "candidate_repositories_read": repository_count,
        "top_k": top_k,
        "size_normalization": size_normalization,
        "ranking": scored,
    }
    return prediction, diagnostics


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepared-root", type=Path, required=True)
    parser.add_argument("--case-id", action="append", dest="case_ids")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument(
        "--size-normalization", choices=("none", "sqrt_files"), default="none"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostics-output", type=Path, required=True)
    args = parser.parse_args()
    if args.top_k < 1:
        raise SystemExit("--top-k must be positive")
    case_ids = args.case_ids or sorted(
        path.name for path in args.prepared_root.iterdir() if path.is_dir()
    )
    predictions = []
    diagnostics = []
    for case_id in case_ids:
        prediction, diagnostic = rank_case(
            args.prepared_root / case_id, args.top_k, args.size_normalization
        )
        predictions.append(prediction)
        diagnostics.append(diagnostic)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.diagnostics_output.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.output, predictions)
    write_jsonl(args.diagnostics_output, diagnostics)
    print(json.dumps({
        "cases_ranked": len(predictions),
        "candidate_repositories_read": sum(
            item["candidate_repositories_read"] for item in diagnostics
        ),
        "size_normalization": args.size_normalization,
        "predictions": str(args.output.resolve()),
        "diagnostics": str(args.diagnostics_output.resolve()),
    }, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

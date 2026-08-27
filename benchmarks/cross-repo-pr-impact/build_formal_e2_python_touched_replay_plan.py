#!/usr/bin/env python3
"""Expand relation plans into pre-existing target tests touched by the maintainer fix."""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from collect_formal_e2_candidate_mirrors import repository_path


HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", re.MULTILINE)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def git_text(mirror: Path, commit: str, path: str) -> str | None:
    completed = subprocess.run(
        ["git", "--git-dir", str(mirror), "show", f"{commit}:{path}"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
    )
    return completed.stdout.decode("utf-8", errors="replace") if completed.returncode == 0 else None


def test_spans(source: str, module: str) -> dict[str, tuple[int, int]]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}
    spans: dict[str, tuple[int, int]] = {}

    def visit(nodes: list[ast.stmt], classes: tuple[str, ...] = ()) -> None:
        for node in nodes:
            if isinstance(node, ast.ClassDef):
                visit(node.body, (*classes, node.name))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("test_"):
                    selector = ".".join((module, *classes, node.name))
                    spans[selector] = (node.lineno, node.end_lineno or node.lineno)

    visit(tree.body)
    return spans


def intersects(span: tuple[int, int], start: int, count: int) -> bool:
    changed_start = max(start, 1)
    changed_end = changed_start + max(count, 1) - 1
    return not (span[1] < changed_start or span[0] > changed_end)


def touched_selectors(
    mirror: Path, base_commit: str, head_commit: str, path: str
) -> list[str]:
    module = path[:-3].replace("/", ".")
    old_source = git_text(mirror, base_commit, path)
    new_source = git_text(mirror, head_commit, path)
    if old_source is None or new_source is None:
        return []
    old_spans = test_spans(old_source, module)
    new_spans = test_spans(new_source, module)
    diff = subprocess.run(
        ["git", "--git-dir", str(mirror), "diff", "--unified=0", base_commit, head_commit, "--", path],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=False,
    ).stdout
    selected: set[str] = set()
    for match in HUNK.finditer(diff):
        old_start, old_count, new_start, new_count = (
            int(match.group(1)), int(match.group(2) or "1"),
            int(match.group(3)), int(match.group(4) or "1"),
        )
        for selector in old_spans.keys() & new_spans.keys():
            if (
                intersects(old_spans[selector], old_start, old_count)
                or intersects(new_spans[selector], new_start, new_count)
            ):
                selected.add(selector)
    return sorted(selected)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--relation-plan", type=Path, required=True)
    parser.add_argument("--target-metadata", type=Path, required=True)
    parser.add_argument("--mirror-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    metadata = {row["candidate_id"]: row for row in read_jsonl(args.target_metadata)}
    attempts: list[dict[str, Any]] = []
    for relation in read_jsonl(args.relation_plan):
        target = next(
            item for item in metadata[relation["candidate_id"]]["targets"]
            if item["number"] == relation["target_change"]
        )
        mirror = repository_path(args.mirror_root, relation["target_repository"])
        selectors: set[str] = set()
        for path in target["changed_paths"]:
            if path.endswith(".py") and Path(path).name.startswith("test_"):
                selectors.update(touched_selectors(
                    mirror, relation["target_base_commit"], relation["target_head_commit"], path
                ))
        for index, selector in enumerate(sorted(selectors), start=1):
            relation_id = relation["case_id"]
            attempts.append({
                **relation,
                "relation_id": relation_id,
                "case_id": f"{relation_id}--test-{index:03d}",
                "test_selector": selector,
                "test_command": ["stestr", "run", selector],
            })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in attempts),
        encoding="utf-8",
    )
    print(json.dumps({
        "relation_count": len({row["relation_id"] for row in attempts}),
        "attempt_count": len(attempts),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

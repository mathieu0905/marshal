#!/usr/bin/env python3
"""Run relation-grouped touched-test replays in parallel."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import subprocess
import sys
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--mirror-root", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--tox", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--skip-relation-id", action="append", default=[])
    args = parser.parse_args()
    relations = sorted({row["relation_id"] for row in read_jsonl(args.plan)})
    relations = [
        relation for relation in relations
        if relation not in set(args.skip_relation_id)
        and not (args.evidence_root / relation).exists()
    ]

    def execute(relation: str) -> dict:
        command = [
            sys.executable, str(Path(__file__).with_name("run_formal_e2_python_touched_relation.py")),
            "--plan", str(args.plan), "--relation-id", relation,
            "--mirror-root", str(args.mirror_root), "--work-root", str(args.work_root),
            "--evidence-root", str(args.evidence_root), "--tox", str(args.tox), "--python", str(args.python),
        ]
        completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
        return {"relation_id": relation, "exit_code": completed.returncode, "driver_output": completed.stdout[-4000:]}

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(execute, relation) for relation in relations]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            results.append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)
    results.sort(key=lambda row: row["relation_id"])
    args.evidence_root.mkdir(parents=True, exist_ok=True)
    (args.evidence_root / "batch-results.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in results), encoding="utf-8"
    )
    print(json.dumps({
        "attempted_relations": len(results),
        "strict_e2": sum(row["exit_code"] == 0 for row in results),
        "rejected": sum(row["exit_code"] == 1 for row in results),
        "setup_failed": sum(row["exit_code"] == 2 for row in results),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

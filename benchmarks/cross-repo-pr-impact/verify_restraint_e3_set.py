#!/usr/bin/env python3
"""Verify the ten-case restraint set against its retained raw evidence."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream, delimiter="\t"))


def resolve(release_dir: Path, reference: str) -> Path:
    path = (release_dir / reference).resolve()
    if release_dir.resolve() not in path.parents:
        raise ValueError(f"evidence reference escapes release root: {reference}")
    return path


def verify(release_dir: Path) -> dict[str, Any]:
    cases = read_jsonl(release_dir / "e3-cases.jsonl")
    packs = read_jsonl(release_dir / "project-packs.jsonl")
    blockers: list[str] = []
    if len(cases) != 10 or len({row.get("e3_id") for row in cases}) != 10:
        blockers.append("case_count_or_uniqueness")
    if len(packs) != 3 or any(not row.get("bounded_universe_complete") for row in packs):
        blockers.append("project_pack_completeness")
    pack_by_id = {row["pack_id"]: row for row in packs}
    verified = 0
    for case in cases:
        case_id = case.get("e3_id", "<missing>")
        if case.get("evidence_layer") != "E3" or not case.get("semantic_review", {}).get("approved"):
            blockers.append(f"{case_id}:layer_or_semantic_review")
            continue
        pack = pack_by_id.get(case.get("pack_id"))
        if pack is None or case.get("target_repository") not in pack.get("bounded_negative_repositories", []):
            blockers.append(f"{case_id}:pack_membership")
            continue
        observation = case.get("observations", {})
        if observation != {"repetitions": 3, "a0_exit_codes": [0, 0, 0], "a1_exit_codes": [0, 0, 0]}:
            blockers.append(f"{case_id}:declared_direction")
            continue
        evidence = case.get("evidence", {})
        if "result_tables" in evidence:
            repository = case["target_repository"].split("/", 1)[1]
            found = []
            for reference in evidence["result_tables"]:
                rows = read_tsv(resolve(release_dir, reference))
                found.extend(row for row in rows if row["repository"] == repository and row["config"] in {"a0", "a1"})
            ok = len(found) == 6 and all(
                row["exit_code"] == "0"
                and row["expected_result"] == "pass"
                and row["actual_version"] == row["expected_version"]
                and row["test_executed"] == "true"
                and row["version_ok"] == "true"
                and row["direction_ok"] == "true"
                for row in found
            )
        elif "exit_codes" in evidence:
            paths = [resolve(release_dir, reference) for reference in evidence["exit_codes"]]
            summary = read_json(resolve(release_dir, evidence["summary"]))
            ok = (
                len(paths) == 6
                and all(path.read_text(encoding="utf-8").strip() == "0" for path in paths)
                and summary["aggregate"]["version_inputs_verified"] == 60
                and summary["aggregate"]["unexpected_nonzero_exits"] == 0
            )
        elif "logs" in evidence:
            paths = [resolve(release_dir, reference) for reference in evidence["logs"]]
            summary = read_json(resolve(release_dir, evidence["summary"]))
            marker = (
                "Executed 3 tests" if "spotless" in case_id
                else "Tests run: 114" if "rabbit" in case_id
                else "BUILD SUCCESS"
            )
            ok = (
                len(paths) == 6
                and all(marker in path.read_text(encoding="utf-8", errors="replace") for path in paths)
                and summary["aggregate"]["version_inputs_verified"] == 60
                and summary["aggregate"]["unexpected_nonzero_exits"] == 0
            )
        else:
            ok = False
        if not ok:
            blockers.append(f"{case_id}:raw_evidence")
        else:
            verified += 1
    return {
        "schema_version": "1.0",
        "case_count": len(cases),
        "project_pack_count": len(packs),
        "raw_evidence_verified_count": verified,
        "blockers": blockers,
        "verified": not blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("release_dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify(args.release_dir)
    if args.output:
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

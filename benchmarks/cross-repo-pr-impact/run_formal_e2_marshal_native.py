#!/usr/bin/env python3
"""Run Marshal's native configured-contract track on the public formal frame."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ROOT.parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from marshal_pack_cowboy.pack import CowboyPack  # noqa: E402


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def catalog_id(reference: str) -> str:
    return reference.split("#", 1)[1]


def predict(
    inputs: list[dict[str, Any]],
    catalogs: dict[str, Any],
    pack: Any,
    created_at: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    predictions = []
    diagnostics = []
    for item in inputs:
        source = item["source"]
        candidates = set(catalogs[catalog_id(item["candidate_repository_catalog"])]["repositories"])
        scope = {
            "repo": source["repository"].rsplit("/", 1)[-1],
            "diff_paths": source["changed_paths"],
        }
        hits = pack.contracts_hit(scope)
        ranked = []
        for invariant in pack.list_invariants(scope):
            if invariant.domain != "cross-repo" or invariant.location_repo not in candidates:
                continue
            ranked.append({
                "repository": invariant.location_repo,
                "paths": [invariant.location_path] if invariant.location_path else [],
                "tests": [invariant.location_test] if invariant.location_test else [],
                "commands": [invariant.run_command] if invariant.run_command else [],
                "execution_result": "not_assessed",
            })
        predictions.append({
            "candidate_id": item["case_id"],
            "case_id": item["case_id"],
            "created_at": created_at,
            "targets": ranked[:5],
        })
        diagnostics.append({
            "candidate_id": item["case_id"],
            "candidate_repository_count": len(candidates),
            "contracts_hit": hits,
            "predicted_target_count": len(ranked[:5]),
            "candidate_code_read": False,
            "reason": "native Marshal configured-contract interface has no candidate-code input",
        })
    return predictions, diagnostics


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    inputs = read_jsonl(args.input_dir / "inputs.jsonl")
    catalogs = read_json(args.input_dir / "candidate-repositories.json")["catalogs"]
    created_at = dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z")
    predictions, diagnostics = predict(inputs, catalogs, CowboyPack(), created_at)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.output_dir / "predictions.jsonl", predictions)
    write_jsonl(args.output_dir / "diagnostics.jsonl", diagnostics)
    manifest = {
        "schema_version": "1.0",
        "system": "Marshal CowboyPack native configured-contract track",
        "created_at": created_at,
        "case_count": len(predictions),
        "labels_read": False,
        "network_used": False,
        "inputs": ["inputs.jsonl", "candidate-repositories.json"],
        "candidate_code_read": False,
        "interpretation": (
            "Native configured-contract coverage only; this is not the offline "
            "candidate-code review adapter."
        ),
    }
    (args.output_dir / "run-manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

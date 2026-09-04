#!/usr/bin/env python3
"""Run the current Marshal planner and reporter against one public case."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from marshal_core.contracts import NormalizedEvent, StructuredResult
from marshal_core.domain_pack import InvariantDef
from marshal_core.executor import reporter
from marshal_core.modules.orchestrator import Orchestrator


class FixturePack:
    def __init__(self, raw: dict):
        self.raw = raw
        self._invariants = {
            row["id"]: InvariantDef(
                id=row["id"],
                domain=row["domain"],
                spec_ref=row["spec_ref"],
                executor_kind=row["executor_kind"],
                location_repo=row["location_repo"],
                location_path=row["location_path"],
                location_test=row["location_test"],
                severity=row["severity"],
                run_command=row["run_command"],
            )
            for row in raw["invariants"]
        }

    @property
    def id(self) -> str:
        return self.raw["id"]

    def contracts_hit(self, scope: dict) -> list[str]:
        labels = set(scope.get("labels", []))
        paths = scope.get("diff_paths", [])
        repo = scope.get("repo")
        matched = []
        for contract in self.raw["contracts"]:
            trigger = contract["trigger"]
            prefixes = tuple(trigger["path_prefixes"])
            if trigger["repo"] != repo:
                continue
            if not any(path.startswith(prefixes) for path in paths):
                continue
            if not set(trigger["required_labels"]).issubset(labels):
                continue
            matched.append(contract["id"])
        return matched

    def list_invariants(self, scope: dict) -> list[InvariantDef]:
        ids = []
        by_contract = {row["id"]: row for row in self.raw["contracts"]}
        for contract_id in self.contracts_hit(scope):
            ids.extend(by_contract[contract_id]["verify_invariants"])
        return [self._invariants[invariant_id] for invariant_id in dict.fromkeys(ids)]

    def classify(self, scope: dict) -> str:
        if self.contracts_hit(scope):
            return self.raw["matched_tier"]
        return self.raw["default_tier"]


class MemoryStore:
    def __init__(self):
        self.invariants = []
        self.gate_runs = []
        self.audit_rows = []

    def register_invariant(self, **row):
        self.invariants.append(row)

    def record_gate_run(self, **row):
        self.gate_runs.append(row)

    def audit(self, **row):
        self.audit_rows.append(row)


def _plan_rows(plan) -> list[dict]:
    return [
        {
            "invariant_id": row["invariant_id"],
            "location_repo": row["location_repo"],
            "executor_kind": row["executor_kind"],
            "run_command": row["run_command"],
        }
        for row in plan.invariants
    ]


def run(case_path: Path) -> dict:
    case = json.loads(case_path.read_text(encoding="utf-8"))
    pack_path = case_path.parent / case["domain_pack_path"]
    pack = FixturePack(json.loads(pack_path.read_text(encoding="utf-8")))
    event = NormalizedEvent(**case["event"])
    store = MemoryStore()
    orchestrator = Orchestrator(pack, store)
    plan = orchestrator.plan(event)
    captured = {}

    def fake_post(url: str, payload: dict) -> dict:
        if url.endswith("/plan"):
            return plan.model_dump()
        if url.endswith("/results"):
            captured["structured_result"] = payload
            result = StructuredResult(**payload)
            decision = orchestrator.handle_result(event, result)
            captured["decision"] = decision.model_dump()
            return decision.model_dump()
        raise AssertionError(f"unexpected reporter URL: {url}")

    original_post = reporter._post
    reporter._post = fake_post
    try:
        reporter.run(
            "http://marshal-fixture",
            event.repo,
            event.change_ref,
            event.diff_paths,
            event.labels,
        )
    finally:
        reporter._post = original_post

    result = captured["structured_result"]
    decision = captured["decision"]
    scope = {
        "repo": event.repo,
        "diff_paths": event.diff_paths,
        "labels": event.labels,
    }
    return {
        "schema_version": "marshal-gate-prediction-1",
        "case_id": case["case_id"],
        "system": "current-marshal-native-reporter",
        "classification": {
            "tier": pack.classify(scope),
            "contracts_hit": pack.contracts_hit(scope),
        },
        "plan": {"invariants": _plan_rows(plan)},
        "execution": {
            "status": result["status"],
            "results": result["payload"]["results"],
            "not_run": result["payload"]["not_run"],
        },
        "decision": {
            "gate_outcome": decision["gates"][0]["outcome"],
            "verdict": decision["verdict"],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("case", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.case)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

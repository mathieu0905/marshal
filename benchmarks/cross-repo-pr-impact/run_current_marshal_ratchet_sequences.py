#!/usr/bin/env python3
"""Run the temporal ratchet task through Marshal's current core integration."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from marshal_core.contracts import NormalizedEvent  # noqa: E402
from marshal_core.knowledge.models import Base  # noqa: E402
from marshal_core.knowledge.store import Store  # noqa: E402
from marshal_core.modules.orchestrator import Orchestrator  # noqa: E402


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class EmptyPack:
    """Represents the product state before a ratchet check enters pack code."""

    def __init__(self, identifier: str):
        self._id = identifier

    @property
    def id(self) -> str:
        return self._id

    def list_invariants(self, scope: dict) -> list:
        return []

    def classify(self, scope: dict) -> str:
        return "mid"


def event(document: dict[str, Any]) -> NormalizedEvent:
    return NormalizedEvent(
        kind="pr",
        repo=document["source_repository"],
        change_ref=document["change_ref"],
        diff_paths=document["changed_paths"],
    )


def run(sequences: list[dict[str, Any]], work_dir: Path) -> list[dict[str, Any]]:
    work_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    for sequence in sequences:
        database = work_dir / f"{sequence['sequence_id']}.sqlite3"
        engine = create_engine(f"sqlite:///{database}")
        Base.metadata.create_all(engine)
        session = sessionmaker(bind=engine)()
        try:
            store = Store(session)
            pack = EmptyPack(sequence["registration"]["domain_pack"])
            orchestrator = Orchestrator(pack=pack, store=store)
            escape = sequence["registration"]["escape_id"]
            check = sequence["registration"]["check_id"]
            store.open_escape(
                id=escape,
                description=f"benchmark escape {sequence['seed_e2_case_id']}",
                root_cause_class=sequence["source_change_family"],
                change_ref=sequence["escape_observation"]["change_ref"],
                domain_pack=pack.id,
            )
            store.close_escape_with_invariant(
                escape,
                spawned_check=check,
                invariant={**sequence["registration"]["invariant"], "domain_pack": pack.id},
            )
            recurrence_plan = orchestrator.plan(event(sequence["recurrence"]))
            unrelated_plan = orchestrator.plan(event(sequence["unrelated_control"]))
            outputs.append({
                "sequence_id": sequence["sequence_id"],
                "registered_check_id": store.get_escape(escape).spawned_check,
                "recurrence_scheduled_check_ids": [row["invariant_id"] for row in recurrence_plan.invariants],
                "unrelated_scheduled_check_ids": [row["invariant_id"] for row in unrelated_plan.invariants],
                "recurrence_execution": {"status": "not_assessed"},
                "recurrence_decision": "not_assessed",
                "diagnosis": "The check is stored in InvariantRegistry, but Orchestrator.plan reads only DomainPack.list_invariants; current core does not schedule the newly registered row.",
            })
        finally:
            session.close()
            engine.dispose()
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sequences", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = run(read_jsonl(args.sequences), args.work_dir)
    args.output.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    print(json.dumps({"sequence_count": len(rows), "recurrence_scheduled_count": sum(bool(row["recurrence_scheduled_check_ids"]) for row in rows)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

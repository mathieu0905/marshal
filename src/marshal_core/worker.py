"""Job worker: claims review_job rows and runs them.

Phase 2 handles only the 'mechanical' kind — it rebuilds a NormalizedEvent and
calls Orchestrator.plan(), which re-selects/registers the applicable invariants.
A mechanical re-plan does NOT produce a gate_run verdict; that is the Phase 3
deep worker's job. 'deep' jobs are failed here with a clear message until then.
"""
import os
import time

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from marshal_core.contracts import NormalizedEvent
from marshal_core.knowledge.models import Base
from marshal_core.knowledge.store import Store
from marshal_core.modules.orchestrator import Orchestrator
from marshal_pack_cowboy.pack import CowboyPack


def _run_mechanical(store: Store, pack, job: dict) -> dict:
    event = NormalizedEvent(kind="pr", repo=job["repo"],
                            change_ref=job["change_ref"], diff_paths=[])
    resp = Orchestrator(pack, store).plan(event)
    ids = [i["invariant_id"] for i in resp.invariants]
    return {"invariant_ids": ids, "count": len(ids), "job_id": resp.job_id}


def run_once(store: Store, pack) -> bool:
    """Claim and process at most one job. Returns True if a job was handled."""
    job = store.claim_next_job()
    if job is None:
        return False
    try:
        if job["kind"] == "mechanical":
            result = _run_mechanical(store, pack, job)
            store.finish_job(job["id"], result=result)
        else:
            store.fail_job(job["id"],
                           error="deep review not available until Phase 3")
    except Exception as exc:  # never leave a job stuck 'running'
        store.fail_job(job["id"], error=f"{type(exc).__name__}: {exc}")
    return True


def main() -> None:  # pragma: no cover - thin process loop
    engine = create_engine(os.environ.get("MARSHAL_DB", "sqlite:///marshal.db"))
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    pack = CowboyPack()
    poll = float(os.environ.get("MARSHAL_WORKER_POLL_SECONDS", "2"))
    while True:
        with Session() as s:
            handled = run_once(Store(s), pack)
        if not handled:
            time.sleep(poll)


if __name__ == "__main__":  # pragma: no cover
    main()

"""Job worker: claims review_job rows and runs them.

Phase 2 handles only the 'mechanical' kind — it rebuilds a NormalizedEvent and
calls Orchestrator.plan(), which re-selects/registers the applicable invariants.
A mechanical re-plan does NOT produce a gate_run verdict; that is the Phase 3
deep worker's job. 'deep' jobs are failed here with a clear message until then.
"""
import json
import os
import subprocess
import time
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from marshal_core.contracts import NormalizedEvent
from marshal_core.knowledge.models import Base
from marshal_core.knowledge.store import Store
from marshal_core.modules.orchestrator import Orchestrator
from marshal_pack_cowboy.pack import CowboyPack


VERDICT_FILE = "MARSHAL_VERDICT.json"


class DeepReviewError(Exception):
    """Raised when a deep review cannot produce a usable verdict."""


def _parse_verdict(path: str) -> dict:
    if not os.path.exists(path):
        raise DeepReviewError(f"verdict file not written: {path}")
    try:
        with open(path) as fh:
            data = json.loads(fh.read())
    except (ValueError, OSError) as exc:
        raise DeepReviewError(f"verdict file unparseable: {exc}")
    if data.get("verdict") not in ("pass", "needs_human", "block"):
        raise DeepReviewError(f"invalid verdict: {data.get('verdict')!r}")
    return data


def _worktree_base() -> str:
    return os.environ.get("MARSHAL_WORKTREE_BASE",
                          os.path.expanduser("~/.marshal/worktrees"))


@contextmanager
def _deep_worktree(repo: str, change_ref: str):
    # Isolated git worktree of the target repo at change_ref, on a STABLE path
    # (never /tmp — /tmp worktrees get reaped mid-run). Torn down unconditionally.
    workspace = os.environ.get("MARSHAL_WORKSPACE", "/home/ubuntu/workspace")
    repo_root = os.path.join(workspace, repo)
    base = _worktree_base()
    os.makedirs(base, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-._" else "_" for c in f"{repo}-{change_ref}")
    wt = os.path.join(base, safe[:120])
    try:
        subprocess.run(["git", "-C", repo_root, "worktree", "add", "--detach", wt, change_ref],
                       check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        raise DeepReviewError(f"worktree add failed: {exc.stderr[:300]}")
    try:
        yield wt
    finally:
        subprocess.run(["git", "-C", repo_root, "worktree", "remove", "--force", wt],
                       capture_output=True, text=True)


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
        # If the handler failed mid-commit the session is in a pending-rollback
        # state; clear it so fail_job can persist the failure on the same session.
        store.s.rollback()
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

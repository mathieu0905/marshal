"""Job worker: claims review_job rows and runs them.

Phase 2 handles only the 'mechanical' kind — it rebuilds a NormalizedEvent and
calls Orchestrator.plan(), which re-selects/registers the applicable invariants.
A mechanical re-plan does NOT produce a gate_run verdict; that is the Phase 3
deep worker's job. 'deep' jobs are failed here with a clear message until then.
"""
import json
import os
import shutil
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


def _worktree_path(repo: str, change_ref: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-._" else "_" for c in f"{repo}-{change_ref}")
    return os.path.join(_worktree_base(), safe[:120])


@contextmanager
def _deep_worktree(repo: str, change_ref: str):
    # Isolated git worktree of the target repo at change_ref, on a STABLE path
    # (never /tmp — /tmp worktrees get reaped mid-run). Torn down unconditionally.
    workspace = os.environ.get("MARSHAL_WORKSPACE", "/home/ubuntu/workspace")
    repo_root = os.path.join(workspace, repo)
    os.makedirs(_worktree_base(), exist_ok=True)
    wt = _worktree_path(repo, change_ref)
    # Self-heal a worktree left behind by a hard-crashed prior run: the path is a
    # deterministic function of (repo, change_ref), so a stale dir/registration would
    # otherwise make `worktree add` fail forever for this ref. prune reclaims dropped
    # registrations; force-remove + rmtree clear a lingering directory.
    subprocess.run(["git", "-C", repo_root, "worktree", "prune"],
                   capture_output=True, text=True)
    subprocess.run(["git", "-C", repo_root, "worktree", "remove", "--force", wt],
                   capture_output=True, text=True)
    if os.path.exists(wt):
        shutil.rmtree(wt, ignore_errors=True)
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


def _deep_timeout() -> float:
    return float(os.environ.get("MARSHAL_DEEP_TIMEOUT_S", "1800"))  # 30 min default


def _invoke_claude(prompt: str, cwd: str, timeout_s: float) -> str:
    # The ONLY un-CI'd seam: shells out to the real `claude -p`. Subprocess mechanics
    # (timeout kill, non-zero exit) are still CI-tested via a fake MARSHAL_CLAUDE_BIN;
    # only the real-Claude semantics are exercised by the manual smoke.
    binary = os.environ.get("MARSHAL_CLAUDE_BIN", "claude")
    proc = subprocess.run([binary, "-p", prompt], cwd=cwd,
                          capture_output=True, text=True, timeout=timeout_s)
    if proc.returncode != 0:
        raise DeepReviewError(f"claude exited {proc.returncode}: {proc.stderr[:500]}")
    return proc.stdout


def _deep_prompt(job: dict) -> str:
    return (
        f"Run the full /marshal deep review gate on the current git worktree, which is "
        f"checked out at commit {job['change_ref']} of the {job['repo']} repo. "
        f"This is a LOCAL-ONLY dashboard-triggered review: do NOT post anything to GitHub, "
        f"Linear, or any external service. When the review is complete, write your final "
        f"verdict to a file named {VERDICT_FILE} in the current working directory, as JSON "
        f'with keys: "verdict" (one of "pass", "needs_human", "block"; map an escalate to '
        f'"needs_human"), "summary" (string), "findings" (array of strings), '
        f'"invariants_run" (int), "invariants_pass" (int).'
    )


def _run_deep(store: Store, job: dict) -> None:
    with _deep_worktree(job["repo"], job["change_ref"]) as wt:
        _invoke_claude(_deep_prompt(job), cwd=wt, timeout_s=_deep_timeout())
        verdict = _parse_verdict(os.path.join(wt, VERDICT_FILE))
    gr = store.record_gate_run(
        change_ref=job["change_ref"], job_id=f"deep-{job['id']}",
        verdict=verdict["verdict"],
        evidence={"source": "dashboard-worker", "job_id": job["id"],
                  "summary": verdict.get("summary", ""),
                  "findings": verdict.get("findings", []),
                  "invariants_run": verdict.get("invariants_run"),
                  "invariants_pass": verdict.get("invariants_pass")})
    store.finish_job(job["id"], result={"verdict": verdict["verdict"], "gate_run_id": gr.id})


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
        else:  # deep
            _run_deep(store, job)
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

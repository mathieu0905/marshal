"""FastAPI 接入端点。POST /webhook (PR 事件), POST /results (CI 回传)。"""
import os
import time
from pathlib import Path
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from marshal_core.config import db_url
from marshal_core.contracts import StructuredResult, NormalizedEvent
from marshal_core.knowledge.models import ensure_schema
from marshal_core.knowledge.store import Store
from marshal_core.modules.orchestrator import Orchestrator
from marshal_core.adapters.github import parse_pull_request_event, build_check_run
from marshal_core import pr_inbox
from marshal_pack_cowboy.pack import CowboyPack

_STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Marshal")
_engine = create_engine(db_url())
ensure_schema(_engine)
_Session = sessionmaker(bind=_engine)
_PACK = CowboyPack()
_pr_cache = {"at": 0.0, "data": None}

_EVENTS: dict[str, NormalizedEvent] = {}


@app.post("/webhook")
async def webhook(request: Request):
    payload = await request.json()
    if "pull_request" not in payload:
        return {"ignored": True}
    ev = parse_pull_request_event(payload)
    _EVENTS[ev.change_ref] = ev
    with _Session() as s:
        job = Orchestrator(_PACK, Store(s)).handle_event(ev)
    return {"job_id": job.job_id, "invariant_ids": job.params["invariant_ids"]}


@app.post("/plan")
async def plan(event: NormalizedEvent):
    with _Session() as s:
        resp = Orchestrator(_PACK, Store(s)).plan(event)
    _EVENTS[event.change_ref] = event
    return resp.model_dump()


@app.post("/results")
async def results(result: StructuredResult):
    change_ref = result.job_id.removeprefix("inv-")
    ev = _EVENTS.get(change_ref) or NormalizedEvent(
        kind="pr", repo="node", change_ref=change_ref)
    with _Session() as s:
        decision = Orchestrator(_PACK, Store(s)).handle_result(ev, result)
    check_run = build_check_run(decision, shadow=True)
    return {"verdict": decision.verdict, "check_run": check_run}


@app.get("/api/inbox")
def api_inbox():
    ttl = float(os.environ.get("MARSHAL_INBOX_TTL_S", "90"))
    now = time.monotonic()
    if _pr_cache["data"] is None or now - _pr_cache["at"] > ttl:
        try:
            with _Session() as s:
                _pr_cache["data"] = pr_inbox.build_inbox(s)
            _pr_cache["at"] = now
        except Exception:
            if _pr_cache["data"] is None:
                _pr_cache["data"] = []   # first build failed -> serve empty, never 500
    return {"prs": _pr_cache["data"],
            "github_token": bool(os.environ.get("GITHUB_TOKEN")),
            "repos": [f"{o}/{r}" for o, r in pr_inbox.bound_repos()]}


@app.get("/api/runs/{run_id}")
def api_run(run_id: int):
    with _Session() as s:
        run = Store(s).get_gate_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="gate_run not found")
        return {"id": run.id, "change_ref": run.change_ref, "job_id": run.job_id,
                "verdict": run.verdict, "evidence": run.evidence,
                "created_at": run.created_at.isoformat()}


@app.get("/api/escapes")
def api_escapes():
    with _Session() as s:
        return Store(s).escape_breakdown()


@app.get("/api/health")
def api_health():
    with _Session() as s:
        st = Store(s)
        payload = st.metrics()
        payload["escape_breakdown"] = st.escape_breakdown()
        payload["invariant_breakdown"] = st.invariant_breakdown()
        payload["verdict_timeseries"] = st.verdict_timeseries()
        return payload


@app.get("/")
def spa():
    return FileResponse(_STATIC_DIR / "index.html")


def _check_job_token(x_marshal_token: str | None) -> None:
    expected = os.environ.get("MARSHAL_JOB_TOKEN")
    if expected and x_marshal_token != expected:
        raise HTTPException(status_code=403, detail="invalid or missing token")


@app.post("/api/jobs")
def api_create_job(body: dict, x_marshal_token: str | None = Header(default=None)):
    _check_job_token(x_marshal_token)
    change_ref = body.get("change_ref")
    if not change_ref:
        raise HTTPException(status_code=422, detail="change_ref required")
    kind = body.get("kind", "mechanical")
    if kind not in ("mechanical", "deep"):
        raise HTTPException(status_code=422, detail="kind must be mechanical or deep")
    with _Session() as s:
        return Store(s).enqueue_job(change_ref=change_ref,
                                    repo=body.get("repo", "node"), kind=kind)


@app.get("/api/jobs/{job_id}")
def api_get_job(job_id: int, x_marshal_token: str | None = Header(default=None)):
    _check_job_token(x_marshal_token)
    with _Session() as s:
        job = Store(s).get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        return job

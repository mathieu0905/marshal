"""FastAPI 接入端点。POST /webhook (PR 事件), POST /results (CI 回传)。"""
import os
from fastapi import FastAPI, HTTPException, Request
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from marshal_core.contracts import StructuredResult, NormalizedEvent
from marshal_core.knowledge.models import Base
from marshal_core.knowledge.store import Store
from marshal_core.modules.orchestrator import Orchestrator
from marshal_core.adapters.github import parse_pull_request_event, build_check_run
from marshal_pack_cowboy.pack import CowboyPack

app = FastAPI(title="Marshal")
_engine = create_engine(os.environ.get("MARSHAL_DB", "sqlite:///marshal.db"))
Base.metadata.create_all(_engine)
_Session = sessionmaker(bind=_engine)
_PACK = CowboyPack()

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
def api_inbox(limit: int = 50):
    with _Session() as s:
        return Store(s).list_needs_human(limit=limit)


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

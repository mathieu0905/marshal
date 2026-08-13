from marshal_core.knowledge.store import Store
from marshal_pack_cowboy.pack import CowboyPack
from marshal_core.worker import run_once


def test_run_once_no_jobs_returns_false(db_session):
    assert run_once(Store(db_session), CowboyPack()) is False


def test_run_once_mechanical_replans_and_marks_done(db_session):
    s = Store(db_session)
    job = s.enqueue_job(change_ref="abc123", repo="node", kind="mechanical")
    handled = run_once(s, CowboyPack())
    assert handled is True
    done = s.get_job(job["id"])
    assert done["status"] == "done"
    assert done["result"]["count"] >= 1
    assert "econ.fee_conservation" in done["result"]["invariant_ids"]


def test_run_once_deep_job_fails_gracefully_in_phase2(db_session):
    s = Store(db_session)
    job = s.enqueue_job(change_ref="abc123", repo="node", kind="deep")
    assert run_once(s, CowboyPack()) is True
    failed = s.get_job(job["id"])
    assert failed["status"] == "failed"
    assert "Phase 3" in failed["error"]


def test_run_once_records_failure_on_handler_exception(db_session, monkeypatch):
    s = Store(db_session)
    job = s.enqueue_job(change_ref="abc123", repo="node", kind="mechanical")
    import marshal_core.worker as w
    monkeypatch.setattr(w, "_run_mechanical",
                        lambda store, pack, jb: (_ for _ in ()).throw(RuntimeError("kaboom")))
    assert run_once(s, CowboyPack()) is True
    failed = s.get_job(job["id"])
    assert failed["status"] == "failed"
    assert "kaboom" in failed["error"]

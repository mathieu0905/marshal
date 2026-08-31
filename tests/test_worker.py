import json
from contextlib import contextmanager

from marshal_core.knowledge.store import Store
from marshal_core.knowledge.models import GateRun, ReviewRun
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


def test_run_once_marks_failed_even_if_finish_job_raises(db_session, monkeypatch):
    # Core invariant: a claimed job is never left 'running'. If finish_job blows up
    # after a successful handler, run_once must still land the job in 'failed'.
    s = Store(db_session)
    job = s.enqueue_job(change_ref="abc123", repo="node", kind="mechanical")

    def boom_finish(*a, **k):
        raise RuntimeError("finish exploded")
    monkeypatch.setattr(s, "finish_job", boom_finish)

    assert run_once(s, CowboyPack()) is True
    row = s.get_job(job["id"])
    assert row["status"] == "failed"           # NOT left 'running'
    assert "finish exploded" in row["error"]


def _deep_verdict(*, evidence=True):
    body = {
        "verdict": "pass",
        "summary": "reviewed",
        "findings": [],
        "invariants_run": 1,
        "invariants_pass": 1,
    }
    if evidence:
        body["evidence"] = {
            "steps": {
                name: {"status": "complete", "evidence_ref": f"artifact:{name}"}
                for name in ("closure", "scout", "prove", "invariant")
            },
            "external_scan": {"status": "complete", "findings": 0},
        }
    return body


def _patch_deep_worker(monkeypatch, worktree, verdict):
    import marshal_core.worker as worker

    @contextmanager
    def fake_worktree(repo, change_ref):
        yield str(worktree)

    def fake_invoke(prompt, cwd, timeout_s):
        (worktree / worker.VERDICT_FILE).write_text(json.dumps(verdict))
        return "ok"

    monkeypatch.setattr(worker, "_deep_worktree", fake_worktree)
    monkeypatch.setattr(worker, "_resolve_pr_number", lambda repo, change_ref: None)
    monkeypatch.setattr(worker, "_invoke_claude", fake_invoke)
    monkeypatch.setattr(worker, "_git_review_identity", lambda wt: {
        "head_sha": "a" * 40,
        "base_sha": "b" * 40,
        "tree_sha": "c" * 40,
    })


def test_deep_worker_closes_review_run_before_recording_pass(db_session, monkeypatch, tmp_path):
    _patch_deep_worker(monkeypatch, tmp_path, _deep_verdict())
    store = Store(db_session)
    job = store.enqueue_job(change_ref="a" * 40, repo="node", kind="deep")

    assert run_once(store, CowboyPack()) is True

    done = store.get_job(job["id"])
    assert done["status"] == "done"
    assert done["result"]["verdict"] == "pass"
    review = db_session.get(ReviewRun, done["result"]["review_run_id"])
    gate = db_session.get(GateRun, done["result"]["gate_run_id"])
    assert review.status == "complete"
    assert review.evidence["commands"][0]["exit_code"] == 0
    assert review.evidence["commands"][0]["stdout_tail"] == "ok"
    assert review.evidence["verdict_payload"]["summary"] == "reviewed"
    assert gate.verdict == "pass"
    assert gate.evidence["review_run_id"] == review.id


def test_deep_worker_downgrades_unevidenced_pass(db_session, monkeypatch, tmp_path):
    _patch_deep_worker(monkeypatch, tmp_path, _deep_verdict(evidence=False))
    store = Store(db_session)
    job = store.enqueue_job(change_ref="a" * 40, repo="node", kind="deep")

    assert run_once(store, CowboyPack()) is True

    done = store.get_job(job["id"])
    assert done["status"] == "done"
    assert done["result"]["raw_verdict"] == "pass"
    assert done["result"]["verdict"] == "needs_human"
    review = db_session.get(ReviewRun, done["result"]["review_run_id"])
    assert review.status == "degraded"
    assert review.evidence["external_scans"][0]["status"] == "unavailable"


def test_deep_worker_failure_closes_degraded_review_run(db_session, monkeypatch, tmp_path):
    import marshal_core.worker as worker

    _patch_deep_worker(monkeypatch, tmp_path, _deep_verdict())

    def fail_invoke(prompt, cwd, timeout_s):
        raise worker.DeepReviewError("model process failed")

    monkeypatch.setattr(worker, "_invoke_claude", fail_invoke)
    store = Store(db_session)
    job = store.enqueue_job(change_ref="a" * 40, repo="node", kind="deep")

    assert run_once(store, CowboyPack()) is True

    failed = store.get_job(job["id"])
    assert failed["status"] == "failed"
    reviews = list(db_session.query(ReviewRun))
    assert len(reviews) == 1
    assert reviews[0].status == "degraded"
    assert reviews[0].evidence["commands"][0]["status"] == "fail"
    assert "model process failed" in reviews[0].evidence["commands"][0]["reason"]

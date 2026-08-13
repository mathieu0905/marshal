from marshal_core.knowledge.models import ReviewJob
from marshal_core.knowledge.store import Store


def test_review_job_defaults(db_session):
    job = ReviewJob(change_ref="node#7", repo="node")
    db_session.add(job)
    db_session.commit()
    assert job.id is not None
    assert job.status == "pending"
    assert job.kind == "mechanical"
    assert job.requested_by == "dashboard"
    assert job.created_at is not None
    assert job.started_at is None
    assert job.finished_at is None
    assert job.result is None
    assert job.error is None


def test_enqueue_and_get_job_roundtrip(db_session):
    s = Store(db_session)
    job = s.enqueue_job(change_ref="node#7", repo="node")
    assert job["id"] is not None
    assert job["status"] == "pending"
    assert job["kind"] == "mechanical"
    fetched = s.get_job(job["id"])
    assert fetched["change_ref"] == "node#7"
    assert fetched["repo"] == "node"
    assert fetched["result"] is None


def test_get_job_missing_returns_none(db_session):
    s = Store(db_session)
    assert s.get_job(99999) is None

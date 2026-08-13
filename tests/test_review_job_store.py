from marshal_core.knowledge.models import ReviewJob


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

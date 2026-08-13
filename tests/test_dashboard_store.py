from marshal_core.knowledge.store import Store


def _seed_runs(s):
    s.record_gate_run(change_ref="node#1", job_id="j1", verdict="pass", evidence={})
    s.record_gate_run(change_ref="node#2", job_id="j2", verdict="needs_human",
                      evidence={"pr": 2, "repo": "node", "tier": "high", "cip": "CIP-3",
                                "dimensions": ["econ"], "invariants_run": 5,
                                "invariants_pass": 5, "high_sev_findings": 0,
                                "advisory_findings": ["a1"]})
    s.record_gate_run(change_ref="node#3", job_id="j3", verdict="needs_human",
                      evidence={"pr": 3, "repo": "runner", "tier": "mid"})
    s.record_gate_run(change_ref="node#4", job_id="j4", verdict="block", evidence={})


def test_list_needs_human_returns_only_needs_human_newest_first(db_session):
    s = Store(db_session)
    _seed_runs(s)
    rows = s.list_needs_human()
    assert [r["change_ref"] for r in rows] == ["node#3", "node#2"]
    assert rows[0]["id"] is not None
    assert rows[0]["verdict"] == "needs_human"
    assert rows[1]["evidence"]["tier"] == "high"


def test_list_needs_human_respects_limit(db_session):
    s = Store(db_session)
    _seed_runs(s)
    assert len(s.list_needs_human(limit=1)) == 1

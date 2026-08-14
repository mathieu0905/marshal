from marshal_core.knowledge.store import Store
from marshal_core import github_backfill as gbf


def test_inbox_summary_reads_backfill():
    ev = {"gates": {"tier": "mid"}, "_backfill": {"repo": "node", "pr": 999}}
    s = Store.inbox_summary(ev)
    assert s["repo"] == "node" and s["pr"] == 999 and s["title"] == "node #999"


def test_candidate_repos_from_links(db_session):
    s = Store(db_session)
    s.record_gate_run(change_ref="a", job_id="a", verdict="escalate",
                      evidence={"gates": {"comment_url": "https://github.com/cowboyinc/node/pull/7#c"}})
    s.record_gate_run(change_ref="b", job_id="b", verdict="pass",
                      evidence={"gates": {"marker_url": "https://github.com/shawhanken/marshal/pull/3"}})
    cands = set(gbf.candidate_repos(db_session))
    assert ("cowboyinc", "node") in cands and ("shawhanken", "marshal") in cands


def test_backfill_writes_repo_pr_and_inbox_reads_it(db_session):
    s = Store(db_session)
    s.record_gate_run(change_ref="known", job_id="k", verdict="escalate",
                      evidence={"gates": {"comment_url": "https://github.com/cowboyinc/node/pull/7#c"}})
    s.record_gate_run(change_ref="baresha123", job_id="bare", verdict="escalate",
                      evidence={"gates": {"tier": "mid"}})

    def fake_fetch(org, repo, sha):
        if (org, repo) == ("cowboyinc", "node") and sha == "baresha123":
            return [{"number": 1307}]
        return []

    assert gbf.backfill(db_session, fetch=fake_fetch) == 1
    row = next(r for r in s.list_needs_human() if r["change_ref"] == "baresha123")
    assert row["summary"]["title"] == "node #1307"


def test_backfill_skips_rows_that_already_have_identity(db_session):
    s = Store(db_session)
    s.record_gate_run(change_ref="x", job_id="x", verdict="escalate",
                      evidence={"gates": {"repo": "node", "pr": 5,
                                          "comment_url": "https://github.com/o/node/pull/5"}})
    calls = []

    def fake_fetch(org, repo, sha):
        calls.append(sha)
        return []

    assert gbf.backfill(db_session, fetch=fake_fetch) == 0
    assert calls == []   # never queried GitHub for an already-identified row

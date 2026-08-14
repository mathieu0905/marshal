from marshal_core import pr_inbox


def test_bound_repos_default(monkeypatch):
    monkeypatch.delenv("MARSHAL_REPOS", raising=False)
    repos = pr_inbox.bound_repos()
    assert ("cowboyinc", "node") in repos and ("shawhanken", "marshal") in repos


def test_bound_repos_from_env(monkeypatch):
    monkeypatch.setenv("MARSHAL_REPOS", "acme/foo, acme/bar")
    assert pr_inbox.bound_repos() == [("acme", "foo"), ("acme", "bar")]


def test_eligibility_conflict_and_ci():
    assert pr_inbox.eligibility("dirty", "success") == (False, "merge conflict")
    assert pr_inbox.eligibility("clean", "failure") == (False, "CI failing")
    assert pr_inbox.eligibility("clean", "success") == (True, None)
    assert pr_inbox.eligibility(None, None) == (True, None)
    assert pr_inbox.eligibility("blocked", "pending") == (True, None)


from marshal_core.knowledge.store import Store


def test_build_inbox_joins_prs_eligibility_and_last_review(db_session, monkeypatch):
    # a prior local review of node#7 at an OLD head -> should show as stale
    s = Store(db_session)
    s.record_gate_run(change_ref="oldhead", job_id="j", verdict="escalate",
                      evidence={"gates": {"repo": "node", "pr": 7}})

    def fake_list(org, repo, per_page=30):
        if repo != "node":
            return []
        return [
            {"number": 7, "title": "fix A", "html_url": "u7", "updated_at": "2026-08-14T02:00:00Z",
             "draft": False, "head": {"sha": "newhead"}},
            {"number": 9, "title": "fix B", "html_url": "u9", "updated_at": "2026-08-14T05:00:00Z",
             "draft": True, "head": {"sha": "h9"}},
        ]
    monkeypatch.setattr(pr_inbox, "list_open_prs", fake_list)
    monkeypatch.setattr(pr_inbox, "pr_detail",
                        lambda o, r, n: {"mergeable_state": "dirty"} if n == 7 else {"mergeable_state": "clean"})
    monkeypatch.setattr(pr_inbox, "commit_status", lambda o, r, sha: "success")

    inbox = pr_inbox.build_inbox(db_session, repos=[("cowboyinc", "node")])
    assert [p["number"] for p in inbox] == [9, 7]          # sorted by updated_at desc
    p9, p7 = inbox[0], inbox[1]
    assert p9["draft"] is True and p9["eligible"] is True   # drafts are eligible
    assert p7["eligible"] is False and p7["blocked_reason"] == "merge conflict"
    assert p7["last_review"] == {"verdict": "escalate", "reviewed_head": "oldhead", "stale": True}
    assert p9["last_review"] is None                        # never reviewed
    assert p7["title"] == "fix A" and p7["url"] == "u7"


def test_build_inbox_uses_newest_review_when_pr_reviewed_twice(db_session, monkeypatch):
    s = Store(db_session)
    # two reviews of node#7: an older one, then a newer one at the PR's current head
    s.record_gate_run(change_ref="oldhead", job_id="j1", verdict="escalate",
                      evidence={"gates": {"repo": "node", "pr": 7}})
    s.record_gate_run(change_ref="curhead", job_id="j2", verdict="needs_human",
                      evidence={"gates": {"repo": "node", "pr": 7}})
    monkeypatch.setattr(pr_inbox, "list_open_prs",
                        lambda o, r, per_page=30: [{"number": 7, "title": "t", "html_url": "u",
                                                    "updated_at": "2026-08-14T00:00:00Z",
                                                    "draft": False, "head": {"sha": "curhead"}}])
    monkeypatch.setattr(pr_inbox, "pr_detail", lambda o, r, n: {"mergeable_state": "clean"})
    monkeypatch.setattr(pr_inbox, "commit_status", lambda o, r, sha: "success")
    inbox = pr_inbox.build_inbox(db_session, repos=[("cowboyinc", "node")])
    lr = inbox[0]["last_review"]
    assert lr["verdict"] == "needs_human"        # the NEWER review wins, not "escalate"
    assert lr["reviewed_head"] == "curhead"
    assert lr["stale"] is False                  # reviewed at the current head


def test_ci_from_check_runs():
    assert pr_inbox._ci_from_check_runs([{"status": "completed", "conclusion": "failure"}]) == "failure"
    assert pr_inbox._ci_from_check_runs(
        [{"status": "completed", "conclusion": "success"},
         {"status": "completed", "conclusion": "success"}]) == "success"
    assert pr_inbox._ci_from_check_runs([{"status": "in_progress", "conclusion": None}]) == "pending"
    assert pr_inbox._ci_from_check_runs([]) is None
    # any failing run wins, even mixed with successes
    assert pr_inbox._ci_from_check_runs(
        [{"status": "completed", "conclusion": "success"},
         {"status": "completed", "conclusion": "timed_out"}]) == "failure"


def test_build_inbox_already_reviewed_current_head_is_pending(db_session, monkeypatch):
    # reviewed at the PR's CURRENT head, no new commits -> 待处理 (skip; pr-sweep principle)
    s = Store(db_session)
    s.record_gate_run(change_ref="curhead", job_id="j", verdict="needs_human",
                      evidence={"gates": {"repo": "node", "pr": 5}})
    monkeypatch.setattr(pr_inbox, "list_open_prs",
                        lambda o, r, per_page=30: [{"number": 5, "title": "t", "html_url": "u",
                                                    "updated_at": "2026-08-14T00:00:00Z",
                                                    "draft": False, "head": {"sha": "curhead"}}])
    monkeypatch.setattr(pr_inbox, "pr_detail", lambda o, r, n: {"mergeable_state": "clean"})
    monkeypatch.setattr(pr_inbox, "commit_status", lambda o, r, sha: "success")
    p = pr_inbox.build_inbox(db_session, repos=[("cowboyinc", "node")])[0]
    assert p["eligible"] is False
    assert "no new commits" in p["blocked_reason"]
    assert p["last_review"]["stale"] is False


def test_build_inbox_stale_review_stays_eligible(db_session, monkeypatch):
    # reviewed at an OLD head -> code changed -> still eligible (re-review the new head)
    s = Store(db_session)
    s.record_gate_run(change_ref="oldhead", job_id="j", verdict="escalate",
                      evidence={"gates": {"repo": "node", "pr": 5}})
    monkeypatch.setattr(pr_inbox, "list_open_prs",
                        lambda o, r, per_page=30: [{"number": 5, "title": "t", "html_url": "u",
                                                    "updated_at": "2026-08-14T00:00:00Z",
                                                    "draft": False, "head": {"sha": "newhead"}}])
    monkeypatch.setattr(pr_inbox, "pr_detail", lambda o, r, n: {"mergeable_state": "clean"})
    monkeypatch.setattr(pr_inbox, "commit_status", lambda o, r, sha: "success")
    p = pr_inbox.build_inbox(db_session, repos=[("cowboyinc", "node")])[0]
    assert p["eligible"] is True
    assert p["last_review"]["stale"] is True


def test_build_inbox_passed_pr_is_pending_even_if_stale(db_session, monkeypatch):
    # latest verdict is pass -> approved, no re-review needed even though head moved
    s = Store(db_session)
    s.record_gate_run(change_ref="oldhead", job_id="j", verdict="pass",
                      evidence={"gates": {"repo": "node", "pr": 5}})
    monkeypatch.setattr(pr_inbox, "list_open_prs",
                        lambda o, r, per_page=30: [{"number": 5, "title": "t", "html_url": "u",
                                                    "updated_at": "2026-08-14T00:00:00Z",
                                                    "draft": False, "head": {"sha": "newhead"}}])
    monkeypatch.setattr(pr_inbox, "pr_detail", lambda o, r, n: {"mergeable_state": "clean"})
    monkeypatch.setattr(pr_inbox, "commit_status", lambda o, r, sha: "success")
    p = pr_inbox.build_inbox(db_session, repos=[("cowboyinc", "node")])[0]
    assert p["eligible"] is False and p["blocked_reason"] == "reviewed pass"
    assert p["last_review"]["stale"] is True

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

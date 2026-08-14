import importlib
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "dash.db"
    monkeypatch.setenv("MARSHAL_DB", f"sqlite:///{db_file}")
    import marshal_core.adapters.api as api
    importlib.reload(api)
    # seed via the same engine the app now uses
    from marshal_core.knowledge.store import Store
    with api._Session() as s:
        st = Store(s)
        st.record_gate_run(change_ref="node#2", job_id="j2", verdict="needs_human",
                           evidence={"pr": 2, "repo": "node", "tier": "high"})
        st.record_gate_run(change_ref="node#9", job_id="j9", verdict="pass", evidence={})
    return TestClient(api.app)


def test_inbox_returns_only_needs_human(client):
    r = client.get("/api/inbox")
    assert r.status_code == 200
    body = r.json()
    assert [row["change_ref"] for row in body] == ["node#2"]
    assert body[0]["evidence"]["tier"] == "high"


def test_runs_endpoint_returns_evidence(client):
    run_id = client.get("/api/inbox").json()[0]["id"]
    r = client.get(f"/api/runs/{run_id}")
    assert r.status_code == 200
    assert r.json()["change_ref"] == "node#2"


def test_runs_endpoint_404_on_missing(client):
    r = client.get("/api/runs/99999")
    assert r.status_code == 404


def test_health_composes_metrics_and_breakdowns(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    # verdict distribution comes straight from metrics()
    assert body["gate_runs_by_verdict"]["needs_human"] == 1
    assert body["gate_runs_by_verdict"]["pass"] == 1
    # new aggregate blocks are present
    assert "escape_breakdown" in body
    assert "invariant_breakdown" in body
    assert "verdict_timeseries" in body
    # honest gaps carried through (but MTTD now computed in Phase 4)
    assert "mean_time_to_detection" not in body["unavailable"]
    assert "mean_time_to_detection" in body                      # now a real top-level metric
    assert "count" in body["mean_time_to_detection"]


def test_escapes_endpoint_returns_breakdown(client):
    with_escape = client.get("/api/escapes")
    assert with_escape.status_code == 200
    assert isinstance(with_escape.json(), list)


def test_root_serves_spa(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Marshal" in r.text
    assert 'id="app"' in r.text


def test_spa_has_rereview_button_wiring(client):
    html = client.get("/").text
    assert "re-review" in html
    assert "startJob" in html
    assert "/api/jobs" in html


def test_rereview_button_has_no_inline_onclick_handler(client):
    # Security regression guard: the button must NOT be wired via an inline
    # onclick that interpolates change_ref/repo (esc() is the wrong encoding for
    # the inline-handler JS sink and is bypassable). It must use addEventListener.
    html = client.get("/").text
    assert 'onclick="startJob' not in html
    assert "addEventListener" in html


def test_spa_has_deep_review_button(client):
    html = client.get("/").text
    assert "deep review" in html          # the new deep button label
    assert "'deep'" in html                # startJob(..., 'deep') wiring
    assert "re-review" in html             # mechanical button still present
    assert 'onclick="startJob' not in html # still no inline handler


def test_spa_locks_both_buttons_during_job(client):
    # UX race guard: a running job disables BOTH buttons in the row (collective
    # querySelectorAll('.btn')), so a user can't start a second concurrent job on
    # the same card and clobber the shared status span.
    html = client.get("/").text
    assert "querySelectorAll('.btn')" in html


def test_spa_renders_real_mttd_not_placeholder(client):
    html = client.get("/").text
    assert "mean_time_to_detection" in html      # SPA reads the real metric
    assert "pending Phase 4" not in html          # placeholder is gone

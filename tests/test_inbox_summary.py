from marshal_core.knowledge.store import Store

STABLE_KEYS = {"tier", "cip", "repo", "invariants_pass", "invariants_total",
               "findings", "advisory", "headline"}


def test_summary_always_has_stable_keys_even_for_empty_evidence():
    for ev in (None, {}, {"gates": {}}, {"gates": "not-a-dict"}):
        s = Store.inbox_summary(ev)
        assert set(s.keys()) == STABLE_KEYS
        assert all(v is None for v in s.values())


def test_summary_from_nested_gates_with_invariants_map():
    # real production shape: fields under `gates`, invariants a {name: status} map
    ev = {"gates": {"tier": "mid",
                    "invariants": {"a": "pass", "b": "pass", "c": "fail"},
                    "change": "test-only python (+64)"}}
    s = Store.inbox_summary(ev)
    assert s["tier"] == "mid"
    assert s["invariants_pass"] == 2
    assert s["invariants_total"] == 3
    assert s["headline"] == "test-only python (+64)"


def test_summary_from_flat_fixture_shape():
    # flat fixture: fields at the top level, invariants as run/pass ints
    ev = {"tier": "high", "cip": "CIP-13", "repo": "node",
          "invariants_run": 10, "invariants_pass": 10,
          "high_sev_findings": 0, "advisory_findings": ["a1", "a2"]}
    s = Store.inbox_summary(ev)
    assert s["tier"] == "high"
    assert s["cip"] == "CIP-13"
    assert s["repo"] == "node"
    assert s["invariants_pass"] == 10
    assert s["invariants_total"] == 10
    assert s["findings"] == 0
    assert s["advisory"] == 2


def test_summary_counts_findings_from_list_or_int():
    assert Store.inbox_summary({"gates": {"findings": ["f1", "f2", "f3"]}})["findings"] == 3
    assert Store.inbox_summary({"gates": {"high_sev_findings": 4}})["findings"] == 4
    # a bare bool must NOT be read as a count
    assert Store.inbox_summary({"gates": {"findings": True}})["findings"] is None


def test_summary_headline_prefers_summary_then_fallbacks():
    assert Store.inbox_summary({"gates": {"summary": "S", "reason": "R"}})["headline"] == "S"
    assert Store.inbox_summary({"gates": {"reason": "R", "remedy": "M"}})["headline"] == "R"
    assert Store.inbox_summary({"gates": {"remedy": "M"}})["headline"] == "M"


def test_list_needs_human_includes_summary(db_session):
    s = Store(db_session)
    s.record_gate_run(change_ref="node#2", job_id="j2", verdict="needs_human",
                      evidence={"gates": {"tier": "low",
                                          "invariants": {"x": "pass"}}})
    rows = s.list_needs_human()
    assert rows[0]["summary"]["tier"] == "low"
    assert rows[0]["summary"]["invariants_total"] == 1
    assert rows[0]["summary"]["invariants_pass"] == 1

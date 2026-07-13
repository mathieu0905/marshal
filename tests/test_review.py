from marshal_core.review import (
    REFUTE_LENSES,
    aggregate_review,
    assign_refute_lenses,
    ratchet_lenses,
    verify_findings,
)


def _f(file, line, dim, sev, source, title="x"):
    return {"file": file, "line": line, "dimension": dim, "severity": sev,
            "source": source, "title": title}


def test_two_lenses_agree_reaches_quorum():
    findings = [
        _f("a.rs", 10, "correctness", "mid", "lens-correctness"),
        _f("a.rs", 10, "correctness", "mid", "lens-security"),
    ]
    out = aggregate_review(findings, quorum=2)
    g = out["groups"][0]
    assert g["support"] == 2 and g["status"] == "confirmed"
    assert out["review_verdict"] == "pass"  # confirmed but not high


def test_high_severity_escalates_even_with_single_support():
    findings = [_f("b.rs", 5, "security", "high", "lens-security")]
    out = aggregate_review(findings, quorum=2)
    assert out["groups"][0]["status"] == "needs_human"
    assert out["review_verdict"] == "needs_human"
    assert len(out["needs_human"]) == 1


def test_lone_low_severity_is_dropped_as_noise():
    findings = [_f("c.rs", 7, "style", "low", "lens-correctness")]
    out = aggregate_review(findings, quorum=2)
    assert out["groups"][0]["status"] == "weak"
    assert out["dropped"] and not out["confirmed"]
    assert out["review_verdict"] == "pass"


def test_group_takes_max_severity_and_distinct_sources():
    findings = [
        _f("d.rs", 1, "econ", "mid", "lens-econ"),
        _f("d.rs", 1, "econ", "high", "lens-correctness"),
        _f("d.rs", 1, "econ", "low", "lens-econ"),  # duplicate source
    ]
    out = aggregate_review(findings, quorum=2)
    g = out["groups"][0]
    assert g["severity"] == "high"
    assert g["support"] == 2  # distinct sources only
    assert g["status"] == "needs_human"


def test_explicit_key_overrides_file_line_dimension():
    findings = [
        {"key": "K", "severity": "mid", "source": "a", "title": "t"},
        {"key": "K", "severity": "mid", "source": "b", "title": "t"},
    ]
    out = aggregate_review(findings, quorum=2)
    assert len(out["groups"]) == 1 and out["groups"][0]["support"] == 2


def _v(*refuted):
    return [{"refuted": r} for r in refuted]


def test_verify_survives_on_majority_uphold():
    items = [{"key": "k1", "severity": "mid", "votes": _v(False, False, True)}]
    out = verify_findings(items)
    assert [g["key"] for g in out["survived"]] == ["k1"]
    assert not out["killed"]


def test_verify_kills_on_majority_refute():
    items = [{"key": "k2", "severity": "mid", "votes": _v(True, True, False)}]
    out = verify_findings(items)
    assert [g["key"] for g in out["killed"]] == ["k2"]


def test_verify_tie_kills_default_to_refute():
    items = [{"key": "k3", "severity": "high", "votes": _v(True, False)}]
    out = verify_findings(items)
    assert [g["key"] for g in out["killed"]] == ["k3"]
    assert out["verdict"] == "pass"  # the lone high was killed


def test_verify_no_votes_is_unverified():
    items = [{"key": "k4", "severity": "low", "votes": []}]
    out = verify_findings(items)
    assert [g["key"] for g in out["unverified"]] == ["k4"]


def test_verify_surviving_high_needs_human():
    items = [{"key": "k5", "severity": "high", "votes": _v(False, False, False)}]
    out = verify_findings(items)
    assert out["survived"] and out["verdict"] == "needs_human"


def test_refute_lenses_are_distinct_and_domain_agnostic():
    names = [x["name"] for x in REFUTE_LENSES]
    assert len(names) == len(set(names)) >= 5      # 互异, 至少 5 类
    assert all(x["prompt"] for x in REFUTE_LENSES)
    # 普世红线: refute lens prompt 不得含项目专属名词 (换 pack 复用)。
    blob = " ".join(x["prompt"] for x in REFUTE_LENSES).lower()
    for token in ("cip", "pvm", "gas", "receipt", "escrow", "cowboy"):
        assert token not in blob


def test_assign_refute_lenses_prefers_distinct_then_round_robins():
    k = len(REFUTE_LENSES)
    # n<=目录: 全互异
    got = assign_refute_lenses(3)
    assert [x["name"] for x in got] == [x["name"] for x in REFUTE_LENSES[:3]]
    assert len({x["name"] for x in got}) == 3
    # n>目录: 铺满后轮转复用
    got = assign_refute_lenses(k + 2)
    assert len(got) == k + 2
    assert {x["name"] for x in got} == {x["name"] for x in REFUTE_LENSES}  # 全铺到
    assert got[k]["name"] == REFUTE_LENSES[0]["name"]                      # 轮转


def test_assign_refute_lenses_nonpositive_is_empty():
    assert assign_refute_lenses(0) == []
    assert assign_refute_lenses(-1) == []


def _e(klass, desc="", ref=None):
    return {"root_cause_class": klass, "description": desc, "change_ref": ref}


def test_ratchet_lenses_rank_by_frequency_and_cap():
    escs = ([_e("state-consensus", f"d{i}") for i in range(5)]
            + [_e("econ-conservation", f"e{i}") for i in range(2)]
            + [_e("determinism-gap", "z")])
    got = ratchet_lenses(escs, max_lenses=2)
    assert len(got) == 2  # capped
    # most frequent first
    assert got[0]["klass"] == "state-consensus" and got[0]["weight"] == 5
    assert got[1]["klass"] == "econ-conservation" and got[1]["weight"] == 2
    assert got[0]["name"] == "ratchet:state-consensus"


def test_ratchet_lenses_normalizes_descriptive_class_to_bucket():
    # long descriptive one-offs collapse on the ':' prefix
    escs = [_e("confidentiality-break: negative property ..."),
            _e("confidentiality-break: another variant ...")]
    got = ratchet_lenses(escs, max_lenses=8)
    assert len(got) == 1
    assert got[0]["klass"] == "confidentiality-break"
    assert got[0]["weight"] == 2


def test_ratchet_lenses_embeds_precedent_samples_capped():
    escs = [_e("econ-conservation", f"root-cause-{i}") for i in range(5)]
    got = ratchet_lenses(escs, max_lenses=8, samples_per_class=2)
    prompt = got[0]["prompt"]
    assert "root-cause-0" in prompt and "root-cause-1" in prompt
    assert "root-cause-2" not in prompt  # capped at samples_per_class
    assert "重新引入" in prompt  # adversarial "reintroduce?" framing


def test_ratchet_lenses_empty_and_unclassified():
    assert ratchet_lenses([]) == []
    got = ratchet_lenses([_e("", "d")])
    assert got[0]["klass"] == "unclassified"


# ---- ④ recall-leak fix: proximity merge + single-source MID survives as advisory ----

def test_same_bug_different_lines_and_dimensions_merges_to_quorum():
    # two lenses flag the SAME conservation bug at nearby lines under different
    # dimensions — must merge (support=2 -> confirmed), not split into 2 weak singletons.
    findings = [
        _f("transaction.rs", 552, "correctness", "mid", "lens-correctness"),
        _f("transaction.rs", 555, "econ", "mid", "lens-econ"),
    ]
    out = aggregate_review(findings, quorum=2, proximity=20)
    assert len(out["groups"]) == 1, "nearby findings must cluster into one group"
    g = out["groups"][0]
    assert g["support"] == 2 and g["status"] == "confirmed"
    assert set(g["dimensions"]) == {"correctness", "econ"}


def test_single_source_mid_survives_as_advisory_not_dropped():
    # the recall-leak core: a lone MID finding must be SURFACED (advisory), not
    # discarded as noise the way a lone LOW is.
    findings = [_f("x.rs", 10, "correctness", "mid", "lens-correctness")]
    out = aggregate_review(findings, quorum=2)
    g = out["groups"][0]
    assert g["status"] == "advisory"
    assert out["advisory"] and not out["dropped"]
    assert out["review_verdict"] == "pass"  # advisory does not block


def test_single_source_low_still_dropped_as_noise():
    findings = [_f("y.rs", 3, "style", "low", "lens-a")]
    out = aggregate_review(findings, quorum=2)
    assert out["groups"][0]["status"] == "weak"
    assert out["dropped"] and not out["advisory"]


def test_findings_beyond_proximity_stay_separate():
    findings = [
        _f("z.rs", 10, "correctness", "mid", "lens-a"),
        _f("z.rs", 200, "correctness", "mid", "lens-b"),  # far apart -> distinct bugs
    ]
    out = aggregate_review(findings, quorum=2, proximity=20)
    assert len(out["groups"]) == 2
    assert all(g["status"] == "advisory" for g in out["groups"])  # each lone MID surfaced


def test_chained_cluster_reaches_quorum_across_a_code_block():
    # the real COW-2287 shape: lenses flag the deferred-fee block at 510/522/540/552;
    # consecutive gaps (12/18/12) all <= proximity -> transitive chain into one group.
    findings = [
        _f("transaction.rs", 510, "determinism", "high", "lens-det"),
        _f("transaction.rs", 522, "security", "high", "lens-sec"),
        _f("transaction.rs", 540, "spec", "high", "lens-spec"),
        _f("transaction.rs", 552, "correctness", "high", "lens-corr"),
    ]
    out = aggregate_review(findings, quorum=2, proximity=20)
    assert len(out["groups"]) == 1
    assert out["groups"][0]["support"] == 4
    assert out["groups"][0]["status"] == "needs_human"  # high


def test_proximity_gap_larger_than_window_does_not_chain():
    # a 30-line gap with no bridging finding stays split (guards over-merge)
    findings = [
        _f("t.rs", 510, "determinism", "mid", "lens-det"),
        _f("t.rs", 540, "spec", "mid", "lens-spec"),
    ]
    out = aggregate_review(findings, quorum=2, proximity=20)
    assert len(out["groups"]) == 2  # 30 > 20, distinct

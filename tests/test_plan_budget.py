from marshal_core.knowledge.store import Store
from marshal_core.knowledge.models import ConceptAnchorRow
from marshal_core.plangate.budget import concept_budget
from marshal_core.knowledge.models import ConceptEdge


def _seed(store, db_session):
    # execution(high) → gas(constitutional, 有子 basefee, 有锚点); timer(mid, 依赖 gas)
    store.upsert_concept(id="execution", domain_pack="c", parent_id="", importance="high",
                         status="a", confidence=0.5, doc_only=True, definition="")
    store.upsert_concept(id="gas", domain_pack="c", parent_id="execution",
                         importance="constitutional", status="a", confidence=0.8,
                         doc_only=False, definition="")
    store.upsert_concept(id="basefee", domain_pack="c", parent_id="gas", importance="high",
                         status="a", confidence=0.8, doc_only=False, definition="")
    store.upsert_concept(id="timer", domain_pack="c", parent_id="execution", importance="mid",
                         status="a", confidence=0.5, doc_only=True, definition="")
    db_session.add(ConceptEdge(src_id="timer", dst_id="gas", kind="depends_on"))
    db_session.add(ConceptAnchorRow(concept_id="gas", repo="node", path="gas.rs",
                                    symbol="Gas", kind="implements", verified=True))
    db_session.commit()


def test_redefine_gas_costs_more_than_redefine_timer(db_session):
    store = Store(db_session)
    _seed(store, db_session)
    gas = concept_budget(store, "c", [{"concept_id": "gas", "op": "redefine"}])
    timer = concept_budget(store, "c", [{"concept_id": "timer", "op": "redefine"}])
    # 改 gas(constitutional, 有子树 basefee, 有锚点) ≫ 改 timer(mid, 无子无锚)
    assert gas["weighted_concept_cost"] > timer["weighted_concept_cost"]
    assert gas["highest_tier_touched"] == "constitutional"
    # 改 gas → timer 会受影响(timer depends_on gas)
    assert "timer" in gas["blast_radius"]
    assert "node" in gas["impacted_repos"]
    assert gas["verdict"] == "cost-only"
    assert "est_impl_days" not in gas          # 工期估算不在确定性 CLI
    # 深审 gaming 拆分: redefine 是 grounded(树算), 无 hinted
    assert gas["grounded_cost"] > 0 and gas["hinted_cost"] == 0


def test_add_new_concept_uses_scope_hint(db_session):
    store = Store(db_session)
    _seed(store, db_session)
    b = concept_budget(store, "c", [
        {"concept_id": "payments", "op": "add", "importance": "high", "est_scope": "large"},
        {"concept_id": "tiny", "op": "add", "importance": "low", "est_scope": "small"},
    ])
    names = {n["concept_id"] for n in b["new_concepts"]}
    assert names == {"payments", "tiny"}
    pay = next(n for n in b["new_concepts"] if n["concept_id"] == "payments")
    tiny = next(n for n in b["new_concepts"] if n["concept_id"] == "tiny")
    assert pay["weight"] > tiny["weight"]      # large/high ≫ small/low(M4: scope 不 count)
    # 全是 add → 成本全落 hinted(可 gaming), grounded 为 0
    assert b["hinted_cost"] > 0 and b["grounded_cost"] == 0


def test_unknown_redefine_surfaced_not_silent_zero(db_session):
    store = Store(db_session)
    _seed(store, db_session)
    b = concept_budget(store, "c", [{"concept_id": "ghost", "op": "redefine"}])
    assert "ghost" in b["unknown_redefines"]   # 不静默按 0, 拎出来
    assert b["redefined_concepts"] == []


def test_blast_radius_is_transitive(db_session):
    """深审 S2-B: A→B→gas, redefine gas 的 blast 必须含传递依赖 A, 不只直接依赖 B。"""
    store = Store(db_session)
    for cid in ("gas", "B", "A"):
        store.upsert_concept(id=cid, domain_pack="c", parent_id="", importance="high",
                             status="a", confidence=0.5, doc_only=True, definition="")
    db_session.add(ConceptEdge(src_id="B", dst_id="gas", kind="depends_on"))
    db_session.add(ConceptEdge(src_id="A", dst_id="B", kind="depends_on"))
    db_session.commit()
    b = concept_budget(store, "c", [{"concept_id": "gas", "op": "redefine"}])
    assert b["blast_radius"] == ["A", "B"]     # 传递闭包, 不只一跳


def test_list_anchors_filters_by_concept_ids(db_session):
    db_session.add(ConceptAnchorRow(concept_id="gas", repo="node", path="a.rs",
                                    symbol="Gas", kind="implements", verified=True))
    db_session.add(ConceptAnchorRow(concept_id="other", repo="runner", path="b.rs",
                                    symbol="X", kind="implements", verified=False))
    db_session.commit()
    store = Store(db_session)
    anchors = store.list_anchors({"gas"})
    assert len(anchors) == 1 and anchors[0].repo == "node"

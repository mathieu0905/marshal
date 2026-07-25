from marshal_core.knowledge.store import Store
from marshal_core.knowledge.models import ConceptEdge
from marshal_core.onboard.report import tech_debt_signals


def test_list_edges_returns_edges_touching_pack(db_session):
    # 深审 run: 语义 = "任一端落在 pack 内"(非两端都在)—— report 需看到悬空引用
    for src, dst, kind in [("a", "b", "depends_on"),   # 两端都在
                           ("a", "x", "depends_on"),   # src 在, dst 悬空
                           ("y", "b", "part_of"),      # dst 在, src 悬空
                           ("c", "d", "part_of")]:     # 都不在
        db_session.add(ConceptEdge(src_id=src, dst_id=dst, kind=kind))
    db_session.commit()
    store = Store(db_session)
    pairs = {(e.src_id, e.dst_id) for e in store.list_edges({"a", "b"})}
    assert pairs == {("a", "b"), ("a", "x"), ("y", "b")}   # 含悬空端, 排除都不在的


def _seed(store):
    # execution(high, 有锚定) → gas(constitutional, doc_only=无锚定)
    store.upsert_concept(id="execution", domain_pack="c", parent_id="",
                         importance="high", status="a", confidence=0.85,
                         doc_only=False, definition="")
    store.upsert_concept(id="gas", domain_pack="c", parent_id="execution",
                         importance="constitutional", status="a", confidence=0.3,
                         doc_only=True, definition="")            # 高重要性无锚定
    store.upsert_concept(id="lonely", domain_pack="c", parent_id="",
                         importance="low", status="a", confidence=0.3,
                         doc_only=True, definition="")            # 孤立
    store.upsert_concept(id="waif", domain_pack="c", parent_id="ghost",
                         importance="low", status="a", confidence=0.3,
                         doc_only=True, definition="")            # 父不存在


def test_tech_debt_signals(db_session):
    store = Store(db_session)
    _seed(store)
    sig = tech_debt_signals(store, "c")
    assert "gas" in sig["unanchored_high"]
    assert "execution" not in sig["unanchored_high"]      # 有锚定, 不算
    assert "lonely" in sig["orphans"]
    assert "gas" not in sig["orphans"]                    # gas 有父, 不算孤立
    assert "waif" in sig["dangling_parent"]
    assert sig["over_fragmented"] == []                   # 无超阈父


def test_over_fragmented_threshold(db_session):
    store = Store(db_session)
    store.upsert_concept(id="root", domain_pack="c", parent_id="", importance="high",
                         status="a", confidence=0.5, doc_only=True, definition="")
    for i in range(13):                                    # 13 > 默认阈值 12
        store.upsert_concept(id=f"k{i}", domain_pack="c", parent_id="root",
                             importance="low", status="a", confidence=0.5,
                             doc_only=True, definition="")
    sig = tech_debt_signals(store, "c")
    assert "root" in sig["over_fragmented"]


def test_dangling_ref_caught_and_not_false_orphan(db_session):
    """深审 run(HIGH): gas depends_on basefee 但 basefee 没建页(onboard 常见)——
    ① basefee 必须进 dangling_refs;② gas 有出边, 不能被误报成 orphan。"""
    from marshal_core.knowledge.models import ConceptEdge
    store = Store(db_session)
    store.upsert_concept(id="gas", domain_pack="c", parent_id="", importance="high",
                         status="a", confidence=0.85, doc_only=False, definition="")
    db_session.add(ConceptEdge(src_id="gas", dst_id="basefee", kind="depends_on"))
    db_session.commit()
    sig = tech_debt_signals(store, "c")
    assert "basefee" in sig["dangling_refs"]      # 悬空引用被抓
    assert "gas" not in sig["orphans"]            # 有出边 → 不是孤立(修前会误报)

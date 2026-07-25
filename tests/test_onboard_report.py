from marshal_core.knowledge.store import Store
from marshal_core.knowledge.models import ConceptEdge


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

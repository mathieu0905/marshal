from marshal_core.knowledge.models import Concept, ConceptEdge, ConceptAnchorRow, ConceptChange
from marshal_core.knowledge.store import Store


def test_concept_tables_roundtrip(db_session):
    db_session.add(Concept(
        id="dual-gas-model", domain_pack="cowboy", parent_id="execution",
        importance="constitutional", status="authoritative", confidence=0.9,
        doc_only=False, definition="dual gas",
    ))
    db_session.add(ConceptEdge(src_id="timer-mechanism", dst_id="dual-gas-model",
                               kind="depends_on"))
    db_session.add(ConceptAnchorRow(concept_id="dual-gas-model", repo="node",
                                    path="execution/src/gas.rs", symbol="GasReport",
                                    kind="implements", verified=True))
    db_session.add(ConceptChange(change_ref="seed", op="add", concept_id="dual-gas-model",
                                 before={}, after={"importance": "constitutional"},
                                 rationale="seed import", actor="system"))
    db_session.commit()

    c = db_session.get(Concept, "dual-gas-model")
    assert c.importance == "constitutional"
    assert c.doc_only is False


def test_upsert_and_tree(db_session):
    store = Store(db_session)
    store.upsert_concept(id="execution", domain_pack="cowboy", parent_id="",
                         importance="high", status="authoritative", confidence=0.5,
                         doc_only=True, definition="exec root")
    store.upsert_concept(id="dual-gas-model", domain_pack="cowboy", parent_id="execution",
                         importance="constitutional", status="authoritative", confidence=0.9,
                         doc_only=False, definition="dual gas")
    # upsert 幂等: 再写一次改 importance
    store.upsert_concept(id="dual-gas-model", domain_pack="cowboy", parent_id="execution",
                         importance="high", status="authoritative", confidence=0.9,
                         doc_only=False, definition="dual gas")

    assert len(store.list_concepts("cowboy")) == 2
    tree = store.concept_tree("cowboy")
    assert tree[0]["id"] == "execution"
    assert tree[0]["children"][0]["id"] == "dual-gas-model"
    assert tree[0]["children"][0]["importance"] == "high"   # upsert 覆盖生效

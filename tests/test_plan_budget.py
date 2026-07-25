from marshal_core.knowledge.store import Store
from marshal_core.knowledge.models import ConceptAnchorRow


def test_list_anchors_filters_by_concept_ids(db_session):
    db_session.add(ConceptAnchorRow(concept_id="gas", repo="node", path="a.rs",
                                    symbol="Gas", kind="implements", verified=True))
    db_session.add(ConceptAnchorRow(concept_id="other", repo="runner", path="b.rs",
                                    symbol="X", kind="implements", verified=False))
    db_session.commit()
    store = Store(db_session)
    anchors = store.list_anchors({"gas"})
    assert len(anchors) == 1 and anchors[0].repo == "node"

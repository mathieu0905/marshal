from marshal_core.plangate.service import plan_review

GAS = """---
type: concept
concept_id: gas
parent: ""
importance: constitutional
anchors:
  - {repo: node, path: execution/src/gas.rs, symbol: GasReport, kind: implements}
status: authoritative
last_updated: 2026-07-26
---
gas
"""


def _setup(tmp_path):
    concepts = tmp_path / "concepts"
    concepts.mkdir()
    (concepts / "gas.md").write_text(GAS)
    repo = tmp_path / "node"
    (repo / "execution" / "src").mkdir(parents=True)
    (repo / "execution" / "src" / "gas.rs").write_text("pub struct GasReport {}\n")
    return concepts, repo


def test_plan_review_returns_neutral_budget(tmp_path):
    concepts, repo = _setup(tmp_path)
    out = plan_review(str(concepts), {"node": str(repo)}, "probe",
                      [{"concept_id": "gas", "op": "redefine"},
                       {"concept_id": "fees", "op": "add",
                        "importance": "high", "est_scope": "medium"}])
    assert out["verdict"] == "cost-only"
    assert any(r["concept_id"] == "gas" for r in out["redefined_concepts"])
    assert any(n["concept_id"] == "fees" for n in out["new_concepts"])
    assert out["grounded_cost"] > 0 and out["hinted_cost"] > 0


def test_plan_review_repo_roots_optional(tmp_path):
    concepts, _ = _setup(tmp_path)
    # 不传 repo_roots 也能算预算(budget 用 anchor 的 repo, 不看 verified/doc_only)
    out = plan_review(str(concepts), {}, "probe", [{"concept_id": "gas", "op": "redefine"}])
    assert out["verdict"] == "cost-only"


def test_plan_review_bad_concepts_dir_raises(tmp_path):
    try:
        plan_review("/does/not/exist", {}, "probe", [])
        assert False, "should raise"
    except ValueError as e:
        assert "concepts-dir" in str(e)


def test_plan_review_does_not_mutate_shared_db(tmp_path, monkeypatch):
    """F1/S2-A: 只读查询绝不碰共享 DB。"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from marshal_core.knowledge.models import Base
    from marshal_core.knowledge.store import Store
    dbfile = tmp_path / "shared.db"
    monkeypatch.setenv("MARSHAL_DB", f"sqlite:///{dbfile}")
    eng = create_engine(f"sqlite:///{dbfile}")
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    Store(s).upsert_concept(id="curated", domain_pack="cowboy", parent_id="",
                            importance="high", status="a", confidence=0.5,
                            doc_only=True, definition="x")
    s.close()

    concepts, repo = _setup(tmp_path)
    plan_review(str(concepts), {"node": str(repo)}, "cowboy",
                [{"concept_id": "gas", "op": "redefine"}])

    s2 = sessionmaker(bind=create_engine(f"sqlite:///{dbfile}"))()
    ids = {c.id for c in Store(s2).list_concepts("cowboy")}
    s2.close()
    assert "curated" in ids            # 共享 DB 未被 plan_review 覆盖

import json

from marshal_core.cli import main

GAS = """---
type: concept
concept_id: gas
parent: ""
importance: constitutional
anchors:
  - {repo: node, path: execution/src/gas.rs, symbol: GasReport, kind: implements}
status: authoritative
last_updated: 2026-07-25
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
    touches = tmp_path / "touches.json"
    touches.write_text(json.dumps([{"concept_id": "gas", "op": "redefine"},
                                   {"concept_id": "fees", "op": "add",
                                    "importance": "high", "est_scope": "medium"}]))
    return concepts, repo, touches


def test_plan_cost_cli(tmp_path, capsys):
    concepts, repo, touches = _setup(tmp_path)
    rc = main(["plan-cost", "--domain-pack", "probe", "--concepts-dir", str(concepts),
               "--repo-root", f"node={repo}", "--touches", str(touches)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["verdict"] == "cost-only"
    assert any(r["concept_id"] == "gas" for r in out["redefined_concepts"])
    assert any(n["concept_id"] == "fees" for n in out["new_concepts"])
    assert "node" in out["impacted_repos"]


def test_plan_cost_bad_touches_fails(tmp_path):
    concepts, repo, _ = _setup(tmp_path)
    rc = main(["plan-cost", "--domain-pack", "probe", "--concepts-dir", str(concepts),
               "--repo-root", f"node={repo}", "--touches", "/does/not/exist.json"])
    assert rc != 0                               # touches 文件缺失 → 硬失败, 不静默

def test_plan_cost_bad_repo_root_fails(tmp_path):
    concepts, repo, touches = _setup(tmp_path)
    rc = main(["plan-cost", "--domain-pack", "probe", "--concepts-dir", str(concepts),
               "--repo-root", "node=/does/not/exist", "--touches", str(touches)])
    assert rc != 0                               # 复用 _require_derive_paths 的 typo 校验


def test_plan_cost_does_not_mutate_shared_db(tmp_path):
    """深审 S2-A: plan-cost 是只读查询, 绝不能碰共享 DB。即使 --domain-pack cowboy +
    一个不同的 concepts-dir, 共享 DB 里已 curated 的 cowboy 概念也必须存活。"""
    import os
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from marshal_core.knowledge.models import Base
    from marshal_core.knowledge.store import Store
    url = os.environ["MARSHAL_DB"]               # autouse fixture 指向 per-test tmp db
    eng = create_engine(url)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    Store(s).upsert_concept(id="curated_marker", domain_pack="cowboy", parent_id="",
                            importance="high", status="a", confidence=0.5,
                            doc_only=True, definition="curated")
    s.close()

    concepts, repo, touches = _setup(tmp_path)   # concepts-dir 只有 gas.md, 无 curated_marker
    rc = main(["plan-cost", "--domain-pack", "cowboy", "--concepts-dir", str(concepts),
               "--repo-root", f"node={repo}", "--touches", str(touches)])
    assert rc == 0

    s2 = sessionmaker(bind=create_engine(url))()
    ids = {c.id for c in Store(s2).list_concepts("cowboy")}
    s2.close()
    assert "curated_marker" in ids               # 共享 DB 未被 plan-cost 覆盖

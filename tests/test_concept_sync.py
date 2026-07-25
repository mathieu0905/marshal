from marshal_core.concept.sync import derive_db
from marshal_core.knowledge.store import Store

PAGE = """---
type: concept
concept_id: dual-gas-model
parent: execution
importance: constitutional
depends_on: [basefee]
anchors:
  - {repo: node, path: execution/src/gas.rs, symbol: GasReport, kind: implements}
spec_refs: [CIP-3]
status: authoritative
last_updated: 2026-07-25
---
双计量 gas。
"""


def _seed_repo(tmp_path):
    repo = tmp_path / "node"
    (repo / "execution" / "src").mkdir(parents=True)
    (repo / "execution" / "src" / "gas.rs").write_text("pub struct GasReport {}\n")
    return {"node": str(repo)}


def _write_pages(tmp_path):
    d = tmp_path / "concepts"
    d.mkdir()
    (d / "dual-gas-model.md").write_text(PAGE)
    return d


def test_derive_creates_concept_edge_anchor(db_session, tmp_path):
    store = Store(db_session)
    derive_db(_write_pages(tmp_path), "cowboy", store, _seed_repo(tmp_path))

    concepts = {c.id: c for c in store.list_concepts("cowboy")}
    assert "dual-gas-model" in concepts
    assert concepts["dual-gas-model"].doc_only is False        # anchor 校验通过 (H1)
    assert concepts["dual-gas-model"].confidence >= 0.8
    tree = store.concept_tree("cowboy")
    # depends_on 边入库
    from marshal_core.knowledge.models import ConceptEdge
    edges = list(db_session.query(ConceptEdge).all())
    assert any(e.kind == "depends_on" and e.dst_id == "basefee" for e in edges)


def test_db_is_not_a_truth_source_rederive_overwrites(db_session, tmp_path):
    """M2: DB 只读派生。手动往 DB 写一个页里没有的概念, 再派生一次, 它不应"幸存"
    为真相 —— 派生是对 markdown 的镜像, 不做 DB→markdown 反哺。"""
    store = Store(db_session)
    pages = _write_pages(tmp_path)
    roots = _seed_repo(tmp_path)
    derive_db(pages, "cowboy", store, roots)

    # 模拟"有人只改了 DB"(非法路径)
    store.upsert_concept(id="ghost", domain_pack="cowboy", parent_id="",
                         importance="high", status="authoritative", confidence=0.9,
                         doc_only=False, definition="not in any page")
    assert any(c.id == "ghost" for c in store.list_concepts("cowboy"))

    # 再派生: derive 以 markdown 为准, ghost 不在页里 → 被清出
    derive_db(pages, "cowboy", store, roots)
    ids = {c.id for c in store.list_concepts("cowboy")}
    assert "ghost" not in ids           # DB-only 写不是真相, 派生把它抹掉
    assert "dual-gas-model" in ids


def test_one_malformed_page_does_not_crash_batch(db_session, tmp_path, capsys):
    """深审 bug C: 27 页种子里一页 anchor typo, 不能崩掉整批;好页照常入库, 坏页告警。"""
    store = Store(db_session)
    d = _write_pages(tmp_path)                      # 写好 dual-gas-model.md
    (d / "broken.md").write_text(                   # 再写一页缺 symbol 的坏页
        "---\ntype: concept\nconcept_id: broken\nimportance: low\n"
        "anchors:\n  - {repo: node, path: p}\n---\nbody\n")
    n = derive_db(d, "cowboy", store, _seed_repo(tmp_path))

    assert n == 1                                   # 只有好页入库
    ids = {c.id for c in store.list_concepts("cowboy")}
    assert "dual-gas-model" in ids and "broken" not in ids
    assert "broken.md" in capsys.readouterr().err   # 坏页被显式告警, 非静默吞

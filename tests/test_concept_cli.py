import json

from marshal_core.cli import main

PAGE = """---
type: concept
concept_id: dual-gas-model
parent: execution
importance: constitutional
anchors:
  - {repo: node, path: execution/src/gas.rs, symbol: GasReport, kind: implements}
spec_refs: [CIP-3]
status: authoritative
last_updated: 2026-07-25
---
双计量 gas。
"""
ROOT = """---
type: concept
concept_id: execution
importance: high
status: authoritative
last_updated: 2026-07-25
---
执行根。
"""


def _setup(tmp_path):
    concepts = tmp_path / "concepts"
    concepts.mkdir()
    (concepts / "dual-gas-model.md").write_text(PAGE)
    (concepts / "execution.md").write_text(ROOT)
    repo = tmp_path / "node"
    (repo / "execution" / "src").mkdir(parents=True)
    (repo / "execution" / "src" / "gas.rs").write_text("pub struct GasReport {}\n")
    return concepts, repo


def test_concept_tree_cli(tmp_path, capsys):
    concepts, repo = _setup(tmp_path)
    rc = main(["concept-tree", "--domain-pack", "cowboy",
               "--concepts-dir", str(concepts), "--repo-root", f"node={repo}"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out[0]["id"] == "execution"
    assert out[0]["children"][0]["id"] == "dual-gas-model"
    assert out[0]["children"][0]["doc_only"] is False


def test_concept_list_cli(tmp_path, capsys):
    concepts, repo = _setup(tmp_path)
    rc = main(["concept-list", "--domain-pack", "cowboy",
               "--concepts-dir", str(concepts), "--repo-root", f"node={repo}"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert {c["id"] for c in out} == {"execution", "dual-gas-model"}


def test_concept_tree_bad_repo_root_fails(tmp_path, capsys):
    # typo 的 repo-root → anchor 全灭 → 假 doc_only;必须 fail-fast, 不静默出错误信号 (N1)
    concepts, _ = _setup(tmp_path)
    rc = main(["concept-tree", "--domain-pack", "cowboy", "--concepts-dir", str(concepts),
               "--repo-root", "node=/does/not/exist"])
    assert rc != 0
    assert "doc_only" not in capsys.readouterr().out


def test_concept_tree_bad_concepts_dir_fails(tmp_path, capsys):
    rc = main(["concept-tree", "--domain-pack", "cowboy",
               "--concepts-dir", str(tmp_path / "nope"), "--repo-root", f"node={tmp_path}"])
    assert rc != 0


def test_concept_list_bad_concepts_dir_fails(tmp_path, capsys):
    rc = main(["concept-list", "--domain-pack", "cowboy",
               "--concepts-dir", str(tmp_path / "nope"), "--repo-root", f"node={tmp_path}"])
    assert rc != 0


def test_concept_tree_does_not_mutate_shared_db(tmp_path):
    """深审 F1: concept-tree 是只读查询, 绝不能碰共享 DB。即使 --domain-pack cowboy +
    一个不同的 concepts-dir, 共享 DB 里已 curated 的 cowboy 概念也必须存活(修前会被 clobber)。"""
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

    concepts, repo = _setup(tmp_path)            # concepts-dir 无 curated_marker
    rc = main(["concept-tree", "--domain-pack", "cowboy", "--concepts-dir", str(concepts),
               "--repo-root", f"node={repo}"])
    assert rc == 0

    s2 = sessionmaker(bind=create_engine(url))()
    ids = {c.id for c in Store(s2).list_concepts("cowboy")}
    s2.close()
    assert "curated_marker" in ids               # 共享 DB 未被 concept-tree 覆盖

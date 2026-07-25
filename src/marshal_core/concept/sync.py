"""M2: 严格单向 markdown → DB 派生。DB 是只读镜像, 不反哺 markdown。
每次派生 = 以当前页集为准重建该 domain_pack 的概念缓存 (页里没有的概念被清出)。"""
import sys
from pathlib import Path

from sqlalchemy import delete

from ..knowledge.models import Concept, ConceptEdge, ConceptAnchorRow, ConceptChange
from ..knowledge.store import Store
from .anchor import verify_anchors
from .model import NotAConceptPage, parse_concept_page


def derive_db(concepts_dir, domain_pack: str, store: Store,
              repo_roots: dict[str, str]) -> int:
    """读 concepts_dir 下所有 *.md → 覆盖式重建 domain_pack 的概念缓存。
    返回派生的概念数。concept-schema.md 等非概念页 (无 concept_id) 跳过。"""
    s = store.s
    # 覆盖式: 先清该 pack 的派生行 (DB 是镜像, 不保留 DB-only 写)。
    # 边/锚点无 domain_pack 列, 故 scope 到本 pack 的概念 id, 不误删他 pack。
    known = {c.id for c in store.list_concepts(domain_pack)}
    s.execute(delete(Concept).where(Concept.domain_pack == domain_pack))
    if known:
        s.execute(delete(ConceptEdge).where(ConceptEdge.src_id.in_(known)))
        s.execute(delete(ConceptAnchorRow).where(ConceptAnchorRow.concept_id.in_(known)))

    count = 0
    malformed: list[str] = []
    for path in sorted(Path(concepts_dir).glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        try:
            page = parse_concept_page(text)
        except NotAConceptPage:
            continue   # 非概念页 (如 concept-schema.md) 静默跳过, 不报错
        except ValueError as e:
            # 深审 bug C: 格式错的概念页 (typo) 不静默吞, 收集并告警, 但不崩整批
            malformed.append(f"{path.name}: {e}")
            continue
        report = verify_anchors(page, repo_roots)
        store.upsert_concept(
            id=page.concept_id, domain_pack=domain_pack, parent_id=page.parent,
            importance=page.importance, status=page.status,
            confidence=report.confidence, doc_only=report.doc_only,
            definition=page.definition,
        )
        for dep in page.depends_on:
            s.add(ConceptEdge(src_id=page.concept_id, dst_id=dep, kind="depends_on"))
        for parent in page.part_of:
            s.add(ConceptEdge(src_id=page.concept_id, dst_id=parent, kind="part_of"))
        for a in page.anchors:
            s.add(ConceptAnchorRow(concept_id=page.concept_id, repo=a.repo, path=a.path,
                                   symbol=a.symbol, kind=a.kind,
                                   verified=a.symbol in report.verified_symbols))
        if page.concept_id not in known:   # S0 只记 add
            s.add(ConceptChange(change_ref="derive", op="add", concept_id=page.concept_id,
                                before={}, after={"importance": page.importance},
                                rationale="markdown→db derive", actor="system"))
        count += 1
    s.commit()
    if malformed:   # 不静默截断: 显式告警哪些概念页格式错被跳过
        print(f"[derive_db] skipped {len(malformed)} malformed concept page(s):",
              *malformed, sep="\n  ", file=sys.stderr)
    return count

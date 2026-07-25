"""Onboard 技术债信号 —— 确定性、可复核地扫描派生概念库(S0 的 Concept/ConceptEdge)。
不做 AI 判断; 只把结构性异味按规则拎出来给人看(§6.4)。"""
from ..knowledge.store import Store

_OVER_FRAGMENT_THRESHOLD = 12
_HIGH_TIERS = {"constitutional", "high"}


def tech_debt_signals(store: Store, domain_pack: str,
                      over_fragment_threshold: int = _OVER_FRAGMENT_THRESHOLD) -> dict:
    concepts = store.list_concepts(domain_pack)
    ids = {c.id for c in concepts}
    edges = store.list_edges(ids)

    # 每概念的入/出边计数 + 子计数
    has_edge = set()
    dangling_refs = set()          # 边指向/来自不存在的概念 (悬空引用 = onboard 最常见真债)
    for e in edges:
        (has_edge if e.src_id in ids else dangling_refs).add(e.src_id)
        (has_edge if e.dst_id in ids else dangling_refs).add(e.dst_id)
    child_count: dict[str, int] = {}
    for c in concepts:
        if c.parent_id:
            child_count[c.parent_id] = child_count.get(c.parent_id, 0) + 1

    unanchored_high, orphans, over_fragmented, dangling_parent = [], [], [], []
    for c in concepts:
        if c.importance in _HIGH_TIERS and c.doc_only:
            unanchored_high.append(c.id)
        if (not c.parent_id and child_count.get(c.id, 0) == 0 and c.id not in has_edge):
            orphans.append(c.id)
        if c.parent_id and c.parent_id not in ids:
            dangling_parent.append(c.id)
    for parent_id, n in child_count.items():
        # parent_id in ids: 悬空(不存在的)父不算 over-split, 它已由 dangling_parent 覆盖
        if n > over_fragment_threshold and parent_id in ids:
            over_fragmented.append(parent_id)

    return {
        "domain_pack": domain_pack,
        "total_concepts": len(concepts),
        "unanchored_high": sorted(unanchored_high),
        "orphans": sorted(orphans),
        "over_fragmented": sorted(over_fragmented),
        "dangling_parent": sorted(dangling_parent),
        "dangling_refs": sorted(dangling_refs),
        "thresholds": {"over_fragment": over_fragment_threshold},
    }

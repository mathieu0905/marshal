"""概念预算 —— 确定性、可复核的成本画像。中性(cost-only), 绝不建议做/不做。
按 scope 加权(深审 M4: 1 个重概念 ≠ 10 个轻概念), 接真实数据(树/边/锚点)。
工期估算(est_impl_days)是 agent 的判断, 由 /plan-cost skill 补, 不在此确定性核心。"""
from ..knowledge.store import Store

_IMPORTANCE_WEIGHT = {"constitutional": 8, "high": 4, "mid": 2, "low": 1}
_SCOPE_WEIGHT = {"small": 1, "medium": 3, "large": 9}
# tier 顺序从权重表派生, 单一真相源 (别再手抄一份可能漂移的列表)。
_TIER_RANK = {t: r for r, t in enumerate(sorted(_IMPORTANCE_WEIGHT, key=_IMPORTANCE_WEIGHT.get))}
_TIER_ORDER = sorted(_TIER_RANK, key=_TIER_RANK.get)


def _higher_tier(a: str, b: str) -> str:
    # 未知 tier (agent 谎标/笔误) 记 -1 → 永不抬高, 不崩。
    return a if _TIER_RANK.get(a, -1) >= _TIER_RANK.get(b, -1) else b


def concept_budget(store: Store, domain_pack: str, touches: list[dict]) -> dict:
    concepts = {c.id: c for c in store.list_concepts(domain_pack)}
    ids = set(concepts)
    edges = store.list_edges(ids)

    # 子树大小(后代计数)
    children: dict[str, list[str]] = {}
    for c in concepts.values():
        if c.parent_id:
            children.setdefault(c.parent_id, []).append(c.id)

    def subtree_size(cid: str) -> int:
        # C1: parent_id 可能成环 (X↔Y), 用 seen 去重防无限循环 + 重复累加。
        n, seen, stack = 0, {cid}, list(children.get(cid, []))
        while stack:
            x = stack.pop()
            if x in seen:
                continue
            seen.add(x)
            n += 1
            stack.extend(children.get(x, []))
        return n

    # depends_on 反查: 谁依赖 X
    dependents: dict[str, set[str]] = {}
    for e in edges:
        if e.kind == "depends_on":
            dependents.setdefault(e.dst_id, set()).add(e.src_id)

    # 锚点 → repo
    repos_of: dict[str, set[str]] = {}
    for a in store.list_anchors(ids):
        repos_of.setdefault(a.concept_id, set()).add(a.repo)

    new_concepts, redefined, unknown, unknown_ops = [], [], [], []
    blast_seeds, impacted_repos = set(), set()
    # 深审 gaming 修正: 拆开可复核 vs 可谎标的成本。
    #   grounded_cost = redefine 成本(从真实树/锚点算, 不可 gaming)
    #   hinted_cost   = add 成本(靠 agent 的 importance/est_scope 提示, 可被谎标 —— 实测:
    #                   把 payments 标 low/small → cost 1)。拆开让可玩弄的部分透明, 靠 skill/人审兜底。
    grounded_cost = hinted_cost = 0
    highest = "low"

    for t in touches:
        cid, op = t["concept_id"], t["op"]
        if op == "add":
            imp = t.get("importance", "mid")
            scope = t.get("est_scope", "small")
            w = _IMPORTANCE_WEIGHT.get(imp, 2) * _SCOPE_WEIGHT.get(scope, 1)
            new_concepts.append({"concept_id": cid, "importance": imp,
                                 "est_scope": scope, "weight": w})
            hinted_cost += w
            highest = _higher_tier(highest, imp)
        elif op == "redefine":
            c = concepts.get(cid)
            if c is None:
                unknown.append(cid)          # 不静默按 0
                continue
            st_size = subtree_size(cid)
            n_repos = len(repos_of.get(cid, set()))
            w = _IMPORTANCE_WEIGHT.get(c.importance, 2) * (1 + st_size + n_repos)
            redefined.append({"concept_id": cid, "importance": c.importance,
                              "subtree_size": st_size, "repos": n_repos, "weight": w})
            grounded_cost += w
            highest = _higher_tier(highest, c.importance)
            blast_seeds.add(cid)
            impacted_repos |= repos_of.get(cid, set())
        else:
            unknown_ops.append(cid)          # 未知 op 拎出来 (与未知 redefine 分开), 不静默

    # 深审 S2-B: blast_radius 要传递闭包, 别只算一跳 (A→B→gas: 改 gas 也影响 A)
    blast, seen, stack = set(), set(blast_seeds), list(blast_seeds)
    while stack:
        x = stack.pop()
        for d in dependents.get(x, ()):
            if d not in seen:
                seen.add(d)
                blast.add(d)
                stack.append(d)

    touched_ids = {t["concept_id"] for t in touches}
    return {
        "domain_pack": domain_pack,
        "new_concepts": new_concepts,
        "redefined_concepts": redefined,
        "unknown_redefines": sorted(unknown),
        "unknown_ops": sorted(unknown_ops),
        "weighted_concept_cost": grounded_cost + hinted_cost,
        "grounded_cost": grounded_cost,   # redefine, 从真实树算, 不可 gaming
        "hinted_cost": hinted_cost,       # add, 靠 agent 提示, 可谎标 —— 拆开透明
        "highest_tier_touched": highest,
        "blast_radius": sorted(blast - touched_ids),   # 触及集自身不算"被波及"
        # 仅直接被 redefine 的概念的锚点 repo (故意不做传递闭包 —— blast_radius 才管波及面)。
        "impacted_repos": sorted(impacted_repos),
        "verdict": "cost-only",
        "note": ("neutral cost picture (deterministic). weighted_concept_cost = "
                 "grounded_cost (redefine, tree-derived) + hinted_cost (add, agent-hinted, "
                 "gameable — cross-check the hints). est_impl_days/est_debt_weeks are agent "
                 "estimates supplied by the /plan-cost skill, not here."),
    }

# S2 · Plan Gate — 概念预算(Concept Budget)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 输入一份 plan 的"概念触及集"(哪些概念被新增/重定义),产出一份**中性成本画像**(概念预算)——按 scope 加权、含依赖爆炸半径与受影响 repo。**绝不建议做/不做**(说话人2:Marshal 只摆成本,不替你决定)。

**Architecture:** 沿用 S0/S1 铁律——`marshal_core` 只做确定性工作,AI 判断由 agent 编排(core 无 LLM)。故 plan-cost 拆成:①**确定性 CLI `plan-cost`**:给定"触及集"(touches),从概念树/边/锚点算出可复核的成本画像——TDD;②**`/plan-cost` skill**:agent 读 plan 文本 + 当前概念树 → 产出 touches JSON + `est_impl_days`/`est_debt_weeks` 估算 → 调 `plan-cost` → 组装最终中性报告。**工期估算是 agent 的猜测,放 skill、不放确定性 CLI**(诚实分离:确定的事实 vs AI 估算)。

**Tech Stack:** Python 3.11 · SQLAlchemy 2.0 · pytest · 复用 S0/S1 的 `derive_db`、`Store`、概念表、`_require_derive_paths`。**不新增 LLM 依赖。**

**上游依据:** [`2026-07-24-marshal-three-gates-concept-registry.zh.md`](2026-07-24-marshal-three-gates-concept-registry.zh.md) §5(含深审 M4 scope-加权修正)、§8 S2;依赖 **S0**(PR #18)+ **S1**(PR #19)已 merge 进 main。

**关键 grounding(已核实 main 的真实 schema,不憑 proposal 空想):**
- S0 `Concept` 表列 = `id/domain_pack/parent_id/importance/status/confidence/doc_only/definition`。**`spec_refs`/`invariant_ids` 未持久化**(frontmatter 解析但 derive 不入库)。故 proposal §5.2 的 `impacted_invariants`/`impacted_spec_reqs` **在现有 schema 算不出**,本 slice **不做**它们。
- 成本模型接**真实可用数据**:子树大小(`parent_id` 树)+ 依赖爆炸半径(`ConceptEdge.kind=depends_on` 反查)+ 受影响 repo(`ConceptAnchorRow.repo`)+ `importance`。这恰是深审 M4「按 scope 不按 count」的正解。
- 复用:`Store.list_concepts/list_edges`、`derive_db`、`cli._require_derive_paths`(S1 加固的路径校验)。

**真 repo 预验证(起草时已做):** 确定性成本核心(`budget.py` + `list_anchors`)已在 scratch(基于当前 main 的 S0+S1)原型化并跑过——**4 单元测试绿**,且对抗探测坐实:redefine `gas`(constitutional/5 子树/3 repo/3 依赖)cost=72 ≫ redefine `leaf`(low)cost=1,blast/impacted_repos 正确。**并抓到一个 gaming 面**:`add` 成本全靠 agent 的 importance/est_scope 提示,把 `payments` 谎标 `low/small` → cost=1(可玩弄);而 `redefine` 成本紮根真实树(不可 gaming)。修正已并入 Task 2:输出**拆开 `grounded_cost`(redefine,可复核)vs `hinted_cost`(add,可谎标)**,让可玩弄部分透明,靠 skill 交叉核对 + 人审兜底。

**范围边界(YAGNI):** 本 slice **只做** 确定性成本画像 CLI + 编排 skill + 人审验收。**不做**:`impacted_invariants/spec_reqs`(需先持久化 spec_refs/invariant 链,另立 slice)、把 plan 文本→touches 的映射写进 core(那是 agent)、MCP 封装(§8 S3)、把预算变成 go/no-go(违背中性原则)、rename/deprecate 全谱(MVP 只 add + redefine)。

---

## 文件结构(先锁定分解)

| 文件 | 责任 | 动作 |
|---|---|---|
| `src/marshal_core/plangate/__init__.py` | 包标记 | Create |
| `src/marshal_core/plangate/budget.py` | `concept_budget(store, domain_pack, touches)` — 确定性成本画像 | Create |
| `src/marshal_core/knowledge/store.py` | 加 `list_anchors(concept_ids)`(budget 算 impacted_repos 用) | Modify |
| `src/marshal_core/cli.py` | 加 `plan-cost` 命令(复用 `_require_derive_paths` + `derive_db`) | Modify |
| `.claude/skills/plan-cost/SKILL.md` | `/plan-cost` 编排 skill(agent plan→touches + 工期估算 + 中性报告) | Create |
| `tests/test_plan_budget.py` | 预算核心测试 | Create |
| `tests/test_plan_cost_cli.py` | CLI 测试 | Create |

**约定:** ruff line-length=100;pytest `pythonpath=["src"]`;`db_session`/tmp_path;每 Task 末 commit;commit message **无 AI 署名**。

---

## Task 1: `Store.list_anchors`(budget 的依赖)

**Files:**
- Modify: `src/marshal_core/knowledge/store.py`
- Test: `tests/test_plan_budget.py`(仅本 Task 的 store 部分)

- [ ] **Step 1: 写失败测试**

Create `tests/test_plan_budget.py`:

```python
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
```

- [ ] **Step 2: 运行验证失败**

Run: `/home/ubuntu/workspace/marshal/.venv/bin/python -m pytest tests/test_plan_budget.py::test_list_anchors_filters_by_concept_ids -v`
Expected: FAIL(`AttributeError: 'Store' object has no attribute 'list_anchors'`)。

- [ ] **Step 3: 实现**

Modify `src/marshal_core/knowledge/store.py` — 文件头 import 补 `ConceptAnchorRow`(与 `Concept`/`ConceptEdge` 同处):

```python
from .models import InvariantRegistry, GateRun, AuditLog, EscapeRegistry, Concept, ConceptEdge, ConceptAnchorRow
```

在 `Store` 类末尾加:

```python
    def list_anchors(self, concept_ids: set[str]) -> list[ConceptAnchorRow]:
        stmt = select(ConceptAnchorRow).where(ConceptAnchorRow.concept_id.in_(concept_ids))
        return list(self.s.scalars(stmt))
```

- [ ] **Step 4: 运行验证通过**

Run: `pytest tests/test_plan_budget.py::test_list_anchors_filters_by_concept_ids -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add src/marshal_core/knowledge/store.py tests/test_plan_budget.py
git commit -m "plangate: add Store.list_anchors for concept-budget impacted repos"
```

---

## Task 2: 概念预算核心(确定性,S2 的价值所在)

**Files:**
- Create: `src/marshal_core/plangate/__init__.py`(空)
- Create: `src/marshal_core/plangate/budget.py`
- Test: `tests/test_plan_budget.py`

> **成本模型(全部确定性、可复核):**
> - **redefine**(改既有概念):weight = `importance_weight × (1 + 子树大小 + 该概念的 repo 数)`。真实 scope 从树/锚点算——改 `gas`(重、子树大、多 repo)≫ 改叶概念。
> - **add**(建新概念):概念还不在树里 → weight = `importance_weight × scope_weight[est_scope]`,`est_scope` 是 agent 给的规模提示(small/medium/large)。
> - **blast_radius**:依赖被 redefine 概念的其他概念(`depends_on` 反查)——"改它谁会受影响"。
> - **impacted_repos**:被触及概念的锚点所在 repo。
> - **unknown_redefines**:redefine 一个不存在的概念 → 不静默按 0 计,拎出来(可能是笔误或其实是 add)。
> - **verdict 恒 = `cost-only`**;**不含** est_impl_days(那是 skill 的 agent 估算,诚实分离)。

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_plan_budget.py`:

```python
from marshal_core.plangate.budget import concept_budget
from marshal_core.knowledge.models import ConceptEdge


def _seed(store, db_session):
    # execution(high) → gas(constitutional, 有子 basefee, 有锚点); timer(mid, 依赖 gas)
    store.upsert_concept(id="execution", domain_pack="c", parent_id="", importance="high",
                         status="a", confidence=0.5, doc_only=True, definition="")
    store.upsert_concept(id="gas", domain_pack="c", parent_id="execution",
                         importance="constitutional", status="a", confidence=0.8,
                         doc_only=False, definition="")
    store.upsert_concept(id="basefee", domain_pack="c", parent_id="gas", importance="high",
                         status="a", confidence=0.8, doc_only=False, definition="")
    store.upsert_concept(id="timer", domain_pack="c", parent_id="execution", importance="mid",
                         status="a", confidence=0.5, doc_only=True, definition="")
    db_session.add(ConceptEdge(src_id="timer", dst_id="gas", kind="depends_on"))
    db_session.add(ConceptAnchorRow(concept_id="gas", repo="node", path="gas.rs",
                                    symbol="Gas", kind="implements", verified=True))
    db_session.commit()


def test_redefine_gas_costs_more_than_redefine_timer(db_session):
    store = Store(db_session)
    _seed(store, db_session)
    gas = concept_budget(store, "c", [{"concept_id": "gas", "op": "redefine"}])
    timer = concept_budget(store, "c", [{"concept_id": "timer", "op": "redefine"}])
    # 改 gas(constitutional, 有子树 basefee, 有锚点) ≫ 改 timer(mid, 无子无锚)
    assert gas["weighted_concept_cost"] > timer["weighted_concept_cost"]
    assert gas["highest_tier_touched"] == "constitutional"
    # 改 gas → timer 会受影响(timer depends_on gas)
    assert "timer" in gas["blast_radius"]
    assert "node" in gas["impacted_repos"]
    assert gas["verdict"] == "cost-only"
    assert "est_impl_days" not in gas          # 工期估算不在确定性 CLI
    # 深审 gaming 拆分: redefine 是 grounded(树算), 无 hinted
    assert gas["grounded_cost"] > 0 and gas["hinted_cost"] == 0


def test_add_new_concept_uses_scope_hint(db_session):
    store = Store(db_session)
    _seed(store, db_session)
    b = concept_budget(store, "c", [
        {"concept_id": "payments", "op": "add", "importance": "high", "est_scope": "large"},
        {"concept_id": "tiny", "op": "add", "importance": "low", "est_scope": "small"},
    ])
    names = {n["concept_id"] for n in b["new_concepts"]}
    assert names == {"payments", "tiny"}
    pay = next(n for n in b["new_concepts"] if n["concept_id"] == "payments")
    tiny = next(n for n in b["new_concepts"] if n["concept_id"] == "tiny")
    assert pay["weight"] > tiny["weight"]      # large/high ≫ small/low(M4: scope 不 count)
    # 全是 add → 成本全落 hinted(可 gaming), grounded 为 0
    assert b["hinted_cost"] > 0 and b["grounded_cost"] == 0


def test_unknown_redefine_surfaced_not_silent_zero(db_session):
    store = Store(db_session)
    _seed(store, db_session)
    b = concept_budget(store, "c", [{"concept_id": "ghost", "op": "redefine"}])
    assert "ghost" in b["unknown_redefines"]   # 不静默按 0, 拎出来
    assert b["redefined_concepts"] == []


def test_blast_radius_is_transitive(db_session):
    """深审 S2-B: A→B→gas, redefine gas 的 blast 必须含传递依赖 A, 不只直接依赖 B。"""
    store = Store(db_session)
    for cid in ("gas", "B", "A"):
        store.upsert_concept(id=cid, domain_pack="c", parent_id="", importance="high",
                             status="a", confidence=0.5, doc_only=True, definition="")
    db_session.add(ConceptEdge(src_id="B", dst_id="gas", kind="depends_on"))
    db_session.add(ConceptEdge(src_id="A", dst_id="B", kind="depends_on"))
    db_session.commit()
    b = concept_budget(store, "c", [{"concept_id": "gas", "op": "redefine"}])
    assert b["blast_radius"] == ["A", "B"]     # 传递闭包, 不只一跳
```

- [ ] **Step 2: 运行验证失败**

Run: `pytest tests/test_plan_budget.py -v`
Expected: FAIL(`ModuleNotFoundError: marshal_core.plangate.budget`)。

- [ ] **Step 3: 实现预算核心**

Create `src/marshal_core/plangate/__init__.py`(空文件)。

Create `src/marshal_core/plangate/budget.py`:

```python
"""概念预算 —— 确定性、可复核的成本画像。中性(cost-only), 绝不建议做/不做。
按 scope 加权(深审 M4: 1 个重概念 ≠ 10 个轻概念), 接真实数据(树/边/锚点)。
工期估算(est_impl_days)是 agent 的判断, 由 /plan-cost skill 补, 不在此确定性核心。"""
from ..knowledge.store import Store

_IMPORTANCE_WEIGHT = {"constitutional": 8, "high": 4, "mid": 2, "low": 1}
_SCOPE_WEIGHT = {"small": 1, "medium": 3, "large": 9}
_TIER_ORDER = ["low", "mid", "high", "constitutional"]


def _higher_tier(a: str, b: str) -> str:
    return a if _TIER_ORDER.index(a) >= _TIER_ORDER.index(b) else b


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
        n, stack = 0, list(children.get(cid, []))
        while stack:
            x = stack.pop()
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

    new_concepts, redefined, unknown = [], [], []
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
            unknown.append(cid)              # 未知 op 也拎出来, 不静默

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
        "weighted_concept_cost": grounded_cost + hinted_cost,
        "grounded_cost": grounded_cost,   # redefine, 从真实树算, 不可 gaming
        "hinted_cost": hinted_cost,       # add, 靠 agent 提示, 可谎标 —— 拆开透明
        "highest_tier_touched": highest,
        "blast_radius": sorted(blast - touched_ids),   # 触及集自身不算"被波及"
        "impacted_repos": sorted(impacted_repos),
        "verdict": "cost-only",
        "note": ("neutral cost picture (deterministic). weighted_concept_cost = "
                 "grounded_cost (redefine, tree-derived) + hinted_cost (add, agent-hinted, "
                 "gameable — cross-check the hints). est_impl_days/est_debt_weeks are agent "
                 "estimates supplied by the /plan-cost skill, not here."),
    }
```

- [ ] **Step 4: 运行验证通过**

Run: `pytest tests/test_plan_budget.py -v`
Expected: PASS(4 passed)。

- [ ] **Step 5: Commit**

```bash
git add src/marshal_core/plangate/__init__.py src/marshal_core/plangate/budget.py tests/test_plan_budget.py
git commit -m "plangate: add deterministic concept-budget (scope-weighted, blast radius)"
```

---

## Task 3: `plan-cost` CLI

**Files:**
- Modify: `src/marshal_core/cli.py`
- Test: `tests/test_plan_cost_cli.py`

> `plan-cost` 派生当前概念树(复用 S0 `derive_db`),读 `--touches <json 文件>`(agent 产出),算 `concept_budget`。路径校验复用 S1 的 `_require_derive_paths`(typo fail-fast)。

- [ ] **Step 1: 写失败测试**

Create `tests/test_plan_cost_cli.py`:

```python
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
```

- [ ] **Step 2: 运行验证失败**

Run: `pytest tests/test_plan_cost_cli.py -v`
Expected: FAIL(argparse: `invalid choice: 'plan-cost'`)。

- [ ] **Step 3: 实现 CLI**

Modify `src/marshal_core/cli.py`:

(a) 文件头 import 区加(`json`/`Path` 已在;`Store`/`derive_db`/`_require_derive_paths` 均 S0/S1 已在):

```python
from .plangate.budget import concept_budget
```

(b) 在 `cmd_onboard_report` 附近加命令:

```python
def cmd_plan_cost(a) -> int:
    if not Path(a.touches).is_file():
        return _fail(f"--touches not a file: {a.touches}")
    with open(a.touches, encoding="utf-8") as f:
        touches = json.load(f)
    roots = _require_derive_paths(a)             # 校验 concepts-dir + repo-root (S1 加固)
    # 深审 S2-A: plan-cost 是**只读成本查询**, 绝不 mutate 共享缓存。derive 进一个隔离的
    # 内存 DB(而非 _session() 的共享 marshal.db)—— 彻底消除 clobber 风险 + 无谓写副作用。
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from .knowledge.models import Base
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    try:
        store = Store(s)
        derive_db(a.concepts_dir, a.domain_pack, store, roots)
        return _emit(concept_budget(store, a.domain_pack, touches))
    finally:
        s.close()
```

(c) 在 `build_parser()`(onboard 子命令附近)加:

```python
    pc = sub.add_parser("plan-cost")
    pc.add_argument("--domain-pack", default="cowboy")
    pc.add_argument("--concepts-dir", required=True)
    pc.add_argument("--repo-root", action="append", default=[])
    pc.add_argument("--touches", required=True, help="JSON file: [{concept_id, op, importance?, est_scope?}]")
    pc.set_defaults(func=cmd_plan_cost)
```

- [ ] **Step 4: 运行验证通过**

Run: `pytest tests/test_plan_cost_cli.py -v`
Expected: PASS(3 passed)。

- [ ] **Step 5: 全量回归 + lint**

Run: `pytest -q && ruff check src tests`
Expected: 全绿(除 2 个 pre-existing `marshal_core/checks/` node-drift 失败),lint 干净。

- [ ] **Step 6: Commit**

```bash
git add src/marshal_core/cli.py tests/test_plan_cost_cli.py
git commit -m "plangate: add plan-cost CLI command"
```

---

## Task 4: `/plan-cost` 编排 skill

**Files:**
- Create: `.claude/skills/plan-cost/SKILL.md`

> 编排文档(agent 大脑),非 TDD 代码。把 plan 文本→touches 的判断 + 工期估算串进确定性 `plan-cost`,并把**中性原则**写死。

- [ ] **Step 1: 写 skill**

Create `.claude/skills/plan-cost/SKILL.md`:

```markdown
---
name: plan-cost
description: Use to get a NEUTRAL concept-budget cost picture for a plan before implementing it — maps the plan to concept touches, computes deterministic weighted cost + blast radius, and adds agent day-estimates. Never recommends do/don't. Triggers — "/plan-cost <plan-file>", "过一下这个 plan 的成本", "concept budget".
---

# Plan-Cost Skill — 概念预算(中性成本门)

你是 plan-cost 的编排器。确定性成本外包给 `marshal_core.cli plan-cost`;plan→touches 的映射与工期估算是你(agent)的判断。

## 前置
    PY="${MARSHAL_HOME:-/home/ubuntu/workspace/marshal}/.venv/bin/python"
    CLI() { "$PY" -m marshal_core.cli "$@"; }

## 流程

1. **读 plan + 当前概念树:** `CLI concept-tree --domain-pack <p> --concepts-dir <pack/concepts> --repo-root <r>=<path>`。

2. **映射 plan → touches(你的判断):** 判断这份 plan 会**新增**哪些概念(op=add,给 importance +
   est_scope small/medium/large 的**规模提示**)、**重定义**哪些既有概念(op=redefine)。写成
   `touches.json`:`[{concept_id, op, importance?, est_scope?}]`。**宁少勿多**;拿不准的概念别硬塞。

3. **算确定性成本:** `CLI plan-cost --domain-pack <p> --concepts-dir <...> --repo-root <...> --touches touches.json`
   → 得 weighted_concept_cost / blast_radius / impacted_repos / highest_tier_touched / unknown_redefines。

4. **补工期估算(你的判断,诚实标注):** 给 est_impl_days / est_debt_weeks,**必带 confidence + "这是估算"**,
   不谎报精度(§6.3)。相对排序比绝对数值重要(深审 M-estimate)。

5. **组装中性报告并呈给用户:** 摆出成本画像 + 你的工期估算。**绝不说"该做/不该做"**
   (说话人2:Marshal 不知道你的预算,不替你决定)。只呈"这些改动触及最高 X 级、加权成本 N、
   会波及 [blast_radius]、你可能要 D 天 + 未来 W 周还债——你自己判断值不值"。

## 铁律
- **中性**:verdict 恒 cost-only;不含 go/no-go。
- **诚实分离**:确定的成本(CLI)与 agent 的工期猜测(你)分开标注,别混成一个"精确数字"。
- **hinted_cost 是你标的、可被玩弄**:交叉核对——若某 `add` 的名字/描述明显对应一个大子系统
  (如 payments/banking),别标 small;`grounded_cost`(redefine)才是不可 gaming 的锚。呈报时
  **显式区分 grounded vs hinted**,别把 hinted 当既成事实。
- **unknown_redefines 非空** → 提示用户:这些概念名在树里不存在(笔误?还是其实是 add?)。
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/plan-cost/SKILL.md
git commit -m "plangate: add /plan-cost orchestration skill"
```

---

## Task 5: S2 验收 run(人审门,非单元测试)

> 坐实 §8 S2 判据。门槛不达标回对应 Task,**不放宽**。

- [ ] **Step 1: 对 3–5 份真实 plan 走 `/plan-cost`**

用我们自己近期的真实 plan(如本仓库 `docs/plans/` 的 S0/S1/本 plan)+ Cowboy 侧几份 → 各产出成本画像。
**门槛(§8 S2):** 成本画像能正确标出"这个方案要新增 N 个概念、触及最高 X 级、加权成本相对排序合理"。

- [ ] **Step 2: 复现 ≥1 例"方案本身有问题"被提前暴露**

挑一份已知偏重/偏乱的 plan(或人为构造:redefine 一个 constitutional 概念 + 新增多个 large 概念)→
成本画像应显式暴露"高 tier + 大 blast_radius + 高加权成本"。对齐说话人1 既往经验(Marshal 查出方案本身有问题)。
**不追求工期数值精准**,追求**相对排序 + 触及集/爆炸半径正确**。

- [ ] **Step 3: 中性性核查**

人工核 `/plan-cost` 输出**从不含** go/no-go 措辞;`verdict` 恒 `cost-only`;工期估算带 confidence 标注。
**门槛:** 任一输出出现"建议做/别做"→ 回 Task 4 skill 修中性原则。

- [ ] **Step 4: 记录验收结果**

Run: `python -m marshal_core.cli gate-record --change-ref "s2-plan-cost-acceptance" --verdict pass`
(仅当 Step 1–3 全达标;任一未达 → `escalate` + 回对应 Task。)

- [ ] **Step 5: 进实现前的纪律**

本 plan 进实现前 **先过 `/marshal` 深审**([[feedback_all_plans_deep_review]]),重点审:①成本模型是否会被 touches 输入"调"出想要的数字(gaming);②确定性成本 vs agent 估算的诚实分离是否真做到;③unknown/未知 op 是否真不静默。

---

## Self-Review(规格覆盖核对)

| 上游 S2 判据 / 深审项 | 对应 Task |
|---|---|
| `plan-cost` 产出成本画像 | Task 2(`concept_budget`)+ Task 3 CLI |
| **中性(cost-only,不建议做/不做)** | Task 2 `verdict="cost-only"` + Task 4 skill 铁律 + Task 5 Step 3 |
| **按 scope 加权(深审 M4,非裸计数)** | Task 2 redefine=树 scope / add=est_scope hint |
| 爆炸半径 / 受影响 repo | Task 2 `blast_radius`(depends_on 反查)/ `impacted_repos`(锚点) |
| **工期估算是 agent 的、诚实分离** | Task 2 显式排除 est_impl_days;Task 4 skill 步骤 4 补 + confidence |
| 路径 typo fail-fast | Task 3 复用 S1 `_require_derive_paths` + `--touches` is_file 校验 |
| CLI 先行(§8 D4,MCP 是 S3) | 本 slice 只 CLI;MCP 封装留 S3 |

**grounding 决定(记录):** proposal §5.2 的 `impacted_invariants/spec_reqs` **本 slice 不做**——S0 未持久化 spec_refs/invariant 链(已核实 schema)。成本模型改接真实可用数据(树 scope + 边爆炸半径 + 锚点 repo + importance),这正是深审 M4「scope 不 count」的落地。若将来要 impacted_invariants,先另立 slice 持久化那些链。

**未覆盖(留后续 slice):** `impacted_invariants/spec_reqs`(需先持久化)、MCP 封装(S3)、rename/deprecate/move 的成本(MVP 只 add+redefine)、plan 文本→touches 自动映射的质量(靠 skill + 人审,非本 slice 证)。

---

## 深审修正记录(Marshal 深审,审法=对真实代码执行 + 对抗反证)

| # | 严重性 | 发现(已执行证实) | 修正 |
|---|---|---|---|
| **起草 gaming** | — | `add` 成本全靠 agent 的 importance/est_scope 提示,把 payments 谎标 low/small → cost 1(可玩弄);redefine 紮根真实树(不可 gaming) | 已并入起草稿:输出拆 `grounded_cost`(redefine)vs `hinted_cost`(add),skill 交叉核对 |
| **S2-A** | **HIGH** | `plan-cost` 复用覆盖式 `derive_db` + `--domain-pack default="cowboy"` → 一个**只读成本查询会 MUTATE 共享 DB**;default cowboy + 错的 concepts-dir **清空 curated cowboy 缓存**(与 S1 N1/onboard-report 同款 footgun,重犯刚学的教训)。实测:curated gas 被清 | Task 3:plan-cost 派生进**隔离内存 DB**(非共享 marshal.db)→ 彻底消除 clobber + 无谓写副作用;加 `test_plan_cost_does_not_mutate_shared_db`。**实测修复后 curated 存活** |
| **S2-B** | MED | `blast_radius` 只算**一跳**直接依赖 → A→B→gas 时,redefine gas 漏掉传递依赖 A,低报真实爆炸半径 | Task 2:改**传递闭包**(reverse depends_on BFS);加 `test_blast_radius_is_transitive`。实测 blast=['A','B'] |

**结论:** S2 plan 确定性核心已执行验证(5 测试绿)。S2-A(HIGH,重犯 S1 教训的 clobber)已修+实测:plan-cost 现用隔离 DB,只读查询不碰共享缓存。S2-B(传递 blast)已修。gaming 面靠 grounded/hinted 拆分透明 + skill 交叉核对 + 人审(工具层不根治,诚实边界)。**可进实现。**

> **教训复盘:** S2-A 是**第三次**碰到「derive_db 覆盖式 + default pack」这一 class(S1 N1 → onboard-report → 现 plan-cost)。根因是每个新 derive 类命令都复制了 `default="cowboy"` 模式。**后续任何新 derive 命令,默认要么隔离 DB(只读查询)、要么 --domain-pack required(写命令)——别再 default cowboy。**

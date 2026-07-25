# S1 · Onboard Processor Phase 0(HEAD 快照)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给定任意 repo 的当前 HEAD,产出一份**技术债信号报告** + **概念树**,并在动手前用 `--dry-run` 显式估价。Phase 0 只吃 HEAD(不回放历史)。

**Architecture:** 遵循 marshal 既有铁律——**`marshal_core` 只做确定性工作,AI 判断由 agent 编排**(core 里无 LLM client,已核实)。故 onboard 拆成:①**确定性 CLI 子命令**(`onboard-estimate` 估价 / `onboard-detect` 出结构化抽取简报 / `onboard-report` 从派生概念库出技术债信号)——全部 TDD;②一个 **`/onboard` skill** 编排 agent:估价门 → detect → agent fan-out 起草概念页 markdown → 复用 S0 `derive_db` → report → 人审接受。AI 抽取质量由**人审接受门**(≥70%)验收,不假装能单元测试(sim≠prod 纪律)。

**Tech Stack:** Python 3.11 · SQLAlchemy 2.0(复用 S0 概念表)· pytest · 复用 S0 的 `marshal_core.concept.{model,anchor,sync}` 与 `Store` 概念方法。**不新增 LLM 依赖。**

**上游依据:** [`2026-07-24-marshal-three-gates-concept-registry.zh.md`](2026-07-24-marshal-three-gates-concept-registry.zh.md) §6、§8 S1;依赖 **S0**(PR #18,`feat/s0-concept-registry`)已落地的概念注册表地基。

**范围边界(YAGNI):** 本 slice **只做** Phase 0 快照的确定性骨架 + 编排 skill + 人审验收门。**不做**:Phase 1 全量 issue/PR 回放(S6)、概念预算 plan-gate(S2)、挂羊头 concept-consistency lens(S4)、可视化(S5)、把 core 变成会自己调 LLM 的东西(违背架构)。

**前置依赖:** 本 plan 的所有代码 import 自 S0 交付物(`marshal_core.concept.sync.derive_db`、`Store.list_concepts/concept_tree`、`Concept`/`ConceptEdge` 表)。**实现前确认 S0 已合并或本分支基于 S0**(`git log` 应含 commit `cbec2d8`)。

**真 repo 预验证(起草时已做):** 三个确定性模块(estimate/detect/report)已在 scratch 原型化并**对真实 `node/` 跑过**——7 单元测试绿,且**真 repo 冒烟抓出并修掉两个 sim≠prod 级坑**:①扫描未排除 vendored/build 目录(`target/`/`.venv/`/`node_modules/`…)→ 估价虚高一个数量级(17.4M tok/$55-275 → 排除后 4.5M/$13-67);②估价的概念数按巢状叶目录计(2361)与"20-40 节点"目标矛盾 → 改按**顶层模块**计(69,同量级)。两个修正 + 各自回归测试已并入下方 Task 1/2。

---

## 文件结构(先锁定分解)

| 文件 | 责任 | 动作 |
|---|---|---|
| `src/marshal_core/onboard/__init__.py` | 包标记 | Create |
| `src/marshal_core/onboard/estimate.py` | `estimate_cost(repo_root)` — dry-run 成本估算(确定性、显式披露方法) | Create |
| `src/marshal_core/onboard/detect.py` | `detect_repo(repo_root)` — repo 画像 + 文档清单 + 模块图 + 候选概念种子(结构化简报) | Create |
| `src/marshal_core/onboard/report.py` | `tech_debt_signals(store, domain_pack)` — 从派生概念库出 4 类技术债信号 | Create |
| `src/marshal_core/knowledge/store.py` | 加 `list_edges(concept_ids)`(report 用) | Modify |
| `src/marshal_core/cli.py` | 加 `onboard-estimate` / `onboard-detect` / `onboard-report` 三命令 | Modify |
| `.claude/skills/onboard/SKILL.md` | `/onboard` 编排 skill(agent 抽取 + 确定性命令串联 + 人审门) | Create |
| `tests/test_onboard_estimate.py` | 估价测试 | Create |
| `tests/test_onboard_detect.py` | 探测测试 | Create |
| `tests/test_onboard_report.py` | 技术债信号测试 | Create |
| `tests/test_onboard_cli.py` | 三命令 CLI 输出测试 | Create |

**约定(全程遵守):** ruff line-length=100;pytest `pythonpath=["src"]`;测试用 `db_session`(内存 SQLite)或 tmp_path;每 Task 末尾 commit;commit message **无 AI 署名**(marshal repo 硬规则)。

---

## Task 1: dry-run 成本估算(确定性,先做——它是动手前的门)

**Files:**
- Create: `src/marshal_core/onboard/__init__.py`(空)
- Create: `src/marshal_core/onboard/estimate.py`
- Test: `tests/test_onboard_estimate.py`

- [ ] **Step 1: 写失败测试**

Create `tests/test_onboard_estimate.py`:

```python
from marshal_core.onboard.estimate import estimate_cost


def _mk_repo(tmp_path, n_code=5, n_doc=2):
    repo = tmp_path / "r"
    (repo / "src").mkdir(parents=True)
    (repo / "docs").mkdir(parents=True)
    for i in range(n_code):
        (repo / "src" / f"m{i}.rs").write_text("pub struct S {}\n" * 50)
    for i in range(n_doc):
        (repo / "docs" / f"d{i}.md").write_text("# doc\n" + "word " * 200)
    return repo


def test_estimate_has_disclosed_method_and_caveat(tmp_path):
    est = estimate_cost(str(_mk_repo(tmp_path)))
    # 必含各字段
    for k in ("est_input_tokens", "est_output_tokens", "est_agent_calls",
              "est_usd_low", "est_usd_high", "method", "is_estimate"):
        assert k in est, f"missing {k}"
    # 必须显式披露"这是估算 + 方法",不谎报精度(§6.3 诚实纪律)
    assert est["is_estimate"] is True
    assert len(est["method"]) > 20            # 方法有实质描述
    assert est["est_usd_low"] <= est["est_usd_high"]


def test_bigger_repo_estimates_more(tmp_path):
    small = estimate_cost(str(_mk_repo(tmp_path / "a", n_code=2, n_doc=1)))
    big = estimate_cost(str(_mk_repo(tmp_path / "b", n_code=20, n_doc=10)))
    assert big["est_input_tokens"] > small["est_input_tokens"]


def test_vendored_dirs_excluded(tmp_path):
    """node/ 冒烟教训: 不排除 target/.venv/node_modules 会让估价虚高一个数量级。"""
    repo = _mk_repo(tmp_path, n_code=2, n_doc=1)
    base = estimate_cost(str(repo))
    # 往 vendored 目录塞大量代码, 估价不应变化
    (repo / "target" / "debug").mkdir(parents=True)
    for i in range(50):
        (repo / "target" / "debug" / f"junk{i}.rs").write_text("pub struct J {}\n" * 200)
    (repo / ".venv" / "lib").mkdir(parents=True)
    (repo / ".venv" / "lib" / "dep.py").write_text("x = 1\n" * 500)
    after = estimate_cost(str(repo))
    assert after["est_input_tokens"] == base["est_input_tokens"]   # vendored 被排除
    assert after["scanned"]["n_modules"] == base["scanned"]["n_modules"]
```

- [ ] **Step 2: 运行验证失败**

Run: `/home/ubuntu/workspace/marshal/.venv/bin/python -m pytest tests/test_onboard_estimate.py -v`
Expected: FAIL(`ModuleNotFoundError: marshal_core.onboard.estimate`)。

- [ ] **Step 3: 实现估算器**

Create `src/marshal_core/onboard/__init__.py`(空文件)。

Create `src/marshal_core/onboard/estimate.py`:

```python
"""Onboard dry-run 成本估算 —— 确定性、显式披露方法、不谎报精度(§6.3)。

启发式,不是承诺值:按文档+采样代码字节估输入 token、按模块数估 agent fan-out 次数、
按候选概念数估输出 token,乘以披露的单价区间。目的是"动手前把量摆出来", 让人决定是否值得跑。
"""
from pathlib import Path

_CHARS_PER_TOKEN = 4              # 粗略英文/代码 char→token 比
_CODE_SAMPLE_FRACTION = 0.3       # 抽取只采样部分代码, 非全读
_CONCEPTS_PER_MODULE = 3          # 每模块估产出的概念数
_TOKENS_PER_CONCEPT_PAGE = 400    # 每页概念 markdown 估输出 token
_FANOUT_MODULES_PER_CALL = 4      # 每次 agent 调用覆盖的模块数
# 披露的单价区间 (USD / 1K token, input+output 合计的粗估), 显式写进 method
_USD_PER_1K_LOW = 0.003
_USD_PER_1K_HIGH = 0.015

_DOC_EXT = {".md", ".rst", ".txt", ".mdx"}
_CODE_EXT = {".rs", ".py", ".js", ".ts", ".go", ".java", ".c", ".cpp", ".h"}
# 排除 vendored/build/deps —— 否则真 repo 上估价虚高一个数量级(node/ 冒烟实测:
# 不排除时 17.4M input tok / $55-275, 排除后 4.5M / $13-67)。
_IGNORE_DIRS = {".git", "target", "node_modules", ".venv", "__pycache__",
                "dist", "build", "vendor", ".mypy_cache", ".pytest_cache", ".ruff_cache"}


def _scan(repo_root: str) -> dict:
    root = Path(repo_root)
    doc_bytes = code_bytes = 0
    top_modules = set()
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel_parts = p.relative_to(root).parts
        if _IGNORE_DIRS & set(rel_parts):          # 跳过 vendored/build/deps
            continue
        ext = p.suffix.lower()
        try:
            size = p.stat().st_size
        except OSError:
            continue
        if ext in _DOC_EXT:
            doc_bytes += size
        elif ext in _CODE_EXT:
            code_bytes += size
            if len(rel_parts) > 1:                 # 顶层模块(与 detect 一致), 非每个叶目录
                top_modules.add(rel_parts[0])
    return {"doc_bytes": doc_bytes, "code_bytes": code_bytes, "n_modules": len(top_modules)}


def estimate_cost(repo_root: str) -> dict:
    s = _scan(repo_root)
    input_chars = s["doc_bytes"] + s["code_bytes"] * _CODE_SAMPLE_FRACTION
    est_input = int(input_chars / _CHARS_PER_TOKEN)
    est_concepts = max(1, s["n_modules"] * _CONCEPTS_PER_MODULE)
    est_output = est_concepts * _TOKENS_PER_CONCEPT_PAGE
    est_calls = max(1, -(-s["n_modules"] // _FANOUT_MODULES_PER_CALL))  # ceil
    total_k = (est_input + est_output) / 1000
    return {
        "est_input_tokens": est_input,
        "est_output_tokens": est_output,
        "est_agent_calls": est_calls,
        "est_concepts": est_concepts,
        "est_usd_low": round(total_k * _USD_PER_1K_LOW, 2),
        "est_usd_high": round(total_k * _USD_PER_1K_HIGH, 2),
        "is_estimate": True,
        "method": (
            f"heuristic (vendored/build dirs excluded): "
            f"input≈(doc_bytes+{_CODE_SAMPLE_FRACTION}*code_bytes)/{_CHARS_PER_TOKEN}; "
            f"output≈{_CONCEPTS_PER_MODULE} concepts/top-module * {_TOKENS_PER_CONCEPT_PAGE} tok "
            f"(est_concepts is a rough UPPER bound; 宁少勿多 curation lands lower, target 20-40); "
            f"usd @ {_USD_PER_1K_LOW}-{_USD_PER_1K_HIGH}/1K tok. ±50% — verify against real run."
        ),
        "scanned": s,
    }
```

- [ ] **Step 4: 运行验证通过**

Run: `pytest tests/test_onboard_estimate.py -v`
Expected: PASS(2 passed)。

- [ ] **Step 5: Commit**

```bash
git add src/marshal_core/onboard/__init__.py src/marshal_core/onboard/estimate.py tests/test_onboard_estimate.py
git commit -m "onboard: add dry-run cost estimator (disclosed heuristic)"
```

---

## Task 2: repo 探测 → 结构化抽取简报(确定性)

**Files:**
- Create: `src/marshal_core/onboard/detect.py`
- Test: `tests/test_onboard_detect.py`

> **目的:** 给 agent 一个确定性起点(repo 画像 + 文档清单 + 模块图 + 候选概念种子),让 AI 抽取有据可依。**detect 不产出概念定义**(那是 agent 的判断),只产出"从哪里看、有哪些候选"。

- [ ] **Step 1: 写失败测试**

Create `tests/test_onboard_detect.py`:

```python
from marshal_core.onboard.detect import detect_repo


def _mk(tmp_path):
    repo = tmp_path / "node"
    (repo / "execution" / "src").mkdir(parents=True)
    (repo / "docs").mkdir(parents=True)
    (repo / "execution" / "src" / "gas.rs").write_text("pub struct GasReport {}\n")
    (repo / "execution" / "src" / "basefee.rs").write_text("pub const X: u64 = 1;\n")
    (repo / "docs" / "cip-3.md").write_text("# CIP-3\n")
    (repo / "README.md").write_text("# node\n")
    (repo / "CODEOWNERS").write_text("execution/ @alice\n")
    return repo


def test_detect_profile_and_seeds(tmp_path):
    brief = detect_repo(str(_mk(tmp_path)))
    assert brief["languages"].get("rust", 0) >= 2            # 2 个 .rs
    assert "README.md" in [d["path"] for d in brief["doc_inventory"]]
    assert any("cip-3.md" in d["path"] for d in brief["doc_inventory"])
    # 模块图: execution 是一个候选顶层模块
    assert any("execution" in m for m in brief["module_map"])
    # 候选概念种子来自模块/目录名(不是概念定义, 只是起点)
    assert "execution" in brief["candidate_seeds"]
    assert brief["has_codeowners"] is True


def test_detect_empty_repo_is_honest(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    brief = detect_repo(str(empty))
    assert brief["languages"] == {}
    assert brief["candidate_seeds"] == []
    assert brief["doc_inventory"] == []


def test_detect_excludes_vendored(tmp_path):
    """真 repo 画像不能被 target/.venv/node_modules 里的依赖代码淹没。"""
    repo = _mk(tmp_path)
    (repo / "target" / "debug").mkdir(parents=True)
    (repo / "target" / "debug" / "dep.rs").write_text("pub struct Dep {}\n")
    (repo / "node_modules" / "x").mkdir(parents=True)
    (repo / "node_modules" / "x" / "y.js").write_text("var z=1\n")
    brief = detect_repo(str(repo))
    assert "target" not in brief["candidate_seeds"]
    assert "node_modules" not in brief["candidate_seeds"]
    assert brief["languages"].get("js", 0) == 0        # vendored js 不计入
```

- [ ] **Step 2: 运行验证失败**

Run: `pytest tests/test_onboard_detect.py -v`
Expected: FAIL(`ModuleNotFoundError`)。

- [ ] **Step 3: 实现探测器**

Create `src/marshal_core/onboard/detect.py`:

```python
"""Onboard repo 探测 —— 确定性的"抽取简报"生成器。给 agent 一个起点:
语言分布 / 文档清单 / 模块图 / 候选概念种子(来自目录与模块名, 非概念定义)。
概念的真正综合与命名是 agent 的判断, 不在这里做。"""
from collections import Counter
from pathlib import Path

_LANG_BY_EXT = {".rs": "rust", ".py": "python", ".js": "js", ".ts": "ts",
                ".go": "go", ".java": "java", ".c": "c", ".cpp": "cpp"}
_DOC_EXT = {".md", ".rst", ".txt", ".mdx"}
# 与 estimate 共用同一套排除(vendored/build/deps), 否则真 repo 画像被依赖淹没
_IGNORE_DIRS = {".git", "target", "node_modules", ".venv", "__pycache__",
                "dist", "build", "vendor", ".mypy_cache", ".pytest_cache", ".ruff_cache"}


def detect_repo(repo_root: str) -> dict:
    root = Path(repo_root)
    langs: Counter = Counter()
    docs = []
    module_dirs: set[str] = set()
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel_parts = p.relative_to(root).parts
        if _IGNORE_DIRS & set(rel_parts):          # 跳过 vendored/build/deps
            continue
        rel = p.relative_to(root).as_posix()
        ext = p.suffix.lower()
        if ext in _LANG_BY_EXT:
            langs[_LANG_BY_EXT[ext]] += 1
            if len(rel_parts) > 1:                  # 顶层模块 = 第一段路径
                module_dirs.add(rel_parts[0])
        elif ext in _DOC_EXT:
            docs.append({"path": rel, "bytes": p.stat().st_size})

    return {
        "repo_root": str(root),
        "languages": dict(langs),
        "doc_inventory": sorted(docs, key=lambda d: d["path"]),
        "module_map": sorted(module_dirs),
        "candidate_seeds": sorted(module_dirs),   # 目录名作候选概念种子起点
        "has_codeowners": (root / "CODEOWNERS").is_file(),
    }
```

- [ ] **Step 4: 运行验证通过**

Run: `pytest tests/test_onboard_detect.py -v`
Expected: PASS(2 passed)。

- [ ] **Step 5: Commit**

```bash
git add src/marshal_core/onboard/detect.py tests/test_onboard_detect.py
git commit -m "onboard: add deterministic repo detect (extraction brief)"
```

---

## Task 3: `Store.list_edges`(report 的依赖)

**Files:**
- Modify: `src/marshal_core/knowledge/store.py`
- Test: `tests/test_onboard_report.py`(仅本 Task 的 store 部分)

- [ ] **Step 1: 写失败测试**

Create `tests/test_onboard_report.py`:

```python
from marshal_core.knowledge.store import Store
from marshal_core.knowledge.models import ConceptEdge


def test_list_edges_returns_edges_touching_pack(db_session):
    # 深审 run: 语义 = "任一端落在 pack 内"(非两端都在)—— report 需看到悬空引用
    for src, dst, kind in [("a", "b", "depends_on"),   # 两端都在
                           ("a", "x", "depends_on"),   # src 在, dst 悬空
                           ("y", "b", "part_of"),      # dst 在, src 悬空
                           ("c", "d", "part_of")]:     # 都不在
        db_session.add(ConceptEdge(src_id=src, dst_id=dst, kind=kind))
    db_session.commit()
    store = Store(db_session)
    pairs = {(e.src_id, e.dst_id) for e in store.list_edges({"a", "b"})}
    assert pairs == {("a", "b"), ("a", "x"), ("y", "b")}   # 含悬空端, 排除都不在的
```

- [ ] **Step 2: 运行验证失败**

Run: `pytest tests/test_onboard_report.py::test_list_edges_returns_edges_touching_pack -v`
Expected: FAIL(`AttributeError: 'Store' object has no attribute 'list_edges'`)。

- [ ] **Step 3: 实现**

Modify `src/marshal_core/knowledge/store.py`:

(a) 文件头 import 补 `ConceptEdge`(与 `Concept` 同处),并从 sqlalchemy 补 `or_`(原为 `from sqlalchemy import select, func`):

```python
from sqlalchemy import select, func, or_
from .models import InvariantRegistry, GateRun, AuditLog, EscapeRegistry, Concept, ConceptEdge
```

(b) 在 `Store` 类末尾加:

```python
    def list_edges(self, concept_ids: set[str]) -> list[ConceptEdge]:
        """返回**任一端**落在 concept_ids 内的边。深审 run 结论:必须包含悬空引用
        (src 在但 dst 是未建概念)—— 否则 report 既漏"悬空引用"信号, 又把"只依赖了尚未
        建立的概念"的节点误报成 orphan(它的唯一边被过滤掉了)。"""
        stmt = select(ConceptEdge).where(
            or_(ConceptEdge.src_id.in_(concept_ids), ConceptEdge.dst_id.in_(concept_ids))
        )
        return list(self.s.scalars(stmt))
```

- [ ] **Step 4: 运行验证通过**

Run: `pytest tests/test_onboard_report.py::test_list_edges_returns_edges_touching_pack -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add src/marshal_core/knowledge/store.py tests/test_onboard_report.py
git commit -m "onboard: add Store.list_edges for tech-debt report"
```

---

## Task 4: 技术债信号报告(确定性,S1 的核心价值)

**Files:**
- Create: `src/marshal_core/onboard/report.py`
- Test: `tests/test_onboard_report.py`

> **5 类信号(全部确定性、可复核,§6.4;`dangling_refs` 由深审 run 补入):**
> - `unanchored_high`: importance ∈ {constitutional, high} 且 `doc_only=True`(高重要性概念无代码锚定 = 风险)。
> - `orphans`: 无父、无子、无任何边的孤立概念(可能是错放/死概念)。
> - `over_fragmented`: 同一父下子节点数 > 阈值(默认 12)(可能被拆太细)。
> - `dangling_parent`: `parent_id` 非空但指向不存在的概念(断裂的树)。
> - `dangling_refs`: `depends_on`/`part_of` 边指向不存在的概念(引用了尚未建立的概念 = onboard 最常见真债;深审实测:S0 的 `gas→basefee` 正是此形)。

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_onboard_report.py`:

```python
from marshal_core.onboard.report import tech_debt_signals


def _seed(store):
    # execution(high, 有锚定) → gas(constitutional, doc_only=无锚定)
    store.upsert_concept(id="execution", domain_pack="c", parent_id="",
                         importance="high", status="a", confidence=0.85,
                         doc_only=False, definition="")
    store.upsert_concept(id="gas", domain_pack="c", parent_id="execution",
                         importance="constitutional", status="a", confidence=0.3,
                         doc_only=True, definition="")            # 高重要性无锚定
    store.upsert_concept(id="lonely", domain_pack="c", parent_id="",
                         importance="low", status="a", confidence=0.3,
                         doc_only=True, definition="")            # 孤立
    store.upsert_concept(id="waif", domain_pack="c", parent_id="ghost",
                         importance="low", status="a", confidence=0.3,
                         doc_only=True, definition="")            # 父不存在


def test_tech_debt_signals(db_session):
    store = Store(db_session)
    _seed(store)
    sig = tech_debt_signals(store, "c")
    assert "gas" in sig["unanchored_high"]
    assert "execution" not in sig["unanchored_high"]      # 有锚定, 不算
    assert "lonely" in sig["orphans"]
    assert "gas" not in sig["orphans"]                    # gas 有父, 不算孤立
    assert "waif" in sig["dangling_parent"]
    assert sig["over_fragmented"] == []                   # 无超阈父


def test_over_fragmented_threshold(db_session):
    store = Store(db_session)
    store.upsert_concept(id="root", domain_pack="c", parent_id="", importance="high",
                         status="a", confidence=0.5, doc_only=True, definition="")
    for i in range(13):                                    # 13 > 默认阈值 12
        store.upsert_concept(id=f"k{i}", domain_pack="c", parent_id="root",
                             importance="low", status="a", confidence=0.5,
                             doc_only=True, definition="")
    sig = tech_debt_signals(store, "c")
    assert "root" in sig["over_fragmented"]


def test_dangling_ref_caught_and_not_false_orphan(db_session):
    """深审 run(HIGH): gas depends_on basefee 但 basefee 没建页(onboard 常见)——
    ① basefee 必须进 dangling_refs;② gas 有出边, 不能被误报成 orphan。"""
    from marshal_core.knowledge.models import ConceptEdge
    store = Store(db_session)
    store.upsert_concept(id="gas", domain_pack="c", parent_id="", importance="high",
                         status="a", confidence=0.85, doc_only=False, definition="")
    db_session.add(ConceptEdge(src_id="gas", dst_id="basefee", kind="depends_on"))
    db_session.commit()
    sig = tech_debt_signals(store, "c")
    assert "basefee" in sig["dangling_refs"]      # 悬空引用被抓
    assert "gas" not in sig["orphans"]            # 有出边 → 不是孤立(修前会误报)
```

- [ ] **Step 2: 运行验证失败**

Run: `pytest tests/test_onboard_report.py -v`
Expected: FAIL(`ModuleNotFoundError: marshal_core.onboard.report`)。

- [ ] **Step 3: 实现报告**

Create `src/marshal_core/onboard/report.py`:

```python
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
        if n > over_fragment_threshold:
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
```

- [ ] **Step 4: 运行验证通过**

Run: `pytest tests/test_onboard_report.py -v`
Expected: PASS(3 passed)。

- [ ] **Step 5: Commit**

```bash
git add src/marshal_core/onboard/report.py tests/test_onboard_report.py
git commit -m "onboard: add deterministic tech-debt signal report"
```

---

## Task 5: 三个 CLI 命令

**Files:**
- Modify: `src/marshal_core/cli.py`
- Test: `tests/test_onboard_cli.py`

- [ ] **Step 1: 写失败测试**

Create `tests/test_onboard_cli.py`:

```python
import json

from marshal_core.cli import main

PAGE = """---
type: concept
concept_id: gas
parent: ""
importance: constitutional
status: authoritative
last_updated: 2026-07-25
---
gas.
"""


def _repo(tmp_path):
    repo = tmp_path / "node"
    (repo / "execution").mkdir(parents=True)
    (repo / "execution" / "gas.rs").write_text("pub struct GasReport {}\n")
    (repo / "README.md").write_text("# node\n")
    return repo


def test_onboard_estimate_cli(tmp_path, capsys):
    rc = main(["onboard-estimate", "--repo", str(_repo(tmp_path))])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["is_estimate"] is True and "method" in out


def test_onboard_detect_cli(tmp_path, capsys):
    rc = main(["onboard-detect", "--repo", str(_repo(tmp_path))])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert "candidate_seeds" in out and out["languages"].get("rust") == 1


def test_onboard_report_cli(tmp_path, capsys):
    concepts = tmp_path / "concepts"
    concepts.mkdir()
    (concepts / "gas.md").write_text(PAGE)          # constitutional, 无 anchor → doc_only
    rc = main(["onboard-report", "--domain-pack", "cowboy",
               "--concepts-dir", str(concepts), "--repo-root", f"node={_repo(tmp_path)}"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert "gas" in out["unanchored_high"]          # 高重要性无锚定被拎出
```

- [ ] **Step 2: 运行验证失败**

Run: `pytest tests/test_onboard_cli.py -v`
Expected: FAIL(argparse: `invalid choice: 'onboard-estimate'`)。

- [ ] **Step 3: 实现 CLI**

Modify `src/marshal_core/cli.py`:

(a) 文件头 import 区加(`Store`、`derive_db` 若已在勿重复;`derive_db` 在 S0 已 import):

```python
from .onboard.estimate import estimate_cost
from .onboard.detect import detect_repo
from .onboard.report import tech_debt_signals
```

(b) 在 `cmd_concept_*`(S0 加的)附近加三个命令:

```python
def cmd_onboard_estimate(a) -> int:
    return _emit(estimate_cost(a.repo))


def cmd_onboard_detect(a) -> int:
    return _emit(detect_repo(a.repo))


def cmd_onboard_report(a) -> int:
    roots = _parse_repo_roots(a.repo_root)     # S0 已有的 helper
    s = _session()
    try:
        store = Store(s)
        derive_db(a.concepts_dir, a.domain_pack, store, roots)   # 复用 S0 单向派生
        return _emit(tech_debt_signals(store, a.domain_pack))
    finally:
        s.close()
```

(c) 在 `build_parser()` 里(S0 的 concept 子命令附近)加:

```python
    oe = sub.add_parser("onboard-estimate")
    oe.add_argument("--repo", required=True)
    oe.set_defaults(func=cmd_onboard_estimate)

    od = sub.add_parser("onboard-detect")
    od.add_argument("--repo", required=True)
    od.set_defaults(func=cmd_onboard_detect)

    orp = sub.add_parser("onboard-report")
    orp.add_argument("--domain-pack", default="cowboy")
    orp.add_argument("--concepts-dir", required=True)
    orp.add_argument("--repo-root", action="append", default=[])
    orp.set_defaults(func=cmd_onboard_report)
```

> 注:`_parse_repo_roots` 是 S0 代码质量修正引入的 helper(cli.py)。若不存在(S0 未合并该修正),改用 `dict(kv.split("=", 1) for kv in a.repo_root)`。

- [ ] **Step 4: 运行验证通过**

Run: `pytest tests/test_onboard_cli.py -v`
Expected: PASS(3 passed)。

- [ ] **Step 5: 全量回归 + lint**

Run: `pytest -q && ruff check src tests`
Expected: 全绿(除 2 个 pre-existing `marshal_core/checks/` node-drift 失败),lint 干净。

- [ ] **Step 6: Commit**

```bash
git add src/marshal_core/cli.py tests/test_onboard_cli.py
git commit -m "onboard: add onboard-estimate/detect/report CLI commands"
```

---

## Task 6: `/onboard` 编排 skill(agent 抽取 + 确定性命令串联)

**Files:**
- Create: `.claude/skills/onboard/SKILL.md`

> 这是**编排文档**(agent 的"大脑"流程),非 TDD 代码。它把确定性 CLI 与 agent 抽取串成 Phase 0 快照流,并把**人审接受门**写死进流程。

- [ ] **Step 1: 写 skill**

Create `.claude/skills/onboard/SKILL.md`:

```markdown
---
name: onboard
description: Use to onboard a repo's HEAD into a Marshal concept registry (Phase 0 snapshot) — dry-run cost gate, deterministic detect, agent-drafted concept pages, tech-debt report, human acceptance. Triggers — "/onboard <repo-path>", "onboard this repo", "跑一次 onboard".
---

# Onboard Skill — Phase 0 HEAD 快照

你是 onboard 的编排器。确定性工作外包给 `marshal_core.cli`;概念抽取是你(agent)的判断工作。

## 前置
    PY="${MARSHAL_HOME:-/home/ubuntu/workspace/marshal}/.venv/bin/python"
    CLI() { "$PY" -m marshal_core.cli "$@"; }

## 流程(严格按序,估价门不过不动手)

1. **估价门(先做):** `CLI onboard-estimate --repo <repo>` → 把 est_usd/tokens/calls + method 摆给用户。
   **显式确认**是否继续(§6.3:成本先摆出来再花)。用户不同意 → 停。

2. **探测:** `CLI onboard-detect --repo <repo>` → 得抽取简报(languages/doc_inventory/module_map/candidate_seeds)。

3. **抽取(你的判断工作,agent fan-out):** 按简报, 对每个 candidate_seed / 关键 doc, 起草概念页 markdown
   写进 `<concepts-out-dir>`(一个**新目录**, 不覆盖已策展的 pack)。每页遵守 S0 `concept-schema.md`:
   - frontmatter 必含 `concept_id`/`importance`/`status`;anchors **必须指向 detect 见过的真实符号定义**
     (H1:无真实定义锚点的概念别硬塞 anchor, 让它自然落为 doc_only, 别谎报锚定)。
   - importance 由你按架构判断给先验;**宁少勿多**(§3.0:只在跨 3+ 源或有矛盾时建概念页)。
   - 树要浅、节点数目标 20–40(§8 S1 验收)。

4. **派生 + 报告:** `CLI onboard-report --domain-pack <p> --concepts-dir <out> --repo-root <repo>=<path>`
   → 得技术债信号(unanchored_high / orphans / over_fragmented / dangling_parent)。

5. **人审接受门(硬门, §8 S1 + 深审 Q②):**
   - 概念树交**第二人或盲抽样**评:概念/父子/重要性正确率 **≥70%** 才算通过;记抽样比例 + 不接受项。
   - **禁止**自评放水;未达标 → 回步骤 3 调抽取, 不放宽门槛。
   - 对高重要性概念**人眼扫语义是否名副其实**(S4 挂羊头 lens 未上线前的临时兜底)。

## 铁律
- **估价门不过不动手**;成本诚实, 不谎报精度。
- **抽取的准确率靠人审门兜底**, 不假装 CLI 能验证语义。
- 概念页写进**新目录**, 不覆盖 refs/wiki 手工策展的种子(除非用户明确要 re-onboard)。
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/onboard/SKILL.md
git commit -m "onboard: add /onboard orchestration skill"
```

---

## Task 7: S1 验收 run(人审门,非单元测试)

> 人参与的验收门,坐实 §8 S1 判据。产出记 `gate-record` 或 `docs/`;门槛不达标回对应 Task,**不放宽**。

- [ ] **Step 1: dry-run 估价对 `node/`**

Run: `python -m marshal_core.cli onboard-estimate --repo /home/ubuntu/workspace/node`
记录估算值。跑完真实 onboard 后回填实际 token(来自 agent 的 `budget.spent()` 或计量),**核对偏差**。
**门槛:** 实际成本落在 est_usd_low..high 的 ±50% 内,或如实记录偏差原因(§6.3 诚实,不放宽)。

- [ ] **Step 2: 走 `/onboard` 全流程 onboard `node/`(写进新目录, 不碰 refs/wiki 种子)**

产出:`node/` 概念树 + 技术债报告。**门槛(§8 S1):20–40 节点树;人审接受率 ≥70%**(第二人/盲抽样,记比例与错项)。未达标 → 回 Task 6 skill 抽取调。

- [ ] **Step 3: 技术债报告 sanity**

人工核 `onboard-report` 输出:`unanchored_high` 里的高重要性概念确实缺代码锚定;`orphans`/`dangling_parent` 确实是异常而非误报。**门槛:** 抽查的信号**多数为真阳**(≥70%),假阳性回 Task 4 调规则/阈值。

- [ ] **Step 4: 记录验收结果**

Run: `python -m marshal_core.cli gate-record --change-ref "s1-onboard-snapshot-acceptance" --verdict pass`
(仅当 Step 1–3 三门全达标;任一未达 → 记 `escalate` 并回对应 Task。)

- [ ] **Step 5: 进实现前的纪律**

本 plan 进实现前 **先过 `/marshal` 深审**([[feedback_all_plans_deep_review]]),重点审:①估价模型是否会被"调参"掩盖真实成本;②detect/report 的确定性测试是否真测了行为(非玩具 fixture 假绿);③skill 的人审门能否被自评绕过(Q② 复现风险)。

---

## Self-Review(规格覆盖核对)

| 上游 S1 判据 / 深审项 | 对应 Task |
|---|---|
| `cli onboard --dry-run` 估价 | Task 1(`onboard-estimate`)+ Task 7 Step 1 |
| repo 探测 / 抽取简报 | Task 2(`onboard-detect`) |
| 技术债信号报告 | Task 4(`tech_debt_signals`)+ Task 5 CLI |
| Markdown 概念树(复用 S0) | Task 5 `onboard-report` 内 `derive_db` + S0 `concept-tree` |
| `/onboard --snapshot` 编排 | Task 6 skill(架构决定:agent 抽取, 非 core 调 LLM) |
| **成本诚实(§6.3,不静默截断)** | Task 1 `is_estimate/method` + Task 6 估价门 + Task 7 Step 1 |
| **人审接受率 ≥70%(§8 + 深审 Q②)** | Task 6 skill 步骤 5 + Task 7 Step 2(第二人/盲审) |
| **H1 锚定=代码验证(复用 S0)** | Task 6 skill 步骤 3(anchor 必指真实定义)+ `onboard-report` 复用 S0 doc_only |

**架构决定(记录):** onboard 的 AI 抽取由 **agent 编排**(marshal_core 无 LLM client,已核实),不是 core 里的 LLM 调用。core 只出确定性的 estimate/detect/report;抽取质量由人审门验收。这与 marshal 既有"薄 CLI + agent 大脑"一致。

**未覆盖(明确留后续 slice):** Phase 1 全量 issue/PR 回放 + 债时间归因(S6)、概念预算(S2)、挂羊头 lens(S4)、可视化(S5)、`onboard` 单命令一键化(需 agent-in-CLI, 违背当前架构, 不做)。

---

## 深审修正记录(Marshal 深审,审法=对真实 node/ 执行 + 对抗反证)

| # | 严重性 | 发现(已执行证实) | 修正 |
|---|---|---|---|
| **起草冒烟①** | — | 扫描未排除 vendored/build → node/ 估价虚高一个数量级($55-275) | 已并入起草稿:`_IGNORE_DIRS`(Task 1/2)→ $13-67 |
| **起草冒烟②** | — | 估价概念数按巢状叶目录计(2361)与 20-40 目标矛盾 | 已并入:改按顶层模块计(69) |
| **H-report** | **HIGH** | `report` 非对称缺陷:`list_edges` 只返回两端都在的边 → ① `depends_on` 指向未建概念(`gas→basefee`,onboard 最常见)**被静默丢**,无信号;② 该节点唯一边被过滤 → **误报成 orphan**(在新 onboard 树上 orphan 假阳性泛滥) | Task 3 `list_edges` 改"任一端在"(`or_`);Task 4 report 加 `dangling_refs` 信号 + `has_edge` 按出现端计 → orphan 不再假阳性;两处加回归测试。**已在 scratch 执行验证**:gas 不再误 orphan、basefee 进 dangling_refs |
| **M-detect** | MED〔接受/记录〕 | `detect` 的 `candidate_seeds` 只是顶层目录名, 比上游 §3.5"约定探测"(系统地址表/共享序列化/测试名)薄很多——近似 `ls` | 接受:S0 快照期 agent 本就会读代码;不硬做重探测(YAGNI)。**记录为已知薄弱点**, 别把 detect 当强信号源 |
| **M-estimate** | MED〔接受/记录〕 | 估价常量(char/token 比、USD 单价、concepts/module)是未校准猜测;唯一真检验是 Task 7 Step 1 的 ±50% 事后核对 | 接受:已显式披露 `is_estimate`+method;数值**不得当权威**, 只作动手前量级参考。Task 7 Step 1 事后核对是硬门 |
| **M-humangate** | MED〔已知限制,复现〕 | 人审接受门(Task 6 步骤5 / Task 7 Step 2)是**流程指令、无工具强制**——独跑的 agent/用户可自评放水(S0 的 Q② 同款,未在工具层解决) | 显式标注为**未强制的已知限制**;缓解靠"第二人/盲抽样"约定 + 记录抽样比例。工具层强制留后续 |

**未闭合、留人裁/待实测:** M-estimate 的常量校准要 Task 7 真实 onboard 才有数;M-humangate 的工具层强制不在本 slice。H-report 已闭合并执行验证。

**结论:** S1 plan 方向与架构成立(薄 CLI + agent 大脑、确定性核心可 TDD),**H-report 是唯一 HIGH 且已修+验证**;三条 MED 是显式接受的边界。可进实现。

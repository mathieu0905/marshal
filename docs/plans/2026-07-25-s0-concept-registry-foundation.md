# S0 · 概念注册表地基(Concept Registry Foundation)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建成一条自持、单向派生、代码锚定的概念注册表竖切:markdown 概念页(真相源)→ 派生 DB 缓存 → 代码锚定校验(H1)→ `cli concept-tree` 打印可审的树,并用 fake-pack 证明核心领域无关。

**Architecture:** markdown 概念页(frontmatter 带 `parent`/`importance`/`depends_on`/`anchors`)是**唯一真相源**;`derive_db` **单向**把页派生进 `marshal.db` 的 4 张缓存表(M2:DB 只读派生,永不回写为真相);`verify_anchors` 对每个 anchor 回查代码符号是否真存在(H1:无验证锚点的概念标 `doc_only` 且 `confidence` 封顶,gate 不得据以高置信);概念内容全归 `marshal_pack_cowboy/concepts/`(D9:Marshal 自有,零 refs 运行时依赖)。

**Tech Stack:** Python 3.11 · SQLAlchemy 2.0 · pydantic v2 · PyYAML(本 slice 新增,解析 frontmatter)· pytest(内存 SQLite,`db_session` fixture)。

**上游依据:** [`2026-07-24-marshal-three-gates-concept-registry.zh.md`](2026-07-24-marshal-three-gates-concept-registry.zh.md) §3、§8 S0,及其深审修正 H1 / M2 / M1 / D9。

**本 plan 已过一轮 Marshal 深审(gate run 750,escalate)——审法是把计划代码真的跑起来(9/9 通过 + 对抗反证)。** 3 条修正已并回:①**H1-weak**(verify_anchors 从"任意出现"收紧为**定义位**匹配 + 边界写清"不判挂羊头语义",Task 5 / Task 9 Step 3);②**bug C**(anchor 缺字段抛 ValueError 非 KeyError + derive 收集坏页不崩批,Task 2 / Task 6);③**Q②**(Task 9 接受率门须独立/盲审,不自评)。已清除的伪 concern:parser 对 body 内 `---` 水平线稳(实测)、M2 测试非假绿(实测)。详见文末「深审修正记录」。

**范围边界(YAGNI):** 本 slice **只做**竖切骨架 + H1 守栏 + fake-pack 护栏 + 单页种子。**不做**:全量 27 页导入(=S0 验收 run,Task 9 手动门)、plan-cost / concept-check / onboard(S1–S4)、可视化(S5)、`ConceptChange` 的 redefine/move 全谱(S0 只记 `add`)。

---

## 文件结构(先锁定分解)

| 文件 | 责任 | 动作 |
|---|---|---|
| `src/marshal_core/concept/__init__.py` | 包标记 | Create |
| `src/marshal_core/concept/model.py` | `ConceptPage` 领域模型 + `parse_concept_page()` frontmatter 解析 | Create |
| `src/marshal_core/concept/anchor.py` | `verify_anchors()` — H1 代码锚定校验 | Create |
| `src/marshal_core/concept/sync.py` | `derive_db()` — 单向 markdown→DB 派生(M2) | Create |
| `src/marshal_core/knowledge/models.py` | 加 `Concept`/`ConceptEdge`/`ConceptAnchor`/`ConceptChange` 4 张缓存表 | Modify |
| `src/marshal_core/knowledge/store.py` | 加 `upsert_concept` / `list_concepts` / `concept_tree` | Modify |
| `src/marshal_core/cli.py` | 加 `cmd_concept_list` / `cmd_concept_tree` + subparsers | Modify |
| `src/marshal_pack_cowboy/concepts/concept-schema.md` | 领域无关"概念协议"(frontmatter 规约) | Create |
| `src/marshal_pack_cowboy/concepts/dual-gas-model.md` | 首个真种子概念页(带 anchors) | Create |
| `tests/test_concept_model.py` | 解析测试 | Create |
| `tests/test_concept_anchor.py` | H1 锚定校验测试 | Create |
| `tests/test_concept_sync.py` | 单向派生测试(M2) | Create |
| `tests/test_concept_store.py` | store 方法 + 树构建测试 | Create |
| `tests/test_concept_cli.py` | CLI 输出测试 | Create |
| `tests/test_fake_pack.py` | 加领域无关概念派生护栏 | Modify |
| `pyproject.toml` | 加 `pyyaml` 依赖 | Modify |

**约定(全程遵守):** ruff line-length=100;pytest `pythonpath=["src"]`;测试用 `db_session`(内存 SQLite);每个 Task 末尾 commit;commit message **不带任何 AI 署名**(marshal repo 规则)。

---

## Task 1: 概念页 frontmatter 规约 + 首个真种子页

**Files:**
- Create: `src/marshal_pack_cowboy/concepts/concept-schema.md`
- Create: `src/marshal_pack_cowboy/concepts/dual-gas-model.md`

- [ ] **Step 1: 写领域无关"概念协议"规约**

Create `src/marshal_pack_cowboy/concepts/concept-schema.md`:

```markdown
# 概念页规约(Concept Page Protocol)

Marshal 自有的概念真相源。每个 `concepts/<slug>.md` 是一个概念节点;人审改这里,
DB 只从这里单向派生(不反向)。种子一次性来自 refs/wiki + refs/analysis 修正案,
导入后与 refs 无运行时依赖。

## Frontmatter(必填字段)

    ---
    type: concept | entity
    concept_id: <kebab-slug>          # 唯一 id,= 文件名去 .md
    parent: <concept_id | "">         # 主父(单 primary_parent);根为空串
    importance: constitutional | high | mid | low   # = 优先级 = 架构判断
    part_of: [<concept_id>, ...]      # 次要归属(多父,不定层级)
    depends_on: [<concept_id>, ...]   # 依赖边(DAG)
    anchors:                          # 代码锚点(H1:必须真实存在)
      - {repo: <r>, path: <p>, symbol: <sym>, kind: implements|named_after}
    spec_refs: [<CIP-N>, ...]         # 规格来源(挂到概念)
    status: authoritative | draft | stale | doc-only
    last_updated: YYYY-MM-DD
    ---

## 权威与派生

- 真相源 = 本目录 markdown;`marshal.db` 是**只读派生缓存**(单向)。
- `confidence` 由代码锚定程度决定,不由文档描述决定:无任何 anchor 通过校验的
  概念标 `doc_only`、confidence 封顶,gate 不得据以给高置信判决(H1)。
- 重要性(importance)是人审定的架构判断,不用 PageRank 自动定。
```

- [ ] **Step 2: 写首个真种子概念页(从 refs/wiki 蒸馏,但落进 Marshal 自有目录)**

Create `src/marshal_pack_cowboy/concepts/dual-gas-model.md`(anchors 指向真实代码符号,供 Task 6 校验):

```markdown
---
type: concept
concept_id: dual-gas-model
parent: execution
importance: constitutional
part_of: [economics]
depends_on: [basefee]
anchors:
  - {repo: node, path: execution/src/gas.rs, symbol: GasReport, kind: implements}
  - {repo: node, path: execution/src/basefee.rs, symbol: BLOCK_CYCLES_TARGET, kind: implements}
spec_refs: [CIP-3]
status: authoritative
last_updated: 2026-07-25
---

# 双计量 Gas 模型(Dual-Metered Gas）

Cowboy 分离**计算(Cycles)**与**数据(Cells)**两种稀缺资源,各自独立 EIP-1559
basefee 市场。改动它牵动全链数值守恒,故 importance=constitutional。

代码权威:`node/execution/src/gas.rs`(GasReport 分类)、`node/execution/src/basefee.rs`
(BLOCK_CYCLES_TARGET 等)。规格与代码历史漂移见 drift 记录(种子自 refs/analysis 修正案)。
```

- [ ] **Step 3: Commit**

```bash
git add src/marshal_pack_cowboy/concepts/concept-schema.md src/marshal_pack_cowboy/concepts/dual-gas-model.md
git commit -m "concept: add concept-page protocol and first seed page (dual-gas-model)"
```

---

## Task 2: `ConceptPage` 模型 + frontmatter 解析

**Files:**
- Modify: `pyproject.toml`(加 pyyaml)
- Create: `src/marshal_core/concept/__init__.py`(空)
- Create: `src/marshal_core/concept/model.py`
- Test: `tests/test_concept_model.py`

- [ ] **Step 1: 加 pyyaml 依赖**

Modify `pyproject.toml` — 在 `dependencies` 列表末尾(`"httpx>=0.27",` 之后)加一行:

```toml
  "pyyaml>=6.0",
```

Run: `pip install -e ".[dev]"`
Expected: 安装成功,`python -c "import yaml"` 无错。

- [ ] **Step 2: 写失败测试**

Create `tests/test_concept_model.py`:

```python
from marshal_core.concept.model import ConceptPage, parse_concept_page

SAMPLE = """---
type: concept
concept_id: dual-gas-model
parent: execution
importance: constitutional
part_of: [economics]
depends_on: [basefee]
anchors:
  - {repo: node, path: execution/src/gas.rs, symbol: GasReport, kind: implements}
spec_refs: [CIP-3]
status: authoritative
last_updated: 2026-07-25
---

# 双计量 Gas 模型

正文定义。
"""


def test_parse_concept_page_fields():
    page = parse_concept_page(SAMPLE)
    assert isinstance(page, ConceptPage)
    assert page.concept_id == "dual-gas-model"
    assert page.parent == "execution"
    assert page.importance == "constitutional"
    assert page.part_of == ["economics"]
    assert page.depends_on == ["basefee"]
    assert page.spec_refs == ["CIP-3"]
    assert len(page.anchors) == 1
    assert page.anchors[0].symbol == "GasReport"
    assert page.anchors[0].repo == "node"
    assert "双计量" in page.definition


def test_parse_rejects_missing_concept_id():
    bad = "---\ntype: concept\nimportance: low\n---\nbody\n"
    try:
        parse_concept_page(bad)
        assert False, "should have raised"
    except ValueError as e:
        assert "concept_id" in str(e)


def test_malformed_anchor_raises_valueerror_not_keyerror():
    """深审 run 750 bug C: anchor 缺字段必须抛 ValueError (可被 derive 收集), 不是
    KeyError (会冒泡令整批 derive 崩)。"""
    bad = ("---\ntype: concept\nconcept_id: x\nimportance: low\n"
           "anchors:\n  - {repo: node, path: p}\n---\nbody\n")   # 缺 symbol
    try:
        parse_concept_page(bad)
        assert False, "should have raised"
    except KeyError:
        assert False, "must not raise KeyError (crashes derive batch)"
    except ValueError as e:
        assert "anchor" in str(e)
```

- [ ] **Step 3: 运行验证失败**

Run: `pytest tests/test_concept_model.py -v`
Expected: FAIL(`ModuleNotFoundError: marshal_core.concept.model`)。

- [ ] **Step 4: 实现模型**

Create `src/marshal_core/concept/__init__.py`(空文件)。

Create `src/marshal_core/concept/model.py`:

```python
"""概念页领域模型 + frontmatter 解析。markdown 是真相源, 这里只做只读解析。"""
from dataclasses import dataclass, field

import yaml

_VALID_IMPORTANCE = {"constitutional", "high", "mid", "low"}


class NotAConceptPage(ValueError):
    """页面不是概念页(无 frontmatter 或无 concept_id)—— derive 应静默跳过, 非错误。
    与"格式错的概念页"(有 concept_id 但 anchor/importance 非法, 抛普通 ValueError)区分:
    后者是真 typo, 不能被静默吞掉(深审 run 750 bug C)。"""


@dataclass
class ConceptAnchor:
    repo: str
    path: str
    symbol: str
    kind: str = "implements"


@dataclass
class ConceptPage:
    concept_id: str
    importance: str
    parent: str = ""
    part_of: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    anchors: list[ConceptAnchor] = field(default_factory=list)
    spec_refs: list[str] = field(default_factory=list)
    status: str = "draft"
    definition: str = ""


def parse_concept_page(text: str) -> ConceptPage:
    """把一页 markdown(frontmatter + body)解析成 ConceptPage。字段缺失即报错,
    不静默给默认 —— 概念真相源必须显式。非概念页抛 NotAConceptPage(可跳过);
    概念页格式错抛 ValueError(是 typo, 不可静默吞)。"""
    if not text.startswith("---"):
        raise NotAConceptPage("not a concept page: missing YAML frontmatter (---)")
    _, fm_raw, body = text.split("---", 2)
    fm = yaml.safe_load(fm_raw) or {}

    concept_id = fm.get("concept_id")
    if not concept_id:
        raise NotAConceptPage("not a concept page: frontmatter has no 'concept_id'")
    importance = fm.get("importance")
    if importance not in _VALID_IMPORTANCE:
        raise ValueError(f"invalid importance {importance!r}; want one of {_VALID_IMPORTANCE}")

    try:
        anchors = [
            ConceptAnchor(repo=a["repo"], path=a["path"], symbol=a["symbol"],
                          kind=a.get("kind", "implements"))
            for a in (fm.get("anchors") or [])
        ]
    except (KeyError, TypeError) as e:   # 缺字段/格式错 → ValueError (深审 bug C: 别抛 KeyError 崩批)
        raise ValueError(f"malformed anchor in concept {concept_id!r}: missing field {e}") from e
    return ConceptPage(
        concept_id=concept_id,
        importance=importance,
        parent=fm.get("parent", "") or "",
        part_of=list(fm.get("part_of") or []),
        depends_on=list(fm.get("depends_on") or []),
        anchors=anchors,
        spec_refs=list(fm.get("spec_refs") or []),
        status=fm.get("status", "draft"),
        definition=body.strip(),
    )
```

- [ ] **Step 5: 运行验证通过**

Run: `pytest tests/test_concept_model.py -v`
Expected: PASS(2 passed)。

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/marshal_core/concept/__init__.py src/marshal_core/concept/model.py tests/test_concept_model.py
git commit -m "concept: add ConceptPage model and frontmatter parser"
```

---

## Task 3: 4 张缓存表进知识核

**Files:**
- Modify: `src/marshal_core/knowledge/models.py`
- Test: `tests/test_concept_store.py`(仅本 Task 的建表/查询部分)

- [ ] **Step 1: 写失败测试(建表 + 直接插查)**

Create `tests/test_concept_store.py`:

```python
from marshal_core.knowledge.models import Concept, ConceptEdge, ConceptAnchorRow, ConceptChange


def test_concept_tables_roundtrip(db_session):
    db_session.add(Concept(
        id="dual-gas-model", domain_pack="cowboy", parent_id="execution",
        importance="constitutional", status="authoritative", confidence=0.9,
        doc_only=False, definition="dual gas",
    ))
    db_session.add(ConceptEdge(src_id="timer-mechanism", dst_id="dual-gas-model",
                               kind="depends_on"))
    db_session.add(ConceptAnchorRow(concept_id="dual-gas-model", repo="node",
                                    path="execution/src/gas.rs", symbol="GasReport",
                                    kind="implements", verified=True))
    db_session.add(ConceptChange(change_ref="seed", op="add", concept_id="dual-gas-model",
                                 before={}, after={"importance": "constitutional"},
                                 rationale="seed import", actor="system"))
    db_session.commit()

    c = db_session.get(Concept, "dual-gas-model")
    assert c.importance == "constitutional"
    assert c.doc_only is False
```

- [ ] **Step 2: 运行验证失败**

Run: `pytest tests/test_concept_store.py::test_concept_tables_roundtrip -v`
Expected: FAIL(`ImportError: cannot import name 'Concept'`)。

- [ ] **Step 3: 加 4 张表**

Modify `src/marshal_core/knowledge/models.py` — 在文件末尾(`EscapeRegistry` 之后)追加。复用已有的 `Base` / `_now` / `mapped_column` imports(文件头已 `from sqlalchemy import String, Integer, JSON, DateTime`,需补 `Boolean, Float`):

先把文件头的 import 行改为:

```python
from sqlalchemy import String, Integer, JSON, DateTime, Boolean, Float
```

再在文件末尾追加:

```python
class Concept(Base):
    """概念节点缓存 (真相源是 marshal_pack_*/concepts/*.md; 此表单向派生, 只读)。"""
    __tablename__ = "concept"
    id: Mapped[str] = mapped_column(String, primary_key=True)          # = concept_id
    domain_pack: Mapped[str] = mapped_column(String, index=True)
    parent_id: Mapped[str] = mapped_column(String, default="")         # primary_parent; 根为 ""
    importance: Mapped[str] = mapped_column(String, default="low")
    status: Mapped[str] = mapped_column(String, default="draft")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    doc_only: Mapped[bool] = mapped_column(Boolean, default=True)      # H1: 无代码锚定
    definition: Mapped[str] = mapped_column(String, default="")


class ConceptEdge(Base):
    """非树关系 (part_of 多归属 / depends_on 依赖 / conflicts_with)。"""
    __tablename__ = "concept_edge"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    src_id: Mapped[str] = mapped_column(String, index=True)
    dst_id: Mapped[str] = mapped_column(String, index=True)
    kind: Mapped[str] = mapped_column(String)


class ConceptAnchorRow(Base):
    """代码锚点 (H1): 概念声称由某符号实现; verified 由 verify_anchors 回查代码得出。"""
    __tablename__ = "concept_anchor"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    concept_id: Mapped[str] = mapped_column(String, index=True)
    repo: Mapped[str] = mapped_column(String)
    path: Mapped[str] = mapped_column(String)
    symbol: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String, default="implements")
    verified: Mapped[bool] = mapped_column(Boolean, default=False)


class ConceptChange(Base):
    """概念树每次变更的 provenance (P3 的宝贵数据)。S0 只记 op=add。"""
    __tablename__ = "concept_change"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    change_ref: Mapped[str] = mapped_column(String, index=True)
    op: Mapped[str] = mapped_column(String)     # add|redefine|move|merge|split|rename|deprecate
    concept_id: Mapped[str] = mapped_column(String, index=True)
    before: Mapped[dict] = mapped_column(JSON, default=dict)
    after: Mapped[dict] = mapped_column(JSON, default=dict)
    rationale: Mapped[str] = mapped_column(String, default="")
    actor: Mapped[str] = mapped_column(String, default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
```

- [ ] **Step 4: 运行验证通过**

Run: `pytest tests/test_concept_store.py::test_concept_tables_roundtrip -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add src/marshal_core/knowledge/models.py tests/test_concept_store.py
git commit -m "concept: add Concept/ConceptEdge/ConceptAnchor/ConceptChange cache tables"
```

---

## Task 4: `Store` 概念方法 + 树构建

**Files:**
- Modify: `src/marshal_core/knowledge/store.py`
- Test: `tests/test_concept_store.py`

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_concept_store.py`:

```python
from marshal_core.knowledge.store import Store


def test_upsert_and_tree(db_session):
    store = Store(db_session)
    store.upsert_concept(id="execution", domain_pack="cowboy", parent_id="",
                         importance="high", status="authoritative", confidence=0.5,
                         doc_only=True, definition="exec root")
    store.upsert_concept(id="dual-gas-model", domain_pack="cowboy", parent_id="execution",
                         importance="constitutional", status="authoritative", confidence=0.9,
                         doc_only=False, definition="dual gas")
    # upsert 幂等: 再写一次改 importance
    store.upsert_concept(id="dual-gas-model", domain_pack="cowboy", parent_id="execution",
                         importance="high", status="authoritative", confidence=0.9,
                         doc_only=False, definition="dual gas")

    assert len(store.list_concepts("cowboy")) == 2
    tree = store.concept_tree("cowboy")
    assert tree[0]["id"] == "execution"
    assert tree[0]["children"][0]["id"] == "dual-gas-model"
    assert tree[0]["children"][0]["importance"] == "high"   # upsert 覆盖生效
```

- [ ] **Step 2: 运行验证失败**

Run: `pytest tests/test_concept_store.py::test_upsert_and_tree -v`
Expected: FAIL(`AttributeError: 'Store' object has no attribute 'upsert_concept'`)。

- [ ] **Step 3: 实现 store 方法**

Modify `src/marshal_core/knowledge/store.py` — 文件头 import 补 `Concept`:

```python
from .models import InvariantRegistry, GateRun, AuditLog, EscapeRegistry, Concept
```

在 `Store` 类末尾(`close_escape` 之后)加:

```python
    def upsert_concept(self, **kw) -> Concept:
        """派生写入 (单向 markdown→DB): 幂等 upsert 一个概念缓存行。"""
        c = Concept(**kw)
        self.s.merge(c)
        self.s.commit()
        return c

    def list_concepts(self, domain_pack: str) -> list[Concept]:
        stmt = select(Concept).where(Concept.domain_pack == domain_pack)
        return list(self.s.scalars(stmt))

    def concept_tree(self, domain_pack: str) -> list[dict]:
        """按 parent_id 组装 primary-parent 树 (可 review 骨架)。返回根列表, 每节点
        含 id/importance/confidence/doc_only/children。孤儿 (parent 不存在) 挂到根。"""
        nodes = {c.id: {"id": c.id, "importance": c.importance,
                        "confidence": c.confidence, "doc_only": c.doc_only,
                        "children": []}
                 for c in self.list_concepts(domain_pack)}
        roots = []
        for c in self.list_concepts(domain_pack):
            node = nodes[c.id]
            parent = nodes.get(c.parent_id) if c.parent_id else None
            (parent["children"] if parent else roots).append(node)
        return roots
```

- [ ] **Step 4: 运行验证通过**

Run: `pytest tests/test_concept_store.py -v`
Expected: PASS(2 passed)。

- [ ] **Step 5: Commit**

```bash
git add src/marshal_core/knowledge/store.py tests/test_concept_store.py
git commit -m "concept: add Store.upsert_concept/list_concepts/concept_tree"
```

---

## Task 5: 代码锚定校验(H1 守栏)

**Files:**
- Create: `src/marshal_core/concept/anchor.py`
- Test: `tests/test_concept_anchor.py`

- [ ] **Step 1: 写失败测试(用临时 fixture repo 目录)**

Create `tests/test_concept_anchor.py`:

```python
from marshal_core.concept.model import ConceptPage, ConceptAnchor
from marshal_core.concept.anchor import verify_anchors


def _page(anchors):
    return ConceptPage(concept_id="c", importance="high", anchors=anchors)


def test_verified_when_symbol_exists(tmp_path):
    repo = tmp_path / "node"
    (repo / "execution" / "src").mkdir(parents=True)
    (repo / "execution" / "src" / "gas.rs").write_text("pub struct GasReport { x: u64 }\n")
    page = _page([ConceptAnchor(repo="node", path="execution/src/gas.rs", symbol="GasReport")])

    report = verify_anchors(page, {"node": str(repo)})
    assert report.verified_count == 1
    assert report.doc_only is False
    assert report.confidence >= 0.8


def test_doc_only_when_symbol_missing(tmp_path):
    repo = tmp_path / "node"
    (repo / "execution" / "src").mkdir(parents=True)
    (repo / "execution" / "src" / "gas.rs").write_text("pub struct Something { x: u64 }\n")
    page = _page([ConceptAnchor(repo="node", path="execution/src/gas.rs", symbol="GasReport")])

    report = verify_anchors(page, {"node": str(repo)})
    assert report.verified_count == 0
    assert report.doc_only is True
    assert report.confidence <= 0.3   # H1: 无代码锚定 → confidence 封顶低


def test_no_anchors_is_doc_only(tmp_path):
    report = verify_anchors(_page([]), {"node": str(tmp_path)})
    assert report.doc_only is True
    assert report.confidence <= 0.3


def test_comment_only_mention_is_doc_only(tmp_path):
    """深审 run 750(H1-weak): 符号只在注释里提及、代码没实现 → 必须 doc_only,
    不能因文本出现就判高置信锚定(否则 H1 沦为文本存在检查, 就是它要防的 sim≠prod)。"""
    repo = tmp_path / "node"
    (repo / "execution" / "src").mkdir(parents=True)
    (repo / "execution" / "src" / "gas.rs").write_text(
        "// TODO: someday implement GasReport here\npub struct Foo {}\n")
    page = _page([ConceptAnchor(repo="node", path="execution/src/gas.rs", symbol="GasReport")])

    report = verify_anchors(page, {"node": str(repo)})
    assert report.verified_count == 0     # 注释提及不算定义
    assert report.doc_only is True


def test_defined_but_semantically_wrong_still_passes_anchor(tmp_path):
    """边界(非 bug): 挂羊头(名 GasReport 实为 UI widget)的**定义**仍通过 verify_anchors
    —— 语义名副其实由 S4 concept-consistency lens 判, 不是 H1 锚定的职责。此测锁定该边界,
    防有人误以为锚定率门=无挂羊头。"""
    repo = tmp_path / "node"
    (repo / "ui").mkdir(parents=True)
    (repo / "ui" / "gas.rs").write_text("pub struct GasReport { pixel_color: u8 }\n")
    page = _page([ConceptAnchor(repo="node", path="ui/gas.rs", symbol="GasReport")])

    report = verify_anchors(page, {"node": str(repo)})
    assert report.verified_count == 1     # 定义存在 → 锚定通过 (语义对错不在此判)
    assert report.doc_only is False
```

- [ ] **Step 2: 运行验证失败**

Run: `pytest tests/test_concept_anchor.py -v`
Expected: FAIL(`ModuleNotFoundError: marshal_core.concept.anchor`)。

- [ ] **Step 3: 实现校验器**

Create `src/marshal_core/concept/anchor.py`:

```python
"""H1 守栏: 概念锚定必须"代码验证", 不能"文档派生"。

深审 run 750(H1-weak)修正: **不能只查符号"出现"** —— 符号出现在注释/字符串/单纯
提及里, 会把"没实现"和"挂羊头"误判成高置信锚定(实测:`// TODO GasReport` 与
`struct GasReport{pixel}` 都被判 verified=0.85)。故收紧为**定义位匹配**(struct/fn/
const/def/class 等定义关键字后紧跟符号), 排除注释/提及。

**边界(必须写清):** 本模块只验"符号是否在此**定义**", **不判语义是否名副其实** ——
"挂羊头"(名 GasReport 实为 UI widget)的 struct 定义仍会通过。判语义错配是 S4 的
concept-consistency lens 的职责, 不是 H1。故 Task 9 Step 3 的锚定率门≠"无挂羊头"。
"""
import re
from dataclasses import dataclass
from pathlib import Path

from .model import ConceptPage

_DOC_ONLY_CONFIDENCE_CAP = 0.3
_VERIFIED_CONFIDENCE = 0.85
# 定义位关键字 (Rust + Python 覆盖本期两语言); 匹配 `<kw> <symbol>`, 排除注释/调用/提及
_DEF_KEYWORDS = r"struct|enum|fn|const|static|trait|type|impl|mod|def|class"


@dataclass
class AnchorReport:
    verified_count: int    # = 在定义位被找到的 anchor 数 (不是语义正确数)
    total: int
    doc_only: bool
    confidence: float
    verified_symbols: list[str]


def _symbol_defined(repo_root: str, rel_path: str, symbol: str) -> bool:
    """符号是否在此文件被**定义**(而非仅出现/被调用/注释提及)。"""
    f = Path(repo_root) / rel_path
    if not f.is_file():
        return False
    pattern = re.compile(rf"\b(?:{_DEF_KEYWORDS})\s+{re.escape(symbol)}\b")
    return bool(pattern.search(f.read_text(encoding="utf-8", errors="ignore")))


def verify_anchors(page: ConceptPage, repo_roots: dict[str, str]) -> AnchorReport:
    """repo_roots: {repo_name: absolute_path}。缺失的 repo 视为该 anchor 未验证。
    verified = 符号在锚点文件被定义; 无一通过 → doc_only + confidence 封顶(H1)。
    注意: anchor 应指向符号的**定义文件**, 非使用处。"""
    verified = [
        a.symbol for a in page.anchors
        if a.repo in repo_roots and _symbol_defined(repo_roots[a.repo], a.path, a.symbol)
    ]
    doc_only = len(verified) == 0
    confidence = _DOC_ONLY_CONFIDENCE_CAP if doc_only else _VERIFIED_CONFIDENCE
    return AnchorReport(
        verified_count=len(verified),
        total=len(page.anchors),
        doc_only=doc_only,
        confidence=confidence,
        verified_symbols=verified,
    )
```

- [ ] **Step 4: 运行验证通过**

Run: `pytest tests/test_concept_anchor.py -v`
Expected: PASS(3 passed)。

- [ ] **Step 5: Commit**

```bash
git add src/marshal_core/concept/anchor.py tests/test_concept_anchor.py
git commit -m "concept: add verify_anchors code-anchoring guard (H1)"
```

---

## Task 6: 单向派生 `derive_db`(M2)

**Files:**
- Create: `src/marshal_core/concept/sync.py`
- Test: `tests/test_concept_sync.py`

- [ ] **Step 1: 写失败测试(含 M2 关键回归:DB 非真相源,再派生覆盖 DB-only 写)**

Create `tests/test_concept_sync.py`:

```python
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
```

- [ ] **Step 2: 运行验证失败**

Run: `pytest tests/test_concept_sync.py -v`
Expected: FAIL(`ModuleNotFoundError: marshal_core.concept.sync`)。

- [ ] **Step 3: 实现单向派生**

Create `src/marshal_core/concept/sync.py`:

```python
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
    s.commit()

    count = 0
    malformed: list[str] = []
    for path in sorted(Path(concepts_dir).glob("*.md")):
        text = path.read_text(encoding="utf-8")
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
```

- [ ] **Step 4: 运行验证通过**

Run: `pytest tests/test_concept_sync.py -v`
Expected: PASS(2 passed)。

- [ ] **Step 5: Commit**

```bash
git add src/marshal_core/concept/sync.py tests/test_concept_sync.py
git commit -m "concept: add one-way derive_db (markdown source of truth, M2)"
```

---

## Task 7: CLI `concept-tree` / `concept-list`

**Files:**
- Modify: `src/marshal_core/cli.py`
- Test: `tests/test_concept_cli.py`

- [ ] **Step 1: 写失败测试(in-process 调 main, capsys 抓 JSON)**

Create `tests/test_concept_cli.py`:

```python
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
```

- [ ] **Step 2: 运行验证失败**

Run: `pytest tests/test_concept_cli.py -v`
Expected: FAIL(argparse: `invalid choice: 'concept-tree'`)。

- [ ] **Step 3: 实现 CLI 命令**

Modify `src/marshal_core/cli.py`:

(a) 在文件头 import 区加(与其它 `from .` imports 同处)。**`Store` 已在 cli.py import(多处 `Store(s)` 在用),勿重复**——只加:

```python
from .concept.sync import derive_db
```

(b) 在其它 `cmd_*` 函数附近(如 `cmd_metrics` 之后)加两个命令 + 一个 helper:

```python
def _derive_into_session(a):
    """CLI helper: 解析 --repo-root k=v 列表, 把 concepts-dir 派生进一个 session。"""
    roots = dict(kv.split("=", 1) for kv in (a.repo_root or []))
    s = _session()
    store = Store(s)
    derive_db(a.concepts_dir, a.domain_pack, store, roots)
    return store


def cmd_concept_tree(a) -> int:
    return _emit(_derive_into_session(a).concept_tree(a.domain_pack))


def cmd_concept_list(a) -> int:
    store = _derive_into_session(a)
    return _emit([{"id": c.id, "importance": c.importance, "confidence": c.confidence,
                   "doc_only": c.doc_only, "parent_id": c.parent_id}
                  for c in store.list_concepts(a.domain_pack)])
```

(c) 在 `build_parser()` 里(其它 `sub.add_parser` 附近,`setup` 之前)加:

```python
    for name, fn in (("concept-tree", cmd_concept_tree), ("concept-list", cmd_concept_list)):
        cp = sub.add_parser(name)
        cp.add_argument("--domain-pack", default="cowboy")
        cp.add_argument("--concepts-dir", required=True)
        cp.add_argument("--repo-root", action="append", default=[],
                        help="repo=abs_path (可多次); anchor 校验用")
        cp.set_defaults(func=fn)
```

- [ ] **Step 4: 运行验证通过**

Run: `pytest tests/test_concept_cli.py -v`
Expected: PASS(2 passed)。

- [ ] **Step 5: Commit**

```bash
git add src/marshal_core/cli.py tests/test_concept_cli.py
git commit -m "concept: add concept-tree/concept-list CLI commands"
```

---

## Task 8: fake-pack 领域无关护栏

**Files:**
- Modify: `tests/test_fake_pack.py`

- [ ] **Step 1: 写失败测试(用假概念页证核心派生不依赖 cowboy 概念)**

追加到 `tests/test_fake_pack.py`:

```python
def test_concept_derive_is_domain_agnostic(db_session, tmp_path):
    """通用性护栏: 概念派生对任意 domain_pack 都跑通, 不含 cowboy 语义。"""
    from marshal_core.concept.sync import derive_db

    concepts = tmp_path / "concepts"
    concepts.mkdir()
    (concepts / "widget.md").write_text(
        "---\ntype: concept\nconcept_id: widget\nimportance: high\n"
        "status: draft\nlast_updated: 2026-07-25\n---\na widget.\n"
    )
    (concepts / "gadget.md").write_text(
        "---\ntype: concept\nconcept_id: gadget\nparent: widget\nimportance: low\n"
        "status: draft\nlast_updated: 2026-07-25\n---\na gadget.\n"
    )
    store = Store(db_session)
    n = derive_db(concepts, "fake", store, {})
    assert n == 2
    tree = store.concept_tree("fake")
    assert tree[0]["id"] == "widget"
    assert tree[0]["children"][0]["id"] == "gadget"
    assert tree[0]["children"][0]["doc_only"] is True    # 无 anchor → doc_only (H1)
```

- [ ] **Step 2: 运行验证通过**

Run: `pytest tests/test_fake_pack.py -v`
Expected: PASS(全部,含新增)。

- [ ] **Step 3: 全量回归**

Run: `pytest -q && ruff check src tests`
Expected: 全绿,无 lint 报错。

- [ ] **Step 4: Commit**

```bash
git add tests/test_fake_pack.py
git commit -m "concept: fake-pack guard proves derive is domain-agnostic"
```

---

## Task 9: S0 验收 run(人审门,非单元测试)

> 这是**人参与的验收门**,不是自动断言。它坐实上游方案的 S0 判据(§8)与深审 H1 / D9。产出记进 `docs/plans/` 或一次 `gate-record`,量化门槛不达标则回到相应 Task 调优,**不放宽门槛**。

- [ ] **Step 1: 种子导入(一次性,含 M1 修正)**

手动:把 `refs/wiki/concepts/*.md` + `refs/wiki/entities/*.md`(27 页)蒸馏进 `src/marshal_pack_cowboy/concepts/`,**并把 `refs/analysis/2026-04-15_documentation_amendments.md` 的漂移条目吸收进对应概念页 / 一个 `concepts/drift.md`**(M1:否则丢漂移 provenance)。给每页补 `parent`/`importance`/`anchors`(anchors 指真实符号)。

验收:`ls src/marshal_pack_cowboy/concepts/*.md | wc -l` ≥ 27;每页 frontmatter 过 `parse_concept_page`(写个一次性脚本遍历,全部无异常)。

- [ ] **Step 2: 对 `node/` 建树 + 人审接受率**

Run: `python -m marshal_core.cli concept-tree --domain-pack cowboy --concepts-dir src/marshal_pack_cowboy/concepts --repo-root node=/home/ubuntu/workspace/node`

人审输出树:概念/父子/重要性抽查。**门槛(§8 S0):人审接受率 ≥ 70%**;不接受项回 Task 1 种子或 Task 5 锚定调。

> **深审修正 Q②(接受率门须有独立性,防自评放水):** 接受率**不得由种子作者自评** —— 同一人写概念又判接受, 门槛会被无意识放宽。硬性:①由**第二人**评, 或②对树**盲抽样**(随机抽 N 个节点, 逐个判"概念/父子/重要性是否正确", 抽样比例与被判错项**记进验收记录**, 不静默)。接受率是**抽样统计值**, 不是"我觉得差不多"。

- [ ] **Step 3: H1 代码锚定覆盖率(注意:这是"代码定义率", 不代表"无挂羊头")**

统计 `concept-list` 输出里 `doc_only=false` 的比例。**门槛:constitutional/high 概念的 `doc_only=false` 覆盖率 ≥ 80%**(高重要性概念必须有代码定义锚定)。未达标 → 回 Task 1 补 anchors。

> **深审修正 H1-weak(此门衡量的是弱代理, 别误读):** `doc_only=false` 现在= "anchor 符号在文件里被**定义**"(Task 5 已从"任意出现"收紧为定义位)。但它**仍不判语义名副其实** —— 一个挂羊头 `struct GasReport{pixel}` 也会让门变绿。故:①本门**只**保证"高重要性概念确实指向了真实代码定义", **不**保证无挂羊头(那是 S4 concept-consistency lens);②验收记录必须写明这层边界, **禁止**把"锚定率 80%"表述成"概念语义已验证";③抽查 Step 2 时对高重要性概念**顺带人眼扫一遍语义是否名副其实**(S4 未上线前的临时人肉兜底)。

- [ ] **Step 4: D9 零 refs 依赖验证**

把 refs 暂时移开验证自持:

```bash
mv /home/ubuntu/workspace/refs /home/ubuntu/workspace/refs.hidden
python -m marshal_core.cli concept-tree --domain-pack cowboy \
  --concepts-dir src/marshal_pack_cowboy/concepts --repo-root node=/home/ubuntu/workspace/node
mv /home/ubuntu/workspace/refs.hidden /home/ubuntu/workspace/refs
```

**门槛:refs 缺席时 `concept-tree` 仍正常输出**(证明零 refs 运行时依赖,D9)。

- [ ] **Step 5: 记录验收结果**

Run: `python -m marshal_core.cli gate-record --change-ref "s0-concept-registry-acceptance" --verdict pass`
(仅当 Step 2–4 三个门槛全达标;任一未达 → 记 `escalate` 并回对应 Task。)

- [ ] **Step 6: 进实现前的纪律**

本 plan 进实现前 **先过 `/marshal` 深审**(团队纪律 [[feedback_all_plans_deep_review]]),重点审:Task 5/6 的测试是否真验证 H1/M2(而非 sim≠prod 的假绿)、Task 9 门槛是否可被"调宽"绕过。

---

## Self-Review(规格覆盖核对)

| 上游 S0 判据 / 深审项 | 对应 Task |
|---|---|
| 概念存储落 `marshal_pack_cowboy/concepts/`(自有) | Task 1 |
| frontmatter 加 `parent`/`importance`/`depends_on` | Task 1、Task 2 |
| frontmatter→DB 派生同步器 | Task 6(`derive_db`) |
| 4 张缓存表 | Task 3 |
| `cli concept-list/tree` | Task 7 |
| `fake-pack` 证核心不含 cowboy 概念 | Task 8 |
| **H1 概念锚定=代码验证** | Task 5(`verify_anchors`)+ Task 9 Step 3 门槛 |
| **M2 单向派生(非双写)** | Task 6 `test_db_is_not_a_truth_source...` |
| **M1 种子含 refs/analysis 修正案** | Task 9 Step 1 |
| **D9 零 refs 依赖** | Task 9 Step 4 |
| 一次性导入 27 页后自持 | Task 9 Step 1 + Step 4 |

**未覆盖(明确留后续 slice,非本 plan 缺口):** `ConceptChange` 的 redefine/move/merge 全谱(S0 只 add)、concept-consistency 挂羊头 lens(S4)、plan-cost 概念预算(S2)、可视化(S5)、H2 概念变更分级人审(需 PR-gate 接线,S4)。

---

## 深审修正记录(Marshal gate run 750)

深审方式:scratch 复制 marshal 源码 + 套用本 plan 全部改动,**真跑** 9 个计划测试(9/9 通过)+ 对抗反证。

| # | 严重性 | 发现(已执行证实) | 修正 |
|---|---|---|---|
| **H1-weak** | HIGH | `verify_anchors` 只查符号"出现" → `// TODO GasReport`(没实现)与 `struct GasReport{pixel}`(挂羊头)都被判 `verified=0.85`;H1 守栏沦为文本存在检查, Task 9 Step 3 门可绿着却漏 | Task 5:收紧为**定义位**匹配(`_symbol_defined`)+ 边界写清"不判语义";Task 5 加 comment-only / 挂羊头边界两测;Task 9 Step 3 措辞校正 + 人肉语义兜底 |
| **C** | MED | anchor 缺字段 → `parse_concept_page` 抛 `KeyError` 而 `derive_db` 只 catch `ValueError` → 一页 typo 崩掉整批 27 页种子 | Task 2:改抛 `ValueError` + 新增 `NotAConceptPage` 区分"非概念页 vs 格式错";Task 6:derive 两级 catch,坏页收集+stderr 告警不崩批;两处各加回归测试 |
| **Q②** | MED | Task 9 接受率门自评、代码锚定门因 H1-weak 可廉价满足 → 两门均软/可绕 | Task 9 Step 2:接受率须第二人/盲抽样, 记抽样比例与错项;Step 3:写明"锚定率≠无挂羊头" |

**已清除的伪 concern(实测,非发现):**
- parser 对真实 refs 概念页 body 内多个 `---` 水平线**稳**(`split(maxsplit=2)` 保留全 body,不截断)。
- M2 测试 `test_db_is_not_a_truth_source` **非假绿**:实测塞 DB-only ghost、再派生后被抹掉,坐实"DB 只读镜像"。唯一保留:证的是函数不是系统纪律(S2+ 接 plan-gate 时留意别读陈旧 DB)。

**残留、留后续裁的边界(非本 plan 阻塞):**
- `_symbol_defined` 是**定义位启发式**(正则匹配 `struct|fn|const|def|class…` + 符号),非真解析;`impl X for Sym` 这类不含独立定义的写法可能漏判 → 未来接 rust-analyzer/LSP 精确化(上游方案 M6 已列)。本期够用:排除注释/调用/单纯提及即达 H1 目的。
- 语义"挂羊头"检测**不在 S0**(S4 concept-consistency lens);S0 靠 Task 9 Step 2 人眼兜底。

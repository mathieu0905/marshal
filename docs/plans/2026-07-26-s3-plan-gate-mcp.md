# S3 · Plan Gate MCP 封装 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 S2 的确定性概念预算(`plan-cost`)封成一个 **MCP tool** `marshal_plan_review`,让 Codex / Claude Code / Opencode 等**任意** agent 都能"每次 plan 完让 Marshal 过一下"拿到中性成本画像——不止 Claude Code 的 `/plan-cost` skill。

**Architecture:** 沿用铁律——`marshal_core` 确定性,AI 判断由 agent 编排。这里的关键:**MCP tool 是薄 wrapper,plan→touches 的映射由调用方 agent(它本身就是 LLM)按工具描述完成**;tool 只跑确定性 `concept_budget`(隔离内存 DB derive)。即"薄核 + agent 大脑",此处大脑=调用方 agent。为此把 S2 `cmd_plan_cost` 的核心抽成共享 `plangate.service.plan_review`,CLI 与 MCP 同一入口(避免 F1 那种"两份实现各自漂移")。

**Tech Stack:** Python 3.11 · 官方 `mcp` SDK(FastMCP,新增 optional dep)· 复用 S2 `concept_budget` + S0 `derive_db` + 隔离内存 DB(S2-A/F1 模式)。**不新增 LLM 依赖**(映射是调用方 agent 的事)。

**上游依据:** [`2026-07-24-marshal-three-gates-concept-registry.zh.md`](2026-07-24-marshal-three-gates-concept-registry.zh.md) §5.3、§8 S3("plan gate=MCP;工具描述=每次 plan 完让 marshal 过一下;输出成本;不建议做不做");依赖 **S0/S1/S2**(全 merged 进 main,PR#18/#19/#20)。

**关键 grounding(已核实):** workspace 无现成 Python MCP server 可参照(`cowpilot/` 空、runner 是 Rust MCP client);marshal 无 `mcp` 依赖。S3 引入 marshal 第一个 MCP server,用官方 `mcp` SDK 的 `FastMCP`。`concept_budget` 只用 anchor 的 repo(`list_anchors`,不看 verified)+ 树 scope,**不看 doc_only**,故 MCP tool 的 `repo_roots` 可选(缺失不影响预算,只影响锚定标记)。

**真 repo 预验证(起草时已做):** `plan_review` service + MCP server 已在 scratch(基于当前 main)原型化并跑过——**6 单元测试绿**(service 4:中性预算/repo_roots 可选/bad-dir raise/不 mutate 共享 DB;MCP 2:工具注册+中性描述/调用返回 cost-only),ruff clean。**并证掉一个 sim≠prod 风险**:装了官方 `mcp` SDK 探测 FastMCP 真实 API——`mcp._tool_manager.list_tools()` 返回带 `.name`/`.description`(=docstring)的 list,**Task 3 测试的注册查询假设正确**,不是我臆想的 API。

**范围边界(YAGNI):** 本 slice **只做** MCP wrapper + 共享 service 抽取 + 接入验收。**不做**:plan 文本→touches 的自动映射(那是调用方 agent 的判断,工具描述引导)、把 est_impl_days 塞进 MCP(agent 估算,不在确定性 tool)、多 tool 的 MCP server(只 `marshal_plan_review` 一个)、鉴权/多租户(S3 是本地 stdio MCP)。

---

## 文件结构

| 文件 | 责任 | 动作 |
|---|---|---|
| `src/marshal_core/plangate/service.py` | `plan_review(concepts_dir, repo_roots, domain_pack, touches)` — 共享确定性核心(路径校验 + 隔离 derive + budget) | Create |
| `src/marshal_core/cli.py` | `cmd_plan_cost` 改调 `plan_review`(DRY,消除第二份隔离实现) | Modify |
| `src/marshal_core/mcp_server.py` | FastMCP server:注册 `marshal_plan_review` tool → `plan_review`;`python -m marshal_core.mcp_server` 启动 | Create |
| `pyproject.toml` | 加 `mcp` optional dep(`[mcp]` extra) | Modify |
| `tests/test_plan_review_service.py` | service 核心测试 | Create |
| `tests/test_mcp_server.py` | MCP tool 注册/描述测试(importorskip mcp) | Create |
| `.claude/skills/plan-cost/SKILL.md` | 补一句:MCP 形态可供非 Claude-Code agent 用 | Modify |

**约定:** ruff line-length=100;`db_session`/tmp_path;每 Task 末 commit;commit message **无 AI 署名**。

---

## Task 1: 共享 service `plan_review`(确定性核心)

**Files:**
- Create: `src/marshal_core/plangate/service.py`
- Test: `tests/test_plan_review_service.py`

> 把 S2 `cmd_plan_cost` 的核心(路径校验 + 隔离内存 DB derive + `concept_budget`)抽成不依赖 argparse/CLI 的函数,CLI 与 MCP 共用。**隔离内存 DB**(F1/S2-A):只读查询绝不 mutate 共享缓存。

- [ ] **Step 1: 写失败测试**

Create `tests/test_plan_review_service.py`:

```python
import os

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
```

- [ ] **Step 2: 运行验证失败**

Run: `/home/ubuntu/workspace/marshal/.venv/bin/python -m pytest tests/test_plan_review_service.py -v`
Expected: FAIL(`ModuleNotFoundError: marshal_core.plangate.service`)。

- [ ] **Step 3: 实现 service**

Create `src/marshal_core/plangate/service.py`:

```python
"""Plan-gate 确定性核心 —— CLI 与 MCP 共享的单一入口(避免 F1 那种多份隔离实现漂移)。
路径校验 + 隔离内存 DB derive + concept_budget。只读查询, 绝不 mutate 共享 marshal.db。"""
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ..knowledge.models import Base
from ..knowledge.store import Store
from ..concept.sync import derive_db
from .budget import concept_budget


def plan_review(concepts_dir: str, repo_roots: dict[str, str],
                domain_pack: str, touches: list[dict]) -> dict:
    """给定概念页目录 + 触及集, 返回中性概念预算(cost-only)。
    repo_roots 可选(budget 用 anchor 的 repo, 不看 verified/doc_only)。路径 typo → ValueError。"""
    if not Path(concepts_dir).is_dir():
        raise ValueError(f"--concepts-dir not a directory: {concepts_dir}")
    for repo, path in (repo_roots or {}).items():
        if not Path(path).is_dir():
            raise ValueError(f"repo-root path not a directory: {repo}={path}")

    # 隔离内存 DB: 只读查询绝不碰共享缓存(F1/S2-A)
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    try:
        store = Store(s)
        derive_db(concepts_dir, domain_pack, store, repo_roots or {})
        return concept_budget(store, domain_pack, touches)
    finally:
        s.close()
```

- [ ] **Step 4: 运行验证通过**

Run: `pytest tests/test_plan_review_service.py -v`
Expected: PASS(4 passed)。

- [ ] **Step 5: Commit**

```bash
git add src/marshal_core/plangate/service.py tests/test_plan_review_service.py
git commit -m "plangate: extract shared plan_review service (CLI + MCP single entry)"
```

---

## Task 2: CLI `cmd_plan_cost` 改用 service(DRY)

**Files:**
- Modify: `src/marshal_core/cli.py`
- Test: `tests/test_plan_cost_cli.py`(现有,应仍全绿)

> 让 CLI 与 MCP 走同一条 `plan_review`,消除第二份隔离-derive 实现(正是 F1 教训:别让同一逻辑多份漂移)。

- [ ] **Step 1: 改 `cmd_plan_cost`**

Modify `src/marshal_core/cli.py`:

(a) 文件头 import 区:**把 S2 的 `concept_budget` import 换成 `plan_review`**(不是并存!)——
`concept_budget` 此后只被 `plan_review` 内部用,cli.py 里若留着它就变**未用 import → ruff F401 会红**
(深审 A 实测确认):

```python
# 删除这行(cmd_plan_cost 不再直接用 concept_budget, 移进了 service):
# from marshal_core.plangate.budget import concept_budget
# 改成:
from marshal_core.plangate.service import plan_review
```

> 自检:`grep concept_budget src/marshal_core/cli.py` 应无残留;其余 import(`derive_db`/`Store`/
> `create_engine`/`sessionmaker`/`Base`/`_require_derive_paths`/`_parse_repo_roots`)仍被
> `_readonly_derive_store` 等命令使用, **不要删**。

(b) 把 `cmd_plan_cost` 整体替换为:

```python
def cmd_plan_cost(a) -> int:
    if not Path(a.touches).is_file():
        return _fail(f"--touches not a file: {a.touches}")
    with open(a.touches, encoding="utf-8") as f:
        touches = json.load(f)
    return _emit(plan_review(a.concepts_dir, _parse_repo_roots(a.repo_root),
                             a.domain_pack, touches))
```

(注:`plan_review` 内部已做 concepts-dir/repo-root 路径校验并 raise ValueError,`main()` 的 `except → _fail` 会把它转成非零退出;与原 `_require_derive_paths` 行为一致。)

- [ ] **Step 2: 运行现有 CLI 测试(应仍全绿)**

Run: `pytest tests/test_plan_cost_cli.py -v`
Expected: PASS(所有原测试:cost-only 输出、bad-touches 非零、bad-repo-root 非零、不 mutate 共享 DB)。

> 若 `test_plan_cost_bad_repo_root_fails` 因错误信息措辞变化而红:`plan_review` 抛的是 `repo-root path not a directory`(无 `--` 前缀),原测试只断言 `rc != 0`,不断言文案 → 应仍绿。若断言了文案,更新为不带 `--` 的措辞。

- [ ] **Step 3: 全量回归 + lint**

Run: `pytest -q && ruff check src tests`
Expected: 全绿(除 2 个 pre-existing `marshal_core/checks/` node-drift 失败),lint 干净。

- [ ] **Step 4: Commit**

```bash
git add src/marshal_core/cli.py
git commit -m "plangate: route cmd_plan_cost through shared plan_review service (DRY)"
```

---

## Task 3: MCP server `marshal_plan_review`

**Files:**
- Modify: `pyproject.toml`(加 mcp 依赖)
- Create: `src/marshal_core/mcp_server.py`
- Test: `tests/test_mcp_server.py`

- [ ] **Step 1: 加 mcp 依赖**

Modify `pyproject.toml` — 在 `[project.optional-dependencies]` 加一行(与 `ci = [...]` 同级):

```toml
mcp = ["mcp>=1.2"]
```

Run: `/home/ubuntu/workspace/marshal/.venv/bin/pip install -e ".[mcp]"`
Expected: 安装成功;`python -c "from mcp.server.fastmcp import FastMCP"` 无错。

- [ ] **Step 2: 写失败测试(importorskip;测工具注册 + 中性描述)**

Create `tests/test_mcp_server.py`:

```python
import pytest

pytest.importorskip("mcp")   # 无 mcp SDK 时跳过(与 zizmor/ci 降级同纪律)


def test_tool_registered_and_neutral():
    from marshal_core import mcp_server
    # 工具已注册, 名字对
    tools = {t.name for t in mcp_server.mcp._tool_manager.list_tools()}
    assert "marshal_plan_review" in tools
    # 描述必须中性: 不含 go/no-go 措辞
    desc = next(t.description for t in mcp_server.mcp._tool_manager.list_tools()
                if t.name == "marshal_plan_review").lower()
    for banned in ("should you", "recommend", "advise", "do it", "don't do"):
        assert banned not in desc


def test_tool_call_returns_cost_only(tmp_path):
    from marshal_core.mcp_server import marshal_plan_review
    concepts = tmp_path / "concepts"
    concepts.mkdir()
    (concepts / "gas.md").write_text(
        '---\ntype: concept\nconcept_id: gas\nimportance: constitutional\n'
        'status: authoritative\nlast_updated: 2026-07-26\n---\ngas\n')
    out = marshal_plan_review(concepts_dir=str(concepts), domain_pack="probe",
                              touches=[{"concept_id": "gas", "op": "redefine"}])
    assert out["verdict"] == "cost-only"
```

- [ ] **Step 3: 运行验证失败**

Run: `pytest tests/test_mcp_server.py -v`
Expected: FAIL(`ModuleNotFoundError: marshal_core.mcp_server`)。

- [ ] **Step 4: 实现 MCP server**

Create `src/marshal_core/mcp_server.py`:

```python
"""Marshal Plan-Gate MCP server —— 把确定性概念预算暴露为一个 MCP tool, 供任意 agent
(Codex / Claude Code / Opencode) "每次 plan 完让 Marshal 过一下"。

薄 wrapper: plan→touches 的映射是**调用方 agent** 的判断(见 tool 描述), 本 tool 只跑
确定性 concept_budget。中性: 只报成本, 绝不建议做/不做。
"""
from mcp.server.fastmcp import FastMCP

from marshal_core.plangate.service import plan_review

mcp = FastMCP("marshal-plan-gate")


@mcp.tool()
def marshal_plan_review(concepts_dir: str, domain_pack: str, touches: list[dict],
                        repo_roots: dict[str, str] | None = None) -> dict:
    """Run a NEUTRAL concept-budget cost review of a plan before you implement it.

    First map your plan to concept `touches`: a list of
    {concept_id, op:"add"|"redefine", importance?, est_scope?:"small"|"medium"|"large"}.
    Use "redefine" for existing concepts, "add" for new ones (give importance + est_scope).
    Then call this. Returns a cost picture:
      - weighted_concept_cost: a UNITLESS relative weight (grounded_cost + hinted_cost),
        NOT hours/days — use it to compare plans, not to quote a schedule.
      - grounded_cost (redefine, computed from the real concept tree — cannot be gamed)
      - hinted_cost   (add, from YOUR est_scope hints — cross-check they are honest)
      - blast_radius  (concepts transitively affected), impacted_repos, highest_tier_touched
      - unknown_redefines / unknown_ops (surfaced, never silent)

    Marshal only puts the cost on the table. It NEVER tells you whether to do the work —
    that is your call against your own budget.
    """
    return plan_review(concepts_dir, repo_roots or {}, domain_pack, touches)


def main() -> None:
    mcp.run()   # stdio transport


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: 运行验证通过**

Run: `pytest tests/test_mcp_server.py -v`
Expected: PASS(2 passed;若本机无 mcp 则 skipped —— 那就先 `pip install -e ".[mcp]"`)。

> 注:`mcp._tool_manager.list_tools()` 已在起草时对**装好的 `mcp` SDK** 实测确认可用(返回带 `.name`/`.description` 的 list,`.description`=docstring)。若将来 SDK 大版本改了该内部结构,改用其实际注册查询 API,测试意图不变(工具名 + 中性描述)。

- [ ] **Step 6: 全量回归 + lint**

Run: `pytest -q && ruff check src tests`
Expected: 全绿(除 2 pre-existing),lint 干净。

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml src/marshal_core/mcp_server.py tests/test_mcp_server.py
git commit -m "plangate: add marshal_plan_review MCP tool (neutral cost review for any agent)"
```

---

## Task 4: skill 补注 + 接入验收(人审门,非单元测试)

**Files:**
- Modify: `.claude/skills/plan-cost/SKILL.md`

- [ ] **Step 1: skill 补一句 MCP 形态**

Modify `.claude/skills/plan-cost/SKILL.md` — 在文首 description 之后加一段:

```markdown
> **MCP 形态(S3):** 同一确定性预算也暴露为 MCP tool `marshal_plan_review`
> (`python -m marshal_core.mcp_server`),供 Codex / Opencode 等**非 Claude-Code** agent
> 直接调用。Claude Code 里用本 skill(CLI)或 MCP tool 均可, 二者走同一 `plan_review` 核心。
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/plan-cost/SKILL.md
git commit -m "plangate: note MCP form in /plan-cost skill"
```

- [ ] **Step 3: 接入验收(人审门,§8 S3)**

手动:
1. 把 MCP server 接进一个 agent 客户端(Claude Code 的 `.mcp.json` 或 Codex config):
   ```json
   {"mcpServers": {"marshal-plan-gate": {"command": "/home/ubuntu/workspace/marshal/.venv/bin/python",
     "args": ["-m", "marshal_core.mcp_server"]}}}
   ```
2. 在该 agent 里对一份真实 plan 触发 `marshal_plan_review`,确认:①能拿到 `cost-only` 预算;②输出**从不含** go/no-go;③grounded/hinted 分开呈现。
3. **门槛(§8 S3):** "plan 完自动过 Marshal" 在至少一个非-Claude-Code agent(Codex/Opencode)里跑通;给"想法多"的队友(Logan/Caleb/Martin/chad)试用,收 **≥3 条反馈**(§5.3 说话人2:先小工具收反馈)。
4. `python -m marshal_core.cli gate-record --change-ref "s3-mcp-acceptance" --verdict pass`(达标后)。

- [ ] **Step 4: 进实现前的纪律**

本 plan 进实现前 **先过 `/marshal` 深审**([[feedback_all_plans_deep_review]]),重点审:①MCP tool 描述是否真中性(无 go/no-go);②`plan_review` service 抽取后 CLI 行为无回归(bad-path/isolation 仍成立);③mcp SDK 的工具注册查询 API 是否与测试假设一致(sim≠prod:测试写法要匹配真实 SDK)。

---

## Self-Review(规格覆盖核对)

| 上游 S3 判据 / 架构项 | 对应 Task |
|---|---|
| MCP tool `marshal_plan_review`(§8 S3) | Task 3 |
| 工具描述="每次 plan 完让 marshal 过一下 + 输出成本 + 不建议做不做"(§5.3) | Task 3 tool docstring(中性)+ Task 3 测试断言无 go/no-go |
| 供**非 Claude-Code** agent(Codex/Opencode)用 | Task 3(stdio MCP)+ Task 4 接入验收 |
| **薄核 + agent 大脑**(映射由调用方 agent) | Task 3 tool 描述引导调用方产 touches;core 只跑 budget |
| CLI 与 MCP 单一入口(反 F1 漂移) | Task 1 `plan_review` service + Task 2 CLI 改道 |
| **只读隔离 DB**(F1/S2-A) | Task 1 service 内隔离 + `test_plan_review_does_not_mutate_shared_db` |
| 中性(cost-only) | Task 1/3 复用 S2 `concept_budget` verdict + Task 3 描述测试 |

**架构决定(记录):** MCP tool 取 **结构化 `touches`**(非 raw plan 文本)—— 因为 plan→touches 的映射需要 LLM 判断,而 marshal 核无 LLM;调用方 agent 本身是 LLM,按工具描述产出 touches。这与 marshal "薄核 + agent 大脑" 一致,只是把"大脑"从 Claude-Code skill 换成任意 MCP 调用方。

**未覆盖(留后续):** raw plan 文本→touches 自动映射(调用方 agent 的事)、est_impl_days(agent 估算, 不进确定性 tool)、多 tool MCP server、鉴权/远程 MCP(S3 是本地 stdio)、MCP tool 的端到端协议测试(靠 Task 4 人工接入验收, 非单元)。

---

## 深审修正记录(Marshal 深审,审法=对真实代码执行 + 对抗反证)

| # | 严重性 | 发现(已执行证实) | 修正 |
|---|---|---|---|
| **起草预验证** | — | service+MCP 6 测试绿;装 mcp SDK 证实 `FastMCP._tool_manager.list_tools()` API 正确(非臆想) | 已并入头部预验证 |
| **A** | MED | Task 2 改用 `plan_review` 后, `concept_budget` import 只被它用过 → **变未用 import → ruff F401**, Task2 的 ruff-clean 门会红。plan 原稿只说"加 plan_review import", 没说删 concept_budget | Task 2 改为**换掉**(删 concept_budget import + 加 plan_review), 加 grep 自检。**实测: 换掉后 ruff clean, S2 plan_cost 测试 4/4 不回归** |
| **B**〔清除〕 | — | 担心 MCP 对 `list[dict]`/`dict\|None` 生成的 inputSchema 无效(我起草只测了函数层, 没测协议层 schema) | **实测排除**: FastMCP 生成有效 schema(touches→array of object、repo_roots→anyOf object/null、required=[concepts_dir,domain_pack,touches]), 真 client 可调 |
| **C** | Minor | tool 描述没说 `weighted_concept_cost` 是无单位相对权重 → 调用方 agent 可能把 cost=72 读成 "72 天" | Task 3 tool docstring 加 "UNITLESS relative weight, NOT hours/days" |

**结论:** S3 plan 确定性核心 + MCP wrapper 已执行验证(6+ 测试绿), mcp SDK API 与 inputSchema 均实测确认(非臆想)。A(ruff F401)已修+实测, C 描述澄清已加。**唯一 MED 是 A, 已闭合。可进实现。** 端到端 MCP 协议接入仍靠 Task 4 人审门(非-Claude-Code agent 接入 + 队友 ≥3 反馈)。

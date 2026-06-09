# Marshal 消费侧 Plugin 分发设计 (异机团队 · 只读单向)

> **定位:** 让**异机的团队成员**也能用上 marshal —— 把 marshal 的**消费侧**(跑门禁的认知闭环)打成一个 Claude Code **plugin**,用 marshal 仓库自身当**内部 marketplace**,通过 GitHub 单向分发。维护侧(本机全量 skill + 全量 `marshal.db`)保持不动;本设计是给队友的**并行产物**,纯增量,不改现有 `src/` 与单人 skill。
>
> **源文档:** [`docs/superpowers/specs/2026-06-01-marshal-skill-design.md`](2026-06-01-marshal-skill-design.md) · [`refs/plans/2026-06-01_marshal-quality-platform-architecture.md`](../../../../refs/plans/2026-06-01_marshal-quality-platform-architecture.md)
>
> **状态:** 设计待实现。对应平台架构 D3(混合中枢 + 适配器,本期只做 GitHub 分发)/ D4(团队优先)。**本设计明确不建中央大脑**(那是方案 ③);只读单向分发是其前置的、低成本的一步。
>
> **日期:** 2026-06-09

---

## 0. 目标与边界

**目标:** 异机队友执行 `/plugin install marshal` 后,无需 clone 本仓库、无需手动建 venv,即可在自己机器上跑 `/marshal`、`/marshal <repo> <PR#>` 的完整门禁流程,读到与维护侧一致的一套不变量/逃逸快照。

**三个已敲定的设计决策(brainstorming 收敛):**

| # | 决策点 | 选择 | 含义 |
|---|---|---|---|
| D1 | 部署拓扑 | **异机** | 队友各自独立机器,无本仓库 / venv / db,bootstrap 与状态同步必须正面解决。 |
| D2 | 使用模型 | **A · 只读消费,单向分发** | 队友只跑门禁(读不变量、对抗 review、出 GateDecision);不变量/棘轮真相源唯一(维护侧),plugin 捎带**快照**,`/plugin update` 才更新。 |
| D3 | CLI bootstrap | **A · uv 托管临时环境** | plugin 捎带消费侧包 + `pyproject.toml`;skill 经 `uv run` 让 uv 按 pyproject 懒解析 sqlalchemy+pydantic 并缓存。**核心代码零改动**,队友一次性装 `uv`。 |

**明确不做(诚实边界):**
- **棘轮不回流。** 队友本地 `ratchet-open/close` 只落其本地 db,不回团队真相源;新不变量仍由维护侧统一发版。要双向同步 → 回到平台方案 ③(中央大脑),不在本设计内。
- **服务端不进 plugin。** `adapters/api.py`、`executor/reporter.py`(fastapi/uvicorn/httpx 那套)只服务于未来常驻服务,plugin 只带消费侧。
- **维护侧不改。** `/home/ubuntu/.claude/skills/marshal` 软链与根 `marshal.db` 保持现状。

---

## 1. 总体架构与分发拓扑

三类角色,GitHub 即分发渠道,零额外服务器基建:

```
  维护侧 (本机, 唯一真相源)                   异机队友 (只读消费)
 ┌──────────────────────────┐              ┌──────────────────────────────┐
 │ 写不变量 / 跑棘轮          │  git push    │ /plugin marketplace add        │
 │ 导出 marshal.snapshot.db  │ ───────────► │   shawhanken/marshal           │
 │ bump plugin.json version  │  (GitHub)    │ /plugin install marshal        │
 │ git push / tag            │              │ /plugin update  ← 拿新快照      │
 └──────────────────────────┘              └───────────────┬──────────────┘
                                                          │ 装好后本地
                                                 ┌────────▼──────────┐
                                                 │ /marshal 跑门禁    │
                                                 │ uv run CLI (只读)  │
                                                 └───────────────────┘
```

- **单向**:维护侧是唯一不变量/棘轮真相源;plugin 内捎带 `marshal.snapshot.db`;队友 `/plugin update` 才刷新。
- **托管**:`.claude-plugin/marketplace.json` 放 marshal repo 根,marketplace 即本仓库,GitHub 负责分发与版本。

---

## 2. Plugin 内容布局

在 marshal repo 新增以下内容(纯增量;现有 `src/`、`.claude/skills/marshal`、根 `marshal.db` 不动):

```
marshal/
├── .claude-plugin/
│   └── marketplace.json          # 内部 marketplace,列 1 个 plugin: marshal
├── plugins/marshal/
│   ├── .claude-plugin/
│   │   └── plugin.json           # name / description / author / version
│   ├── skills/marshal/
│   │   ├── SKILL.md              # 消费侧改版:预检走 uv,路径走 $CLAUDE_PLUGIN_ROOT
│   │   └── references/           # 从现有 .claude/skills/marshal/references/ 同步
│   ├── pyproject.toml            # 供 uv run 解析依赖(只列消费侧需要的 sqlalchemy + pydantic)
│   ├── marshal_core/             # 捎带的消费侧包(由打包脚本从 src/ 同步)
│   ├── marshal_pack_cowboy/      # 领域包(同步自 src/)
│   └── data/marshal.snapshot.db  # 不变量/逃逸只读快照(发版时从根 marshal.db 导出)
└── scripts/build_plugin.py       # 打包脚本:同步包 + 导出快照 + 校验 uv run 跑通
```

**清单文件字段(对齐 Claude Code 现行格式):**
- `marketplace.json`:`name` / `description` / `owner` / `plugins[]`(每项 `name` / `description` / `author` / `source`)。
- `plugin.json`:`name` / `description` / `author` / `version`。

**消费侧 `pyproject.toml`** 只保留门禁所需依赖(`sqlalchemy>=2.0`、`pydantic>=2.6`),**剔除** fastapi/uvicorn/httpx(服务端专用),以缩小 uv 解析面。

---

## 3. CLI bootstrap + 数据流 + db 落地

### 3.1 Bootstrap(uv 托管,零手动 venv)

SKILL.md 预检改为绝对路径、与 cwd 无关:

```bash
ROOT="${CLAUDE_PLUGIN_ROOT}"          # Claude Code 为 plugin 注入,指向已装 plugin 目录
uv run --project "$ROOT" -m marshal_core.cli classify --repo node --paths README.md
```

- uv 首次按 `$ROOT/pyproject.toml` 解析并缓存环境,之后秒起。
- 失败(无 uv)→ 提示 `curl -LsSf https://astral.sh/uv/install.sh | sh` 后停止。
- **核心代码零改动**:`cli.py` 仍以 `marshal_core.cli` 模块入口被调用;只是解释器从写死的 `$MARSHAL_HOME/.venv/bin/python` 换成 `uv run`。

### 3.2 只读快照 vs 本地自写(db seed)

门禁流里命令分两类(核自 `src/marshal_core/cli.py`):

| 类别 | 命令 | 读/写 |
|---|---|---|
| 无 db | `classify` / `review-quorum` / `review-verify` / `spec-*` / `conformance` | 不碰 db(走 pack/review) |
| 只读 | `invariants` / `metrics` | 读 `invariant_registry` 等 |
| **本地自写** | `gate-record`(写 `gate_run`) / `ratchet-open` / `ratchet-close`(写 `escape_registry` 等) | 写 |

因此「纯只读 db」不成立——需区分**上游权威只读数据**与**队友本地自写数据**。又因 plugin 目录会被 `/plugin update` 覆盖,不能就地写。落地为「seed 进用户可写 db」:

1. **真相源**:快照 `data/marshal.snapshot.db` 的 `invariant_registry` + `escape_registry`(上游权威)。
2. **落地**:首次 / 快照版本变化时,把这两张权威表 seed 进**用户可写 db** `${XDG_DATA_HOME:-~/.local/share}/marshal/marshal.db`;`MARSHAL_DB` 指向它。
3. **本地自写**:`gate_run` / `audit_log` 写进同一可写 db,seed 时**保留不清**;队友本地棘轮也只落这里(不回流)。

**唯一新增命令** `cli seed --snapshot <path> --version <v>`(幂等):
- 确保 schema(复用现有 `Base.metadata.create_all`)。
- 读可写 db 里的版本标记;若 == `<v>` 则直接返回(no-op)。
- 若 != `<v>`:**仅替换** `invariant_registry` + `escape_registry` 两表内容,写入新版本标记,**不动** `gate_run` / `audit_log`。

SKILL.md 预检每会话调一次 `seed`(廉价幂等)。`MARSHAL_DB` 由预检导出后,所有后续 `cli` 调用复用同一可写 db。

### 3.3 版本标记

复用知识核存一行 `meta(key='snapshot_version', value=<v>)`(或最小独立表);`<v>` 取自 `plugin.json` 的 `version`,由打包脚本写进快照,保证 plugin 升级 ↔ 快照刷新一一对应。

---

## 4. 安装 / 更新 / 发版

### 4.1 队友一次性安装

```
/plugin marketplace add shawhanken/marshal
/plugin install marshal            # 装 skill + 消费侧包 + 快照
# 一次性装 uv(若未装):curl -LsSf https://astral.sh/uv/install.sh | sh
```

之后 `/marshal`、`/marshal <repo> <PR#>` 等照常用。

### 4.2 更新

`/plugin update` 拉新 commit → 带来新 `marshal.snapshot.db` + 新 `plugin.json` version → 下次 `/marshal` 预检的 `seed` 检出版本变化,自动刷新权威两表,本地 `gate_run` 保留。

### 4.3 维护侧发版流程

1. 在本机改不变量 / 跑棘轮(照旧落根 `marshal.db`)。
2. 跑 `scripts/build_plugin.py`:从 `src/` 同步 `marshal_core` + `marshal_pack_cowboy` 到 `plugins/marshal/`;从根 `marshal.db` 导出权威两表为 `plugins/marshal/data/marshal.snapshot.db`;校验 `uv run -m marshal_core.cli classify` 跑通。
3. bump `plugins/marshal/.claude-plugin/plugin.json` 的 `version`(同步写进快照版本标记)。
4. `git push`(必要时 `git tag`)。

---

## 5. 测试 / 验收

1. **打包脚本测试**:`build_plugin.py` 同步产物可被 `uv run --project plugins/marshal -m marshal_core.cli classify ...` 跑通;快照只含权威两表、不含服务端表多余数据。
2. **seed 幂等性测试**:同版本重复 `seed` 为 no-op;版本 bump 后只换权威两表、`gate_run` 行数不变。
3. **干净房间验收**:在一个**不含 `/home/ubuntu/workspace`、仅有 git + uv** 的临时 HOME 中 `/plugin install` → 跑一次 `/marshal <PR#>` 全流程绿(证明异机零依赖可起)。
4. **回归**:现有 48 测试 + 新增 `cli seed` 测试全绿;Python 侧跑 `ruff`(无 Rust,不涉 `cargo fmt`)。

---

## 6. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 队友机器无 uv | 预检明确报错 + 一行安装指引;uv 安装无需 root,跨平台。 |
| `${CLAUDE_PLUGIN_ROOT}` 在某些 Claude Code 版本未注入 | 预检先校验该变量非空,缺失即报错并指明最低 Claude Code 版本要求。 |
| 快照与维护侧 db 漂移(忘记重新导出) | `build_plugin.py` 为发版唯一入口,把「同步包 + 导出快照 + bump version」绑成一步,杜绝手动遗漏。 |
| 队友误以为棘轮会共享 | SKILL.md 消费侧版在 `ratchet` 路由处显式提示「本地 only,不回流团队」。 |
| 消费侧 `pyproject` 依赖与 `src/` 漂移 | 打包脚本校验消费侧命令在精简依赖下确实可跑(CI 可挂同一校验)。 |

---

## 7. 与平台演进的关系

本设计是平台架构 §10 演进路线上**团队分发的最小一步**:不建中央大脑(③)、不接 CI 适配器(④),只用 plugin 把消费侧认知闭环单向铺给团队。它与未来的中央大脑**不冲突**——届时 SKILL.md 预检的数据源从「本地 seed 的快照 db」切到「brain-url HTTP」即可,plugin 外壳与 uv bootstrap 可整体复用。

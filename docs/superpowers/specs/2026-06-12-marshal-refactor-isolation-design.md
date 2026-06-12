# Marshal 重构隔离 + 金标语料回归 设计文档

- 日期:2026-06-12
- 状态:待评审
- 范围:工程基建/流程(不是产品功能);目标是让 marshal 能在不中断日常 gate 的前提下做重构级别升级

## 1. 背景与问题

本机的 marshal 同时是**生产工具**(每天 `/marshal` 审真实 PR 的质量门禁)和**开发对象**(要做重构级升级)。三处耦合让"边飞边修引擎"会直接打断日常 gate:

1. **Skill 入口单一且指向工作仓库**
   `~/.claude/skills/marshal` 是单个 symlink(`cli setup` 创建),
   `SKILL.md:14` 默认 `MARSHAL_HOME=${MARSHAL_HOME:-/home/ubuntu/workspace/marshal}`,
   `SKILL.md:15` `PY="$MARSHAL_HOME/.venv/bin/python"`。
   → `/marshal` 跑的就是工作仓库当前 checkout 的代码 + venv。
2. **Editable 安装**
   `pip install -e .`(`pyproject` `pythonpath=["src"]`),改 `src/marshal_core/**` 即时生效到 prod CLI。
3. **`marshal.db` 进版本库(TRACKED)**
   代码与状态共用同一 repo/分支;近期 commit 多为 `chore: update marshal.db binary`,分支切换会让 db 二进制冲突、串味。

利好现状:`MARSHAL_HOME` / `MARSHAL_DB` 两个 env 是天然总开关(`cli.py:23-33`),且"权威快照 vs 可变 db"已半成形——`cli seed` 从 `plugins/marshal/data/marshal.snapshot.db` 把 invariants/escapes 两张权威表 seed 进可写 db(`snapshot_version` 控幂等),本地 `gate_run` 另存。本设计顺势补全,不另起炉灶。

## 2. 目标 / 非目标

**目标**
- G1 重构全程,日常 `/marshal` 走一份**冻结的稳定版**,永不被半成品影响,且一条命令可回退。
- G2 重构在**隔离的 dev 环境**(独立分支/worktree + 独立 venv + 独立 db)进行,爆炸不波及 prod。
- G3 有**客观验收闸**:新版必须在一批历史判过的 PR 上**复现判决**才允许上位(行为不变的证据,而非"我觉得没问题")。
- G4 顺手解掉 db 进版本库 / `MARSHAL_DB` 写仓库根的老坑,且重构不丢 ratchet/escape 历史。

**非目标**
- 不在本设计里定义具体要怎么重构 core(模块拆分、DomainPack 解耦的内容)——那是被本基建保护的"载荷",另开 spec。
- 不改 gate 的判决语义作为目标;若重构顺带要改契约/db 格式,按 §6 的迁移流程走,但默认保持行为等价。

## 3. 方案总览

**方案 A(冻结稳定版 + dev worktree 双装)做底座 + 金标语料回归做验收闸。**

- A 保证 G1/G2:prod 与 dev 是两份独立的 home(各自 venv / db / skill 入口),靠 `MARSHAL_HOME`+`MARSHAL_DB` 切。
- 金标语料回归保证 G3:用稳定版录制一批 PR 的判决为 golden,新版必须复现才切。
- §6 的 db 解耦保证 G4。

弃用方案 B(单 venv + 分支切换):db 在版本库 + editable + 不确定时长 = 必串味,已在头脑风暴排除。

## 4. 隔离架构

两份完全独立的 marshal home,互不共享 venv / db / skill:

| 维度 | 稳定版(prod) | 开发版(dev) |
|------|----------------|---------------|
| 位置 | 新建独立 clone:`~/marshal-stable`(checkout 冻结 tag) | 现有 `workspace/marshal` 的 `refactor/*` 分支,或其 worktree `.../marshal--worktrees/refactor` |
| `MARSHAL_HOME` | `~/marshal-stable` | dev 仓库/worktree 根 |
| venv | `~/marshal-stable/.venv`(非 editable 或 pin 到 tag) | dev 根 `.venv`(editable,可带未稳定依赖) |
| `MARSHAL_DB` | `~/marshal-stable/marshal.db`(权威,稳定) | `marshal-dev.db`(gitignored,可随便重建) |
| Skill 入口 | `~/.claude/skills/marshal` → `~/marshal-stable/.claude/skills/marshal` | `~/.claude/skills/marshal-dev` → dev 仓库 `.claude/skills/marshal` |
| 触发词 | `/marshal`(日常) | `/marshal-dev`(只在验证新版时用) |

要点:
- **稳定版是独立 clone,不是工作仓库的 checkout**。这样在 dev 仓库里 `git switch` / rebase / 重建 venv 都不碰 prod。
- **冻结点打 tag**:`git tag prod-stable-2026-06-12`(现仅有 `v0.1基础版` 一个 tag),`~/marshal-stable` checkout 该 tag。
- **dev skill 自带 home**:dev 的 `SKILL.md` 顶部硬编 `MARSHAL_HOME` 指向 dev home(覆盖默认),确保 `/marshal-dev` 永远调 dev 的 venv/db,绝不串到 prod。
- **两个 skill 名字不同 → Claude Code 同时可见、互不覆盖**(`cli setup` 当前会 unlink 重建同名 link,需扩成支持 `--name marshal-dev`,见 §10 阶段 1)。

## 5. 金标语料回归(验收闸)

目的:给"行为不变"一个可执行的客观证据。诚实拆成**两层**,因为 marshal 的判决一半是确定性 CLI、一半是 Claude 编排器的判断:

### 5a. 确定性层(可精确 diff,自动化)
覆盖纯 CLI 输出:`classify`(风险分级)、`invariants`(命中清单)、`ci-security`/`ci-scan`、`contracts`/`spec`/`conformance` 的结构化结果。
- 语料 = 一组 fixture,每条:`{repo, pr_number, head_oid(钉死), cli_args}`。
- 用历史判过的真实 PR 当种子(手头现成:#599 假阳 retract、#646 codec、#649 CI 安全、#660 Almanax 核对、#665 reflection、#1024 opcode 撞号 等)。
- 录制:在**稳定版**上对每条 fixture 跑 CLI,把 JSON 输出存为 `golden/<repo>-<pr>.json`。
- 比对:在**dev**上跑同样 fixture,逐字段 diff;任何偏差必须是有意改动并在该 fixture 记 `expected-change` 说明,否则视为回归。
- 落地:`tests/golden/` 目录 + 一个 `test_golden_corpus.py`,CI 与本地都能跑。

### 5b. 判断层(重跑 skill,结构化比对,允许有据偏离)
覆盖只有编排器能给的 `GateDecision`(最终 verdict / needs_human / 对抗 review 结论)。
- 对同一批 PR,用 `/marshal`(稳定)与 `/marshal-dev`(新版)各跑一遍,产出结构化 `GateDecision`。
- 比对 verdict 与触发的不变量集合;**判决等价**为通过标准;若新版判决不同,必须给出理由并人工确认是改进而非回归。
- 这层不要求逐字一致(LLM 判断本就有表述差异),要求的是**结论稳定**。

### 5c. 验收门槛(cutover gate)
- 确定性层:golden 语料 **100% 复现**(或全部偏差均标注为有意改动)。
- 判断层:抽样 PR 判决 **0 回归**(改进可接受,降级不可接受)。
- 两者皆过方可进入 §7 切换。

## 6. DB 解耦与迁移

把"代码"和"可变状态"彻底分家,顺手填老坑:

1. **停止提交活的 `marshal.db`**:`git rm --cached marshal.db`,加入 `.gitignore`。版本库只保留**权威快照** `plugins/marshal/data/marshal.snapshot.db`(已存在),由显式步骤(`scripts/` 加一个 `make snapshot` / `snapshot.sh`)从权威 db 导出 invariants/escapes 两表后才更新——杜绝"binary db diff 噪音 commit"。
2. **dev 用独立 db**:`MARSHAL_DB=sqlite:///.../marshal-dev.db`,gitignored,可随时 `seed` 重建,绝不污染 prod ratchet 历史。
3. **格式变更走迁移**:若重构改 db schema/快照格式——
   - 写一次性迁移脚本(沿用现有 `snapshot_version` 机制 bump 版本);
   - 稳定版 db 保留**只读副本**;
   - 切换时把权威表(invariants/escapes 全量历史)**迁移前推**,确保 ratchet/escape 不丢条目(回归之一:迁移后 `cli metrics` 的 invariant 数 / escape 数 ≥ 迁移前)。
4. **`MARSHAL_DB` 写仓库根的老坑**:`adapters/api.py:15` 默认 `sqlite:///marshal.db`(相对 cwd)。本次把默认也走 `_db_url()`(绝对 `$MARSHAL_HOME/marshal.db`),消除 cwd 依赖。

## 7. 日常工作流(重构期间)

- 审真实 PR:照常 `/marshal <repo> <pr#>` → 稳定版,零变化。
- 推进重构:在 dev worktree 改代码、`pytest`、`/marshal-dev <repo> <pr#>` 自测。
- 定期(每完成一块)跑 §5a golden 语料,确认确定性层没漂。
- 里程碑节点跑 §5b 判断层抽样。

## 8. 切换(cutover)与回退

**切换清单(全绿才执行)**
1. §5c 两层验收门槛通过。
2. dev 分支合 main;`git tag prod-stable-<new-date>`。
3. `~/marshal-stable` 重新 checkout 新 tag + 重建其 venv;或直接把 stable clone 指向新 tag。
4. 若 db 格式变:对 prod db 跑迁移脚本(已留只读副本)。
5. `cli metrics` 复核:invariant 数 / escape 数不减;conformance% 不降。
6. 撤掉 `/marshal-dev` 临时 skill。

**回退(任意时刻)**
- 一条命令把 `~/.claude/skills/marshal` 指回旧 `~/marshal-stable`(冻结 clone 始终在);
- db 用切换前的只读副本还原。
- 即:回退不依赖 dev 仓库状态,只依赖冻结 clone + db 副本。

## 9. 验收标准

- [ ] 重构期间 `/marshal` 始终可用且行为=冻结版(随机抽 3 个真实 PR 验证)。
- [ ] `/marshal-dev` 与 `/marshal` 完全独立(改 dev 代码不改变 `/marshal` 输出)。
- [ ] `tests/golden/` 语料存在,`test_golden_corpus.py` 在稳定版 100% 绿。
- [ ] `marshal.db` 不再 TRACKED;快照由显式脚本生成。
- [ ] 切换后 `cli metrics` invariant/escape 数不减、conformance% 不降。
- [ ] 回退演练成功:模拟切换后一条命令回到冻结版。

## 10. 阶段与里程碑

- **阶段 0 — 冻结 prod**:打 `prod-stable-2026-06-12` tag;建 `~/marshal-stable` 独立 clone + 独立 venv;`~/.claude/skills/marshal` 指向它。验证 `/marshal` 正常。(可回退基线就位)
- **阶段 1 — 建 dev 通道**:dev worktree + dev venv;扩 `cli setup --name marshal-dev` 支持第二 skill;dev `SKILL.md` 硬编 dev `MARSHAL_HOME`/`MARSHAL_DB`。验证 `/marshal-dev` 命中 dev、不串 prod。
- **阶段 2 — 建金标语料**:选 8–12 个历史 PR,确定性层录 golden + `test_golden_corpus.py`;判断层定抽样名单与比对模板。
- **阶段 3 — db 解耦**:`git rm --cached marshal.db` + gitignore + snapshot 脚本;修 `api.py:15` 默认。
- **阶段 4 — 重构(载荷,另开 spec)**:在 dev 通道做实际重构,持续跑阶段 2 语料。
- **阶段 5 — 切换/回退**:按 §8 执行。

阶段 0–3 是本设计交付物;阶段 4 的内容另立 spec。

## 11. 风险与权衡

- **两套 venv/skill 的维护成本**:接受。换来 prod 永不断档,值得;切换是显式动作,不易误用。
- **判断层无法逐字回归**:已诚实承认,故拆两层;判断层只保"结论稳定 + 人工确认改进"。silent 接受 LLM 表述差异,但 verdict 降级零容忍。
- **golden 语料会老化**:语料是快照,反映录制时的稳定版行为;新增不变量后需有意更新对应 fixture 的 `expected-change`,不可无声覆盖。
- **稳定 clone 占额外磁盘**:可忽略。

## 12. 后续(非本设计范围)

- 实际 core / DomainPack 解耦重构(阶段 4 载荷)。
- 把 golden 语料接入某种 CI(本机无 CI 则保持本地 `pytest` 门禁)。
- 移除 plugin 分发遗留的 seed/Meta 死代码(memory 已记)。

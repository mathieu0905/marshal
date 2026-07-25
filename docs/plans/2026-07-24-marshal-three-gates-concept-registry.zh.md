# Marshal 三件套方案:PR Gate / Plan Gate / Onboard Processor + 概念注册表地基

> **定位:** 把 2026-07-23 讨论(`docs/discuz/2026-07-23 关于marshal的讨论.txt`)蒸馏为一份**经得起检验、可施工**的工程方案。目标是把 Marshal 从"PR 事后门禁工具"扩展为覆盖 **plan → PR → onboard** 全链路的质量工程产品。
>
> **与既有文档的关系:** 本文**不重写**平台总体蓝图,而是**增量**接在其上。地基仍是 [`docs/architecture/platform-architecture-design.zh.md`](../architecture/platform-architecture-design.zh.md)(v1.3:领域无关核心 + Domain Pack + 分层规格 + 棘轮 + 知识核)。本文只描述蓝图**尚未覆盖的三个新增能力**及它们共同依赖的一个新地基(概念注册表),并给出可验证的分期落地。
>
> **状态:** proposal draft，待评审。含**待裁决策点**(§9),技术项已给推荐,不阻塞。已过一轮 Marshal 深审(gate run 746,verdict=escalate),3 HIGH + 6 MED + 2 LOW 已并回本文(各 §标注「深审修正」;汇总见 §12)。
>
> **日期:** 2026-07-24(v2 并回深审 2026-07-25)

---

## 0. TL;DR(一页读懂)

讨论提出把 Marshal 做成"三件套"产品:**PR gate(已有)、plan gate(要做)、onboard processor(要做,产品化命门)**。三者共同缺一块地基——一个**可被人 review 的中间层**:把自然语言 CIP/规格与海量代码之间,抽象出一棵**概念树(Concept Registry)**。

核心论点(讨论原话蒸馏):

1. 瓶颈不在"代码怎么写"(AI 已能写),而在**全局概念一致性**——没有任何 coding agent 负责它,技术债因此以前所未有速度**净流入**。
2. CIP 是自然语言、无规则、无法 review;3000 行代码人也审不过来。但**一棵 20–30 节点、带层级的概念树,加一个/减一个节点这种粒度,人可以 review**。这就是要抽象的中间层。
3. 概念有**层级与优先级**(Gas ≫ Timer),不是扁平图;架构的本质就是优先级。
4. 每一次概念树的变更(新增/重构/重命名)是**极宝贵的数据**——它能区分 GitHub PR 无法区分的"重构 vs 加 feature",能反推"架构如何演变"。
5. 三个产品的统一输出是**成本**:把"你这次改动要动多少概念、引入多少技术债、要还多久"显式摆到人面前(**概念预算**)。Marshal **保持中性**——只报成本,不替人决定做不做。

本文把这些落成:一个新地基(§3 概念注册表)+ 三个能力(§4 PR gate 增强 / §5 Plan gate / §6 Onboard processor)+ 分期路线(§8)+ 待裁点(§9)。

---

## 1. 讨论蒸馏:主张清单(可追溯)

下表把录音里的可执行主张逐条提炼,标注**新增(既有蓝图/代码未覆盖)** vs **已有**。§10 有逐条与录音时间戳的对照。

| # | 主张 | 性质 | 落到本文 |
|---|---|---|---|
| P1 | CIP 与代码之间加一层 **concept registry(概念注册表)** | 新增 | §3 |
| P2 | 概念是**树形结构**(有父子、有优先级),不是扁平图;Gas ≫ Timer | 新增 | §3.2 |
| P3 | 概念树的**每次变更是宝贵数据**(区分重构/加 feature、反推架构演变、判断何时该重构) | 新增 | §3.4 `concept_change` |
| P4 | **概念预算**:一个想法/方案要新增多少概念 → 显式成本;超预算就别干 | 新增 | §5 |
| P5 | **Plan gate**:方案阶段先过 Marshal,产出**中性成本分析**(要改几天、引入多少债、还债多久),**不建议做不做** | 新增 | §5 |
| P6 | **Onboard processor**:给定任意 GitHub 项目,从零建概念图谱 + 全量回放 issue/PR → 现有技术债盘点 | 新增 | §6 |
| P7 | PR gate 要能抓**"挂羊头卖狗肉"**(命名为 GAS 实则与 gas 无关)——现有工具(含 Marshal)抓不到 | 新增 | §4 |
| P8 | 最终必须有一个**简单的、人能 review 的报告**;概念一开始不准无所谓,**从不准到变准的过程本身也是价值** | 新增 | §3.5 §3.6 |
| P9 | Marshal 内部知识需**可视化**(图/线框),让人看到它怎么工作 | 新增 | §3.7 |
| P10 | Plan gate 以 **MCP** 形态接入 Codex / Claude Code;工具描述="每次 plan 完让 marshal 过一下" | 新增 | §5.3 |
| P11 | 技术债是**延迟的、难归因的**成本;coding agent 有**结构性问题**(task-based,无人管全局一致性) | 背景论证 | §7 |
| P12 | PR diff 门禁成本高(改两天被拦、再改两天);需**更前置**的 plan 阶段介入 | 背景论证 | §5 动机 |
| P13 | 商业:CTO 买单、用量大价高、有 plan 数据沉淀、利润 50–100%、SEO/GEO 打法 | 商业假设 | §7(中性呈现) |
| — | PR gate 本身(风险分级 + 不变量门禁 + 对抗 review + 棘轮) | **已有** | 蓝图 §5;`.claude/skills/marshal` |
| — | 分层规格(白皮书宪法 / CIP 修正案 / 代码实然)+ ConformanceMatrix + 跨层漂移 | **已有(蓝图规划)** | 蓝图 §4.5 |
| — | Domain Pack、知识核、棘轮、领域知识冷启动三来源 | **已有(蓝图规划)** | 蓝图 §4.6 |

> **蒸馏纪律:** 上表只收录可落成工程动作的主张;催 Martin 要测试网等运营事项不在本文范围。

---

## 2. 与现有架构的关系:只增量,不另起炉灶

**现状核对(以代码为准,非以蓝图为准):**

- 已**落地**:薄 CLI(`marshal_core.cli`:classify / invariants / review-quorum / conformance / ratchet-* / gate-record / metrics 等)、知识核**4 张表**(`InvariantRegistry` / `GateRun` / `EscapeRegistry` / `AuditLog`,见 `src/marshal_core/knowledge/models.py`)、`cowboy-pack`、`.claude/skills/marshal` 门禁流程(流 A/B/C + deep review)。
- 蓝图**规划但代码未落**:`ConformanceMatrix` / `Classifications` / `Findings` / `Metrics` 四张表、GitHub App 中枢、无状态执行器。
- **完全不存在**:plan gate、MCP、onboard processor、概念的**结构化/带优先级树**表示。
- **已存在但在 Marshal 之外、且未结构化**:讨论里的 "RAFS wiki 知识图谱" 真身 = **`refs/wiki/`**(27 个概念/实体页 + `AGENTS.md` 操作规约 + drift.md/log.md,LLM 维护、人审读)。它已验证概念层可行,但**是扁平 markdown(无父子/无重要性/无结构化 provenance)、Cowboy 专属、手工跑**——本方案的地基就是把它产品化(§3.0)。

**关键架构判断(本文的立场):**

> 概念注册表是一个**新的一等实体**,不是把它塞进现有 `spec_layers` / `ConformanceMatrix`。

理由:`spec_layers` 仍是**自然语言文档**(白皮书、CIP 原文),`ConformanceMatrix` 是**规格 requirement ↔ 不变量**的覆盖矩阵。二者都**不是**讨论要的那个"20–30 节点、可一眼 review、带优先级的中间层"。概念注册表恰好补这个空:它是从规格与代码里**蒸馏出的命名节点树**,规格 requirement 挂到概念上、不变量挂到概念上、代码 anchor 挂到概念上。它是**连接三者的枢纽**,而非其中任何一个的子集。

这条判断即 §9 待裁 D2 的推荐项。

**复用清单(新能力必须站在这些之上,不重造):**

| 复用既有 | 新能力如何用 |
|---|---|
| 知识核 SQLite + SQLAlchemy | 概念注册表新增表进同一个 `marshal.db` |
| `classify`(风险分级) | plan/PR gate 复用,给概念改动定 tier |
| `invariants`(不变量选择) | 概念 ↔ 不变量双向挂接;概念重要性继承不变量 severity |
| `conformance` / `spec-requirements` | 规格 requirement 挂到概念;plan 成本计入受影响 requirement |
| 棘轮(escape → spawned_check) | "挂羊头卖狗肉"漏过 → escape → spawn 概念一致性检查(§4.3) |
| Domain Pack 契约 | 概念抽取规则、重要性先验、命名规范由 pack 提供(领域无关核心不含 CIP/gas 字样) |
| Claude Agent SDK + deep-review harness | 概念抽取 / plan 映射 / onboard 回放都用 agent fan-out(已有 `harness/`) |
| **`refs/wiki/`(已运行的概念 wiki)** | **一次性** seed + 操作模式蓝本:S0 导入 27 页 + `AGENTS.md` 规约到 Marshal 自有存储,**导入后零 refs 运行时依赖**(§3.0) |

---

## 3. 地基:概念注册表(Concept Registry)

三件套都依赖它,先建它。

### 3.0 设计原则:Marshal 自持 + 持续成长;`refs/wiki` 仅作一次性种子

**两条硬约束(用户明确):**

1. **概念体系必须能持续更新/成长**——不是一次生成的静态快照,而是随规格、代码、PR、plan 不断织密的活资产。
2. **Marshal 自有、自维护,不依托 `refs` repo**——`refs/wiki/` 只作**冷启动的一次性种子 + 模式蓝本**,导入后 Marshal 完全拥有自己的副本,**零 refs 运行时依赖**。

**为什么 `refs/wiki` 只能当种子、不能当依赖:** 它验证了模式可行(已用"LLM 维护、人审读"管了 20 概念 + 7 实体 + 40+ 条漂移),但 (a) 它是 Cowboy 专属、手工跑、扁平 markdown;(b) 按团队既有认知 `refs/` 只是 `cowboy/docs/` 的镜像([[reference_spec_source_of_truth]]),依托镜像本身就脆。故:**raw source 权威取 `cowboy/docs/` + workspace 代码,不取 refs**;`refs/wiki` 的概念散文仅在 S0 一次性导入,之后 Marshal 在自己的存储里自持自长。

> **深审修正 M1(provenance 缺口,已实锤):** "零 refs 依赖"不是免费的。refs/wiki 概念页的 `sources:` 大量指向 **`refs/analysis/2026-04-15_documentation_amendments.md`(修正案权威)**,而 `cowboy/docs/` **无等价物**(已核:`find cowboy/docs -iname '*amendment*'` 为空)。这批"规格说 X、代码是 Y、因修正案 A-1"的漂移推理链是**概念体系最有价值的内容**,却是 refs-only。故 S0 种子导入**必须同时把 `refs/analysis/` 的修正案内容一并吸收进 Marshal 自有 `drift.md`/概念页**(不只导 wiki 27 页),否则要么丢漂移知识、要么仍隐性依赖 refs。导入后这些内容归 Marshal 自有,refs 可删。
>
> **深审修正 L2(raw 源映射比设想乱):** `cowboy/docs/` 的白皮书是**按子系统分的**(`cowboy-storage-whitepaper.md`/`cowboy-secrets-whitepaper.md`…),**无统一 `whitepaper/` 目录**。Domain Pack 的 `spec_layers.source` 映射须按实际文件枚举,不能假设单一白皮书路径。

**存储落点(自持的物理载体):** 概念体系是**领域内容 → 归属领域包**,不进领域无关核心,也不留在 refs:

```
marshal/src/marshal_pack_cowboy/concepts/     # 概念页 markdown(真相源,人审这里)—— Marshal 自有、git 版本控制
                                /entities/     # 实体页
                                /concept-schema.md   # 从 refs AGENTS.md 蒸馏的领域无关"概念协议"(Ingest/Query/Lint 规约)
                                /drift.md /log.md    # Marshal 自己的漂移看板 + provenance 日志
marshal/marshal.db                             # 从 frontmatter 派生的结构化缓存(可查询,供概念预算/plan gate/度量)
```

> 对**任意** onboard 的新 repo,同理:概念存储落在**该 repo 生成的领域包**(或 Marshal 管理的工作区),永不写回 refs、永不依赖 refs。这是 onboard processor 通用化的前提(§6)。

**持续成长引擎(概念体系如何不断更新——四个入口,全部落 `ConceptChange` + git commit + log append):**

| 入口 | 触发 | 动作 |
|---|---|---|
| **Ingest**(新源) | 新/改的规格(`cowboy/docs`)或代码合并 | agent 判断新增 vs 修订概念 → 更新受影响概念页 + frontmatter |
| **Lint**(周期健康检查) | 定时 / 人触发 | orphan / contradiction / stale / drift / missing-concept / **挂羊头**(§4)→ 提修订 |
| **Ratchet**(棘轮) | 概念一致性真漏过 | 开 escape → 加固该概念定义 + spawn 概念检查([[feedback_all_plans_deep_review]] 纪律) |
| **Plan-gate 反馈** | 一份 plan 被采纳并实现 | 其 `ConceptChange` 候选集从 proposed → active,并入概念树 |

概念体系因此"从不准到变准、越跑越密",且**成长记录本身可查询、可计费**(P3/P8)。这直接落地蓝图 §4.6 的"静态包 ⇄ 动态核晋升回路",但真相源在 Marshal 自己的包里,不在 refs。

> **深审修正 H2(不要把人审瓶颈重新引入):** 若每个 `ConceptChange` 都卡人审,在多 repo、每天多 PR 下,concept-change 审查会**变成新的 per-PR 人肉门禁**——恰是 Marshal 要消灭的东西(方法论核心)。故按重要性**分级自动化**:
> - **constitutional / high 重要性概念**的 add/redefine/move → **必须人审小树 diff**(这才是"20–30 节点可审"成立的场景);
> - **mid / low 重要性**的概念变更 → **自动 commit**(origin 记 `ai-auto`,confidence 上限设低),进**异步审计队列**周期抽检,不阻塞任何 gate;
> - 任何把概念从低 tier **提升到 high/constitutional** 的操作,一律人审(升级即高价值信号)。
>
> 这样人审负载 ∝ 高价值概念变更数,而非总 PR 数;"人可 review"从对所有变更的承诺,收敛为对**关键子集**的承诺。此分级即 §9 D11。

**整套借鉴 `refs/wiki` 的模式(一次性搬进 Marshal 自有存储,之后自维护):**

| `refs/wiki/` 现有机制 | 落到三件套 | 说明 |
|---|---|---|
| **三层架构**(raw 不可变 / wiki 由 LLM 全权维护 / schema 规则文件) | 概念注册表整体架构 | raw=各 repo 代码+规格;wiki=概念层;schema=Domain Pack 的"概念协议" |
| **Ingest / Query / Lint** 三操作(`AGENTS.md`) | **= 三个产品的操作接口** | **Ingest→Onboard**(新源→建/更新概念页);**Lint→PR/Plan gate 一致性引擎**;**Query→人可读报告** |
| 页面 **frontmatter**(type/tags/sources/last_updated/status) | Concept 结构化元数据 | `sources[]`=spec_refs;`status`(authoritative/draft/stale)=confidence 代理;`type`=concept vs entity 分类 |
| **权威层级**(代码>修正案>CIP>白皮书) | 描述轴(实然,蓝图 §4.5) | 已成文规则,直接搬 |
| **"宁少勿多"**(跨 3+ 源或有矛盾才建页) | **概念预算的天然抑制器** | 防概念爆炸;正是 onboard 自动生成时最需要的护栏 |
| **drift.md**(高/中/低严重性 + ID + status + precondition gap) | 漂移看板 | 成熟真实产物,直接演进为 gate 的 drift 输出 |
| **log.md**(append-only,`## [YYYY-MM-DD] ingest\|query\|lint` 可 grep) | `ConceptChange` provenance(P3) | 已在捕获"何时发生什么",只需结构化成 op 记录 |
| **index.md** | 人可读报告骨架(P8) | 本身就是"简单的、人能 review 的报告"雏形 |
| `[[wiki-link]]` 交叉引用 | `ConceptEdge`(depends_on/references) | 已存在,需从散文提升为结构化边 |

**需要补的 delta(讨论要、wiki 还没有):** ①**树 + 优先级**(wiki 是扁平 `concepts/`+`entities/`,无父子无重要性,§3.2);②**结构化可算层**(见 §3.0-决定);③**挂羊头检测**(Lint 现查 orphan/contradiction/stale/drift,不查"名 X 实 Y",§4);④**概念预算记账**(§5);⑤**通用化**(现为 Cowboy 专属手工跑 → Domain-Pack 驱动、可复现、任意 repo)。

**§3.0-决定(即 §9 D8):markdown 为人审真相源,派生结构化 index 供计算。** 概念页 markdown 利于人 review(讨论的硬需求 P8)但算不了概念预算;纯 DB 可算但丢了人可读报告。故**双表示**:markdown 概念页(+ frontmatter 里的 `parent`/`importance`/`depends_on`)是**人拥有的唯一真相源**,§3.3 的结构化表是**从 frontmatter 派生的可查询缓存**。这样 markdown **就是** P8 要的报告,DB **就是** plan gate 的计算底座,一石二鸟。

> **深审修正 M2(不是"双向同步",是单向派生 + 提议-提交):** 派生缓存不能同时是写入源——两个 master 必漂移。故严格**单向 markdown→DB 派生**:
> - 所有概念变更(Ingest/Lint/Ratchet/Plan 反馈)一律**先落 markdown**(agent 编辑概念页 + frontmatter),再重新派生 DB;
> - DB 侧的自动分析(如 lint 发现的漂移)只能**提议**一个 markdown 补丁(`DB proposes`),经流程写进 markdown 后才生效(`markdown commits`);DB 永不是权威。
>
> 蓝图"静态包 ⇄ 动态核晋升回路"仍成立,但那是**包(markdown)与知识核累积态之间的人审晋升**,不是 markdown↔DB 两个 master 的自动双写。

**一个张力(须显式管控):** wiki 的"宁少勿多 → 只 20 概念"是**人工为 Cowboy 精心策展**的结果;onboard 陌生 repo 时 AI 自动抽取会**过度生成**。控制手段:把 wiki 的 Lint 纪律 + 概念预算做成可执行闸门,让"宁少勿多"从人肉习惯变成检查。

### 3.1 它是什么(一句话)

从项目的规格与代码里**蒸馏出的、带层级与优先级的命名概念树**,是"CIP(自然语言)↔ 代码(海量)"之间**唯一人类可 review 的中间表示**。

### 3.2 结构:树骨架 + 类型化 DAG 边(解决"树 vs 图"之争)

讨论里 说话人2 坚持**树**(有父子、有优先级),说话人1 提议**图 + PageRank**。二者其实各对一半,工程解法是**分开承载**:

- **主结构 = 树(单父)**:承载"谁是谁的爸爸 / 谁比谁重要"。这是**可 review 的骨架**和**重要性继承**的载体。例:`gas` 是 `execution` 的子节点,`timer` 是 `scheduler` 的子节点。
- **次结构 = 类型化边(DAG,不定义层级)**:承载真实**依赖/引用/冲突**关系。例:`timer` --depends_on--> `gas`(timer 依赖 gas,但 gas 不是 timer 的父)。

> 为什么不用纯 PageRank 定重要性:说话人2 的反例成立——"1000 个微服务的客服系统关联再多也不重要"。**重要性是 design 层判断,不是关联度**。故:关联度(树内 fan-in + 依赖边入度)只作**重要性先验**,最终重要性由人审定(树小,可行)。见 §9 D3。

> **深审修正 M3(单父是简化,真实概念常多父——须防"虚假结构"churn):** 现实里 `gas` 既属 `execution` 又属 `economics`。强制单父会导致父节点反复重指(move op 频发),反而破坏"稳定、加减一节点即可审"的前提。故明确:
> - 每个概念选**一个 primary_parent**(主归属,承载重要性继承与树的可视化骨架),其余归属写成 `ConceptEdge(kind=part_of)` cross-link——**归属的多值性由边承载,层级的可审性由树承载**;
> - **primary_parent 变更本身是高成本 `ConceptChange`**(op=move),按 M3 记账并计入概念预算,而非随手改;冷启动时 primary_parent 的选择由人审定,减少后续 churn。
>
> 即:树骨架不假装能表达全部归属,它只表达"主干 + 优先级";多归属和依赖都在 DAG 边里。

### 3.3 数据模型(派生自 markdown frontmatter 的可查询缓存,进现有 `marshal.db`)

领域无关 schema,取值由 Domain Pack 定义(与既有表同纪律)。**真相源是 §3.0 的 markdown 概念页 + 其 frontmatter(新增 `parent`/`importance`/`depends_on` 字段);下表是从 frontmatter 派生同步的结构化缓存**,供概念预算/plan gate/度量计算。人审只审 markdown 树,不审 DB。

```
Concept                                # 概念节点
  id            # slug, 如 "gas" / "timer" / "payments"
  domain_pack   # "cowboy"
  name          # 规范名
  definition    # 规范含义(此概念"究竟是什么")
  parent_id?    # 树:单父;根为 null
  importance    # constitutional | high | mid | low(= 优先级 = 架构判断)
  status        # proposed | active | deprecated
  origin        # ai-draft | human-curated | ratchet
  confidence    # 0..1 抽取置信度(冷启动低,随人审升高)
  spec_refs[]   # → ConformanceMatrix(哪些 CIP/白皮书条款定义它)
  invariant_ids[] # → InvariantRegistry(哪些不变量守护它)

ConceptEdge                            # 非树关系(DAG)
  src_id, dst_id, kind                 # depends_on | references | conflicts_with

ConceptAnchor                          # 代码里"声称实现某概念"的锚点
  concept_id, repo, path, symbol, kind # implements | named_after
                                       # ← 用于"挂羊头卖狗肉"检测(§4)

ConceptChange                          # 概念树的每次变更(P3 的"宝贵数据")
  id, change_ref                       # PR# / plan-id / onboard-run
  op                                   # add|redefine|move|merge|split|rename|deprecate
  concept_id, before(JSON), after(JSON)
  rationale, actor, created_at
  # 这是 GitHub PR 无法区分"重构 vs 加 feature"的补丁:每次树变更都被显式记账
```

`ConceptChange` 是整套方案的**数据金矿**:它让"架构如何演变"变成可查询、可 review、可计费的结构化流。

### 3.4 与既有知识核的挂接

- `Concept.invariant_ids` ↔ `InvariantRegistry.id`:概念**继承**其守护不变量的最高 severity 作为重要性先验(gas 有 constitutional 级守恒不变量 → gas 概念天然高优先级)。
- `Concept.spec_refs` ↔ 蓝图 `ConformanceMatrix.requirement_id`:规格 requirement 归属到概念。
- `ConceptChange` 与 `EscapeRegistry` 联动:概念一致性漏过 → 开 escape → spawn 概念检查(§4.3),复用现有棘轮的数据库级"非空才 close"约束。

> **深审修正 M5(避免 requirement→invariant 的 N 路重复记账):** 现在一条规格 requirement 既可经 `ConformanceMatrix.requirement→invariant` 到达,又可经 `concept.spec_refs + concept.invariant_ids` 到达——两条路径若各自维护会漂移。定明**唯一权威归属**:
> - **概念是枢纽**:requirement 与 invariant 都**只挂到概念**(`spec_refs` / `invariant_ids`);
> - 蓝图的 `ConformanceMatrix`(requirement↔invariant 覆盖矩阵)**降为从概念派生的视图**(`requirement --via concept--> invariants`),不再独立维护 requirement→invariant 的直连;
> - 好处:conformance 覆盖率天然按概念(即按架构优先级)切片,"哪个高重要性概念缺不变量覆盖"一眼可见(§6.4 技术债信号直接复用)。

### 3.5 构建方式:AI 起草 → 人审定(复用蓝图 §4.6 冷启动三来源)

不靠人力维护(说话人1 明确),但**必须有人把关**(说话人2 明确:小树可 review)。三步:

1. **约定探测(自动)**:目录结构、`CLAUDE.md`/`README`/`docs`、现有测试名、系统地址表(cowboy `constants.rs` 的 `0x06/0x09/0x91-95`)→ 候选概念 + anchor。
2. **AI 抽取(agent fan-out,复用 `harness/`)**:读规格目录 + 代码符号 → 草拟概念树(节点 + 父子 + 依赖边 + 重要性先验 + anchor)。
3. **人工策展**:审 AI 草稿的**小树**(20–30 节点级),增删节点/调父子/定重要性 → commit 进 `cowboy-pack`(概念定义作为版本控制的领域内容;累积态在 DB)。

> **深审修正 H1(最高优先级 · sim≠prod 命门):概念的锚定与重要性必须"代码验证",不能"文档派生"。** 风险:抽取(步骤 2)主要读 docs/规格,但 `drift.md` 存在的全部理由就是**文档≠代码**(CIP-3 写 10M、代码是 20M)。若概念树编码的是**文档里的架构(aspirational)**,则建在其上的 plan-gate / PR-gate / onboard 会算在一个失真模型上,**自信地误导——正是 CIP-36 失败模式的翻版**([[project_cow824_live_bug_sim_vs_prod]])。硬约束:
> - **文档只给候选,代码才裁决**:一个概念的 `importance` 先验取**真实调用图 fan-in / 不变量 severity**(代码侧),不取"文档提及次数";`ConceptAnchor` 必须指向**存在的代码符号**,agent 抽取后**回查代码确认符号确实存在且行为吻合**;
> - **`confidence` 由代码锚定程度决定**,而非文档是否描述:纯文档来源、无代码 anchor 的概念,`confidence` 封顶低(标 `doc-only`),**不得**据以给出高置信的概念预算 / 挂羊头判决;
> - **概念-代码漂移是一等信号**:概念定义与其 anchor 实际行为不符 → 进 `drift.md`(实然轴代码为真),而非默默采信文档。
>
> 一句话:概念树是代码的模型,不是文档的复述;凡未被代码锚定的概念,gate 一律降级、不假装可信。

### 3.6 准确性演进(P8:一开始不准无所谓)

准确性是**演化属性**,不是一次成型:

- 每个 `Concept.confidence` 冷启动低;每次人审确认/纠正 → 升 confidence + 记 `AuditLog`。
- **棘轮驱动收紧**:一次"挂羊头卖狗肉"真漏过 → escape → spawn 概念一致性检查 → 该概念 anchor 的判定规则被永久加固(§4.3)。网在被咬处织密。
- 度量演进:新增指标 `concept_confidence_avg`、`concept_review_coverage`,进 `metrics`。让"从不准到变准的过程"可观测。

### 3.7 可视化与人可读报告(P8 + P9)

两种产物,**报告优先、可视化其次**:

- **人可读报告(MVP,必做)**:一份 Markdown/JSON —— 概念树缩进列表 + 每节点(重要性、confidence、守护不变量数、spec 覆盖、anchor 数、本次变更 op)。这就是说话人2 要的"简单的、人能 review 的报告"。
- **交互可视化(次期)**:静态自包含 HTML(概念树 + 依赖边 + 漂移/挂羊头标记着色);可作为 Artifact 产出。**不引入重前端**;先服务"让人看到 Marshal 怎么工作"。

### 3.8 领域无关纪律(守蓝图 §4.4 lint 约束)

核心表/代码不得出现 `CIP`/`gas`/`PVM` 字样;概念的**内容**(gas/timer/payments 定义、cowboy 命名规范、重要性先验规则)全部由 `cowboy-pack` 注入。`fake-pack` 契约测试须覆盖一个 2–3 节点的假概念树,证明核心不依赖 cowboy 概念。

---

## 4. 能力一:PR Gate 增强 —— 概念一致性 / 挂羊头卖狗肉(P7)

### 4.1 动机

现有 PR gate 抓 bug、抓规格漂移、抓安全,但**抓不到"命名为 GAS 实则与 gas 无关"**——这是严重 issue(说话人2:"是很严重的 issue")。因为它不违反执行、不违反不变量,只违反**架构语义**。

### 4.2 检测机制(可施工,分确定性 + AI 两段)

一个 PR 的 diff → 提取新增/改名的符号与模块 → 对每个**声称实现某概念的 anchor** 做一致性判定:

1. **确定性预筛**:符号命名匹配到概念 slug(如新符号名含 `gas`)→ 建候选 `ConceptAnchor(kind=named_after)`。检查它的**依赖闭包**是否触及该概念的既有 anchor / 守护不变量。名叫 `gas` 却完全不依赖 gas 概念子树 → 高嫌疑。
2. **AI 语义判定(对抗式 review lens,复用 ReviewOrch)**:新增 review 视角 `concept-consistency`,prompt 大意:"符号 X 命名/归类为概念 C,其实际行为与依赖是否符合 C 的 definition?是否应属于另一概念,或需新建概念?" 默认怀疑,quorum 收敛。

> **深审修正 M6(别把预筛当"便宜"——它需要真实依赖图基建 + 噪音管理):** 步骤 1 的"依赖闭包是否触及概念 anchor"要求**跨语言(Rust + PVM Python)符号级依赖图**,是 rust-analyzer 级静态分析,不是免费的。故分档落地,不一步到位:
> - **MVP 用轻量近似**:import/use 语句 + 同文件符号引用 + 调用点文本匹配(不追全精度调用图),明确标为"近似预筛,可能漏"(不静默);
> - **精确依赖图作为后续增强**(接 rust-analyzer / LSP,见工具 seam),非 S4 前置;
> - **步骤 2 的 AI 判定须管精度**:概念错配是否定性属性、易假阳性,一个"乱叫"的检测器会被无视 → 只在**高重要性概念**(§H2 分级)上开这个 lens,低 tier 不跑,把信噪比守住;确认判决一律 `escalate` 人裁(§4.3),不自动 block。
3. **概念预算增量**:PR 若新增概念(如引入 `domain`/`gateway`,说话人2 原例),在门禁报告里显式列出**新增概念清单**(不阻断,只让"引入了新概念"这件事无法被忽略)。

### 4.3 判决与棘轮

- 判决沿用现有语义:确认的高 severity 概念错配 → `escalate`(治理 a 档,人裁,不自动 block——是"合法的新抽象"还是"挂羊头"由人定,Marshal 只负责让它无法被忽略)。
- 一次挂羊头**漏过**并事后确认 → `/marshal ratchet` 开 escape → spawn 一条**概念一致性检查**(记为 `hazard:<id>` 型,因为它是否定性属性,不可往返化——复用现有 ratchet-flow 对"否定性属性"的处理)。

### 4.4 与既有流程的接缝

在 skill 流 A 第 4 步(对抗 review)**新增一个可选视角** `concept-consistency`,由 `cowboy-pack` 的 `review_dimensions` 提供;classify 命中"新增顶层符号 / 触及概念 anchor 密集区"时激活。**不改动现有流 A/B/C 的判决主干**。

### 4.5 MVP 与验收

- MVP:`cli concept-check --repo <r> --paths <diff>` 输出新增/疑似错配概念清单(先确定性预筛,AI 视角作为 deep 模式可选)。
- 验收:在 3 个历史"引入新概念"的真实 PR(如引入 domain/gateway 的那批)上回放,能列出被引入的新概念且人工确认清单正确;至少复现 1 个真实"命名与语义不符"案例。

---

## 5. 能力二:Plan Gate —— 概念预算(P4/P5/P10/P12)

### 5.1 动机

PR 阶段拦截**太晚、太贵**(改两天被拦、再改两天,说话人1/2 共识 P12)。要在**方案阶段**就把成本摆出来。这是通往"loop engineering 自动化闭环"两头把控的**前端**(说话人1:后端质量工程 + 前端设计工程,两头抓才不越走越偏)。

### 5.2 核心产物:概念预算(中性成本报告,绝不建议做不做)

输入一份 plan 文本(AI 或人写的方案),输出**成本画像**:

```
ConceptBudget(plan_id, repo)
  new_concepts[]              # 本方案要新增的概念(及父节点归属 + 每个的 scope_weight,见 M4)
  redefined_concepts[]        # 要重定义的既有概念(按 importance 加权:动 gas ≫ 动 timer)
  weighted_concept_cost       # 按 scope 加权的概念成本(非裸计数,见 M4 深审修正)
  highest_tier_touched        # 触及的最高重要性层(动 constitutional 概念 = 重大信号)
  impacted_invariants         # 受影响不变量数(来自 invariants)
  impacted_spec_reqs          # 受影响规格 requirement 数(来自 conformance)
  impacted_repos[]            # 爆炸半径
  est_impl_days               # AI 估算实现工期(带 confidence + 诚实免责)
  est_debt_weeks              # AI 估算后续还债周期(带 confidence)
  verdict = COST_ONLY         # 恒为中性;不含 go/no-go
```

> **深审修正 M4(概念"计数"是弱成本代理,须按 scope 加权):** 新增 1 个 `payments`(整个子系统)≠ 新增 10 个瑣碎概念;裸计数会误导。故成本以 **`scope_weight`** 为主指标,不以 new_concept 计数为头条:`scope_weight` ≈ f(该概念的预期子树规模 / 守护不变量数 / 爆炸半径 / importance tier)。报告同时列**加权成本**和**明细清单**(让人看到是"1 个重概念"还是"10 个轻概念"),避免"10 个概念"这类数字被单独拿去当结论。

> **中性原则(说话人2 明确):** Marshal 不知道你的预算,不替你决定。"有些人我知道你要全改,我就是要全改。" Marshal 只把成本摆出来:"这些改动至少三天,可能引入 N 周技术债,你自己判断值不值。"

### 5.3 交付形态:CLI 先行,MCP 随后(P10)

- **CLI(先做)**:`cli plan-cost --plan <file> --repo <r> [--base <ref>]` → 输出 `ConceptBudget` JSON + 人可读摘要。先在**我们自己的 plan** 上验证(说话人1:已多次遇到 Marshal 查出方案本身有问题)。
- **MCP(随后)**:包一层 MCP server `marshal-plan-gate`,暴露工具 `marshal_plan_review`。工具描述即说话人2 的原话:**"每次执行完 plan 之后,让 Marshal 过一下,给出成本;不建议做还是不做。"** 接入 Codex / Claude Code / Opencode,给"想法多"的队友(Logan / Caleb / Martin / chad)先用起来收反馈(说话人2:先搞小工具 + 小 demo)。

> **深审修正 H3(冷启动采用悖论——工具最弱时正好第一次见信任最关键的用户):** plan-gate 输出质量 ∝ 概念树成熟度,而树在早期又薄又不准(§3.6 自承)。若过早把噪音报告推给 Logan/Caleb/Martin,他们会**在工具成熟前就先失去信任**,采用死在摇篮。故对外顺序设约束:
> - **先在树已养厚的 Cowboy 上把 plan-gate 跑到可信**(§8 S2 验收:复现 ≥1 例"方案本身有问题"被提前暴露)**,再对外**(S3);
> - 早期每份 plan-gate 输出**显式标 `tree_maturity: N%` 与 `confidence`**,并把低置信项标"仅供参考,概念覆盖不足",而非当结论;
> - 首批用户从**最能容忍粗糙、最认同理念的人**起步(内部、我们自己的 plan),把"可信"做出来再扩散。

### 5.4 计算流程(复用既有能力)

1. `agent` 解析 plan → 映射到"要触及哪些概念"(读当前概念树 + 被改文件周边,JIT 上下文)。
2. diff 概念树 → 得 `ConceptChange` 候选集(add/redefine/move…)。
3. `classify` 定 tier;`invariants` 数受影响不变量;`conformance` 数受影响 requirement。
4. `agent` 估工期与还债周期(**必须带 confidence 和"这是估算"的诚实标注**,不谎报精度)。
5. 组装 `ConceptBudget` → 落 `GateRun`(verdict=`cost-only`)+ **plan 数据沉淀**(说话人2 商业点:"每次 plan 我都看得到")。

### 5.5 MVP 与验收

- MVP:CLI `plan-cost`,概念 diff + 受影响不变量/requirement 计数 + AI 工期估算。
- 验收:在近期 3–5 份真实 plan 上跑,概念预算报告能正确标出"这个方案要新增 N 个概念、触及最高 X 级";至少复现 1 例"方案从一开始就有问题"被成本画像提前暴露(对齐说话人1 的既往经验)。**不追求工期估算数值精准**,追求相对排序与新增概念清单正确。

---

## 6. 能力三:Onboard Processor(P6)—— 产品化命门

### 6.1 目标

给定**任意** GitHub 项目,从零:建概念图谱 + 盘点技术债 + 标出概念一致性违规。说话人2:"把 open-clow onboard 一次,你就清楚你的技术债多少、有哪些概念、还会不会有人加更多概念。"这是最好卖的一环(每个项目买一个)。

### 6.2 两阶段(便宜先行,昂贵后置且先估价)

- **Phase 0 · HEAD 快照(MVP,相对便宜)**:只吃当前 HEAD —— 文档 + 代码结构 + 测试 → §3.5 三步建初始概念树。产出:概念图谱 + **初期技术债信号**(挂羊头 anchor、孤儿概念、过度碎片化=一个概念被拆成太多、命名冲突)。**不回放历史**。
  > **深审修正 L1:** "便宜"是相对 S6 全量回放而言;对大 repo,Phase 0 的 agent fan-out(全码库抽概念 + 回查代码锚定,H1)绝对成本也不低。故 Phase 0 **同样先过 `--dry-run` 估价**(§6.3),不假设它免费。
- **Phase 1 · 全量回放(后置,昂贵)**:按时间顺序回放 issue + PR → 重建 `ConceptChange` 历史 → 技术债的**时间归因**(说话人2 的"债难归因"正是要用这段历史来破)。

### 6.3 成本诚实(硬约束,呼应记忆:不静默截断)

说话人1 已点出"Marshal 费算力大"。故:

- `cli onboard --dry-run` **先估价**:扫仓库规模(文件数 / issue 数 / PR 数)→ 输出预计 token/时间/成本区间,再决定是否全量跑。
- 全量回放用**采样 + checkpoint**,任何采样/上限**必须在报告里显式声明**(丢了什么、为什么),绝不让"采样跑"读起来像"全量覆盖"。
- 成本计入 `GateRun.evidence.cost`(复用现有真实 token 计量 `budget.spent()`)。

### 6.4 产物

1. **技术债盘点报告**(人可读):概念一致性违规 + 孤儿/碎片化概念 + 缺规格覆盖的高重要性概念。
2. **概念知识图谱**(§3.3 数据 + §3.7 可视化)。
3. **onboard 摘要**:概念总数、最高重要性概念、初期债热点。

### 6.5 MVP 与验收

- MVP:`cli onboard --repo <path-or-url> --snapshot`(仅 Phase 0)。**先 onboard Marshal 自己 + cowboy `node/`**(吃狗粮)。
- 验收:对 `node/` 产出 20–40 节点概念树 + 一份技术债信号报告,人工抽查概念/父子/重要性**多数正确**(定义"多数"=人审接受率 ≥70%,不接受项进演进循环);`--dry-run` 成本估算与实跑偏差在合理区间(如 ±50%)并诚实披露。

---

## 7. 产品化与商业(中性呈现,不拔高)

以下为**讨论中的商业假设**,记录以便后续验证,**非既成事实**:

- **痛点结构(P11):** coding agent 是 task-based,无人负责全局概念一致性 → 技术债净流入,且**延迟 + 难归因**(类比金融风控)。此为方案的第一性动机,可由"我们自己项目的痛"佐证(说话人1:工作中很痛)。
- **市场时机假设(待验证):** "75% 技术负责人认为 12 个月内技术债海量爆发"——**引用需核实来源**,不作为既定事实写入对外材料。
- **买方与定价假设:** CTO 买单、开发者不买;用户量小但单价高、用量大;plan/onboard 沉淀**数据资产**(说话人2:"每次 plan 我都看得到")。利润 50–100%,算力成本转嫁("羊毛出在羊身上")。
- **打法:** SEO + GEO;先给"想法多"的队友小工具/小 demo 收反馈,再产品化。
- **定位一句话:** Marshal 不写代码,负责**全局概念一致性**——解决"软件应该怎么架构",不是"代码怎么写"。

> 纪律:对外材料里,把"假设/主张"与"已验证事实"分开标注;数据(如 75%)必须附来源或标注为"业内观感"。

---

## 8. 分期实施路线(每步带可验证判据;先影子后强制)

沿用蓝图"先影子、后强制"纪律。地基(§3)必须最先,三能力依赖它。

| 阶段 | 交付 | 依赖 | 可验证成功判据 |
|---|---|---|---|
| **S0 概念注册表地基** | 概念存储落 `marshal_pack_cowboy/concepts/`(Marshal 自有)+ frontmatter 加 `parent`/`importance`/`depends_on` + frontmatter→DB 派生同步器 + 4 张缓存表 + `cli concept-list/tree`;**一次性导入 `refs/wiki/` 27 页作种子后即自持**(不再读 refs);`fake-pack` 假概念树契约测试 | 知识核 | `pytest -q` 绿;`fake-pack` 证核心不含 cowboy 概念;导入后树带 `parent`/`importance` 并回写 Marshal 自有 markdown;**断网/删 refs 后 `cli concept-tree` 仍正常**(验证零 refs 依赖) |
| **S1 Onboard Phase 0(快照)** | `cli onboard --snapshot` + `--dry-run` 估价 + 技术债信号报告 + Markdown 概念树 | S0 | onboard `node/` 产 20–40 节点树,人审接受率 ≥70%;`--dry-run` 成本披露正确 |
| **S2 Plan Gate CLI** | `cli plan-cost` → `ConceptBudget` + 人可读摘要 | S0,S1 | 3–5 份真实 plan 上产出成本画像;复现 ≥1 例"方案本身有问题"被提前暴露 |
| **S3 Plan Gate MCP** | `marshal-plan-gate` MCP server + 工具描述 | S2 | Claude Code/Codex 里"plan 完自动过 Marshal";内部队友试用收 ≥3 条反馈 |
| **S4 PR Gate 概念一致性** | 流 A 新增 `concept-consistency` 视角 + `cli concept-check` + 棘轮接线 | S0 | 历史 PR 回放能列新增概念;复现 ≥1 真实"挂羊头"案例;漏过可上棘轮 spawn 检查 |
| **S5 可视化 + 演进度量** | 概念树静态 HTML(可 Artifact)+ `concept_confidence`/`review_coverage` 进 metrics | S1–S4 | 一张可交互概念图给非工程人看懂;度量能显示"从不准到变准"趋势 |
| **S6 Onboard Phase 1(全量回放)** | issue/PR 时间序回放 → `ConceptChange` 历史 + 债时间归因 | S1,成本实测 | 对一个中型 repo 全量回放,成本在 `--dry-run` 估算区间内;产出债时间线 |

> **每个阶段进实现前**:该切片的 plan.md 先过 `/marshal`(含 plan gate 自审——吃狗粮),重点审"sim≠prod 的测试真实性"(呼应团队既有纪律)。

---

## 9. 待裁决策点(技术项已给推荐,不阻塞;治理/商业项留人裁)

| # | 决策 | 选项 | 推荐 | 理由 |
|---|---|---|---|---|
| **D1** | 概念注册表是否独立一等实体 | (a) 新实体 / (b) 并入 spec_layers/Conformance | **(a) 新实体,且为枢纽** | spec_layers 是自然语言文档、Conformance 是覆盖矩阵,都不是"可 review 的优先级树";概念是枢纽,ConformanceMatrix 降为**从概念派生的视图**(深审 M5,§3.4) |
| **D2** | 概念结构 | (a) 纯树 / (b) 纯图+PageRank / (c) 树骨架+类型化 DAG 边 | **(c) + 单 primary_parent** | 树给可 review + 优先级继承;DAG 边给真实依赖 + **多归属(part_of 边)**;primary_parent 变更是高成本 move op(深审 M3,§3.2) |
| **D3** | 重要性如何定 | (a) 全自动(fan-in) / (b) AI 先验+人审定 | **(b)** | 重要性是 design 判断非关联度;树小,人审可行(说话人1/2 均落到"人把关") |
| **D4** | Plan gate 交付顺序 | (a) 直接 MCP / (b) CLI 先、MCP 随后 | **(b)** | 先在自己 plan 上验证成本模型对不对,再包 MCP 给队友(说话人2:先小工具收反馈) |
| **D5** | Onboard MVP 范围 | (a) 直接全量回放 / (b) HEAD 快照先行 | **(b)** | 全量回放贵且难;快照便宜可证价值(说话人2:先搭框架);全量作 S6 且先 dry-run 估价 |
| **D6** | 挂羊头判决 | (a) 自动 block / (b) escalate 人裁 | **(b)** | "合法新抽象 vs 挂羊头"是品味/治理判断;沿用治理 a 档,只标记不自动拦 |
| **D8** | 概念层真相源 | (a) DB 为主、markdown 为输出 / (b) markdown 为主、DB 为派生缓存 | **(b) 单向派生** | markdown 即 P8 人可读报告、**唯一真相源**;DB 为**只读派生缓存**;变更先落 markdown 再派生(深审 M2,非双写,§3.0-决定) |
| **D9** | 概念体系归属与依赖 | (a) 依托 refs/wiki / (b) Marshal 自有(存领域包)、refs 仅一次性种子 | **(b)** | 用户硬约束:自持自维护、持续成长、零 refs 运行时依赖;**种子须连 `refs/analysis` 修正案一并吸收**(深审 M1),raw 权威取 `cowboy/docs`+代码 |
| **D10**〔深审新增 H1〕 | 概念锚定与重要性的来源 | (a) 文档派生 / (b) 代码验证优先 | **(b) 代码验证** | 文档≠代码(drift.md 存在的理由);gate 建在文档派生模型上=sim≠prod 误导。anchor 必须代码存在、confidence 由代码锚定决定(§3.5 H1) |
| **D11**〔深审新增 H2〕 | 概念变更是否都卡人审 | (a) 全部人审 / (b) 按重要性分级 | **(b) 分级** | 全部人审=重新引入 per-PR 人肉瓶颈。仅 high/constitutional 概念变更人审,mid/low 自动 commit + 异步抽检(§3.0 H2) |
| **D7**〔留人裁〕 | 定价 / 利润率 / 对外数据引用(75%) | — | — | 商业与合规决策,非工程可定;§7 已标"待验证" |

---

## 10. 附:录音主张 ↔ 本文落点对照(可追溯)

| 录音时间戳 | 主张 | 本文落点 |
|---|---|---|
| 00:51–01:32 | concept registry:概念是什么/如何定义/什么层级/被谁引用 | §3.1 §3.3 `Concept` |
| 02:54–04:13 | 概念变更是宝贵数据;判断何时重构 | §3.4 `ConceptChange` |
| 04:13–04:49 | 给客户:合法但违反架构的问题也要拎出来 | §4(概念一致性) |
| 04:49–05:47 | 轻量级架构 agent / Marshal MCP,写代码前先审 | §5(plan gate MCP) |
| 13:30–14:37 | Gas ≫ Timer;树形非扁平图;PageRank 不足 | §3.2 §9 D2/D3 |
| 16:00–16:57 | 最终要人能 review 的简单报告;20–30 节点可审 | §3.5 §3.7 |
| 16:57–17:25 | CIP 到代码中间抽象一层可 review 的东西 | §3 整节 |
| 17:25–19:31 | 不变量/恒等式(钱守恒);从代码反推架构 | §3.4(挂不变量)复用既有 |
| 10:26–11:30 | 概念预算;提需求者不知成本;把成本摆客户面前 | §5.2 |
| 22:09–22:47 | 概念层级可视化;一开始不准无所谓,演进过程是价值 | §3.6 §3.7 |
| 23:26–26:46 | plan 阶段审 + PR 新增概念要审;挂羊头卖狗肉是严重 issue | §4 §5 |
| 27:42–29:46 | 决策逻辑=成本账;技术债延迟难归因;金融风控类比 | §5 §7 |
| 30:09–31:12 | 全局概念一致性无人负责=结构性问题 | §7(定位) |
| 35:47–39:58 | 三件套:PR gate / plan gate / onboard processor 定义 | §4 §5 §6 |
| 36:15–38:00 | plan gate=MCP;输出成本;不建议做不做(中性) | §5.2 §5.3 |
| 42:11–43:03 | 先给想法多的队友小工具 + 小 demo 收反馈 | §5.3 §8 S3 |

---

## 12. 深审修正汇总(Marshal gate run 746,verdict=escalate)

本文 v1 经一轮 Marshal 深审(设计/plan 对抗式 review),11 条已并回上文对应 §。按严重性:

| # | 严重性 | 发现 | 修正落点 |
|---|---|---|---|
| **H1** | HIGH | 概念树"文档派生"→ gate 建在会继承 doc-drift 的失真模型上(sim≠prod,CIP-36 翻版) | §3.5 深审修正 H1;§9 D10 |
| **H2** | HIGH | 成长引擎四入口若都卡人审 → 重新引入 per-PR 人肉瓶颈 | §3.0 深审修正 H2;§9 D11 |
| **H3** | HIGH | 冷启动采用悖论:plan-gate 最弱时正好第一次见信任最关键用户 | §5.3 深审修正 H3 |
| **M1** | MED | provenance 缺口:修正案推理链 refs-only,`cowboy/docs` 无等价物(已实锤) | §3.0 深审修正 M1 |
| **M2** | MED | D8"双向同步"自相矛盾(派生缓存不能是写入源) | §3.0-决定 深审修正 M2;§9 D8 |
| **M3** | MED | 单父树强加虚假结构(真实概念多父)→ move op churn | §3.2 深审修正 M3;§9 D2 |
| **M4** | MED | 概念"计数"是弱成本代理(1 个重概念 ≠ 10 个轻概念) | §5.2 深审修正 M4 |
| **M5** | MED | requirement→invariant N 路重复记账 | §3.4 深审修正 M5;§9 D1 |
| **M6** | MED | 挂羊头"确定性预筛(便宜)"低估了跨语言依赖图基建 + 噪音 | §4.2 深审修正 M6 |
| **L1** | LOW | Onboard Phase 0"便宜"是相对的 | §6.2 深审修正 L1 |
| **L2** | LOW | raw 源映射比设想乱(白皮书按子系统分,无统一目录) | §3.0 深审修正 L2 |

**未闭合(留人裁/待 PoC 证):** D7(商业/定价/75% 数据来源);H1/M4/M6 的可行性最终要 S0 PoC 实测才能证——现文已把它们从"乐观假设"降级为"显式风险 + 缓解设计",但**工程可行性的最终裁决在 S0**(概念抽取准确率、依赖图基建工时)。

---

## 修订记录

- **2026-07-24 v1** — 从 2026-07-23 讨论蒸馏成文;定位为 v1.3 平台蓝图的增量方案(新增概念注册表地基 + 三件套能力 + 分期路线 + 待裁点)。
- **2026-07-25 v2** — 并回 Marshal 深审(gate run 746)11 条修正(3 HIGH + 6 MED + 2 LOW);新增 §12 汇总、§9 D10/D11;核心变更:H1 概念锚定必须代码验证(反 sim≠prod)、H2 概念变更分级人审(反瓶颈重现)、M1 种子须吸收 refs/analysis 修正案、M2 单向派生。

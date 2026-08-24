# 研究与产品方案：Marshal Project Change-Set Review

## Problem Anchor

- **Bottom-line problem**：Marshal 需要从“单个 PR 的问题检测”扩展为“同一大型项目内多个相互依赖仓库的联合审查”，能够回答一个变化会影响哪些仓库、应该验证哪组仓库版本，以及哪些结论有真实执行证据。
- **Must-solve bottleneck**：当前运行单位仍是单 `repo/ref`；跨仓 invariant 在自动 reporter 中会被记为 `not_run`，手工流程又默认在目标仓 tip 上执行，因此可能测试错误的仓库组合并产生假绿或假红。
- **Non-goals**：不建立永久企业知识图谱；不自动修改或合并协调 PR；不默认新增 hash、冻结 baseline、通用 contract 或 project gate；不把依赖关系命中直接当作 bug；不在首轮追求所有语言和构建系统。
- **Constraints**：保留 Marshal 现有 checkout 校验、零测试检测和降级语义；关系扫描不能替代真实构建、测试或模拟；第一阶段应 run-local、只读、advisory；仓库身份使用 `owner/repo`；拿不到真实组合时必须报告 unknown。
- **Success condition**：相较单仓审查和“只增加跨仓上下文”，该方案在真实可复现的跨仓破坏上显著提高受影响仓库召回与故障检测，同时在兼容升级和带协调修复的 change set 上保持可接受的误报，并能展示执行过的准确 repo/ref 组合。

## 已核验的当前能力与断点

Marshal 已具备一些跨仓线索，但还不是项目级审查器：

1. Cowboy `Contract` 能列出参与仓、路径触发和验证 invariant，但关系无 provider/consumer 方向，也不描述实际版本组合。
2. invariant 与计划携带 `location_repo`，可是自动 reporter 遇到异仓位置会明确写入 `not_run`。
3. 手工 skill 会为异仓 invariant 建 worktree，但选择的是该仓 `origin/devnet`、`origin/main` 或 tip，不是当前 change set 指定的组合。
4. concept graph 有 `depends_on` 和 `impacted_repos`，表达的是语义依赖，不包含构建选择、依赖版本或消费证明，不能替代 repo dependency graph。
5. `NormalizedEvent`、`DispatchJob`、`ReviewJob`、`ReviewRun` 都围绕单仓变化；GitHub adapter 还会丢掉 owner，部分内存/任务索引只使用 SHA。
6. Dashboard 与 sweep 能枚举多个仓，但仍是多个独立 PR 的队列，不是一个协调 change set。

最直接的失败场景是：wallet 修改 wire encoding，node 自己的 round-trip 在 node tip 上仍然全绿，因为它没有消费 wallet 产出的字节。Git SHA 和版本号能标识快照，却不能证明 node 真正消费了这次 wallet 变化。

## Technical Gap

### 竞品已覆盖的部分

- CodeRabbit 已支持手工/自动关联仓库、API/schema/shared-library 等关系发现、显式 companion PR/branch 以及同名 branch 匹配。
- Qodo 已支持手工/自动关系、companion PR/branch，并在 PR 中报告跨仓 conflict；其关系本身明确为 non-directional，每次选最相关的 10 条 active relationship。
- Greptile 用 repo cluster 为每个成员提供其他仓库的只读上下文。
- Bito AI Architect 建立 cross-repository knowledge graph，并把上下游影响送入 code review。
- Zuul 用 `Depends-On` 构建跨项目 change DAG，并对组合做 speculative testing。

因此，“把多个 repo 放进上下文”已经是 table stakes。Marshal 不能把 linked repositories 或更大 context window 当作核心差异。

### 缺失的机制

真正缺的是一条闭环：

```text
变化集合
  -> 有证据且有方向的依赖路径
  -> 明确的 repo/ref 组合
  -> 针对每条影响路径的验证义务
  -> 确实消费该组合的构建/测试/模拟
  -> 区分影响、执行结果与覆盖缺口
```

只做静态关系图会漏掉序列化字节、生成代码、feature flag、build script 和部署组合；只做 LLM 跨仓检索则无法证明其选中的 ref 或测试真正消费了 provider 变化。

## 两条候选路线

### Route A：Cross-repo context expansion

维护相关仓库列表，将相关文件、schema、历史和 companion PR 一并送入 reviewer。

- 优点：最小、容易与现有 deep review 结合。
- 缺点：与 CodeRabbit、Qodo、Greptile、Bito 重叠；不能解决错误 ref、错误消费路径和“测试未观察到变化”的假绿。
- 结论：可作为组件，不足以成为主方案。

### Route B：Evidence-directed Project Change-Set Review

把审查单元从单 PR 提升为一个 run-local Project Change Set：先解析方向与准确组合，再为受影响 consumer 生成临时验证义务，最后要求执行证据证明所选 consumer 确实消费了所选 provider。

- 优点：直接命中 Marshal 当前断点；与 Marshal 的 evidence-first 思路一致；差异不依赖更大的模型或上下文。
- 风险：组合 materialization 因语言/构建系统而异，必须从一个生态和少量 adapter 起步。
- 结论：选择 Route B，Route A 只作为其上下文选择层。

## Method Thesis

- **One-sentence thesis**：将审查单位从孤立 PR 改为带方向依赖、准确 repo/ref 组合和 consumption proof 的 Project Change Set，能够把跨仓相关性判断提升为可验证的兼容性证据。
- **Smallest adequate intervention**：不重建 Marshal 数据库或引入永久知识图谱，只增加一次运行内的 project context、change-set resolver、impact path 和 verification obligation；执行继续复用仓库已有命令。
- **Frontier-era positioning**：LLM 适合从 diff 与图路径中提出验证义务、筛选上下文和解释失败；组合解析、构建结果、测试计数和产物消费仍由结构化工具提供，避免让模型自证正确。

## Contribution Focus

- **Dominant contribution**：一个以 Project Change Set 为审查原子、以真实组合执行为结论依据的跨仓 review protocol。
- **Supporting contribution**：面向跨仓审查的 executable benchmark protocol，覆盖破坏、兼容升级、协调修复与 distractor repos。
- **Explicit non-contributions**：不声称提出新的基础模型、依赖图算法、通用 contract DSL、CI 系统或自动 merge scheduler。

## Proposed Method

### Complexity Budget

- **Frozen / reused**：Git commit/ref、manifest/lockfile、CI checkout 信息、现有 Cowboy contract 线索、仓库已有 build/test/simulation、Marshal 当前 evidence 规则和 deep reviewer。
- **New run-local concepts**：`RepoSnapshot`、`RepoChange`、`RelationCandidate`、`DependencyEdge`、`Composition`、`VerificationObligation`、`EvidenceRecord`。
- **Intentionally excluded**：数据库 migration、内容 hash、冻结 baseline、自动生成永久 contract、学习型全局 dependency graph、默认 project gate。

### System Overview

```text
Project input
  |-- repo checkouts / PRs / explicit refs
  |-- changed repos
  |-- optional explicit relationship hints
  v
Snapshot + Change-Set Resolver
  |-- canonical owner/repo identity
  |-- exact candidate snapshot for every changed repo
  |-- no silent fallback to target-repo tip
  v
Evidence-backed Relation Discovery
  |-- manifest / lockfile / cargo metadata
  |-- CI actions/checkout repository+ref+path
  |-- existing Cowboy Contract as undirected candidate
  |-- explicit project input for deployment/wire relations
  v
Directional Impact Planner
  |-- consumer -> provider edges
  |-- bounded reverse traversal from changed provider
  |-- unresolved/conflicting evidence remains explicit
  v
Obligation Planner (LLM-assisted, tool-grounded)
  |-- boundary changed: API / wire / schema / generated / build / deploy
  |-- affected consumer and relevant tests/simulations
  v
Composition + Execution
  |-- materialize intended repo/ref combination
  |-- prove consumer loaded provider snapshot or artifact
  |-- run existing build/test/simulation
  v
Project Review Report
  |-- impact paths
  |-- execution evidence
  |-- coverage gaps and unknowns
```

### 1. Run-local Project Context

每个 repo 使用 `owner/repo` 身份和一个明确 snapshot。干净 checkout 复用 Git commit；dirty worktree 标为不可重放，并记录其 diff/untracked 范围，不另造派生 hash。

一次运行允许多个 `RepoChange`。这避免把 wallet PR 与 node companion PR 拆成两个互不相干的判断，也避免同名 fork 或相同 SHA 覆盖彼此。

### 2. Relationship Evidence, Not Relationship Truth

发现器只产生候选证据，不直接产生 finding、contract 或 gate：

- manifest/lockfile/包管理器 metadata：给出 build dependency 与解析版本；
- CI checkout：给出 pipeline 实际拉取的 repo/ref/path；
- Cowboy Contract：提名共享 boundary 和已有 invariant，但在没有方向证据时保持 unresolved；
- 显式输入：描述源码无法推断的 runtime、wire、generated 或 deploy 关系。

当 manifest、lockfile 与 CI ref 冲突时，报告冲突，不用单一 confidence score 静默选择。

### 3. Change-Set Resolution

ref 解析优先级只用于解释来源，不用于猜测：

1. change set 中显式 companion PR/ref；
2. CI 或 dependency config 指定的 ref/version；
3. caller 明确选择的本地 checkout；
4. 其余情况为 unknown。

同名 branch 和 default branch 可以作为只读 review context，但不能冒充 compatibility combination。尤其不能在异仓 ref 缺失时回退到 `origin/main`、`origin/devnet` 或 tip 后声明 pass。

### 4. Directional Impact and Temporary Obligations

解析成功的边统一表达为 `consumer -> provider`，并保留 kind、selector 和来源证据。从 changed provider 反向遍历 consumer，第一阶段只做一跳，后续才增加有界传递。

每条 impact path 生成本次运行内的验证义务，例如：

- consumer 是否仍能在 provider API 变化后编译；
- provider 新产物能否被 consumer 解析；
- schema/client codegen 是否同步；
- deployment config 是否仍引用存在的 artifact/interface。

这些 obligation 不是永久 contract。没有足够关系或执行 adapter 时，它只产生 `not_assessed`，不会自动升级成新 gate。

### 5. Composition and Consumption Proof

执行前必须证明测试观察到了候选组合：

- build dependency：包管理器 metadata 显示 consumer 解析到所选 provider checkout/version；
- wire/schema：由 provider 生成真实 artifact，再交给 consumer 解析或模拟；
- CI relation：重放对应 checkout/ref 选择；
- 无法证明时，consumer 自身测试只能算 repo-local evidence。

这一步专门防止“两个 checkout 都对，但 build cache/lockfile 仍使用旧 provider”的假绿。

### 6. Execution and Evidence

复用仓库已有 build、typecheck、test、conformance 或 simulation。证据至少记录：

- repo/ref map；
- cwd 与 argv；
- selection reason 与 consumption proof；
- exit code；
- 实际测试/模拟数量；
- 与 obligation 相关的输出摘录。

exit 0 但零测试不算 passed；基础设施错误不算兼容；一个明确失败不能被其他 `not_run` 覆盖。

### 7. Output Semantics

静态影响与动态评估分开：

- **Impact**：`affected | not_affected | unknown`
- **Assessment**：`passed | failed | not_run | not_assessed`

`passed` 只表示计划范围内的相关证据在真实消费候选组合后通过，不表示全局兼容。项目聚合使用：

- `incompatibility_found`
- `verified_for_planned_scope`
- `incomplete`

不复用单 PR 的 `pass/block` 作为项目结论。

## Modern Primitive Usage

- **Primitive**：现有 coding/review LLM，不新增训练组件。
- **Role**：根据 changed boundary 与 impact path 提出/排序 verification obligation，选择最小相关上下文，解释结构化执行结果。
- **Oracle boundary**：LLM 不选择未经证实的 ref，不判断命令是否真实运行，不把自身推理当 compatibility evidence。
- **Why appropriate**：跨语言 boundary 语义和测试定位适合模型推理；repo identity、dependency resolution、checkout、退出码与测试数量适合确定性工具。

## Failure Modes and Diagnostics

1. **关系方向未知**：保留 `RelationCandidate`，影响状态 unknown，不猜双向边。
2. **companion PR 缺失**：可使用 default branch 做上下文，但 assessment 为 not_assessed。
3. **仓库组合正确但未真实消费**：consumption proof 缺失，repo-local pass 不上升为 cross-repo pass。
4. **传递范围爆炸**：报告 traversal bound 与未评估节点；不靠隐藏截断伪装完整。
5. **仓库本身已坏**：同次运行可做普通对照帮助归因，但不保存为冻结 baseline。
6. **LLM 提议错误测试**：由实际运行、零测试检测和 obligation coverage 揭示；保留失败与 not_run。
7. **同名仓/fork 冲突**：所有 run-local key 使用 `owner/repo`，pack 裸名仅是 adapter alias。

## Novelty and Defensibility

相比直接竞品，Marshal 不应声称独有“multi-repo context”或“companion PR awareness”。可防守的差异是三者组合：

1. 有方向、带来源的 impact path；
2. first-class coordinated change set 与明确的 ref provenance；
3. 对 intended combination 的 executable evidence 与 consumption proof。

CodeRabbit/Qodo 是 review-context 直接竞品；Bito 是 system knowledge 竞品；Zuul 是组合执行的相邻强基线。Marshal 的机会是把 review obligation、组合执行和解释性 evidence 合在一个 advisory workflow 中。

## Claim-Driven Validation Sketch

### Claim 1：真实组合执行提高跨仓故障发现

- **Minimal experiment**：在共享同一 upstream old/new update 的 BUMP 多 consumer 组上，对比单仓上下文、跨仓 context-only、完整 change-set + execution 三种条件。
- **Metrics**：break/no-break precision/recall/F1、affected-repo Recall@k/MRR、可执行证据覆盖率。
- **Expected evidence**：完整方案显著减少单仓与 context-only 的 false negative，收益来自准确 consumer/ref 组合而非单纯增加 token。

### Claim 2：显式 unknown 与 consumption proof 降低错误兼容结论

- **Minimal experiment**：加入真实构建确认的绿色 dependency updates、带 companion fix 的 coordinated changes、错误/default ref 和 distractor repos。
- **Metrics**：绿色/协调修复 false-positive rate、错误组合上的 false-compatible rate、unknown calibration、affected-file Recall@5。
- **Expected evidence**：完整方案在无法证明消费时拒绝报 passed，并在 companion fix 存在时少于只看 provider/default branch 的误报。

## Experiment Handoff Inputs

- **Must-prove claims**：C1 组合执行带来独立于 context expansion 的增益；C2 consumption proof/unknown 语义减少假绿和假红。
- **Must-run comparisons**：single-repo、linked-context-only、directional change set without execution、full method。
- **Primary data**：BUMP 多 client update groups + 重放确认的 green bot PR；OpenDev/Zuul coordinated changes 做外部有效性。
- **Auxiliary data**：Breaking Bad/Maracas 做静态 impact localization，REQBench 做 Python version compatibility；不得把静态分析标签当独立执行真值。
- **Highest-risk assumptions**：能否可靠构造 provider release -> 多 consumer change episode；能否在不重写每个项目 CI 的情况下证明 consumer 实际消费 provider 变化。

## Resource and Timeline Estimate

- **Model training**：无；不需要 GPU 训练。
- **Execution**：主要是 Docker、Maven/Java build 与 LLM review 调用；按 case 记录 wall time、CPU、磁盘、token 和费用。
- **Data footprint**：BUMP Zenodo tar 为 149.9 GB，完整加载官方提示至少 250 GB；pilot 应按 GHCR tag 拉取单例，不先下载全量。
- **First pilot**：8-10 个重复 upstream update group，每组 2-5 个 failing consumer，再补同族 green controls；先测可重放率和区分度，再决定是否扩到全部 39 组/104 cases。
- **Human work**：两名 reviewer 对模型 finding 做盲审和分歧仲裁；build/test oracle 仍以真实执行为准。

## Evidence Sources

- CodeRabbit Multi-Repo Analysis: https://docs.coderabbit.ai/knowledge-base/multi-repo-analysis.md
- Qodo Cross-repository Code Review: https://docs.qodo.ai/governance/cross-repo-code-review.md
- Greptile Cross Repo Context: https://www.greptile.com/docs/code-review/cross-repo-context.md
- Bito Knowledge Graph: https://docs.bito.ai/ai-architect/knowledge-graph.md
- Zuul Cross-Project Dependencies: https://zuul-ci.org/docs/zuul/latest/gating.html#cross-project-dependencies
- BUMP: https://github.com/chains-project/bump and https://zenodo.org/records/10041883
- Breaking Bad / Maracas dataset: https://zenodo.org/records/5221840
- REQBench: https://github.com/PCART-tools/REQBench

# 最终方案：Marshal Proof-Bound Cross-Repository Review

**日期**：2026-08-22
**设计状态**：可进入 D0 数据可行性研究；尚无实证，不可宣称通用跨仓能力或论文就绪

## 结论

Marshal 值得从单 PR review 扩展到 project-level cross-repo review，但核心不应是“把更多 repo 放进上下文”。CodeRabbit、Qodo、Greptile、Bito 已经覆盖了不同形式的 linked repositories、跨仓上下文或 impact tracing，Zuul 也已经覆盖跨项目依赖组合执行。

Marshal 最可防守的定位是：

> 对一组明确的多仓候选变化，只有当执行证据证明 consumer 实际消费了 intended provider snapshot 或其产物时，才允许把相关跨仓 obligation 标为 `passed`；否则必须显式报告 `not_assessed`、`not_run` 或 `unknown`。

这称为 **proof-bound pass**。Project Change Set、方向 edge、LLM reviewer 和 report 都是支撑件，不是并列贡献。

## Problem Anchor

- **Bottom-line problem**：Marshal 需要从“单个 PR 的问题检测”扩展为“同一大型项目内多个相互依赖仓库的联合审查”，能够回答一个变化会影响哪些仓库、应该验证哪组仓库版本，以及哪些结论有真实执行证据。
- **Must-solve bottleneck**：当前运行单位仍是单 `repo/ref`；跨仓 invariant 在自动 reporter 中会被记为 `not_run`，手工流程又默认在目标仓 tip 上执行，因此可能测试错误的仓库组合并产生假绿或假红。
- **Non-goals**：不建立永久企业知识图谱；不自动修改或合并协调 PR；不默认新增 hash、冻结 baseline、通用 contract 或 project gate；不把依赖关系命中直接当作 bug；不在首轮追求所有语言和构建系统。
- **Constraints**：保留 Marshal 现有 checkout 校验、零测试检测和降级语义；关系扫描不能替代真实构建、测试或模拟；第一阶段应 run-local、只读、advisory；仓库身份使用 `owner/repo`；拿不到真实组合时必须报告 unknown。
- **Success condition**：相较单仓审查和“只增加跨仓上下文”，该方案在真实可复现的跨仓破坏上提高受影响仓库召回和故障检测，同时控制绿色样本误报，并能展示实际执行的 repo/ref 组合和消费证据。

## Marshal 当前断点

| 断点 | 代码证据 | 后果 |
|---|---|---|
| 单仓输入 | `src/marshal_core/contracts.py:6-20` | `NormalizedEvent` / `DispatchJob` 只有一个 repo/ref |
| 异仓不执行 | `src/marshal_core/executor/reporter.py:121-130` | `location_repo != repo` 直接记 `not_run` |
| 关系无方向/ref | `src/marshal_pack_cowboy/pack.py:165-178` | `Contract` 不能决定 consumer/provider 或候选组合 |
| 异仓回退 tip | `.agents/skills/marshal/references/gate-flow.md:34-40` | 手工验证可能测试错误版本 |
| repo identity 不完整 | `src/marshal_core/adapters/github.py:7-18` | GitHub event 只保留裸仓名，fork/同名仓可能混淆 |

典型机制级失败：wallet PR 触发 `tx-encoding` contract，而 invariant 位于 node。自动 reporter 不执行；手工流程即使在 node tip 上跑绿，也可能只验证 node 自己生成并消费的编码，没有消费 wallet PR 产生的字节。Git SHA 能标识源码快照，但不能证明该次测试观察了另一仓的候选产物。

## Research Question

AI code review 在什么条件下有资格声称一个跨仓兼容性 obligation 已被验证？

回答不是“找到相关文件”或“命令退出 0”，而是以下证据链闭合：

```text
candidate changes
  -> sourced consumer -> provider edge
  -> exact repo/ref composition
  -> relevant verification obligation
  -> real build/test/simulation
  -> consumption proof
  -> assessment + coverage gaps
```

## 状态语义

静态影响和动态评估必须分开：

- **Impact**：`affected | not_affected | unknown`
- **Assessment**：`passed | failed | not_run | not_assessed`

判定规则：

- `affected` 需要有来源的 provider-to-consumer impact path；没有发现 edge 不等于 `not_affected`。
- `passed` 需要消费证明、相关工作实际发生、命令成功。
- `failed` 需要消费证明和相关命令失败；因果归因另行记录。
- `not_run` 表示已有可执行计划，但 checkout、环境或命令在相关观察前失败。
- `not_assessed` 表示没有 adapter、ref/edge 未解析或缺少消费证明。
- 一个 compile obligation 需要观察到编译阶段；test obligation 还必须有非零相关测试数。

项目聚合只使用：

- `incompatibility_found`
- `verified_for_planned_scope`
- `incomplete`

不复用现有 `GateDecision pass/block`，不新增 project gate。

## Run-Local 设计

以下只是研究原型的可变输入/输出形状，不是稳定 API、永久 contract 或数据库 schema。

### Project Change Set

| 字段 | 含义 |
|---|---|
| repository | canonical `owner/repo` |
| root | 本地 checkout |
| candidate revision | Git commit/ref；dirty worktree 明确标记不可重放 |
| base revision | changed repo 的 diff base |
| role | changed provider / candidate consumer |
| edge | `consumer -> provider` 和 dependency kind |
| edge evidence | manifest path、GAV selector、显式来源 |

V0 不生成内容 hash。干净状态复用 Git commit；dirty 状态不伪装成可重放快照。

### Verification Obligation

V0 由确定性 Maven planner 产生：consumer、provider、boundary kind、adapter、selector、expected observation、existing command reference 和 rationale。

LLM 不进入 V0。只有 D0 表明固定 obligation 不够时，V1 才允许 LLM 提议同一 typed shape；LLM 永远不能选择 ref、声明命令已运行或给出 `passed`。

### Evidence Record

至少记录：

- exact `owner/repo -> revision` composition；
- edge 及来源；
- requested/effective dependency selector；
- effective POM 与 dependency tree 的选择结果；
- 隔离依赖仓、resolved path；
- cwd、argv、exit code、compile/test measurement；
- `consumption.status = proved | not_proved` 及证据文件；
- impact、assessment、attribution 和 coverage gaps；
- `oracle_visibility = hidden_from_reviewed_system`，确保 BUMP label/log 不泄漏。

## V0：Deterministic Maven Research Slice

V0 只支持：

1. 显式 repo/ref 组合；
2. 显式或 POM 可确认的一跳 `consumer -> provider`；
3. released Maven dependency update；
4. 只读 advisory report。

Maven observation sequence：

```text
mvn -B -ntp -Dmaven.repo.local=<RUN_M2> \
  help:effective-pom -Doutput=<RUN_ROOT>/effective-pom.xml

mvn -B -ntp -Dmaven.repo.local=<RUN_M2> \
  dependency:tree -Dverbose -Dincludes=<GROUP>:<ARTIFACT> \
  -DoutputType=text -DoutputFile=<RUN_ROOT>/dependency-tree.txt
```

随后在同一隔离 `RUN_M2` 下执行已验证的 repository command。解析器必须确认 requested GAV、effective version、selected dependency、conflict/override 信息和相关工作量。若 candidate version 未生效，不能执行一个旧组合后报绿，而是 `not_assessed`。

对于同 GAV/SNAPSHOT 的未发布 provider，普通 Git SHA、版本字符串和测试不足以排除旧 `~/.m2` JAR。后续 adapter 应使用本次运行的空 Maven repository 构建 provider，并确认 consumer 从该路径解析。这里不需要新增 artifact hash；若无法隔离并证明路径，就不报 `passed`。

## D0 数据可行性研究

D0 不修改 Marshal 产品代码，只验证这条研究路线能否得到可靠数据。

### 输入和资源上限

- 3 个 update packs，来自 3 个 provider repos；
- 至少一个 compilation failure pack 和一个 test failure pack；
- 每 pack 至少 2 个 BUMP failing consumers；
- 目标每 pack 2 个完全相同 `(GAV, old, new)` 的 verified-green consumers；
- 单 image/command 尝试最多 30 分钟，case pair 最多 60 分钟；
- 每 pack 最多筛 30 个 green candidates；
- 总计最多 2 engineer-days；基础设施/网络/flaky 只做一次受控重试。

### 数据判定

- positive：pre pass、candidate fail；
- green：pre 与 candidate 各 `2/2` pass，且 dependency tree 确认 candidate version 生效；
- replay failure：BUMP positive 无法复现；
- green-control failure：找不到或无法验证绿色 consumer；
- adapter failure：组合/解析/命令机制失败；
- method failure：adapter 成功但 reviewer 判断错误。

### 研究决策

- **Proceed**：3 packs 全部重放，至少 6 positives，且至少 2 packs 各得到 2 个 green controls。
- **Narrow case study**：positive 可重放，但不足 2 packs 得到完整 green controls；只报告案例，不声称 balanced benchmark。
- **Stop dataset route**：positive attrition >20%、没有 pack 得到 2 个 green controls，或中位 pair time 超过上限。

这些标准只决定研究投入，不影响 merge、release 或产品 gate。

## 主评测设计

如果 D0 Proceed，再构建 18-24 个 pack，每 pack 2-4 positives + 2-4 verified greens。四个条件使用相同模型、prompt、repo 集、总预算和 fresh session：

| 条件 | repo 可见性 | direction edge | repo-local 执行 | candidate composition |
|---|---|---|---|---|
| C0 single-repo | provider only | no | provider only | no |
| C1 flat-context | provider + all consumers | no | yes, current consumer state | no |
| C2 directional-no-exec | same as C1 | yes | same as C1 | no |
| C3 proof-bound | same as C1/C2 | yes | yes | yes |

C1 可以搜索并执行 current consumer tests，避免人为削弱；但它不能把未消费 candidate provider 的结果称为跨仓验证。C3 相对 C2 唯一新增 intended composition 和 consumption proof。

核心指标：

- unsupported-pass / false-compatible rate；
- repo precision/recall/F1/MCC、green FPR；
- `no impact / compilation / test` macro-F1；
- pack-macro MAP、Recall@3/5、nDCG@5；
- evidence correctness、executable-evidence rate；
- tokens、tool calls、opened files、built repos、wall time 和费用；
- 三次重复的 prediction-set Jaccard 和分类一致率。

## 不外推原则

BUMP 只支持 Maven dependency-update claim。即使 D0/D1 成功，也不能声称 Marshal 已解决：

- Cargo/workspace 依赖；
- wallet/node wire encoding；
- schema/codegen；
- runtime/deploy relationship；
- coordinated PR scheduling；
- 通用跨语言 project review。

这些需要独立 adapter 和真实 artifact handoff 证据。Cowboy wallet/node 只能作为 post-D0 产品 case study。

## 分阶段路线

1. **D0**：3-pack 数据可行性，不改产品代码。
2. **D1**：development packs 上跑 C0-C3，校准指标和错误分类。
3. **D2**：held-out component split，形成可信结论。
4. **P1**：只有研究结果支持时，设计一个真实 Cowboy wallet-to-node artifact handoff。
5. **P2**：再评估 Cargo、CI checkout discovery、wire/schema adapter 和有界 traversal。

默认后移：LLM planner、自动关系发现、永久 graph、持久缓存、内容 hash、冻结 baseline、project gate。

## 最终判断

这是一个值得做的方向，但第一步不是重写 Marshal 架构，而是验证两件事：

1. flat multi-repo context 之外，direction 与 composition 是否带来可测增益；
2. proof-bound semantics 是否真正减少 unsupported compatibility conclusions。

设计已经足够进入 D0。未获得 D0 数据前，继续扩写大架构只会增加未经证实的复杂度。

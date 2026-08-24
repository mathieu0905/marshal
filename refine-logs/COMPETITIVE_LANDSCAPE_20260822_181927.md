# 跨仓代码审查竞品调研

**核验日期**：2026-08-22
**证据范围**：仅使用官方公开文档；`unknown` 表示官方资料未明确确认，不代表产品一定没有该能力。

## 核心结论

- 最直接竞品：CodeRabbit、Qodo、Bito。
- context 类竞品：Greptile。
- 强相邻系统：Zuul。
- 跨仓变更/现代化相邻产品：Sourcegraph Batch Changes、Moderne。
- Marshal 不能把 multi-repo context、companion PR/ref、dependency graph 或“能运行测试”单独当作差异。

## 能力矩阵

| 产品 | 关系模型 | Companion ref | 跨仓执行证据 | 公开限制 | 对 Marshal 的含义 |
|---|---|---|---|---|---|
| [CodeRabbit](https://docs.coderabbit.ai/knowledge-base/multi-repo-analysis) | 手工 linked repos；Pro+/Enterprise 可按 import、manifest、API usage 等自动发现，方向未明确 | 显式 PR/branch；自动同名 branch matching | 文档重点是 context/review findings；未确认执行 consumer against candidate provider | [Free/Pro/Pro+/Enterprise 为 0/1/10/20 linked repos](https://docs.coderabbit.ai/management/plans#linked-repositories) | linked context 与 companion refs 已是 table stakes |
| [Qodo](https://docs.qodo.ai/governance/cross-repo-code-review) | 自动/手工 relationship；明确 non-directional，agent 双向追踪 impact | 默认 main；PR 描述/ticket 可指定异仓 PR/branch | CI feedback 文档确认读取已有 checks/logs；候选组合执行 unknown | [手工每 repo 100 条；每次 review 选择最相关 10 条 active relationships](https://docs.qodo.ai/governance/cross-repo-code-review/repository-relationships) | Marshal 需要 sourced direction、覆盖缺口和真实组合证据 |
| [Greptile](https://www.greptile.com/docs/code-review/cross-repo-context) | Repo Cluster 全互联只读 context；可按共同贡献者建议 | unknown | cluster repos 是 read-only context；未确认组合候选 refs | cluster 至少 2 repos，总大小 20 GB | 不能用“多仓检索”作为主差异 |
| [Bito](https://docs.bito.ai/ai-architect/knowledge-graph) | 跨仓 knowledge graph，覆盖 downstream impact 与 code-review context | unknown | graph impact 已确认；跨仓 composition test unknown | 自托管规模信息见官方 prerequisites | Marshal 不应竞争永久企业图，而应强调 run-local proof |
| [GitHub Copilot code review](https://docs.github.com/en/copilot/concepts/agents/code-review) | 官方明确 current-repository context；MCP 可接外部信息，原生跨仓关系 unknown | 异仓 companion unknown | 临时执行环境可用工具；跨仓组合 unknown | setup timeout 等受产品限制 | 相邻 reviewer，不是当前最直接 cross-repo 对手 |
| [Sourcegraph Batch Changes](https://sourcegraph.com/docs/batch-changes) | 搜索或显式选择多仓 workspace，不建消费关系 | 可批量创建/跟踪 changesets | 每 repo/workspace 可执行容器命令 | Enterprise；面向大规模 changesets | 解决“批量改代码”，不是“review 结论证据边界” |
| [Moderne](https://docs.moderne.io/) | type-aware dependency 与 migration wave | 可批量创建 PR | 可执行 recipe/build/VerifyCompilation | 大规模企业场景 | 强在迁移与批改，不等于 PR-time composition proof |
| [Zuul](https://zuul-ci.org/docs/zuul/latest/gating.html#cross-project-dependencies) | 显式 `Depends-On` 构成跨项目 DAG | 消费已有 cross-project changes | 强：global repo state + speculative testing | CI scheduler，可配置 pipeline/window | 是组合执行强基线；Marshal 应区别于 merge gate/scheduler |

## 直接竞品解读

### CodeRabbit

已公开支持：manual/automatic repository linking、API/schema/shared-library 等 use cases、default branch、显式 companion PR/branch、同名 branch 自动匹配，并展示实际使用的 ref。其 linked repo 数量按 plan 限制。

不能再声称的差异：related repo discovery、更多 repo context、companion branch awareness。

### Qodo

已公开支持：自动/手工关系、Code/Service/Data/Pipeline 类型、跨仓 conflict finding、指定异仓 branch/PR。关系明确 non-directional，每次只分析与当前 PR 最相关的 10 条 active relationships。

可比较点：Marshal 的 edge 是否有来源和方向；超过分析范围的 repo 是否显式 `not_assessed`；是否能证明 consumer 消费候选组合。

### Bito

AI Architect 将 code/history/docs/observability/tribal knowledge 放入知识图，支持 system impact 和 code review enhancement。它更像长期 system knowledge 层。

Marshal 不应复制这个范围。更合适的边界是一次 review 内的 exact refs、临时 obligation 和可重放执行事实。

## 强相邻系统：Zuul

Zuul 使用 `Depends-On` 表达单向跨项目依赖，并在 dependent/independent pipeline 中用组合变化执行测试；同一 queue item 还保持一致的 global repo state。

因此不能声称“跨项目 DAG + exact composition + execution”本身独有。Marshal 的候选差异只能更窄：从 review impact path 生成 obligation，并将消费证明、unknown 与 coverage gap 作为 review evidence 呈现；它不做 merge scheduling。

## 推荐定位

> Marshal 是 proof-bound cross-repository reviewer：对 exact change set 生成有来源的验证义务，并要求每个跨仓 `passed` 结论引用消费候选 provider 的执行证据。

对外表达要加两条限定：

1. 这是基于公开文档的定位空位，不是对竞品内部实现缺失的证明。
2. 在 BUMP/Cowboy 实验完成前，它只是设计假设，不是性能优势。

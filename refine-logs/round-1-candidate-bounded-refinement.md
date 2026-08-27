# Round 1 Refinement

## Problem Anchor

- **Bottom-line problem**：给定一个源仓变更、项目内已知候选仓集合及其观察时点代码，判断并排序哪些候选仓需要检查、适配或联合验证。
- **Must-solve bottleneck**：当前路线把开放世界发现、因果正例、可靠负例和兼容变化同时设为项目包准入，偏离 Marshal 已知关系路由设定并导致极低产率。
- **Non-goals**：不做开放世界仓库发现；不要求完整影响集合；不把未观察修复的仓标负例；不要求每例 A3；不新增产品 gate、冻结 contract 或内容 hash。
- **Success condition**：复用统一排序接口，同时严格分开历史适配与因果破坏结论，并保留已有高质量三臂正例。

## Anchor Check

- 原始瓶颈仍是已知候选仓内的影响排序和证据验证；没有重新加入开放世界发现。
- E1/E2 分开 claim，避免把更容易的历史适配找回冒充因果破坏发现。

## Simplicity Check

- 主贡献保持为 candidate-bounded assessment。
- 删除 `unknown` schema 变化，复用 v1 `not_assessed`。
- 删除每例完整四臂要求；E3/E4 作为独立证据层。
- 不增加训练模块、关系图或新产品接口。

## Changes Made

1. 将“统一主任务”修正为“统一输入/输出接口，E1/E2 分开计分和解释”。
2. 明确当前候选目录由 targets 与 `DISTRACTORS` 合并产生，正式结果前必须做 provenance 审计；四个单例目录只进开发/敏感性集。
3. 明确当前 100 条全为 `test`，新增有向关系、源提交族、机制和修复模板的组级 split 设计。
4. v1 不使用 `unknown`；证据不足统一 `not_assessed`，`no_cross_repo_impact` 限于 E3。
5. 增加现有 evidence level 到 E0-E4 的 crosswalk。
6. 限制不完整标签下的指标，并固定 E2 端到端分母。

## Revised Proposal

完整修订设计见 `benchmarks/cross-repo-pr-impact/CANDIDATE_BOUNDED_DESIGN.md`。

# Refinement Report

**Problem**：Marshal cross-repository project review research and design
**Date**：2026-08-22
**Rounds**：3 / 5
**Final Score**：8.06 / 10
**Final Verdict**：`REVISE as paper / GO for D0 feasibility study`

## Final Thesis

Marshal 只有在结构化证据证明 consumer 的相关执行实际消费 intended provider snapshot/产物时，才允许把跨仓 obligation 标为 `passed`；否则必须显式 `not_assessed/not_run/unknown`。

## Score Evolution

| Round | Problem Fidelity | Method Specificity | Contribution Quality | Frontier Leverage | Feasibility | Validation Focus | Venue Readiness | Overall | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 7.5 | 5.0 | 6.0 | 5.5 | 5.0 | 5.0 | 5.0 | 5.70 | REVISE |
| 2 | 8.0 | 7.5 | 7.2 | 7.0 | 6.8 | 7.5 | 6.5 | 7.30 | REVISE |
| 3 | 8.5 | 8.4 | 8.0 | 7.5 | 7.8 | 8.5 | 7.0 | 8.06 | REVISE / GO D0 |

## Method Evolution Highlights

1. 将 change set、relation discovery、execution 和 benchmark 四个并列方向收敛为 proof-bound pass 一个中心规则。
2. 把 V0 砍到显式 edge + deterministic Maven adapter + evidence report。
3. 用 fresh dependency repository、effective POM、dependency tree 和 observed work 解决 stale/unused provider 假绿，不新增内容 hash。
4. 把 LLM 删除出 V0；只有 deterministic route 实测不足时才考虑 typed proposer。
5. 明确 BUMP 不支持 Cargo/wire/runtime 的外推。

## Pushback / Drift Log

| Reviewer Suggestion / Risk | Response | Outcome |
|---|---|---|
| 增加完整自动关系发现 | 会扩大首轮且不解决 proof 缺失 | deferred |
| 用 artifact hash 排除旧 cache | fresh isolated repository + in-run production/resolved path 已能处理具体失败 | rejected for V0 |
| 强化 LLM frontier component | V0 correctness 不需要模型；强加会稀释贡献 | removed |
| 用 BUMP 支撑一般跨仓 review | 数据只覆盖 Maven dependency update | claim narrowed |
| 继续抽象打磨到 9 分 | 没有 D0 数据无法获得 paper readiness | stopped at GO D0 |

## Remaining Weaknesses

- BUMP positive replay 与 verified-green mining 未执行。
- D0 可能因数据 attrition 失败。
- proof-bound semantics 的准确率/coverage tradeoff 未测量。
- Cowboy wallet/node 仍只有机制级失败说明，没有真实 artifact handoff case。
- 竞品比较基于公开文档，不能证明内部不存在相同机制。

## Raw Reviewer Responses

完整原文保存在：

- `refine-logs/round-1-review.md`
- `refine-logs/round-2-review.md`
- `refine-logs/round-3-review.md`

这些文件包含每轮分数、verdict、drift warning、blocking issues 和 raw response，未在本报告重复复制。

## Output Files

- Proposal：`refine-logs/FINAL_PROPOSAL.md`
- Review summary：`refine-logs/REVIEW_SUMMARY.md`
- Experiment plan：`refine-logs/EXPERIMENT_PLAN.md`
- Tracker：`refine-logs/EXPERIMENT_TRACKER.md`
- Competitors：`refine-logs/COMPETITIVE_LANDSCAPE.md`
- Datasets：`refine-logs/DATASET_RESEARCH.md`
- Pipeline summary：`refine-logs/PIPELINE_SUMMARY.md`

## Next Step

本轮用户要求仅调研和设计，因此不运行 D0、不写产品代码。下一实施授权应从 `EXPERIMENT_TRACKER.md` 的 R001-R006 开始，而不是直接改 Marshal 架构。

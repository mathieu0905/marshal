# Refinement Report

**Problem**：Marshal 跨仓数据集是否应由数据集提供已知候选仓，以及如何据此降低构造成本。
**Initial approach**：历史适配校准集与需要完整四臂项目包的因果旗舰集。
**Date**：2026-08-25
**Rounds**：2
**Final Score**：9.16 / 10
**Final Verdict**：READY

## Final Design

1. 数据集提供项目级候选仓目录和时点快照，不评测开放世界仓库发现。
2. 系统统一输出候选仓排序；E1 历史适配与 E2 因果破坏分别计分和解释。
3. 严格 A0/A1/A2 即可形成 E2；E3 有界负例和 E4 兼容变化是独立支持层。
4. schema v1 保持不变；证据不足使用 `not_assessed`，`no_cross_repo_impact` 限于 E3。
5. 正式运行前先完成 catalog provenance、关系组 split 和 evidence migration。

## Critical Audit Finding

当前 `materialize_impact_discovery_set.py` 由已知 targets 与手工 `DISTRACTORS` 的并集生成候选目录；四个目录只服务一条案例，100 条索引全部标为 `test`。因此现有材料可以开发和诊断，但还不能给出正式无泄漏产品分数。

## Outputs

- Canonical design：`benchmarks/cross-repo-pr-impact/CANDIDATE_BOUNDED_DESIGN.md`
- Task definition：`benchmarks/cross-repo-pr-impact/TASK_DEFINITION.md`
- Active plan：`benchmarks/cross-repo-pr-impact/PLAN.md`
- Experiment plan：`refine-logs/EXPERIMENT_PLAN.md`
- Reviews：`refine-logs/round-1-candidate-bounded-review.md`、`round-2-candidate-bounded-review.md`

## Remaining Work

- 审计或重建 12 个候选目录；
- 生成关系组和 split proposal；
- 将现有 case/workstream 迁移到 E0-E4；
- 在 development split 上运行首个真实候选代码排序。

不再优先扩大完整四臂项目包数量。

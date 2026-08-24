# Pipeline Summary

**Problem**：Marshal 的单 repo/ref review 无法对相互依赖的多仓变化给出可信的组合验证结论。
**Final Method Thesis**：跨仓 `passed` 必须绑定 exact composition、真实执行和 consumption proof。
**Final Verdict**：`GO for D0 feasibility study / REVISE as paper`
**Date**：2026-08-22

## Final Deliverables

- Proposal：`refine-logs/FINAL_PROPOSAL.md`
- Review summary：`refine-logs/REVIEW_SUMMARY.md`
- Experiment plan：`refine-logs/EXPERIMENT_PLAN.md`
- Experiment tracker：`refine-logs/EXPERIMENT_TRACKER.md`
- Competitive landscape：`refine-logs/COMPETITIVE_LANDSCAPE.md`
- Dataset research：`refine-logs/DATASET_RESEARCH.md`

## Contribution Snapshot

- **Dominant contribution**：proof-bound cross-repository review semantics。
- **Supporting product surface**：run-local change set + evidence/coverage report。
- **Intentionally rejected**：LLM in V0、自动 dependency graph、永久 contract、hash、冻结 baseline、project gate、通用多语言 adapter。

## Must-Prove Claims

- C3 是否降低 reproducible Maven dependency updates 上的 unsupported-pass / false-compatible。
- direction 与 intended composition 是否相对 flat context 提供独立准确率或效率价值。

## First Runs to Launch

1. R001：schema/oracle sanity。
2. R002-R003：一个 case 后扩到 3-pack positive replay。
3. R004-R006：green mining、2/2 replay、Maven proof adapter dry run。

## Main Risks

- verified-green controls 不足：2 engineer-days 后止损并降级 case study。
- BUMP 外推边界：只声称 Maven dependency updates。
- proof 过于保守：同时报告 assessment coverage，不能靠全部 abstain 获得低误报。

## Next Action

等待明确授权后运行 D0。当前不修改产品代码。

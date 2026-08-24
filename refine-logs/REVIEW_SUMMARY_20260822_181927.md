# Review Summary

**Problem**：将 Marshal 从单 PR review 扩展为可信的跨仓 project review。
**Initial Approach**：多仓 change set、关系发现、impact planning、组合执行和 benchmark。
**Date**：2026-08-22
**Rounds**：3 / 5
**Final Score**：8.06 / 10
**Final Verdict**：`REVISE as paper / GO for D0 feasibility study`

## Problem Anchor

跨仓 review 必须回答受影响 repo、实际验证的 repo/ref 组合和执行证据；不能在异仓 tip 或未消费 provider 变化的测试上给出兼容结论。

## Round-by-Round Resolution Log

| Round | Main Concerns | What Changed | Result | Remaining Risk |
|---|---|---|---|---|
| 1 | 架构愿景过大；consumption proof 无 adapter；BUMP claim 外推 | 主张收窄为 proof-bound pass；V0 限 Maven；LLM typed/optional | 5.70→7.30 | 可执行细节、greens |
| 2 | schema/argv/条件/D0 标准不够具体 | 加三个实验结构、Maven sequence、C0-C3、D0 止损 | 7.30→8.06 | 缺真实数据 |
| 3 | 方案已可启动，但 paper readiness 不能凭设计获得 | 停止继续扩写，转入 D0 计划 | GO D0 | replay/green attrition |

## Overall Evolution

- 从“project-level multi-repo system”收窄到一个主规则：跨仓 `passed` 必须有 consumption proof。
- 将 relation discovery、benchmark、change set、report 降为支撑件。
- 删除 V0 的 LLM、自动 graph、CI discovery、Cargo/wire/schema 和 project gate。
- 把 BUMP 的 claim 限制在 Maven dependency updates。
- 用四个受控条件隔离更多上下文、方向 edge 和真实 composition 的贡献。

## Final Status

- **Anchor**：preserved。
- **Focus**：tight；一个 dominant contribution。
- **Modernity**：intentionally conservative；V0 不需要 LLM。
- **Design readiness**：ready for D0 feasibility study。
- **Paper readiness**：not ready；没有实证。
- **Strongest part**：proof-bound state semantics 和对错误组合假绿的具体防线。
- **Weakest part**：verified-green controls 的可得性尚未测量。

## Key Files

- Final proposal：`refine-logs/FINAL_PROPOSAL.md`
- Experiment plan：`refine-logs/EXPERIMENT_PLAN.md`
- Competitive landscape：`refine-logs/COMPETITIVE_LANDSCAPE.md`
- Dataset research：`refine-logs/DATASET_RESEARCH.md`
- Raw reviews：`refine-logs/round-1-review.md`、`round-2-review.md`、`round-3-review.md`

# Round 1 Review: Candidate-Bounded Cross-Repository Benchmark

## Raw reviewer response

<details>
<summary>GPT-5.5 review</summary>

Verdict: REVISE。设计方向是对的，但还没到 READY；主要卡在候选目录泄漏、split 未落地、schema/输出语义不一致、证据层到现有标签的映射不够可执行。

| 项 | 分数 |
|---|---:|
| Problem Fidelity | 8.5 |
| Method Specificity | 7.5 |
| Contribution Quality | 8.5 |
| Frontier Leverage | 9.0 |
| Feasibility | 8.0 |
| Validation Focus | 8.0 |
| Venue Readiness | 7.0 |
| Overall | 8.18 |

阻断问题：

1. `TASK_DEFINITION.md` 当前明确两轨道不能混分，proposal 说改成“统一主任务”，容易把 E1 历史适配和 E2 因果破坏又混成一个结论。建议改成“统一输出接口和主排序指标，按证据层分开 claim”。
2. 候选集泄漏控制还不够。现有 12 个 catalog 中有四个只被一条案例使用。需要 catalog provenance；单例目录只能进开发或敏感性报告。
3. split 还没有实现。当前 100 条全是 `test`，目标频率强。没有按有向关系、机制模板和源提交族隔离前，不能形成正式结论。
4. 输出语义和 schema 不一致。proposal 允许 `unknown`，但 v1 schema 不允许。当前不需要改 schema；使用 `not_assessed`，等需要证据引用时再做 v2。
5. E1-E4 需要和现有 `specification_proven`、`implementation_proven`、`executed`、`ci_contrast_proven`、`coordination_proven` 做明确 crosswalk。

主集不能报告 precision、F1、specificity、false positive rate、accuracy 或 AP。额外预测只能记 `unjudged`。E3 只有完整 bounded denominator 时才能报告 precision/specificity。E2 执行准确率必须把漏报目标计入分母。

</details>

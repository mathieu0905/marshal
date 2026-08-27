# Round 2 Review: Candidate-Bounded Cross-Repository Benchmark

## Raw reviewer response

<details>
<summary>GPT-5.5 re-evaluation</summary>

Verdict: READY，限定为“设计方案可进入文档/实现 handoff”。这不是说当前 100 条已经可报正式产品结论；proposal 已正确把 catalog 审计和关系隔离 split 列为正式评测前置条件。

| 项 | 分数 |
|---|---:|
| Problem Fidelity | 9.5 |
| Method Specificity | 9.0 |
| Contribution Quality | 9.2 |
| Frontier Leverage | 9.5 |
| Feasibility | 8.8 |
| Validation Focus | 9.0 |
| Venue Readiness | 8.8 |
| Overall | 9.16 |

五个阻断项均已解决：

1. E1/E2 使用统一输出接口，但分开计分和解释。
2. catalog 要求来源规则、生成时间、纳入理由和使用案例数；单例目录排除出正式主分数；当前 targets + `DISTRACTORS` 生成事实已公开。
3. 当前 all-test 缺口已公开，正式结论前要求按有向关系、源提交族、机制/修复模板和根仓折叠做组级 split。
4. v1 使用 `not_assessed`，不再使用 schema 不支持的 `unknown`。
5. 已增加 existing evidence level crosswalk，并将 `coordination_proven` 降为 E0。

剩余建议：E0 明确为非评分候选线索层；`no_cross_repo_impact` 只能在 E3 bounded universe 中使用。两项已进入最终设计。

</details>

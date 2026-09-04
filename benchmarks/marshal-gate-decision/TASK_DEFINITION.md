# Marshal Domain-Pack Gate 评测任务

## 要测的能力

本评测不测通用代码 review，也不要求系统从开放世界发现关联仓库。给定一个真实 PR
差异、一个与该条结果标签独立构造的 Domain Pack，以及 Pack 声明的检查所需仓库快照，
受测系统需要完成：

1. 对变更分级；
2. 从 Domain Pack 中选择被触发的不变量；
3. 按 `location_repo` 路由并实际执行检查；
4. 解释 `pass`、`fail` 或 `not_run`；
5. 输出 `pass`、`block` 或 `escalate`。

主任务输出不是候选仓排序，不报告 MRR、Recall@K，也不把检查所在仓等同于“发现的受影响仓”。

## Public input

每条案例公开：

- `NormalizedEvent` 可表达的 PR 事件；
- PR 的代码补丁；
- 固定版本 Domain Pack，包含触发规则和完整不变量定义；
- Pack 所需的源仓和检查仓截止时点快照；
- 组合执行所需的公开依赖变化信息。

Domain Pack 可以直接声明 `location_repo`、测试路径和命令。这些是系统配置，不是隐藏答案。
隐藏的是：候选变更下检查究竟通过、失败还是无法执行，以及最后应作何判决。

## Private gold

每条案例隐藏：

- 期望的 tier、契约集合、不变量集合及路由；
- 候选组合下每条检查的真实结果；
- `pass/block/escalate` 判决；
- 支撑结果的三臂或等价真实执行证据；
- 维护者修复与失败签名，仅用于标签验证，不提供给受测系统。

严格破坏正例仍要求 A0 旧组合通过、A1 只采用源候选变化后失败、A2 只加入维护者目标
修复后恢复。A2 不是系统输入。

## Domain Pack 独立性

正式案例使用的规则必须先于该案例标签揭示形成，或者由只读取截止时点源码、依赖清单、
测试清单和 CI 配置的确定性规则生成。若某条案例参与了规则或生成器的设计，它只能进入
development，不能进入 evaluation 或 holdout。

本目录的首条 `mgd-dev-001` 是规则编写和端到端打通案例，因此明确属于 development；
它不能被改名冒充正式评测案例。

## 计分

分别报告：

- tier accuracy；
- contract set exact match；
- invariant set exact match；
- `invariant_id -> (location_repo, executor_kind)` route exact match；
- execution result exact match；
- verdict accuracy；
- 全链路 exact match。

集合按无序集合比较，不以 Domain Pack 的列表顺序计分。不存在任意加权总分。

## 当前 Marshal 的解释边界

当前 reporter 对 `location_repo != event.repo` 的检查会如实写入 `not_run`，随后得到
`escalate`。这是当前实现的真实诊断，但不是完整跨仓执行能力的正确答案。对一个已由真实
重放证明在候选组合下失败的检查，完整能力 gold 仍是 `fail -> block`；当前 Marshal 应表现为
“plan/route 命中，execution/verdict 未命中”，以便数据集直接指出研发缺口。

## 集合要求

正式发布前，集合至少同时包含：

- 会触发且检查失败的 `block` 案例；
- 会触发且检查通过的 `pass` 案例；
- 检查确实无法运行或证据不完整的 `escalate` 案例；
- 相同 Pack 下不触发的近邻变更；
- 本地检查与异仓检查；
- 明确失败与其他检查 `not_run` 同时存在、仍应 `block` 的优先级案例。

不得用全是破坏正例的数据发布误报结论，也不得用全是异仓 `escalate` 的集合让恒定预测器
获得高分。

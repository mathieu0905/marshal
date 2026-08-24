# SLF4J 项目包第四仓复核

评估日期：2026-08-25

## 结论

RabbitMQ JMS Client 可以从“影响未知”重标为正例。在原有单元测试没有判定日志退化的情况下，本轮加入一个只检查真实日志提供方初始化的固定合同，得到严格三臂：

| 臂 | SLF4J API | Logback | 结果 |
|---|---:|---:|---|
| A0 | 1.7.36 | 1.2.11 | 通过，115 项测试 |
| A1 | 2.0.0 | 1.2.11 | 失败，115 项中只有提供方合同 1 项失败 |
| A2 | 2.0.0 | 1.4.0 | 通过，115 项测试 |

A1 明确报告 Logback 1.2.11 的旧式绑定被忽略，`LoggerFactory` 返回 `NOPLoggerFactory`，而合同要求实际配置的 `LoggerContext`。A2 只采用维护者合并的 PR 190 中 Logback 1.2.11 到 1.4.0 的修改，保持 SLF4J 2.0.0 和其余目标内容不变，同一合同恢复。

因此，现有 SLF4J 闭集达到四个已判定根仓：

- 正例：`jadler-mocking/jadler`、`rabbitmq/rabbitmq-jms-client`；
- 限定负例：`Password4j/password4j`、`diffplug/spotless`。

这项补充不改变 Password4j 和 Spotless 原有标签上限，也不把 PNC 的编译证据提升成负例。

## 历史因果链

RabbitMQ PR 189 在 2022-08-22 合并，只把 `slf4j-api` 从 1.7.36 更新到 2.0.0。PR 190 在 2022-08-29 合并，只把测试范围的 Logback Classic 从 1.2.11 更新到 1.4.0。两个 PR 的 Git 树连续，A1 合并树与 A2 父树完全相同。

PR 190 的正文列出 Logback 1.4.0 中“升级到 SLF4J 2.0.0”的上游提交。虽然目标 PR 是自动产生的，RabbitMQ 维护者实际合并了它；A2 采用的也是该目标仓提交本身，而不是数据集作者设计的依赖组合。

一周后，维护者选择了另一条最终策略：移除直接 SLF4J 依赖，恢复 Logback 1.2.11，并依赖 RabbitMQ Java Client 提供 SLF4J 1.7.x。因此这条关系的标签是“维护者合并过的短期提供方协调修复”，不是“项目最终保留 SLF4J 2”。`later-reversion.patch` 保存该边界证据。

## 候选框

本轮核对的现有候选框共有六个独立根仓。Jadler、Password4j、Spotless、RabbitMQ 与 PNC 来自前一轮 BUMP 和历史筛选；FSE 只有 `PhantomThief/buffer-trigger` 一条 `slf4j-api` 记录，但它对应 1.7.35 到 1.7.36，不是本包的 1.7.36 到 2.0.0 合同。

RabbitMQ 是唯一能在现有框中新增高强度判定的根仓。PNC 仍因测试不进入生产日志路径而拒绝。PhantomThief 的记录是时序断言失败，而且 1.7.36 没有相关 API Java 行为变化，不能移入本包凑数。完整逐仓判断见 `candidate-frame.jsonl`。

## 证据边界

新增测试不是目标仓历史原生测试。它之所以必要，是因为原有 114 项测试在日志提供方退化为无操作实现后仍然全部通过，无法区分“兼容”和“静默丢失日志”。本合同直接执行 `LoggerFactory` 和目标依赖图中的 Logback，判定的正是原负标签撤销时缺失的行为。

115 项测试不包含需要 RabbitMQ 服务的集成测试。本正例只证明日志提供方初始化合同，不外推到消息代理集成行为。

该结果使 SLF4J 达到四个已判定仓，但公共台账、正式拆分和完整项目包状态仍需主线程统一验收；本工作流没有修改公共台账，也没有替代独立语义复核。

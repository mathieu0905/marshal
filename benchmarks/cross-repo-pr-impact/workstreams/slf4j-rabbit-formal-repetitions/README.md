# RabbitMQ 日志提供方合同正式重复

本工作流只重复 `rabbitmq/rabbitmq-jms-client` 的新增日志提供方合同，不重新裁决其他 SLF4J 消费仓。

固定三臂为：

- A0：`41b2abf72827e123c8c472d3f07b30ac3bc24be0`，SLF4J 1.7.36 与 Logback 1.2.11；
- A1：`4fa8b7fea9971db148c98a5a3816a3c850332a92`，SLF4J 2.0.0 与 Logback 1.2.11；
- A2：`c2695a908a60b5c3db041afa193399cceb18f10c`，SLF4J 2.0.0 与 Logback 1.4.0。

每轮、每臂都从固定提交建立新检出，并加入同一个 `LoggingProviderCompatibilityTest`。每轮使用独立的 Maven 本地仓库副本。执行先保存解析后的 SLF4J 与 Logback 依赖树，再运行完整 `mvn clean test`。

验收要求是三轮均满足：A0 的 115 项测试通过；A1 执行 115 项测试，唯一失败是新增合同发现 `NOPLoggerFactory`；A2 的 115 项测试全部恢复。

## 历史边界

A2 是维护者合并的 PR 190，只把测试范围的 Logback 从 1.2.11 升到 1.4.0。但一周后，维护者提交 `7075e98c50a70e05cd3e4890fd49d7afe2ec9aa0` 移除了直接 SLF4J 依赖并回到 Logback 1.2.11，依赖 RabbitMQ Java Client 提供 SLF4J 1.7.x。正式重复证明 A2 在固定 SLF4J 2.0.0 输入下可恢复日志提供方合同，不把这条短期策略写成项目最终选择。

三次重复是稳定性测量，不是三个独立关系，也不替代独立语义复核。

## 结果

三轮共执行 9 个完整 Maven 测试命令，累计执行 1,035 项测试；依赖解析与预期方向均为 9/9。每轮都是 A0 的 115 项通过、A1 的 115 项中只有新增合同 1 项因 `NOPLoggerFactory` 失败、A2 的 115 项全部恢复。结果位于 `results/slf4j-rabbit-contract-formal-repetitions-2026-08-25/`。

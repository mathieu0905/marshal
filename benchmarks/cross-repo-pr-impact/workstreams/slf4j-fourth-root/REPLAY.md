# RabbitMQ JMS 三臂重放

## 固定输入

- A0：`rabbitmq/rabbitmq-jms-client@41b2abf72827e123c8c472d3f07b30ac3bc24be0`；
- A1：`rabbitmq/rabbitmq-jms-client@4fa8b7fea9971db148c98a5a3816a3c850332a92`；
- A2：`rabbitmq/rabbitmq-jms-client@c2695a908a60b5c3db041afa193399cceb18f10c`；
- Java 11；
- Maven 3.9.8。

A1 是目标仓 PR 189 的头提交，只把 `slf4j-api` 从 1.7.36 更新到 2.0.0。该提交与 PR 189 的合并提交 `f53fb2a7ef2dc0c452c682780b18e227feeae9dd` 的 Git 树相同。

A2 是紧随其后的 PR 190 合并提交；该 PR 的变化提交为 `a127ab8221ab8544d7db257f75dee0fc9b02aa8f`，只把测试范围的 Logback Classic 从 1.2.11 更新到 1.4.0。A2 的父提交就是 PR 189 的合并提交。A1 合并树与 A2 父树相同，因此 A1 到 A2 的内容差异只有这一行依赖协调修改。

## 测试装置

在三棵检出树中加入相同的 `LoggingProviderCompatibilityTest.java`。测试执行 `LoggerFactory` 初始化，并要求实际工厂为 `ch.qos.logback.classic.LoggerContext`。它不修改生产代码，也不把“普通测试仍绿”误当成提供方兼容。

## 执行

```bash
./run-rabbit-three-arm.sh \
  <A0 检出树> \
  <A1 检出树> \
  <A2 检出树> \
  <结果目录>
```

脚本对每臂先记录依赖树，再执行包含原有单元测试和新增提供方断言的 `mvn -B clean test`。预期退出方向是 A0 为 0、A1 为 1、A2 为 0。

本次执行的解析输入为：

| 臂 | SLF4J API | Logback Classic | Logback Core |
|---|---:|---:|---:|
| A0 | 1.7.36 | 1.2.11 | 1.2.11 |
| A1 | 2.0.0 | 1.2.11 | 1.2.11 |
| A2 | 2.0.0 | 1.4.0 | 1.4.0 |

## 历史边界

PR 190 的 Logback 1.4.0 更新确实由维护者合并，但只在主分支保留一周。后续维护者提交 `7075e98c50a70e05cd3e4890fd49d7afe2ec9aa0` 移除了直接 `slf4j-api` 依赖，并退回 Logback 1.2.11，让 RabbitMQ Java Client 的传递依赖决定 SLF4J 1.7.x。这证明 A2 是真实但短暂的维护者合并适配，不代表项目最终承诺长期采用 SLF4J 2。

后续提交不能作为本三臂的 A2，因为它改变了源输入，无法满足“固定 SLF4J 2.0.0，只加入相邻仓修复”的干预要求。

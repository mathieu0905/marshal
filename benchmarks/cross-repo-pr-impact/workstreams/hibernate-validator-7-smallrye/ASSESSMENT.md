# Hibernate Validator 7 与 SmallRye Config 筛选结论

## 结论

Hibernate Validator `6.2.3.Final -> 7.0.0.CR1` 对固定 SmallRye Config 提交构成可重放的破坏关系，但当前历史 A2 **不是精确维护者修复**，不能作为严格三臂正例升格。

固定消费仓提交为 `dfedeac7d08c944c45d9f57de943e70ae0719dad`。A0 只把测试依赖固定为 Hibernate Validator 6.2.3.Final，`ValidateConfigTest` 四项全部通过；A1 只把该依赖改为 7.0.0.CR1，同四项全部以 `javax.validation.NoProviderFoundException` 出错。两臂实际类路径都保留 Validation API 2.0.2 和 EL 3.0.4，区别只有 Hibernate Validator 版本。

后继提交 `b9f347561893d39ed396e53e6f12ad941b3139f7` 的完整臂在把 Hibernate Validator 固定回同一个 7.0.0.CR1 输入后，四项测试全部恢复。破坏和恢复方向成立。

## 为什么拒绝“精确修复”

该后继提交题为 `Move to Jakarta`，修改 98 个路径、增加 207 行并删除 207 行。Validator 子树只有 4 个路径、11 行增加和 11 行删除；其余 94 个路径还同时迁移 CDI、JSON、示例、测试套件、工具模块与文档。根 POM 同步发生以下平台变化：

- `smallrye-parent` 改为 `smallrye-jakarta-parent`；
- MicroProfile Config 2.0 改为 3.0.1；
- SmallRye Common 1.8.0 改为 2.0.0-RC1；
- SmallRye Testing Utilities 1.0.0 改为 2.0.0-RC1；
- 项目版本 2.8.2-SNAPSHOT 改为 3.0.0-SNAPSHOT。

因此，完整提交恢复只能证明广泛 Jakarta 迁移吸收了该破坏，不能把整次提交当成只针对 Hibernate Validator 的精确维护者修复。

## 最小消融

两个消融使用相同的 Hibernate Validator 7.0.0.CR1 和同一个四项测试：

| 实验臂 | 输入 | 结果 |
| --- | --- | --- |
| Validator 子树迁移 | 基于 `dfedeac7`，只应用 Validator 的 4 个文件：Validation API 3.0.1、EL 4.0.2、生产代码与测试的 `javax.validation` 到 `jakarta.validation` 导入迁移 | 4 项通过 |
| 其余平台迁移 | 保留完整提交中的其余 95 个路径，但撤掉 Validator 导入迁移，并保留 Validation API 2.0.2 与 EL 3.0.4 | 4 项全部以同一 `NoProviderFoundException` 出错 |

这说明恢复所需片段位于 Validator 自身的 API、EL 与命名空间迁移，根级 MicroProfile Config、SmallRye Common 等升级不是该失败的恢复原因。但四文件片段是从广泛提交中抽取的合成消融，并不是独立的历史维护者提交，不能据此把历史 A2 改称精确修复。

## 执行边界

首次尝试运行依赖模块的全部测试时，SmallRye Core 有两项 HTTPS 测试因本机证书链失败，Validator 模块尚未执行。该结果只作为未计入的基础设施记录保留。有效筛选先以 `-DskipTests` 编译和安装 `validator` 及其依赖模块，再只执行 FSE 记录对应的 `io.smallrye.config.validator.ValidateConfigTest`。这保留了目标编译与运行合同，同时排除了无关网络测试。

所有新克隆、Maven 仓库、构建输出、`TMPDIR` 和 `java.io.tmpdir` 都位于项目内 `.work/hibernate-validator-smallrye/replay-20260825/`。没有使用或复制全局 Maven 仓库。结果位于 `results/hibernate-validator-7-fse-smallrye-replay-2026-08-25/`。

最终计数：严格三臂正例 0；可重放破坏关系 1；广泛迁移恢复锚点 1；合成最小恢复消融 1。候选保留为高证据破坏线索，不进入要求“精确维护者 A2”的正式项目包。

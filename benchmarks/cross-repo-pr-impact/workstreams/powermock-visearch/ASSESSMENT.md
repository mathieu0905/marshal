# PowerMock 到 ViSearch 的因果筛选

更新日期：2026-08-24

## 结论

本轮正式接纳零条。固定 `visenze/visearch-sdk-java` 提交 `5f6e72e` 后，公开论文记录的失败可以复现，但维护者提交 `8fdd482` 不能在只升级 `powermock-module-junit4` 的条件下恢复同一测试合同。三臂实际方向是“通过、失败、仍然失败”，不满足 A0/A1/A2 正例定义。

此外，目标前置提交还显式声明了 `org.powermock:powermock-api:1.6.4`。该坐标发布的是聚合 POM，Maven Central 没有对应 JAR；干净依赖解析会在测试前失败。公开论文执行环境显然曾越过这一历史依赖问题，但复制包只提供约 10GB 的虚拟机镜像，没有给出该本地仓库条目的来源。为了核对论文失败签名，本轮在隔离缓存中放入一个无代码的聚合占位 JAR，并让三个诊断臂共同使用。这个恢复不改变项目源码，也不参与臂间差异，但不能冒充严格 A0，因此即使 A2 恢复也仍需进一步核实原始环境。

计数为：严格因果正例零条、限定负例零条、A3 零条。同源公开记录中的其他目标没有独立维护者修复证据，只能保留为未知，不能因为共享失败签名而计作负例。

## 公开线索与提交边界

线索是 `fse2024-behavioral-0615`。公开记录给出的变化为 `org.powermock:powermock-module-junit4 1.6.4→1.6.5`，目标为 `com.visenze:visearch-java-sdk`，失败测试为 `ViSearchTest`，异常是：

`MockingFrameworkReporterFactoryImpl could not be located in classpath`

目标仓历史中，维护者提交 `8fdd4826f7719be850614fc5359bdf4cca32a20c` 的说明是“修复依赖问题”，父提交正是 `5f6e72ec5d16987f4cee959ef2063a20989cb40f`。该提交只有一个修改：从 `pom.xml` 删除显式 `org.powermock:powermock-api:1.6.4` 六行依赖声明。它没有修改测试、生产代码、`powermock-module-junit4` 或 `powermock-api-mockito` 的版本。

PowerMock 1.6.5 的发布提交为 `f075346a5524e68b33ad6f2346fd5ed2111d7ad0`。与 1.6.4 相比，1.6.5 在 JUnit 运行器中新增框架报告器装载：核心代码按固定类名加载 `org.powermock.api.extension.reporter.MockingFrameworkReporterFactoryImpl`。Mockito 对应实现位于 1.6.5 新增的 `api/mockito-common` 模块中。

## 执行结果

所有测试臂固定：

- 目标提交 `5f6e72e`；
- Java 8；
- 原生命令 `mvn test`；
- 同一个隔离 Maven 缓存；
- 除指定依赖版本与维护者补丁外，目标代码完全相同。

结果如下：

| 执行 | `module-junit4` | `api-mockito` | 目标修改 | 结果 |
|---|---:|---:|---|---|
| 干净基线诊断 | 1.6.4 | 1.6.4 | 无 | 测试前解析失败：缺少 `powermock-api:jar:1.6.4` |
| A0 恢复环境 | 1.6.4 | 1.6.4 | 无 | 71 项测试通过 |
| A1 恢复环境 | 1.6.5 | 1.6.4 | 无 | `ViSearchTest` 以公开异常失败 |
| A2 恢复环境 | 1.6.5 | 1.6.4 | 只删除显式 `powermock-api` | 与 A1 相同异常失败 |

A1 精确复现了论文记录，说明依赖升级的失败线索本身可信。A2 则直接否定了“`8fdd482` 是该升级的维护者恢复”这一假设。

## A2 为什么不能恢复

A1 与 A2 的依赖树都保留 `powermock-api-mockito:1.6.4`，后者继续带入 `powermock-api-support:1.6.4`。与此同时，`powermock-module-junit4:1.6.5` 带入 1.6.5 的 JUnit 公共模块、核心模块和反射模块。运行器来自 1.6.5，要求报告器工厂；Mockito 扩展仍来自 1.6.4，不含该实现类。

维护者删除的是没有代码的 `powermock-api` 聚合坐标。它既不会把 `powermock-api-mockito` 升到 1.6.5，也不会提供缺失实现。因此删除后出现同一异常符合依赖图，而不是偶发环境失败。

如果额外升级 `powermock-api-mockito`，就已经超出维护者 `8fdd482` 的真实修改，不能拿来改造 A2。数据集要求 A2 是维护者精确修复，因此本轮到此拒绝。

## 同源目标、负空间与 A3

公开候选框中还有七条 `module-junit4 1.6.5` 的同签名记录：`fse2024-behavioral-0611`、`0612`、`0613`、`0614`、`0616`、`0617` 和 `0618`。它们证明该混合版本错误在多个客户端中发生，但公开记录没有给出各自的维护者恢复提交，也没有证明某个客户端完整执行了变化路径后仍兼容。

因此这些目标全部保持未知：

- 不能把“没有找到修复”写成负例；
- 不能把同一异常的多个客户端拆成多个独立因果正例；
- 不能用任意绿色测试替代维护者 A2。

本轮没有找到独立且被测试覆盖的相邻 PowerMock 变化，所以 A3 为零。普通绿色构建不构成变化代码覆盖证据。

## 证据边界

机器结果位于 `results/powermock-visearch-screening-2026-08-24/`，保留干净解析日志、三个恢复环境测试日志、三份依赖树、每臂 POM、臂间差异、维护者原始差异和退出状态。

当前证据足以拒绝该候选，但不证明论文虚拟机中的 `powermock-api` 条目就是空 JAR。若未来完整恢复虚拟机中的 Maven 仓库，应重新核对该条目的内容和来源；除非严格 A0 可执行且维护者原始 A2 能恢复，否则不能改变本轮零接纳结论。

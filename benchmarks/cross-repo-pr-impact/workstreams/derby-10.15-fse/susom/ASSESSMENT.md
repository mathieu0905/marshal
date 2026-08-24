# Derby 10.15 到 susom/database 的因果重放

评估日期：2026-08-25

## 结论

本轮建立一条高证据跨仓机制锚点。Apache Derby 提交 `5a6efccce73b05ac7a27512563868192303f564d` 把 `org.apache.derby.jdbc` 包从 `derby.jar` 移到 `derbytools.jar`。`susom/database` 仍让 Hikari 显式加载 `org.apache.derby.jdbc.EmbeddedDriver`，但只声明 `org.apache.derby:derby`，因此从 Derby 10.14.2.0 升到 10.15.1.3 后无法找到该类。维护者提交 `811158529d847bde72fc97c5701d411301f395b4` 只增加 `derbytools` 测试依赖；将同一修复移植到固定目标基线后，原生测试恢复。

目标侧固定发布版的 A0/A1/A2 已成立，但源侧尚未构建 `5a6efcc` 的父、子提交制品。正式旗舰计数因此仍为零；当前计数为一个高证据机制锚点、零个源提交隔离案例、零个限定负例、零个 A3。它既不是多仓关系族，也不能在补完源提交隔离前进入旗舰正式集。

## 目标基线恢复

FSE 记录 `fse2024-behavioral-0310` 没有保存客户端 Git 修订。这里采用 `b9aac59d053af41144f59c77a7f9053f8fe61102`，即项目自身把 Derby 升到 10.14.2.0 之前的最后一个提交。该状态同时匹配公开执行的全部可判别指纹：

- POM 中 Derby 为 10.13.1.1，HikariCP 为 2.7.9；
- Hikari 抛出异常的位置为 `HikariConfig.java:512`；
- `DatabaseProvider.createPool()` 的显式驱动加载位于第 1124 行；
- `DatabaseProviderVertx.pooledBuilder()` 位于第 102 行；
- `VertxLoggingTest.testMdcTransferToWorkerDatabase()` 的调用位于第 102 行；
- 测试类、方法和异常文本均与 FSE 工作簿一致。

这些指纹把目标状态夹定在维护历史中的同一代码区间，但公开材料仍不足以证明唯一 SHA。`b9aac59` 是该区间内、目标自身升级前的最后状态，因此本包称其为“重建基线”，不冒充 FSE 未公开的原始修订。

## 精确源变化

源提交 `5a6efcc` 的标题明确为把 `org.apache.derby.jdbc` 移入 `derbytools.jar`。提交中的制品内容清单显示：

- `EmbeddedDriver.class` 从 `derby.jar` 清单删除；
- 同一个类加入 `derbytools.jar` 清单。

发布制品与之吻合：10.14.2.0 的 `derby.jar` 含该类；10.15.1.3 的 `derby.jar` 不含；10.15.1.3 的 `derbytools.jar` 含该类。A1 只换发布制品后以缺类失败，A2 只把维护者选择的制品放回类路径后通过。因此 `5a6efcc` 足以解释本关系，不需要把 Derby 10.15 的其余发布变化纳入标签。

本轮没有从源仓构建 `5a6efcc` 的父、子提交制品。提交清单差异、正式发布制品内容和目标侧单因素恢复共同支持这一机制解释，但不能实验性证明“只加入 `5a6efcc`”就足以产生失败。进入旗舰正式集前必须另做父、子制品构建，并在同一目标基线上重放；当前不得把它写成已完成的源提交隔离案例。

## 维护者修复纯度

维护者先在 `18921de101938afbb6658246a5d09e8acc283e48` 把 Derby 升到 10.16.1.1，随后以 `8111585` 增加 `derbytools`。`8111585` 只修改 `pom.xml`，净增加六行；没有生产代码、测试代码或其他依赖变化，也没有显式增加 `derbyshared`。

合并提交 `f60723eb53f5aba831d18f5f3d79ceecae4bb879` 同时升级 PostgreSQL、Jetty、Vert.x 并删除 Travis 配置，不能作为精确 A2。本包使用 `8111585` 的单一依赖增量，并把其版本与 A1 对齐到 10.15.1.3，避免把 10.15 到 10.16 的发布差异带入恢复臂。原始补丁和版本对齐后的执行补丁分别保存在 `maintainer-8111585.patch` 与 `susom-derbytools-maintainer-repair.patch`。

## 三臂结果

目标侧三臂固定 Java 11.0.30、Maven 3.9.8、目标提交、测试选择器以及除 Derby 发布版输入外的全部依赖。执行命令是项目原生 Maven 测试：

```text
mvn -Dfindbugs.skip=true -Dtest=com.github.susom.database.test.VertxLoggingTest#testMdcTransferToWorkerDatabase -DfailIfNoTests=false test
```

仅跳过与目标合同无关的旧 FindBugs 检查；生产代码编译、测试代码编译和原生测试均实际执行。

| 臂 | Derby 输入 | 目标输入 | 结果 |
|---|---|---|---|
| A0 | 10.14.2.0 | 重建基线 | 通过，1 个测试 |
| A1 | 10.15.1.3 | 同一重建基线 | 失败，1 个错误；`Failed to load driver class org.apache.derby.jdbc.EmbeddedDriver` |
| A2 | 10.15.1.3 | 只增加匹配版本的 `derbytools` | 通过，1 个测试 |

## Java 8 边界

FSE 公开执行使用 Java 8。本包另行在 Java 8u482 下重放：A0 通过，A1 以完全相同的缺驱动签名失败，因而复核了公开观察；A2 会在加载 10.15.1.3 的 `EmbeddedDriver` 时收到 class file 53，而 Java 8 只支持到 52。Derby 10.15 的制品本身要求 Java 9，故不可能在 Java 8 下形成有效恢复臂。

为保持目标侧三臂只改变 Derby 发布版输入，比较统一使用 Java 11。不能把 Java 8 下 A2 的版本错误解释成维护者修复无效，也不能把 Java 11 的三臂结果描述为对 FSE 原始环境的逐字节重放。

## 负空间与证据边界

本轮没有限定负例，也没有 A3。未声明 `derbytools` 的其他仓库、普通绿色构建或没有维护者修复的客户端都不能自动变成负例。`susom/database` 的维护者修复晚于公开失败数年，但时间晚不改变其补丁纯度；该时间差必须在正式数据中保留，不能写成即时协调响应。

可重复运行器为 `run_screening.sh`。结果目录 `results/derby-10.15-fse-susom-2026-08-25/` 保存三臂日志、Surefire XML、测试输出、依赖树、输入补丁、Java 8 环境观察和制品内容证据。

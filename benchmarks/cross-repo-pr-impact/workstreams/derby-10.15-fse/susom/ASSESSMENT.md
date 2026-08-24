# Derby 10.15 到 susom/database 的因果重放

评估日期：2026-08-25

## 结论

本轮建立一条高证据跨仓机制锚点。Apache Derby 提交 `5a6efccce73b05ac7a27512563868192303f564d` 把 `org.apache.derby.jdbc` 包从 `derby.jar` 移到 `derbytools.jar`。`susom/database` 仍让 Hikari 显式加载 `org.apache.derby.jdbc.EmbeddedDriver`，但只声明 `org.apache.derby:derby`，因此从 Derby 10.14.2.0 升到 10.15.1.3 后无法找到该类。维护者提交 `811158529d847bde72fc97c5701d411301f395b4` 只增加 `derbytools` 测试依赖；将同一修复移植到固定目标基线后，原生测试恢复。

目标侧固定发布版的 A0/A1/A2 与源提交隔离三臂均已成立。源提交隔离使用同一工具链分别构建 `8f3b7b2` 与 `5a6efcc`，再把两侧制品以同一测试版本装入相互隔离的 Maven 仓库。固定 Susom 基线在父制品上通过，在子制品上以 `EmbeddedDriver` 缺失失败，只加入同侧 `derbytools` 后恢复。因此当前计数为一个源提交隔离正例。它仍不是多仓关系族；项目包是否进入旗舰正式集，继续服从仓库数量、负空间和重复执行等包级标准。

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

源提交隔离使用 JDK 9+181、Ant 1.10.15 和 JUnit 3.8.2，对父子提交执行相同的 `clobber buildsource buildjars`。两侧构建均成功。父提交的 `derby.jar` 含 `EmbeddedDriver`；子提交的 `derby.jar` 不含该类，而子提交的 `derbytools.jar` 含该类。父子制品都以 `10.15.0.0-exact` 安装到各自独立的 Maven 仓库，`derby` 的测试 POM 只声明同侧、同版本的 `derbyshared`，没有混入正式发布版制品。

旧构建首次因源码树缺少 JUnit 3.8.2 在 `build.xml:163` 中止。该失败被保留；补入 JUnit 是两侧完全相同的构建前置，不改变源码或父子比较。构建过程中缺少 `svnversion` 只产生相同警告，父子均完成全部制品构建。

## 源提交隔离三臂

三个目标臂固定 Susom 提交、Java 11、测试选择器和除 Derby 输入外的所有依赖。父臂与子臂的目标 `pom.xml` 差异逐字节相同，均只把 Derby 改为 `10.15.0.0-exact`；恢复臂在子臂上增加同版本 `derbytools`。

| 臂 | 源制品 | 目标结果 |
|---|---|---|
| 父 | `8f3b7b2` 的 `derby` 与 `derbyshared` | 通过，1 个测试 |
| 子 | `5a6efcc` 的 `derby` 与 `derbyshared` | 失败，1 个错误；`Failed to load driver class org.apache.derby.jdbc.EmbeddedDriver` |
| 子加恢复 | 子制品再加入同侧 `derbytools` | 通过，1 个测试 |

这组结果实验性证明 `5a6efcc` 对当前目标破坏充分，且维护者选择的 `derbytools` 依赖对恢复充分。

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

发布版重放运行器为 `run_screening.sh`，结果目录为 `results/derby-10.15-fse-susom-2026-08-25/`。源提交隔离运行器为 `run_source_commit_isolation.sh`，新结果目录 `results/derby-10.15-fse-susom-source-isolation-2026-08-25/` 保存父子构件、构建日志、工具链失败尝试、制品清单、目标三臂日志、Surefire XML、依赖树、输入补丁和机器摘要。

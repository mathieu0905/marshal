# HSQLDB FSE 2024 关系族历史筛选

更新日期：2026-08-25

## 结论

FSE 2024 中 `org.hsqldb:hsqldb` 共有 21 条记录。按根仓折叠模块重复后，得到 16 个唯一根仓；`rmpestano/dbunit-rules` 同时出现在两个版本变化中，因此统计单位是 17 个“根仓与版本变化”组合。

本轮正式接纳 0 条，未执行 A0/A1/A2。原因不是公开失败不真实，而是 17 个审计单元中没有一个同时具备“可固定的源输入变化”和“保持 A1 输入不变的维护者精确 A2”。四个 SQL Processor 模块提供了一个可隔离的源机制锚点，但目标仓历史中没有对应维护者修复。HSQLDB 2.5.2 到 2.6.0 的主体则是发布制品从 Java 8 类文件变为 Java 11 类文件；这项发布差异可以直接测量，但不能诚实压缩成源树中的一个破坏提交。

计数如下：

| 统计项 | 数量 |
|---|---:|
| FSE 原始记录 | 21 |
| 唯一根仓 | 16 |
| 根仓与版本变化组合 | 17 |
| 可隔离的精确源机制锚点 | 1 |
| 保持固定 A1 输入的维护者精确 A2 | 0 |
| 严格三臂正式正例 | 0 |
| 完整项目包 | 0 |

逐组合机器审计位于 `candidate-root-audit.jsonl`，汇总位于 `results/hsqldb-fse-history-screening-2026-08-25/summary.json`。发布物类头和清单的原始输出保存在同一结果目录的 `artifact-bytecode-evidence.txt`，SQL Processor 源提交的差异证据保存在 `sql-processor-source-commit-evidence.txt`。

## 四组版本变化

| 版本变化 | 原始记录 | 根仓 | 结论 |
|---|---:|---:|---|
| 2.2.8 到 2.6.1 | 2 | 2 | 一个历史停更且失败位于 Arquillian；一个后续为百文件 Java 11 迁移，均无精确 A2 |
| 2.5.0 到 2.5.1 | 4 | 1 | 精确源提交成立，但四模块属于同一根仓且没有维护者 A2 |
| 2.5.2 到 2.6.0 | 14 | 13 | Java 8 到 Java 11 发布制品机制成立；所有看似修复均改变了 HSQLDB 版本或属于宽泛迁移 |
| 2.6.0 到 2.6.1 | 1 | 1 | 目标仓 2016 年后无代码修复，公开失败也未归因到可隔离源变化 |

SQL Processor、Motown 的模块记录只作为一个根仓审计。DBUnit Rules 的 `core` 与 `junit5` 虽来自同一根仓，但对应不同版本变化，因此保留两个审计单元而不伪装成两个独立仓。

## 精确源机制锚点

HSQLDB 提交 `016e51e49219a8eebcafd47a8d06a9c321ec270b` 在 `DateTimeType` 中删除了对 `java.sql.Timestamp.getNanos()` 的读取，改为只从 `java.util.Date.getTime()` 恢复毫秒部分。该提交进入 2.5.1，直接解释 SQL Processor 四个模块中时间戳从 `14:55:02.123456` 变为 `14:55:02.123` 的失败。

该提交只改三个文件，相关行为位于 `src/org/hsqldb/types/DateTimeType.java`，因而源变化可以精确隔离。但是 SQL Processor 的四个相关测试从公开失败时点之后没有出现针对纳秒截断的维护者修复；2024 年和 2025 年的变化是 Java 21、弃用接口与 JUnit 迁移。没有 A2 就不执行三臂，也不把四个 Maven 模块算成四条正例。

## Java 制品变化

直接读取 Maven 发布物中的 `org/hsqldb/jdbc/JDBCDriver.class` 类头与清单得到：

| 制品 | 类文件主版本 | 可运行基线 | 清单构建环境 |
|---|---:|---|---|
| 2.5.2 默认包 | 52 | Java 8 | JDK 8 |
| 2.6.0 默认包 | 55 | Java 11 | JDK 11 |
| 2.6.1 默认包 | 55 | Java 11 | JDK 11 |
| 2.6.1 `jdk8` 包 | 52 | Java 8 | JDK 11 交叉构建 |

因此 Java 8 客户端不能加载 2.6.0 默认制品这一机制成立，`No suitable driver`、`UnsupportedClassVersionError` 及其后的上下文加载失败与之相符。但 2.6.0 的默认类等级取决于发布构建环境；源树没有一个单一提交把默认 Maven 制品从 Java 8 切为 Java 11。版本标签和发布物能够固定观测输入，不能把一个发布过程差异虚构成单提交 Marshal 输入。

并非所有包装异常都足以逐条证明相同根因。Sitebricks 与 embedded-db-junit 的“无合适驱动”最接近类加载机制；LanguageTool 后续提交说明也支持同一问题。其余记录包含二次空指针、Spring 上下文失败、Mockito 未完成桩和与 Derby 相关的异常摘录，均只保留为线索。

## 两条看似精确但不合格的恢复

LanguageTool 的 `ad5e824cda8c0694204681b45899a304978dfa67` 只在服务模块增加 `jdk8` 分类器，提交说明为“fix hsqldb java problem”。但该提交使用 HSQLDB 2.7.1，而固定 A1 是 2.6.0。它证明维护者后来选择了 Java 8 分类制品，不能证明在保持 2.6.0 输入不变时恢复。

Embedded DB JUnit 的 `3919591881ba05d215c7495ec148002e0d58750d` 及合并提交 `f52d8ce5ded294c4aa22746e45f854b7218ebb85` 同时把 HSQLDB 从 2.5.1 升到 2.7.0并增加 `jdk8` 分类器。2021 年 `ccb465a900eabf62fc2508270736cffc46bfdafb` 只升到 2.6.1，没有选择分类器，默认包仍是 Java 11 类文件。前者同时改变源版本，后者没有完成修复，二者都不是固定 2.6.0 的 A2。

## 其余历史筛选

- Sitebricks、Shiro JDBI Realm、Motown、DBUnit Rules、LivingDoc、Testfun 等仓的相关代码历史在 2014 至 2019 年已经停止，没有后续维护者 A2。
- Random JPA 后续是 Java 17 与 Jakarta 的 186 文件迁移，且公开失败为 Mockito 未完成桩，不是同一合同的精确修复。
- Kundera 的公开镜像主线被重建为 2025 年单个初始提交，无法恢复精确历史。
- JDBC Performance Logger 后续只有持续集成调整，公开失败摘录还指向 Derby，不能把包装失败归因于 HSQLDB。
- RobotFramework Maven Plugin 没有 HSQLDB 或 Java 基线修复。
- MyBatis Spring 的 2.6.0 版本提交 `151f7715fd006c7fc901d3d6fc17d6023d5a1368` 只存在于未合并引用，默认主线从 2.5.1 独立升到 2.5.2，没有维护者 A2。
- CTP Query 的相关测试最后一次实质修改在 2013 年，仓库 2020 年后停止；公开失败发生在 Arquillian Servlet Runner 查找阶段。
- GuttenBase 的 `851605b0da8d83d3f62f1160e9b5b0e002fca77c` 同时把项目迁移到 Java 11并修改约 100 个文件，是平台迁移，不是针对固定 HSQLDB 输入的精确恢复。
- DBUnit Rules 的 2.6.0 到 2.6.1 记录是 Windows 输出文件不存在断言；仓库仍固定旧 HSQLDB，且没有后续代码历史，不能建立源归因或 A2。

## 为什么不执行三臂

这里具体避免的失败场景是：先为 17 个旧仓恢复重型构建环境，随后发现目标历史根本没有可应用的维护者修复，只能由数据集作者发明 A2。Git 提交、版本号和普通测试可以证明运行了哪个状态，却不能把宽泛 Java 迁移、未合并依赖升级或不同 HSQLDB 版本上的分类器选择变成固定 A1 输入下的维护者恢复。

因此本轮只做历史与发布物测量。没有找到修复的仓保持未知，不记负例；普通绿色构建也不能补出 A3 或完整项目包。

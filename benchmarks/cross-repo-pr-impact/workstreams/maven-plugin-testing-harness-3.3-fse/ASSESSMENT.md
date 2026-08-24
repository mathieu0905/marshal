# Maven Plugin Testing Harness 3.3.0 的 FSE 关系族筛选

更新日期：2026-08-25

## 结论

完整精确版本框共有 2 条候选、2 个断言失败，分别来自 `reines/dropwizard-debpkg-maven-plugin` 和 `meridor/stecker`，去重后仍是 2 个独立根仓。本轮正式接纳 0 条，没有执行 A0、A1、A2，也没有限定负例或 A3。

公开失败的源机制可以精确定位。`maven-plugin-testing-harness` 3.3.0 包含提交 `65c28851c702a295cdb0cd4014ad65fd530b9d30`，它在 `AbstractMojoTestCase.setUp` 中读取测试进程类路径上的 `maven-core` 版本，并在版本不高于 3.2.3 时抛出工作簿记录的断言：`Maven 3.2.4 or better is required`。该提交不在 3.2.0 中，而且只修改这个测试基类，因此不需要把整个发布差异当成源机制。

两个目标仓的完整远程历史都没有采用 3.3.0，也没有在保持 3.3.0 的前提下升级 Maven 库并恢复测试。工作簿同时没有保存目标 Git 修订。人工把目标 POM 中的 Maven 库改到 3.2.4 以上，可能制造一个可以通过的 A2，但它不是维护者修订，不能作为历史因果标签。

## 完整候选框

| FSE 候选 | 目标模块 | 失败观察 | 根仓 |
|---|---|---:|---|
| `fse2024-behavioral-0341` | `com.jamierf.dropwizard:dropwizard-debpkg-maven-plugin` | 1 | `reines/dropwizard-debpkg-maven-plugin` |
| `fse2024-behavioral-0342` | `org.meridor.stecker:stecker-plugin-generator` | 1 | `meridor/stecker` |

两条记录的目录提示、远程身份和提交历史互不相同，因此这里确实是两个根仓，不是同仓模块或改名仓的重复计数。

## 精确源变化

3.2.0 标签指向提交 `5f2f3a23b62bf1cc2465c94b173700ee557edc5a`，3.3.0 标签指向提交 `7733ae9dfa24bba9f92c4d2335acf35f553fae82`。两者之间的提交 `65c28851c702a295cdb0cd4014ad65fd530b9d30` 新增了三个动作：

1. 从测试进程资源 `/META-INF/maven/org.apache.maven/maven-core/pom.properties` 读取 Maven 库版本；
2. 把该版本解析为 Maven 的制品版本；
3. 在每个 `AbstractMojoTestCase` 的 `setUp` 开始处断言版本必须高于 3.2.3。

两个 FSE 记录的异常类型、消息、测试基类和行号都与这段新增代码一致。后续版本直到 2024 年才删除 Maven 3 支持代码，不影响 3.3.0 的归因。

## 运行环境与目标代码的边界

该断言检查的不是 CI 日志里 `mvn --version` 显示的外部命令版本，而是项目测试进程类路径上的 `maven-core` 库。两个目标仓的 POM 都把相关 Maven 库固定在 3.2.3：

- Dropwizard 插件在根 POM 中固定 `maven-plugin-api` 和 `maven-compat` 为 3.2.3；
- Stecker 的生成器模块固定 `maven-plugin-api` 和 `maven-compat` 为 3.2.3。

因此，单独声称“升级 CI 的 Maven”不足以构成 A2。有效修复必须由目标维护者在保持 harness 3.3.0 的情况下提供兼容的测试类路径，并由同一失败测试证明恢复。当前历史中没有这种修订。

## 目标历史审计

### Dropwizard 插件

远程共有 16 个引用、132 个唯一可达提交和 33 个相关 POM 内容块。默认分支最终提交为 `7cc70dbaaac57cb5bdc1268c860eccf8de5099a5`，日期为 2016-03-09。源机制在 2014-11-17 出现后，该仓继续维护一年多；历史中所有 harness 声明都停留在 3.2.0，没有任何提交采用 3.3.0，也没有把固定的 Maven 3.2.3 库升级到满足断言的版本。

### Stecker

远程共有 29 个引用、63 个唯一可达提交和 30 个相关 POM 内容块。默认分支最终提交为 `4c41a24513339d71d7f581691ae627870816e80e`，日期为 2017-03-03。该仓在 3.3.0 发布后继续维护两年多；历史中所有 harness 声明同样停留在 3.2.0，后期使用的 `maven-plugin-api` 和 `maven-compat` 均为 3.2.3，没有固定 3.3.0 的维护者恢复。

## 为什么不执行三臂

FSE 工作簿证明了合成升级会触发真实断言，但没有记录实验所用的目标 Git 修订。当前远程头仍包含相同依赖形状和失败测试，只能用于解释机制，不能倒推出公开执行的唯一输入。

更重要的是，完整目标历史中不存在 A2。若本轮自行选择一个目标提交、把 harness 改成 3.3.0，再把 Maven 库升级到 3.2.4 或 3.2.5，普通测试只能证明作者设计的方案可行，不能证明维护者曾做出这项跨仓适配。具体误标场景是把两个长期停留在 3.2.0 的项目描述成“维护者采用 3.3.0 后修复”。Git 提交和版本号可以固定人工实验，却不能补出不存在的维护者行为。

按当前准入顺序，本组应在执行前停止。两条记录保留为“源变化会击中哪些旧 Maven 测试类路径”的高质量线索，不进入旗舰因果正例。

## 证据边界

本组能够证明 3.3.0 新增最低 Maven 库版本约束，并且两个独立目标的合成升级都触发了该约束。它不能证明目标维护者实际采用 3.3.0、不能提供维护者 A2，也不能提供独立负例或 A3。

机器可读候选、根仓裁决和历史证据分别位于 `candidate-frame.jsonl`、`root-audit.jsonl` 与 `history-evidence.json`；紧凑结果位于 `results/maven-plugin-testing-harness-3.3-fse-history-screening-2026-08-25/summary.json`。

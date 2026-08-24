# aws-powertools 第四仓筛选结论

## 结论

`aws-powertools/powertools-lambda-java` 可以作为 Log4j 2.17.2 到 2.18.0 项目包的第四个独立消费仓，但标签只能是限定负例，不能写成因果正例。

维护者 PR 912 把同一个 `log4j.version` 属性从 2.17.2 升到 2.18.0。该属性同时控制 `log4j-api`、`log4j-core`、`log4j-slf4j-impl` 和 `log4j-layout-template-json`，所以仓库执行的是同步升级，不存在 Neqsim 中 API 与 Core 错配的破坏臂。

## 固定输入

- 基线提交：`0184106b997ba587a33a5ac09a669ad33c3aa6b5`
- PR 头提交：`76d6c35e99f936e3548df040eec5b2a9a35927e7`
- 合并提交：`6d9050a5ae4b7737a5bf4d7c0cfae34d25b3985e`
- 原生测试：`org.apache.logging.log4j.core.layout.LambdaJsonLayoutTest`
- Java：11

PR 头提交还把 AWS SDK 从 2.17.223 升到 2.17.224。为排除这个混杂，筛选单独运行了固定 AWS SDK 2.17.223、只覆盖 `log4j.version=2.18.0` 的隔离臂；同时也运行了未经改写的维护者头提交。

## 执行结果

| 臂 | Log4j | AWS SDK | 结果 |
| --- | --- | --- | --- |
| 基线 | 2.17.2 | 2.17.223 | 3 项通过 |
| 隔离 Log4j 升级 | 2.18.0 | 2.17.223 | 3 项通过 |
| 维护者 PR 头 | 2.18.0 | 2.17.224 | 3 项通过 |

三个臂退出码均为 0。隔离升级臂与维护者头提交方向一致，说明绿色结果不依赖同一提交中的 AWS SDK 更新。所选 `powertools-logging` 模块的依赖树也不含 AWS SDK，而 Log4j 四个直接发布物均按预期同步切换版本。

## 变化面覆盖

隔离升级臂的覆盖数据命中 Log4j Core 2.18.0 的 `ThreadContextDataInjector.java:77`：遗漏指令 0、覆盖指令 9。该行调用 API 2.18.0 新增的 `ServiceLoaderUtil`，正是 Neqsim 破坏臂暴露的接口变化面。因此这条绿色观察不是“测试没有运行到变化代码”。

## 标签边界

这条记录只支持以下判断：在固定提交、Java 11、原生结构化日志测试和同步 Log4j 2.18.0 发布物的条件下，该消费仓无需额外协调即可通过。它不证明所有测试、追加器、部署环境或非同步版本组合都兼容。

它补足 Log4j 项目包的第四个独立根仓，但没有增加正例数量，也不能替代 Neqsim 的真实破坏与维护者恢复三臂。

## 产物

- 重放脚本：`run_screening.sh`
- 固定输入：`source-record.json`
- 结果：`results/log4j-2.18-aws-powertools-screening-2026-08-25/`

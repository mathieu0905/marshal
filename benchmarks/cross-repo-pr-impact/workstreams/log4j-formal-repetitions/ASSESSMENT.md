# Log4j 四仓项目包正式重复

本工作流对已经完成单次筛选的 Log4j 四仓候选做三次独立重复，不重新定义标签：

- `equinor/neqsim` 是正例，A0、A1、A2 分别使用仓库真实合并历史中的三个提交；
- `archifacts/archifacts`、`elimu-ai/webapp`、`aws-powertools/powertools-lambda-java` 是限定负例，A1 与 A2 使用相同输入但独立检出和执行；
- 四仓的 A3 都固定为同步 Log4j 2.17.1 到 2.17.2。

每轮、每臂、每仓使用独立源码副本；五个试验臂使用相互隔离的 Maven 本地仓库。镜像、检出、缓存和 Java 临时目录都位于项目内的 `.work/log4j-formal/`；已有 `~/.m2` 只作为只读文件仓库按需提供种子制品。运行器保存 Maven 解析后的 Log4j API/Core 版本、输入差异、命令、原始日志、Surefire XML、测试数和方向判定。三个限定负例还逐轮验证 A1/A2 输入相同，以及 A0/A3 后臂输入相同。

测试入口沿用单次筛选：Neqsim、archifacts 和 elimu-ai 执行完整 `mvn clean test`；Powertools 只执行 `LambdaJsonLayoutTest`，不能把其 3 项定向测试与其他仓的全量测试数横向比较。

变化面覆盖不在正式重复中重新插桩。单次接纳证据保持原边界：三个限定负例在 Log4j 2.18.0 命中 `ThreadContextDataInjector.java:77`；A3 的四仓共同最小变化面是 `LoggerContext.java:291`。正式重复只验证固定输入和执行方向的稳定性，不能替代独立语义复核。

运行方式：

```text
run_formal_repetition.sh 1
run_formal_repetition.sh 2
run_formal_repetition.sh 3
```

运行器不接受外部工作根覆盖。正式检出与缓存固定写入仓库根目录下的
`.work/log4j-formal/`；`~/.m2/repository` 只通过只读 `file://` 仓库提供按需种子制品。
elimu-ai 和 Neqsim 的直接 Log4j 依赖逐个合成，并在进入依赖解析和测试前从
`pom.xml` 回读校验，避免版本插件无修改却返回成功。

## 正式结果

2026-08-25 完成三轮独立重复。每轮均执行 20 个“试验臂×仓库”组合，合计
60 次；版本匹配、方向匹配和预期失败签名均为 60/60。聚合验证结果见
`results/log4j-formal-repetitions-2026-08-25/verification-results.tsv`，最终状态为
`verification=pass`。

Neqsim 的三轮结果完全一致：A0 均为 180 项测试通过；A1 均运行 134 项测试，
产生 0 个失败、131 个错误和 1 个跳过，并命中
`NoClassDefFoundError: org/apache/logging/log4j/util/ServiceLoaderUtil`；A2 均恢复为
180 项测试通过。三轮 A1 的失败测试套件集合也完全一致。

三个限定负例在每轮中都满足 A1/A2 输入一致。验证器重新解析完整 Log4j
依赖坐标图后，A1 与 A2 仍逐仓一致且非空：archifacts 和 elimu-ai 各有 3 个
坐标，Powertools 有 4 个坐标。A3 前后臂的四仓执行方向也全部符合预期。

本结果证明固定输入下的执行方向具有三轮稳定性，但不扩大单次筛选已经声明的
因果边界：限定负例仍只是对选定测试入口和观测变化面的限定结论，Powertools
仍只覆盖 3 项定向测试。

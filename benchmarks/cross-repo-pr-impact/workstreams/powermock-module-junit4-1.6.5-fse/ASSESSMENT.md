# PowerMock JUnit4 1.6.5 的 FSE 关系族筛选

更新日期：2026-08-25

## 结论

FSE 2024 的完整精确版本框共有 8 条候选、8 个独立根仓，八条公开执行记录都报告同一异常：只把 `powermock-module-junit4` 换成 1.6.5 后，运行器找不到 `MockingFrameworkReporterFactoryImpl`。

这个版本族有可信的执行破坏线索，也能定位精确源机制，但没有一条满足旗舰因果关系的准入条件。七个根仓的全部远程引用中都找不到固定 1.6.5 的维护者恢复；唯一看似相关的 Visenze 提交已经在前一轮严格执行，维护者补丁不能恢复 A1，而且原始 A0 还依赖公开仓库中不存在的历史 JAR。最终计数是 8 条破坏线索、0 条正式正关系、0 条限定负例、0 条 A3、0 个完整项目包。

## 完整候选框

| 候选 | 客户端模块 | 根仓 | 裁决 |
|---|---|---|---|
| `0611` | `com.feedzai.fos:fos-server` | `feedzai/fos-core` | 无固定 1.6.5 的 A2 |
| `0612` | `com.github.mcac0006:sift-java` | `mcac0006/sift-java` | 无固定 1.6.5 的 A2 |
| `0613` | `com.github.linsolas:casperjs-runner-maven-plugin` | `linsolas/casperjs-runner-maven-plugin` | 无固定 1.6.5 的 A2 |
| `0614` | `net.rcarz:jira-client` | `bobcarroll/jira-client` | 无固定 1.6.5 的 A2 |
| `0615` | `com.visenze:visearch-java-sdk` | `visenze/visearch-sdk-java` | 候选 A2 执行后仍失败 |
| `0616` | `net.unit8.wscl:websocket-classloader` | `kawasima/websocket-classloader` | 无固定 1.6.5 的 A2 |
| `0617` | `org.asciidoctor:asciidoclet` | `asciidoctor/asciidoclet` | 无固定 1.6.5 的 A2 |
| `0618` | `org.sonarqubecommunity.buildbreaker:sonar-build-breaker-plugin` | `adnovum/sonar-build-breaker` | 无固定 1.6.5 的 A2 |

仓库编号分别为 `16077092`、`18561243`、`9330890`、`10305633`、`27907059`、`17473671`、`10024228` 和 `7388815`。`rcarz/jira-client` 已重定向到 `bobcarroll/jira-client`，`SonarCommunity/sonar-build-breaker` 已重定向到 `adnovum/sonar-build-breaker`；编号核对后不存在别名重复。

## 精确源机制

行为提交 `3ed63349711fc6194658e5e54db852d82c80502c` 属于 1.6.5，不属于 1.6.4。它让 JUnit4 运行器在执行委托测试前调用框架报告器，并由 Core 按固定类名加载 `org.powermock.api.extension.reporter.MockingFrameworkReporterFactoryImpl`。Mockito 实现同时新增在 `powermock-api-mockito-common` 中。

因此，客户端只升级 `powermock-module-junit4` 时会得到 1.6.5 的运行器和 Core，但旧 `powermock-api-mockito` 仍来自 1.6.4，不含新增实现。八条公开记录的同一缺类异常与这个混合版本机制一致。最小行为差异保存在 `source-mechanism.patch`；它不是把整个 1.6.4 到 1.6.5 发布差异冒充一个变化。

## Visenze 执行证据

`visenze/visearch-sdk-java` 是唯一存在紧邻维护者“修复依赖问题”提交的根仓。前一轮已固定父提交 `5f6e72ec5d16987f4cee959ef2063a20989cb40f`，在 Java 8 下执行同一测试合同：

| 执行 | `module-junit4` | `api-mockito` | 目标变化 | 结果 |
|---|---:|---:|---|---|
| 恢复环境 A0 | 1.6.4 | 1.6.4 | 无 | 71 项通过 |
| A1 | 1.6.5 | 1.6.4 | 无 | 公开异常失败 |
| 候选 A2 | 1.6.5 | 1.6.4 | 删除显式 `powermock-api` | 同一异常失败 |

维护者提交 `8fdd4826f7719be850614fc5359bdf4cca32a20c` 只删除没有代码的 `powermock-api` 聚合坐标，不会升级仍为 1.6.4 的 `powermock-api-mockito`，所以它不是该影响的恢复。

更重要的是，历史 POM 显式请求 `org.powermock:powermock-api:jar:1.6.4`，而 Maven Central 只有聚合 POM，没有对应 JAR。干净缓存中的严格 A0 在测试前解析失败。前一轮为了核对公开异常，给三个诊断臂共同放入空占位 JAR；这足以否定候选 A2，却不能把恢复环境 A0 升格为严格基线。

## 八仓历史审计

八仓合计审计 492 个引用、1926 个唯一可达提交，包括分支、标签和拉取请求头。依赖构建文件历史中没有任何根仓固定 `powermock-module-junit4` 1.6.5。Visenze 的候选修复已通过执行排除；其余七仓没有可执行的维护者 A2。

这里的裁决只是“不接纳正关系”，不是负例。没有发现修复不能证明客户端不受影响，公开的八条失败记录反而说明它们很可能受到了同一混合版本问题。缺少的是保持源输入 1.6.5 不变、由维护者完成并恢复同一合同的第三臂。

## 证据边界

FSE 工件没有保存八个客户端的精确 Git 修订。除 Visenze 外，本轮不从仓库历史中猜测见证提交，也不为了得到更多数量而人工编写 A2。`candidate-frame.jsonl` 保留全部八条检出记录，`candidate-root-audit.jsonl` 给出按仓库编号去重后的历史裁决。

执行日志仍位于 `results/powermock-visearch-screening-2026-08-24/`，本轮汇总位于 `results/powermock-module-junit4-1.6.5-fse-history-screening-2026-08-25/`。本项目包没有新增产品代码、公共台账、基线或门禁。

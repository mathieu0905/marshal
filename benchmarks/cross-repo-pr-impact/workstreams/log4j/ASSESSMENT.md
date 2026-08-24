# Log4j Core 项目包筛选记录

## 当前结论

Log4j Core 已形成一个四仓候选，但还不是完整四臂项目包。当前可接受单元是：

- 正例：`equinor/neqsim`；
- 限定负例：`archifacts/archifacts`、`elimu-ai/webapp`、`aws-powertools/powertools-lambda-java`；
- 兼容变化：Log4j 2.17.1 到 2.17.2，前三个仓都执行到真实变化行并通过；Powertools 只补足主变化的限定负空间，不补写尚未执行的 A3。

第四个仓由 `aws-powertools/powertools-lambda-java` 补足。它在同步升级 Log4j API、Core、SLF4J 实现和模板布局时通过原生结构化日志测试，并命中 Neqsim 失败对应的 `ServiceLoaderUtil` 调用面。当前缺口不再是仓库数量，而是 Powertools 的 A3 和全包三次独立重复。`ApkToolBoxGUI` 的破坏可重放，但没有维护者接受的精确恢复；`ivymx` 的绿色测试没有进入兼容变化表面。二者仍不接纳。

## 完整失败候选框

BUMP 固定版本 `324d5513aa5ca40b5cb32de5b816a58fa60bd7bb` 中，`org.apache.logging.log4j:log4j-core` 有 7 条已重放失败记录、5 个唯一消费仓：

| 消费仓 | 记录数 | 观察到的版本对 |
| --- | ---: | --- |
| `elimu-ai/webapp` | 3 | 2.16.0 到 2.18.0、2.19.0、2.20.0 |
| `equinor/neqsim` | 1 | 2.17.2 到 2.18.0 |
| `jiangxincode/ApkToolBoxGUI` | 1 | 2.17.2 到 2.19.0 |
| `oripa/oripa` | 1 | 2.12.1 到 2.15.0 |
| `quick-perf/quickperf` | 1 | 2.11.1 到 2.16.0 |

这些记录只提供失败线索，不自动产生正例。正式主变化收窄为 Log4j 2.17.2 到 2.18.0，因为只有 Neqsim 在这个版本对上保留了仓库实际合并的破坏臂和精确配对恢复。

## Neqsim 真实三臂

Neqsim 的两个依赖更新来自同一父提交。仓库先合并 Core PR 484，再在其上合并 API PR 483：

| 臂 | 仓库提交 | Log4j API/Core | 原生命令结果 |
| --- | --- | --- | --- |
| A0 | `6cea014aecf9ca0956bb402bce2ed18e803b9b4b` | 2.17.2 / 2.17.2 | 180 项通过 |
| A1 | `e23721cb00132a55b32efcbd6fc6b382fb60e959` | 2.17.2 / 2.18.0 | 134 项启动后失败 |
| A2 | `d622943718685b394364d36d5af61474cf881339` | 2.18.0 / 2.18.0 | 180 项通过 |

A1 的失败签名是 `NoClassDefFoundError: org/apache/logging/log4j/util/ServiceLoaderUtil`，随后还出现 `ThreadContextDataInjector` 和 `LoggerContext` 初始化失败。A2 是维护者实际合并树，只在 A1 上加入配对 API 更新，不是数据集作者发明的修复。

三臂脚本与原始结果位于：

- `run_log4j_neqsim_historical_screening.sh`
- `results/log4j-neqsim-historical-screening-2026-08-24/`

## 三个限定负例

固定真实消费仓提交并同步到 API/Core 2.18.0 后：

| 消费仓 | 测试结果 | A1 变化面覆盖 |
| --- | ---: | --- |
| `archifacts/archifacts` | 92 项通过 | `ThreadContextDataInjector.java:77` 为 `0/9` |
| `elimu-ai/webapp` | 122 项通过 | `ThreadContextDataInjector.java:77` 为 `0/9` |
| `aws-powertools/powertools-lambda-java` | 3 项通过 | `ThreadContextDataInjector.java:77` 为 `0/9` |

第 77 行正是 Core 2.18.0 调用 API 新增 `ServiceLoaderUtil` 的位置，与 Neqsim A1 的失败接口一致。因此这三个结论不是“没有运行到所以绿色”。标签只覆盖同步 Log4j 发布物、原生命令与实际进入的日志初始化路径，不外推到其他追加器或部署组合。

脚本与结果位于：

- `run_log4j_2_18_negative_screening.sh`
- `results/log4j-2.18-negative-screening-2026-08-24/`
- `workstreams/log4j-2.18-fourth-repo/aws-powertools/run_screening.sh`
- `results/log4j-2.18-aws-powertools-screening-2026-08-25/`

这里还保留一个任务本体边界：Log4j 是多模块源仓。Neqsim 的破坏来自只更新 Core，而三个限定负例按各自版本管理方式同步消费 API/Core；Powertools 还同步升级 SLF4J 实现和模板布局。这个项目包测的是“同一源发布下，哪些消费仓需要额外协调版本声明”，不能写成任意 Core 二进制替换对所有仓的影响。

## 兼容变化与覆盖

A3 选择 2.17.1 到 2.17.2。后者修改了 Log4j Core 初始化与脚本启用路径。三个可接受仓的前后臂都通过，后臂覆盖均命中真实变化行：

| 消费仓 | `LoggerContext.java:291` | `AbstractConfiguration.java:220/221/222` |
| --- | ---: | ---: |
| Neqsim | `0/2` | `0/11`、`0/4`、`0/4` |
| archifacts | `0/2` | `0/11`、`0/4`、`0/4` |
| elimu-ai | `0/2` | 未作为接纳所需的共同最小行 |

elimu-ai 另有独立的四臂筛选：2.17.1、2.17.2、2.18.0 和 2.19.0 均各运行 122 项测试；2.17.2 后臂命中 `LoggerContext.java:291`。相关结果位于 `results/log4j-elimu-candidate-screening-2026-08-24/`。

## 明确拒绝的候选

### ApkToolBoxGUI

固定基线下，Core 2.17.2 到 2.19.0 会因同一个 `ServiceLoaderUtil` 缺失签名失败；同步 API/Core 后 13 项测试恢复。但 BUMP 的 Core 更新提交未进入默认分支，也没有找到维护者接受的精确配对修复。人工同步只能证明机制，不能充当 A2。因此它保留为失败锚点，不计正式正例。

### ivymx

2.17.1 和 2.17.2 两臂的 177 项测试都通过，但 Log4j Core 覆盖数据只有 46 字节。`LoggerContext.java:291` 为 `2/0`，`AbstractConfiguration.java:220/221/222` 分别为 `11/0`、`4/0`、`4/0`。测试没有进入兼容变化表面，不能形成限定负例或 A3 证据。

首次覆盖脚本还因 archifacts 预安装没有进入消费仓目录而中止。失败产物保留在 `results/log4j-a3-coverage-audit-2026-08-24-attempt-1/`；修正后的完整结果位于不带 `attempt-1` 后缀的目录。

## 下一步

1. 为 Powertools 补做 2.17.1 到 2.17.2 的 A3 前后臂，并核对同一变化面覆盖；普通绿色构建不接纳。
2. A3 成立后，按 A0、A1、A2、A3 前臂、A3 后臂做三次独立重复。
3. 对 Neqsim 两个合并 PR 的关系、三个限定负例的标签上限和多模块源发布口径做独立语义复核。
4. 在上述条件完成前，本组只计一个四仓候选，不进入正式项目包数量和停止能力指标。

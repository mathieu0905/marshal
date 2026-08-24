# Jackson Core 2.11.0 的 FSE 关系族筛选

更新日期：2026-08-25

## 结论

完整精确版本框共有 5 条候选，按仓库编号和历史重定向去重后对应 4 个独立客户端根仓。本轮接纳 1 条执行验证的正关系：`internetitem/logback-elasticsearch-appender` 在 Jackson Core 从 2.8.0 升到 2.11.0 后，8 项 `PropertySerializerTest` 全部失败；紧随其后的维护者提交只修测试断言，保持 2.11.0，8 项全部恢复。

同一组测试还做了单变量反事实：在 A0 代码上只把 Jackson Core 改成 2.11.0，同样得到 8/8 失败和相同调用签名。因此 A1 同时更新的其他依赖不是这组失败的必要原因。

其余三个根仓都没有固定 2.11.0 的可分离维护者 A2。本组正式计数为 5 条候选、4 个独立根仓、1 条正关系、0 条限定负例、0 条 A3；它是一条高强度因果关系，不是完整旗舰项目包。

## 完整候选框

| 候选 | 目标模块 | 根仓 | 裁决 |
|---|---|---|---|
| `0020` | `org.opentripplanner:otp` | `opentripplanner/OpenTripPlanner` | 无固定 2.11.0 A2 |
| `0021` | `com.sdl.dxa:dxa-data-model` | `RWS/dxa-web-application-java` | 与 `0022` 同根；修复和 2.12.3 升级不可分离 |
| `0022` | `com.sdl.dxa:dxa-tridion-provider` | 同上 | 同上 |
| `0023` | `com.internetitem:logback-elasticsearch-appender` | `internetitem/logback-elasticsearch-appender` | 接纳 1 条正关系 |
| `0027` | `ie.corballis:json-fixtures-lib` | `corballis/json-fixtures` | 从未采用 2.11.0 |

历史地址 `sdl/dxa-web-application-java` 当前重定向到 `RWS/dxa-web-application-java`，仓库编号保持为 `40543847`，所以两条 SDL 记录只计一个根历史。

## 精确源机制

源提交 `4ca96e5f7752102cc38d89e2c43eea021a79ada0` 只修改 `JsonGenerator.java`，把 `writeNumberField`、`writeObjectField`、`writeBooleanField` 等字段级便利方法从 `final` 改为普通可覆写方法。它属于 `jackson-core-2.11.0`，不属于 `jackson-core-2.10.5`。

目标项目使用 Mockito 1.10 模拟抽象类 `JsonGenerator`。旧 Jackson 中这些 `final` 方法不能被模拟框架拦截，真实便利方法继续调用底层 `writeNumber`、`writeObject` 或 `writeBoolean`，所以旧断言通过。2.11.0 中字段级方法可被直接拦截，真实方法体不再展开，测试观察到的是 `writeNumberField(null, 123)` 等字段级调用。这个机制与 FSE `0023` 的原始错误逐字一致。

精确差异保存在 `source-mechanism.patch`。该机制只解释 `0023`，不能因为五条记录共享版本号，就把其余快照、反序列化和日期输出失败归到同一提交。

## Logback Appender 三臂

A0、A1、A2 是连续的维护者提交。A1 把 Jackson Core 从 2.8.0 升到 2.11.0，同时更新其他依赖与构建插件，但没有改 Java 代码。A2 只修改 `PropertySerializerTest.java`，保持 2.11.0，并将断言改为字段级调用。A2 还把已经能在 A1 编译的 `assertThat` 静态导入从 JUnit 换到 Hamcrest；这项清理不改变八项模拟调用断言的恢复机制。

| 臂 | Jackson Core | 结果 |
|---|---:|---|
| A0 `c7081311...` | 2.8.0 | 8/8 通过 |
| A1 `20de8375...` | 2.11.0 | 8/8 失败 |
| A2 `19890dee...` | 2.11.0 | 8/8 通过 |
| A0 单变量反事实 | 2.11.0 | 8/8 失败 |

维护者补丁见 `maintainer-repair.patch`，固定环境和执行命令见 `REPLAY.md`。

## 其余根仓

OpenTripPlanner 在 Jackson 2.10.1 下加入命中的 BikeRental 快照测试，后来直接把版本升到 2.12.5。中间没有 2.11.0 的维护者采用和恢复，历史中的快照改动还混有位置、路线参数和区域设置变化，不能充当本题 A2。

SDL 在 `ef4c26df...` 中同时把 Jackson 从 2.10.5 升到 2.12.3，并加入题为 `jackson 2.11+ fix` 的生产代码适配，随后 `8b5d02ba...` 继续补充模块注册和兼容修改。这是很强的相邻版本适配线索，但升级和首轮修复在同一个提交中，且实际源输入是 2.12.3，不是固定 2.11.0，不能拆成当前合同的 A1/A2。

JSON Fixtures 在 2019 年把 Jackson 升到 2.9.9。全部可达 POM 历史没有 2.11.0 声明；后续宽重构虽修改相同生成器测试，也不能视为固定新版本下的恢复。

## 证据边界

接纳关系证明的是 Jackson 方法可覆写性改变了客户端测试对模拟调用的观察，因此目标测试需要随相邻仓变化。它不证明 Logback Appender 的生产序列化结果错误，也不覆盖 Jackson 2.11.0 的其他变化。

未接纳的三个根仓只是缺少当前合同所需的维护者 A2，不是“不受影响”的负例。当前也没有对同一方法变化有覆盖的干扰仓或独立兼容源变化，不能补报限定负例或 A3。

机器可读候选、根仓裁决和历史证据位于本目录；执行报告位于 `results/jackson-core-2.11-fse-screening-2026-08-25/`。本工作流没有修改公共候选台账、结果索引或 `.claude`，也没有独立提交。

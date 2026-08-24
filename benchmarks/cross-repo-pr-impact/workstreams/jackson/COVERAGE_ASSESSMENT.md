# Jackson 依赖覆盖与 A3 判定

## 判定结果

两个限定负例都进入了 `2.10.5.1 -> 2.12.6.1` 的 Databind 真实变化面，不是因为没有执行 Jackson 才保持绿色。A3 最终改用 `2.11.4 -> 2.12.0`：四仓前后臂全部通过，并共同执行了 2.12 新增的构造器检测与创建器收集路径。

覆盖成立并没有补上第二个高强度正例。Jackson 目前仍应保留为“一个已确认正例、两个已确认限定负例、一个已确认兼容控制”的单正例锚点，不提升为多正例旗舰项目包。

## 限定负例

覆盖报告针对实际解析的 `jackson-databind-2.12.6.1.jar` 生成，并只统计从 2.10.5.1 到 2.12.6.1 发生变化的 209 个生产类。

| 仓库 | 原生测试 | 被执行的变化类 | 变化行证据 |
| --- | ---: | ---: | --- |
| `spotify/github-java-client` | 96 | 133 / 209 | `BeanSerializerFactory.java:415` 新调用点 `ci=6`；`ObjectMapper`、`BasicDeserializerFactory`、`POJOPropertiesCollector` 等变化类均有指令覆盖 |
| `tokuhirom/avans` | 69 | 114 / 209 | `BeanSerializerFactory.java:415` 新调用点 `ci=6`；`ObjectMapper`、`BasicDeserializerFactory`、`POJOPropertiesCollector` 等变化类均有指令覆盖 |

两仓都通过 Jackson BOM 同步切换版本，测试中存在直接的 JSON 读写。它们因此可以作为“同步升级不需要消费仓适配”的限定负例；结论只覆盖各自固定提交和原生命令，不外推到仓库其他版本。

## A3 搜索

### 淘汰：2.12.5 -> 2.12.6

四仓在修复后的 Splunk 消费仓版本上前后臂均可通过。四仓也都执行了新增的 `BeanSerializerFactory.java:415` 调用和 685 行类型判断，但只走了 `CharSequence` 判断的假分支；真正改变序列化结果的分支没有执行。其余语义变化 `FactoryBasedEnumDeserializer.skipChildren` 和 `NodeSerialization` 也均未覆盖。因此这组不能用“进入了变化类”冒充“进入了行为变化”。

### 淘汰：2.12.3 -> 2.12.4

后臂四仓全部通过，但四个生产变化文件没有一条新增可执行行被四仓共同覆盖。Dropwizard 和 GitHub Java Client 进入了部分新路径，Splunk 与 Avans 没有。它不满足共同变化表面要求。

### 接受候选：2.11.4 -> 2.12.0

| 仓库 | 2.11.4 | 2.12.0 | 测试数 |
| --- | --- | --- | ---: |
| `splunk/kafka-connect-splunk`，使用维护者修复提交 `ddbd37d5...` | 通过 | 通过 | 143 |
| `pac4j/dropwizard-pac4j`，同步对齐 Jackson 组件 | 通过 | 通过 | 16 |
| `spotify/github-java-client`，同步 BOM | 通过 | 通过 | 96 |
| `tokuhirom/avans`，同步 BOM | 通过 | 通过 | 69 |

2.12.0 相对 2.11.4 有 9991 条新增生产源码行，其中 434 条新增可执行行被四仓共同覆盖。共同证据不是仅加载类：四仓都执行了 2.12 新增的 `BasicDeserializerFactory` 构造器检测路径，包括 258--262、271--274、279、284、296--297、303--306、312 和 316 行；305 行两个分支均覆盖，306 行至少一个新增分支覆盖。该路径引入 `ConstructorDetector`、新的创建器候选收集状态和隐式构造器决策，属于真实行为路径。

这是一组相邻次版本兼容控制，不是补丁版本控制。正式使用时必须保留这个名称和边界，不能描述成“相邻补丁发布”。

## A2 精度

Splunk PR 330 的提交 `ddbd37d5ffa2f745130cd449e631222fba71d7c7` 直接以失败臂父提交 `374ef350f9f255bc28957326f45e1461bf321dad` 为父提交。差异只有两个文件：

- `pom.xml`：Core `2.10.5 -> 2.12.6`，Databind `2.10.5.1 -> 2.12.6.1`；
- `Event.java`：把 `StdDateFormat.instance` 换成维护者指定的 UTC 时间格式。

因此 A2 可以直接抽取 `374ef350... -> ddbd37d5...` 的原始补丁，不需要重写或猜测修复。原生重放为 143 项全通过，解析版本正确。

## 可接受规模

- 候选源输入：2 条，即破坏变化 `2.10.5.1 -> 2.12.6.1` 和兼容控制 `2.11.4 -> 2.12.0`。
- 可接受仓库级标签：7 个，即 1 个破坏正例、2 个破坏限定负例和 4 个兼容控制通过标签。
- 可接受的多正例旗舰项目包：0 个。Dropwizard 的破坏臂可重放，但没有维护者精确修复且来自陈旧 PR 基线，不作为第二个正式正例。
- 可保留的单正例锚点：1 个项目包、2 条源输入。

# JUnit 4.13.1 到 4.13.2 的 FSE 关系族筛选

更新日期：2026-08-25

## 结论

FSE 2024 的精确版本组共有三条记录，目录分别解析为三个独立根仓：`j-easy/easy-props`、`SonarSource/sonar-ldap` 和 `awslabs/amazon-kinesis-client`。本轮正式接纳零条，未执行 A0/A1/A2，也没有限定负例或 A3。

拒绝不是因为三个公开失败都不真实，而是没有任何候选同时具备“能解释该失败的单一 JUnit 源机制”和“保持 JUnit 4.13.2 不变的维护者精确恢复”：

- Easy Props 的失败是目标测试把 `junit-4.13.1.jar` 写死在注解中。版本变化会确定性地让这个文件名失效，但仓库在 4.13.2 发布前已经停止，维护者从未采用 4.13.2，也没有对应修复。
- Sonar LDAP 的 `Invalid signature file digest` 不是 JUnit 特异信号。同一 FSE 框中，替换 JSR-305、Servlet API 和 ApacheDS 也出现相同的 `JarVerifier` 签名；目标仓也从未采用 JUnit 4.13.2。
- Amazon Kinesis Client 后来真实采用了 JUnit 4.13.2，也在 2023 年精确修复了公开失败的那个异步测试，但维护者明确把它定性为易波动测试。失败方法只是普通 `@Test`，不使用 4.13.2 改动的超时线程组、假设序列化或浮点断言路径，因此不能把客户端自身的启动竞争归因给 JUnit。

计数为：三条 FSE 记录、三个唯一根仓、三个失败观察、一个历史隔离版本变化、一个确定的制品文件名机制、一个保持 4.13.2 的精确客户端修复、零个“源机制与 A2 同时成立”的候选、零次重放、零条正式关系。

## 完整候选框与去重

| FSE 候选 | 目录提示 | 规范化根仓 | 公开失败 |
|---|---|---|---|
| 0265 | `benas_adp4j` | `j-easy/easy-props` | 注解仍查找 `junit-4.13.1.jar`，属性注入失败 |
| 0266 | `SonarCommunity_sonar-ldap/sonar-ldap-plugin` | `SonarSource/sonar-ldap` | JAR 清单签名摘要无效 |
| 0267 | `awslabs_amazon-kinesis-client/amazon-kinesis-client` | `awslabs/amazon-kinesis-client` | 异步处理尚未发生，Mockito 报 `handleInput` 未调用 |

GitHub 仓库主键核对证明前两个目录只是仓库转移后的旧名称，不是额外根仓：`benas/adp4j` 解析到仓库编号 10227959 的 `j-easy/easy-props`，`SonarCommunity/sonar-ldap` 解析到仓库编号 4673630 的 `SonarSource/sonar-ldap`。三条记录最终仍是三个独立根仓，没有模块重复。

## JUnit 源变化边界

版本标签固定为：

- `r4.13.1`：`1b683f4ec07bcfa40149f086d32240f805487e66`
- `r4.13.2`：`05fe2a64f59127c02135be22f416e91260d6ede6`

标签之间不是单一行为变化。需要优先核对的生产变化包括 `FailOnTimeout` 的线程组处理和 `AssumptionViolatedException` 的序列化修复；发布提交还固定了 4.13.2 的制品身份。只有 Easy Props 的硬编码文件名能直接落到制品身份变化，但它没有维护者 A2。Kinesis 的失败方法没有 JUnit 超时或假设序列化路径，公开签名又正是后来维护者承认的异步启动竞争。Sonar 的失败在多个无关依赖替换中重复出现，不能从发布差异中任选一个提交做归因。

因此不能把完整 `4.13.1 -> 4.13.2` 发布差异直接作为一个 Marshal 源变更，也不能因错误日志中出现 JUnit 版本就反推具体源提交。

## 三仓历史审计

### Easy Props

远程别名 `benas/adp4j` 已转移到 `j-easy/easy-props`。完整远程引用包含 248 个可达提交，时间从 2013-05-22 到 2020-11-15；62 个唯一 POM 块全部声明 JUnit，其中 8 个使用 4.13.1，使用 4.13.2 的数量为零。

最终测试在四处注解参数中写死 `junit-4.13.1.jar`。这足以解释 FSE 异常，但仓库最终提交早于 JUnit 4.13.2 的 2021-02-13 发布。把字符串手工改为 `junit-4.13.2.jar` 可以制造一个恢复臂，却不是维护者行为，不能成为 A2。

### Sonar LDAP

远程别名 `SonarCommunity/sonar-ldap` 已转移到归档仓 `SonarSource/sonar-ldap`。完整远程引用包含 369 个可达提交，时间从 2009-12-22 到 2021-04-28；153 个唯一 POM 块中 115 个声明 JUnit，3 个使用 4.13.1，使用 4.13.2 的数量为零。

更关键的反证来自 FSE 自身：候选 0061、0241、0266 分别替换 JSR-305、Servlet API 和 JUnit，却在同一个 Kerberos 测试中得到相同的 JAR 签名摘要错误；候选 0323 在同仓另一模块替换 ApacheDS 时也得到相同签名。它说明公开执行捕获了一个通用签名制品问题，而不是 JUnit 4.13.2 的特定行为变化。仓库后续也没有 4.13.2 适配。

### Amazon Kinesis Client

完整远程引用包含 3753 个可达提交，时间从 2013-11-07 延伸到当前历史；1416 个唯一 POM 块中 1122 个声明 JUnit，55 个包含 4.13.1，799 个包含 4.13.2。

拉取请求 879 的中间提交 `8084281e` 相对父提交 `c872cab0` 只把两个模块的 JUnit 4.13.1 改为 4.13.2，因此历史中确有隔离的版本变化。但 FSE 工作簿没有目标修订，不能断言它就是公开执行的精确检出；主线合入提交 `9c53c0ce` 还同时更新了多项依赖和构建插件。

拉取请求 1084 的 `b8d3390b` 是精确的目标侧变化：它只修改 `ShardConsumerSubscriberTest.java`，前后都保留 JUnit 4.13.2，通过增加等待确保订阅先启动。该提交的标题和说明直接称这两个测试为易波动测试。公开失败方法只是普通 `@Test`，失败发生在客户端线程调度与 Mockito 验证之间；它没有进入 JUnit 4.13.2 的超时线程组、假设序列化或浮点断言变化面。因此这是一条有价值的“错误归因反例”，不是 JUnit 跨仓影响正例。

## 为什么不执行三臂

已有准入顺序要求同时满足精确源机制和维护者精确 A2 后才重放。本组的具体失败场景是：若仅凭 Kinesis 的 A1 版本提交与后来易波动测试修复执行三臂，重复运行很可能得到随调度变化的通过或失败；即使某轮呈现通过、失败、通过，也不能证明 JUnit 变化造成了竞争。提交号、版本号和普通测试只固定输入，不能补出缺失的源代码因果路径。

Easy Props 与 Sonar 更不应补做手工恢复：前者会把数据集作者改字符串冒充维护者修复，后者会把通用签名环境故障冒充 JUnit 行为。停在历史筛选比生成方向漂亮但语义错误的日志更可靠。

## 证据边界

三条 FSE 记录继续保留为执行失败线索。Easy Props 可作为“版本化制品名称写死”的机制示例；Sonar 可作为同签名跨依赖重复的归因反例；Kinesis 可作为“精确客户端修复不自动证明上游因果”的反例。三者都不进入正式正例、负例或 A3。

机器可读候选、根仓裁决和历史统计分别位于 `candidate-frame.jsonl`、`root-audit.jsonl` 与 `history-evidence.json`；紧凑结果位于 `results/junit-4.13.2-fse-history-screening-2026-08-25/summary.json`。

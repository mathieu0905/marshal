# JUnit 4.11 候选历史筛选

## 结论

FSE 2024 复现实验中，`junit:junit 4.10 -> 4.11` 共命中 3 条记录，分别来自 `knightliao/hermes-jsonrpc`、`hmsonline/storm-cassandra-cql` 和 `pveentjer/Multiverse`。三个仓库都不是 GitHub 派生仓，初始提交历史也不同，因此保留为 3 个独立根仓关系，没有按模块虚增案例。

前两条有同一个精确上游机制：JUnit 4.11 开始拒绝静态 `@Rule` 字段，错误文本与公开执行完全一致。但两个目标的完整历史都没有维护者修复。第三条只是目标并发测试中的布尔断言失败，JUnit 只负责把 `false` 报成 `AssertionError`，没有找到能解释目标计时结果的精确源变化，也没有维护者恢复。

三条都在重放前拒绝，正式接纳 0 条。

## 候选框与独立性

| 候选 | 根仓 | 失败 | 源机制 | 维护者 A2 |
|---|---|---|---|---|
| 0252 | `knightliao/hermes-jsonrpc` | 静态 `wireMockRule` 被拒绝 | 精确 | 无 |
| 0253 | `hmsonline/storm-cassandra-cql` | 静态 `cqlUnit` 被拒绝 | 精确 | 无 |
| 0254 | `pveentjer/Multiverse` | 等待线程计时断言失败 | 未定位 | 无 |

每条记录本身已经是根仓级关系。三个 GitHub 仓库均报告 `fork=false`，其初始提交分别为 `4b15c8ab`、`e2173abe` 和 `4a84f85e`，不存在共享 Git 历史需要再次折叠。

## 上游变化边界

版本标签解引用后的提交为：

- `r4.10`：`45a44647e7306262162e1346b750c3209019f2e1`
- `r4.11`：`c2e4d911fadfbd64444fb285342a8f1b72336169`

关键提交 `b4f0afa639b42fa551fdcb26d9c1855ae4d778cf` 的标题是 `@Rule fields/methods must not be static`。它是 `r4.11` 的祖先，不是 `r4.10` 的祖先。提交把 `RuleFieldValidator` 从“只要求 `@ClassRule` 为静态”改为同时拒绝静态 `@Rule`，并新增断言精确错误文本的测试。

这能完整解释 Hermes 的 `The @Rule 'wireMockRule' must not be static.` 和 Storm Cassandra CQL 的 `The @Rule 'cqlUnit' must not be static.`。它不能解释 Multiverse：后者失败在目标代码 `assertTrue(t.result < TimeUnit.SECONDS.toNanos(10))`，说明等待线程返回值达到了或超过十秒。JUnit 4.10 与 4.11 的 `assertTrue` 都只在参数为 `false` 时抛错；堆栈行号变化不是造成计时条件变化的机制。

## 目标仓历史

### Hermes JSON-RPC

完整远程历史有 152 个可达提交。`BaseTestCase.java` 的 5 个唯一内容版本全部保留同一个组合：静态 `wireMockRule` 同时标注 `@ClassRule` 和 `@Rule`。维护者在 2021 年把 JUnit 4.10 升到 4.13.1，仍未改掉该组合。没有精确 A2。

### Storm Cassandra CQL

完整远程历史有 253 个可达提交。`CqlTestEnvironment.java` 的 5 个唯一内容版本和 `SalesTopology.java` 的 3 个唯一内容版本全部保留静态 `@Rule`，全历史没有引入 `@ClassRule`。81 个唯一 POM 内容块都使用 JUnit 4.10，没有 4.11 采用或对应修复。没有精确 A2。

### Multiverse

完整远程历史有 67 个可达提交。失败测试文件只有一个唯一内容版本，相关断言自初始提交起从未改变。28 个唯一 POM 内容块中没有 JUnit 4.11；主分支最后活动在 2013 年。既没有精确源机制，也没有维护者 A2。

## 为什么不执行三臂

Hermes 与 Storm 的 A1 方向可以通过手工替换依赖重现，但正式正例还要求维护者在同一固定源输入下给出精确恢复。现在删除 `@Rule` 或改成 `@ClassRule` 只会证明数据集作者知道如何修，不会恢复历史维护者行为。

Multiverse 的风险更直接：一次计时断言失败可能来自调度抖动、目标实现或执行环境。版本号和提交号可以固定输入，重复测试可以估计失败率，但在没有对应 JUnit 源机制和维护者修复时，无法把它升级为跨仓因果标签。因此三条都不投入重型重放。

## 证据边界

前两条仍是高质量影响线索，适合检查 Marshal 能否从规则校验变化定位到错误的静态字段。第三条只保留为被拒绝的公开失败观察。整个族不贡献正例、限定负例或 A3。

候选明细位于 `candidate-frame.jsonl`，根仓裁决位于 `root-audit.jsonl`，完整统计位于 `history-evidence.json`。

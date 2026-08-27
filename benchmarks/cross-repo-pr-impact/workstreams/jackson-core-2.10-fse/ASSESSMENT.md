# Jackson Core 2.10 的 FSE 关系族历史筛选

更新日期：2026-08-25

## 结论

预筛任务中的 `fse2024-behavioral-0045/0046` 与指定坐标不一致。候选框中，`0045` 是 OpenTripPlanner 的 `jackson-datatype-jdk8 2.10.1 -> 2.11.0`，`0046` 是 json-rules 的 `jackson-datatype-jdk8 2.9.9 -> 2.10.0`。`com.fasterxml.jackson.core:jackson-core`、last passing 2.9.10、breaking 2.10.0 的完整两条记录实际是：

- `fse2024-behavioral-0025`：`wix-incubator/openrest4j` 的 `openrest4j-api`；
- `fse2024-behavioral-0026`：`santanusinha/json-rules` 的根模块。

两个根仓的全部远程历史均没有固定 Jackson 2.10.0 的维护者 A2。openrest4j 的 192 个引用、1,025 个可达提交从未声明 2.10.0。json-rules 的 68 个引用、201 个可达提交中，唯一的 2.10.0 修订是未合并的 Dependabot PR 28 头 `11d3a3f0cdfbac9867948b81378186c76600abcf`；它只改一个 POM 属性，且没有任何后继修复提交。

因此本组在历史筛选后停止：候选 2、根仓 2、固定 2.10.0 的维护者 A2 0、重放 0、接纳 0。

## 候选与仓库身份

| 正确候选 | 客户端 | FSE current / previous / breaking | 根仓 |
|---|---|---|---|
| `fse2024-behavioral-0025` | `com.wix.openrest:openrest4j-api` | 2.9.5 / 2.9.10 / 2.10.0 | `wix-incubator/openrest4j` |
| `fse2024-behavioral-0026` | `io.appform.rules:json-rules` | 2.9.9 / 2.9.10 / 2.10.0 | `santanusinha/json-rules` |

GitHub 把旧地址 `wix/openrest4j` 重定向到 `wix-incubator/openrest4j`，仓库编号为 `7316492`。json-rules 的仓库编号为 `68243583`。两者没有根仓别名重叠。

## 坐标归因边界

这两条记录都不能解释成“只替换 jackson-core 后发生的 core 行为变化”。

json-rules 的根 POM 用同一个 `<jackson.version>` 同时控制 `jackson-core`、`jackson-databind`、`jackson-datatype-jsr310` 和 `jackson-datatype-jdk8`。仓库中唯一的 2.10.0 升级提交也明确一次升级这四个构件。FSE 候选框对四个坐标分别保存了相同的 `Operand is not a number` 失败，说明坐标记录是共享属性升级的四个视图，不是四次独立的源变化。

openrest4j 同样用一个 `<com.fasterxml.jackson.version>` 同时控制 core、annotations 和 databind。它的测试依赖 `wix-restaurants-json 1.7.0` 又固定 `jackson-module-scala` 2.9.5。因此把共享属性升到 2.10.0 会得到 Databind 2.10.0 与 Scala module 2.9.5 的混合运行时。

这个边界不能通过版本号或 Maven 依赖坐标自动消除：版本号能说明最终解析到哪些 JAR，却不能把共享属性的一次多构件替换重新归因为其中某一个坐标。

## json-rules 的有效机制

公开失败位于 `ExpressionTest.java:412`。测试把不存在的 `$.value1` 用作数值操作数，并期望表达式返回 false。产品路径先让 JsonPath 在 `SUPPRESS_EXCEPTIONS` 下返回 Java `null`，随后调用 `ObjectMapper.valueToTree`：

- Databind 2.9.x 对 `valueToTree(null)` 返回 Java `null`，客户端的 `if (jsonNode == null) return false` 生效；
- Databind 提交 `6c3144dfa2856c9ba1c3a2d4089258337bae2b4b`（`Fix #2430`）改为返回非空 `NullNode`；
- 客户端只检查 Java `null`，接着发现节点既不是整数也不是浮点数，于 `NumericJsonPathBasedExpression.java:74` 抛出 `IllegalArgumentException: Operand is not a number`。

提交 `6c3144d` 是 `jackson-databind-2.10.0` 的祖先，不是 `jackson-databind-2.9.10` 的祖先；其发布说明明确写着 `Change ObjectMapper.valueToTree() to convert null to NullNode`。`source-mechanism.patch` 保存该提交中直接改变此合同的实际 hunk。

这精确解释了公开失败，但它是 Databind 机制，不是 jackson-core 源提交。Jackson Core 的发布标签只是共享版本升级中的一个同行构件。

维护者在 2021 年提交 `b2c9626582080d365a978d219c400d0f6bf009a7`，把同一异常分支改为 `return false`。这是语义上匹配的真实修复，但该提交固定 `<jackson.version>2.13.1</jackson.version>`，不是固定 2.10.0 的 A2，不能回接到本组三臂。

## openrest4j 的有效机制

公开失败位于 `LocaleTest.java:49`，第一次调用 `com.wix.restaurants.json.Json.stringify` 时触发 `ExceptionInInitializerError`，记录的底层异常类型为 `JsonMappingException`。

`wix-restaurants-json 1.7.0` 的静态初始化器创建 ObjectMapper 并注册 `DefaultScalaModule`。它固定 Jackson 和 Scala module 2.9.5。Scala module 2.9.5 的 `JacksonModule.setupModule` 明确要求 mapper 的 major/minor 与模块完全相同，否则抛出：

```text
Scala module 2.9.5 requires Jackson Databind version >= 2.9.0 and < 2.10.0
```

openrest4j 的共享 Jackson 属性升到 2.10.0 后，Databind 变成 2.10.0，但测试依赖内的 Scala module 仍为 2.9.5。注册模块时的版本保护精确产生公开的初始化失败。这里同样不存在 jackson-core 的独立行为提交；真正边界是跨模块 minor 不匹配。

openrest4j 的所有可达 POM 只经历 2.5.3、2.6.1、2.7.4、2.8.11 和 2.9.5，没有 2.10.0，也没有后续客户端适配。

## 目标修订边界

FSE 没有保存客户端 Git 修订。json-rules 的公开第 412 行对应测试 blob `1a551ecd2a601c119b676b7e74ec07019ecee686`，出现在 51 个可达提交中。openrest4j 的第 49 行对应测试 blob `c6518079f8b7166393a0cea9a6c24a22f9a34c10`，出现在 616 个可达提交中。仅靠测试名和行号无法恢复唯一输入。

json-rules 的唯一 2.10.0 PR 可以提供一个强 A1 候选，但它没有 A2。openrest4j 连固定 2.10.0 的 A1 历史修订都不存在。手工选择匹配测试 blob、修改共享版本属性，再移植 2021 年的 `return false`，会把 2.10.0、2.13.1 和未知 FSE 修订拼成维护者从未采用的组合。

具体误标风险是把 Databind #2430 或 Scala module 版本保护记到 jackson-core 名下，再把不同 Jackson 版本上的客户端修复当作固定 2.10.0 A2。Git 能固定各提交，Maven 能解析最终 JAR，普通测试也能让手工组合转绿，但三者都不能消除坐标归因和固定输入不一致。因此不执行 A0/A1/A2，也不生成作者修复、限定负例或 A3。

详细结构化证据见 `candidate-frame.jsonl`、`root-audit.jsonl` 和 `source-evidence.json`。

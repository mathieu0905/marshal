# JMockit 1.42 的 FSE 关系族筛选

更新日期：2026-08-25

## 结论

FSE 2024 的完整精确版本框共有 3 条候选、6 个异常观察，分别来自 `ipp-v3-java-devkit`、`oauth2-platform-api` 和 `payments-api`。三个目录都是 `intuit/QuickBooks-V3-Java-SDK` 的模块，折叠后只有 1 个根仓关系。本轮正式接纳 0 条，未执行 A0/A1/A2，也没有限定负例或 A3。

公开失败有清晰的 JMockit 机制：1.42 不再通过 Attach API 自行加载 Java agent，而目标三个模块都没有传入 `-javaagent`。OAuth 和 Payments 的日志直接报告 `JMockit didn't get initialized; please check the -javaagent JVM initialization parameter was used`。但是目标完整历史从未采用 JMockit 1.42，也从未加入 `-javaagent`；维护者面对较新 JMockit 版本导致的测试问题时选择回退到 1.25，而不是在新版本下修复。因此不存在保持 1.42 不变的维护者 A2。

此外，公开工作簿没有记录目标 Git 修订。三个失败方法与 OAuth 日志中的第 69 行只能把检出约束在 `5e5ce63a...` 到 `947c0f1c...` 的主线窗口，不能从窗口内唯一确定一个提交。没有精确目标修订且没有 A2，继续执行三臂只会制造数据集作者修复，不能产生正式因果关系。

## 完整候选框与去重

| FSE 候选 | Maven 模块 | 失败观察 | 根仓 |
|---|---|---:|---|
| `0546` | `com.intuit.quickbooks-online:ipp-v3-java-devkit` | 1 | `intuit/QuickBooks-V3-Java-SDK` |
| `0547` | `com.intuit.quickbooks-online:oauth2-platform-api` | 2 | 同上 |
| `0548` | `com.intuit.quickbooks-online:payments-api` | 3 | 同上 |

三条记录的目录提示都以 `intuit_QuickBooks-V3-Java-SDK` 开头，远程历史中也能同时找到三个模块及对应测试方法。模块数量和异常行数都不能替代关系独立性，所以本组的关系单位是 1 个根仓，不是 3 条或 6 条。

## 上游变化边界

JMockit 1.41 的版本提交是 `094ccebbc4209298dc00fa5d1d0caf1b347c9dd9`。1.42 的变化不是一个提交：

- `1393abf13c3c28e4f547c7dab87436a847c32dda` 让 JUnit 5 和 TestNG 集成直接验证 agent 已初始化，不再尝试自行加载；
- `6af75a3b9b8e3de1cc3b0ef6b19ea8aec251d8d4` 删除通用 Attach API 自加载能力，并把未初始化异常改为工作簿中的 `-javaagent` 提示；
- `8a86aba58163917fb566108a855b9ec4b816da58` 把主制品版本改为 1.42，同时还改了 Javadoc 配置；
- `33d53be506c0ddb47840691ab4b5a92fb7b94001` 同步其余模块版本。

行为起点可以定位到 `1393abf1...`，工作簿中的精确异常文本还依赖 `6af75a3b...`。所以可以把机制限定为“1.42 发布中的强制预加载 Java agent”，不能把整个 1.41 到 1.42 发布差异冒充单一源提交，也不能把版本号提交本身说成行为改动。

## 目标修订恢复边界

工作簿只保存目录、模块、版本、测试方法和错误日志，没有 Git 修订。公开日志仍能提供一个窗口：

- `5e5ce63ab6d7cb873c1183769a4b308882d6ae17` 是默认分支上第一个同时包含三个失败方法的提交；
- 到 `947c0f1c25cd1e36d13296e2bc92e9fd9c893368`，`OAuth2PlatformClientTest.setup` 仍位于日志记录的第 69 行；
- 下一提交 `6c3874591f7fde1bfa5a70244722dd4aff6dd05b` 改动该测试，使同一语句移动到第 67 行。

这证明公开执行对应 2019-10-31 至 2019-12-23 之间的一次检出，但不能证明窗口中的哪一个提交是实验输入。选择窗口起点、终点或任意中间提交都属于推断，不是固定目标修订。

## 维护者历史审计

完整远程引用共有 499 个可达提交，覆盖 2017-01-20 至 2026-07-17。三个模块共有 235 个唯一 POM 内容块，其中 153 个有效声明 JMockit：7 个使用 1.16、4 个使用 1.39、141 个使用 1.25、1 个使用 1.48，使用 1.41 或 1.42 的数量均为 0；另有 1 个内容块只在 XML 注释中保留 1.25，不计作声明。包含 `-javaagent` 的数量也是 0。

历史里有两组容易误判为 A2 的变化：

- Payments 的拉取请求 85 先加入 JMockit 1.39 和 `-Djdk.attach.allowAttachSelf`，随后拉取请求 87 以“revert PR #85 and fix broken tests”为说明退回 1.25。系统属性允许旧版本自行附加，不等于给 1.42 传入 `-javaagent`。
- IPP 的拉取请求 102 中间把 1.25 改成 1.48，随即在合入前退回 1.25，并保留 `-Djdk.attach.allowAttachSelf`。它同样是回退，不是保持新源输入的恢复。

OAuth 模块从加入 JMockit 测试开始就使用 1.25。全历史没有任何维护者提交在 1.42 下恢复三个公开失败契约。

## 为什么不执行三臂

若把版本人工改为 1.42，再由数据集作者给 Surefire 拼接 `-javaagent`，很可能得到 A0 通过、A1 失败、A2 通过。但这个 A2 不存在于维护者历史，且工作簿的目标提交也没有唯一恢复。Git 提交和版本号可以固定我们选定的输入，普通测试可以验证该人工方案，却都不能证明它是维护者对该影响的真实修复。

具体误标场景是把维护者明确选择的“退回 1.25”改写成“维护者适配了 1.42”，再把同一根仓的三个模块计成三条关系。按现有准入顺序，本组应在执行前停止。

## 证据边界

这 3 条记录继续保留为一个高质量的多模块影响线索：它证明 JMockit 强制 Java agent 预加载会同时击中同一仓库的多个测试模块。它不提供精确目标修订、维护者 A2、独立负例或 A3，因此不能进入旗舰正式包，也不能按模块扩散增加关系数量。

机器可读候选、根仓裁决和历史证据分别位于 `candidate-frame.jsonl`、`root-audit.jsonl` 与 `history-evidence.json`；紧凑结果位于 `results/jmockit-1.42-fse-history-screening-2026-08-25/summary.json`。

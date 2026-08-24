# Jersey 1.19.1 候选历史筛选

## 结论

FSE 2024 复现实验中，`com.sun.jersey:jersey-core 1.19 -> 1.19.1` 与 `com.sun.jersey:jersey-server 1.19 -> 1.19.1` 共命中 4 条候选记录、8 次异常观察。表面上有两个仓库名和两个坐标，实际只能算 1 个根仓关系：

- `wordnik/swaggersocket` 会重定向到 `swagger-api/swagger-socket`，两者的 34 条远程引用完全一致；
- 四条记录都指向同一个 `swaggersocket-java-jsr356-client` 模块；
- 两个坐标的变化来自同一个上游提交，并触发同一种兄弟模块版本错配。

上游机制已经定位。Jersey 提交 `4416e81f38c76fa3b72179fdf5947a64b3177343` 把十个模块的 `META-INF/jersey-module-version` 从 `1.19-SNAPSHOT` 改为 `1.20-SNAPSHOT`，且该提交只进入 1.19.1。目标模块却把 core、server、servlet、json 四个 Jersey 组件分别固定在 1.19。FSE 每次只替换 core 或 server 中的一个坐标，于是 `ServiceFinder` 会过滤掉版本标记不同的兄弟模块服务，嵌入式应用无法完成 WebSocket 升级并返回 HTTP 500。

但是，目标完整历史里没有任何 Jersey 1.19.1 采用，更没有维护者把四个兄弟模块一起升级或以其他方式恢复该失败。因此本组在重放前拒绝，正式接纳 0 条。

## 候选框折叠

| 坐标 | 当前所有者记录 | 旧所有者记录 | 原始异常行 | 根仓关系 |
|---|---:|---:|---:|---:|
| `jersey-core` | 1 | 1 | 4 | 1 |
| `jersey-server` | 1 | 1 | 4 | 同上 |

每条候选都包含两个连续异常：首先是服务器以 HTTP 500 拒绝 WebSocket 升级，随后清理阶段报告连接从未打开。这不是两个独立影响，也不能把仓库迁移前后的别名算成两个消费仓。

候选明细位于 `candidate-frame.jsonl`，根仓裁决位于 `root-audit.jsonl`。

## 上游变化边界

版本标签解引用后的提交为：

- `1.19`：`9c7a76c4655a69573d9d29954ed57e23f90b3677`
- `1.19.1`：`8eff6863e79a0b3b3ca6f13be3eec8bb9d9c1117`

关键提交 `4416e81f38c76fa3b72179fdf5947a64b3177343` 的标题为 `Post-release version upgrade in jersey-module-version files.`。它是 1.19.1 的祖先，不是 1.19 的祖先，并同步修改 core、server、servlet、json 等十个模块的版本标记。

这里不能只依据 Git 标签推断发布物。对 Maven Central 四个实际 JAR 的检查确认：

| 发布物 | `META-INF/jersey-module-version` |
|---|---|
| `jersey-core:1.19` | `1.19-SNAPSHOT` |
| `jersey-core:1.19.1` | `1.20-SNAPSHOT` |
| `jersey-server:1.19` | `1.19-SNAPSHOT` |
| `jersey-server:1.19.1` | `1.20-SNAPSHOT` |

`jersey-core` 中的 `ServiceFinder` 会读取自身标记，并检查黑名单内 Jersey 模块的服务描述文件；若对方标记不同，就从候选服务中移除。目标模块同时依赖 core、server、servlet、json 1.19，因此单独替换 core 或 server 都会制造精确的版本错配。

这个结论也限定了影响语义：它证明的是“只升级一个 Jersey 坐标会失败”，不是“完整对齐到 1.19.1 仍会失败”。

## 目标仓历史

`swagger-api/swagger-socket` 的分支与拉取请求引用中共有 409 个可达提交，主分支有 364 个提交。JSR-356 客户端模块由提交 `6dd601941f34257639aab2412cde901d70a25076` 引入。

对历史的检查结果为：

- 全仓共有 519 个唯一 POM 内容块；
- 没有任何 POM 内容块包含 Jersey 1.19.1；
- JSR-356 客户端模块的 POM 只有一个唯一内容版本；
- 该 POM 始终把 core、server、servlet、json 四个组件固定为 1.19；
- 没有维护者提交修复 FSE 记录的版本错配。

仓库后来只是从 `wordnik` 组织迁移到 `swagger-api`，不是第二个独立消费仓，也没有产生 A2。

## 为什么不执行三臂

现有证据足以确定 A1 的机制，但旗舰正例还要求维护者针对同一固定上游输入给出精确 A2。现在把四个 Jersey 依赖一起改成 1.19.1，很可能能恢复测试，却只会证明数据集作者理解了版本对齐要求。

这里的具体误标风险是把“作者补齐兄弟模块版本”冒充“历史维护者修复”。Git 能固定目标历史，发布版本和 JAR 内容能固定源输入，普通测试能测手工方案是否通过，但这些都不能补出不存在的维护者行为。因此不投入重型重放。

## 证据边界

四条记录保留为一个高质量影响线索：Marshal 应能从一个模块的版本标记变化追到同仓 POM 中必须同步升级的其他 Jersey 坐标。但它不贡献正式正例、限定负例或 A3。

完整证据位于 `history-evidence.json`，紧凑结果位于 `results/jersey-1.19.1-fse-history-screening-2026-08-25/summary.json`。

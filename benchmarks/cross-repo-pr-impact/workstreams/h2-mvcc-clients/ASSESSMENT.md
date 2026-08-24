# H2 MVCC 连接设置跨仓关系族

评估日期：2026-08-24

## 结论

H2 1.4.199 到 1.4.200 的 `MVCC` 连接设置变化形成两条可执行的跨仓正关系，目标根仓分别是：

1. `database-rider/database-rider`；
2. `CloudSlang/score`。

公开候选表中的五条记录不能计成五条。Database Rider 对应一个根仓；CloudSlang 的 node 与 orchestrator 是同一根仓内的模块；`openscore/score` 又会解析到同一个 `CloudSlang/score` 仓库，当前提交和 GitHub `node_id` 均相同。因此本关系族只计两个独立目标根仓、两条正关系。

两条关系的 A0、A1、A2 均已由目标原生测试重放。没有找到满足同一连接设置表面且由自身检查证明无需修改的限定负例，也没有找到保持该行为兼容的相邻 H2 变化作为 A3。本包是两条高证据因果关系，不是含负空间和 A3 的完整旗舰项目包。

## 精确源输入

源 PR 是 [h2database/h2database#2143](https://github.com/h2database/h2database/pull/2143)，但 Marshal 输入只取其中真正改变 `MVCC` 行为的提交 `92692e63df10c3f73dd799f122949c705769e7b1`，标题为 `Throw exception on usage of MVCC setting`。它只做两项行为修改：

- 从 `ConnectionInfo` 允许的连接设置中删除 `MVCC`；
- 从 SQL `SET MVCC` 的兼容空操作分支中删除 `MVCC`。

该提交属于 1.4.200，不属于 1.4.199。补丁可以直接应用到 `version-1.4.199`；重建后的 jar 保留 1.4.199 的其余代码。直接 JDBC 探针结果如下：

| 输入 | 旧 `MVCC` URL | 结果 |
|---|---|---|
| H2 1.4.199 | 保留 | 通过 |
| H2 1.4.200 | 保留 | 失败，错误码 `90113` |
| H2 1.4.200 | 删除 `MVCC` | 通过 |
| H2 1.4.199 + 精确行为提交 | 保留 | 失败，错误码 `90113` |

最后一臂排除了 1.4.200 其余发布变化的贡献。源补丁在 `h2-source-mvcc-rejection.patch`，四个探针输出和源构建日志位于结果目录。

## Database Rider

目标基准提交是 `c78ffe0add11caf4f2af07d30b56432f242c2646`，使用 H2 1.4.199，并在 `rider-micronaut` 中配置：

`jdbc:h2:mem:devDb;MVCC=TRUE;LOCK_TIMEOUT=10000;DB_CLOSE_ON_EXIT=FALSE`

维护者 PR [database-rider/database-rider#376](https://github.com/database-rider/database-rider/pull/376) 的合并提交为 `2e38b6e513521f5956a116bff80feb322045c9a3`，其父提交正是上述基准。PR 还包含 H2 2.x 的其他适配；本包只采用与当前合同对应的最小行为修复，即从 URL 删除 `MVCC=TRUE`，不采用其他代码和版本变化。

原生测试 `example.controllers.OwnerControllerTest` 的结果为：

| 臂 | H2 | URL | 结果 |
|---|---:|---|---|
| A0 | 1.4.199 | 旧 URL | 通过，1 个测试 |
| A1 | 1.4.200 | 旧 URL | 失败，`Unsupported connection setting "MVCC" [90113-200]` |
| A2 | 1.4.200 | 只删除 `MVCC=TRUE` | 通过，1 个测试 |

## CloudSlang Score

目标基准提交是 `f72e1adaf5dca565a91c6ab89d9df7ba6fdf8f89`，使用 H2 1.4.199。node 的 `testContext.xml` 和 orchestrator 的两个 Spring 配置都含有：

`jdbc:h2:mem:db1;DB_CLOSE_DELAY=-1;MVCC=TRUE;LOCK_TIMEOUT=5000`

维护者 PR [CloudSlang/score#405](https://github.com/CloudSlang/score/pull/405) 的合并提交为 `ab4fa3d87e26393a0f80f6ae2ce11a64817262d3`，其父提交正是目标基准。该 PR 升级到 H2 2.1.210，并加入 `NON_KEYWORDS`、`MODE=LEGACY` 及大量其他适配。它们属于 H2 2.x 合同，不属于 1.4.200 的 `MVCC` 变化。本包的 A2 只从三个 URL 删除 `MVCC=TRUE`。

两个原生测试分别执行，避免第一个 A1 失败使 Maven reactor 跳过另一个模块：

| 臂 | `WorkerLockRepositoryTest#deleteByUuidTest` | `SuspendedExecutionsRepositoryTest#simpleCreateAndReadTest` |
|---|---|---|
| A0：1.4.199 + 旧 URL | 通过 | 通过 |
| A1：1.4.200 + 旧 URL | 失败，`90113` | 失败，`90113` |
| A2：1.4.200 + 最小 URL 修复 | 通过 | 通过 |

Score 的历史代码以 Java 8 为编译目标，在 Java 11 上缺少已被移出 JDK 的 `javax.annotation.Generated` 和 `PostConstruct`。重放对三臂统一加入 `javax.annotation-api:1.3.2`，只恢复历史编译环境，不改变 H2 版本、连接设置或测试逻辑。第一次未加该依赖的构建失败没有计入 A1。

## 重放与边界

重放入口为 `run_family.sh`。它从精确修订物化三个目标臂，重建精确源提交，分别执行直接探针、Database Rider 原生测试和 Score 两个模块的原生测试。机器结果位于 `results/h2-mvcc-clients-family-2026-08-24/`。

正式计数边界：

- 接受的跨仓正关系：2；
- 正目标根仓：2；
- 折叠的公开记录：5 条折叠为 2 个根仓；
- 限定负例：0；
- A3：0。

当前语义结论仍需另一名复核者独立确认，尤其是公开五条记录的去重和 Score 维护者修复的最小边界；复核前不得把 node、orchestrator 或 `openscore` 别名拆成额外样本。

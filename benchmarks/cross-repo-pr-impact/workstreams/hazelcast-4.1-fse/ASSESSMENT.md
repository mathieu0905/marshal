# Hazelcast 4.1 的 FSE 关系族筛选

更新日期：2026-08-25

## 结论

FSE 2024 的精确候选框包含两条记录：`driver-hazelcast4` 和 `driver-hazelcast4plus` 都在把 `com.hazelcast:hazelcast` 从 4.0 系列替换为 4.1 后，让 `BuildInfoUtilsTest.testGetMinorVersion` 在第 59 行得到 `expected:<0> but was:<1>`。

两个仓名不是两个独立根仓。GitHub 对 `hazelcast/hazelcast-stabilizer` 的请求重定向到 `hazelcast/hazelcast-simulator`，两者返回同一个仓库编号 `11445479`。两个镜像也具有相同的 HEAD、引用集合和 7,409 个可达提交。因此本组是 2 条原始记录、1 个唯一跨仓关系。

源机制可以精确解释失败，但目标历史里不存在固定 Hazelcast 4.1 的维护者 A2。相关驱动从 4.0 直接进入 4.2 或 5.x；全部远程历史都没有 4.1 声明，也没有把该测试所依赖的默认 minor 改为 1 的提交。本轮在重放前拒绝，A0/A1/A2 均不执行，正式接纳 0 条。

## 完整候选框

| 候选 | 原始仓名与模块 | 公开失败 | 根仓裁决 |
|---|---|---|---|
| `fse2024-behavioral-0157` | `hazelcast/hazelcast-simulator`，`drivers/driver-hazelcast4` | `BuildInfoUtilsTest.java:59`，期望 0、实际 1 | 无固定 4.1 的维护者 A2 |
| `fse2024-behavioral-0158` | `hazelcast/hazelcast-stabilizer`，`drivers/driver-hazelcast4plus` | 同一测试、同一断言 | 仓名是 simulator 的旧别名，折叠到同一根仓 |

候选明细保存在 `candidate-frame.jsonl`，去重后的单根审计保存在 `root-audit.jsonl`。

## 源版本与机制

源仓 `hazelcast/hazelcast` 的 GitHub 仓库编号为 `3786237`。三个发布标签解引用为：

- `v4.0`：`8b959f580ab91d42c071eac142feb04c5acea72f`，根 POM 版本为 4.0；
- `v4.0.6`：`32f20b11ad3c02547120927ca8e55c100c48755a`，根 POM 版本为 4.0.6；
- `v4.1`：`072dc5e1b279e651fc6af9b64397c9ca99b2faa1`，根 POM 版本为 4.1。

这里不是 `BuildInfoProvider` 的解析算法在 4.1 中发生了改变。三个标签中的 `GeneratedBuildProperties.java` 模板 blob 都是 `d2f88ee416dec2f00b781cd1ba5f7e51295d7bd9`，`BuildInfoProvider.java` blob 都是 `8bfeadff216e59fcf01bdebdf8ce7f9045e872a5`。构建时，`hazelcast/pom.xml` 的资源插件以过滤模式复制 Java 模板，把 `VERSION = "${project.version}"` 替换为 Maven 项目版本；`BuildInfoProvider` 再读取这个静态 `VERSION` 字段并构造 `BuildInfo`。

目标侧的 `BuildInfoUtils.getMinorVersion()` 调用 `BuildInfoProvider.getBuildInfo().getVersion()`，再解析第二段。因此 4.0 与 4.0.6 返回 minor 0，4.1 返回 minor 1，而硬编码的 `DEFAULT_MINOR_VERSION` 仍为 0。公开断言正好观测到这条版本元数据路径。

提交 `b01417639a16b9be41c4a34396bc502fc0257eae` 把根模块和 Hazelcast 模块从 `4.0-SNAPSHOT` 切到 `4.1-SNAPSHOT`；发布提交 `072dc5e1b279e651fc6af9b64397c9ca99b2faa1` 再把 `4.1-SNAPSHOT` 固定为 `4.1`。前一提交是 `v4.1` 的祖先，但不是 `v4.0` 或 `v4.0.6` 的祖先。`source-mechanism.patch` 保存前一提交中直接进入模板过滤输入的两个 POM 版本 hunk。

## 目标历史

`driver-hazelcast4` 在提交 `31718782c6a5a9b866bf078f99f00b0cea286180` 中以 `<hazelcast.version>4.0</hazelcast.version>` 出现。提交 `1c4623248435420fd00b436123a93f058354e167` 后，模块改名为 `driver-hazelcast4plus`，版本仍是 4.0。随后可达分支或提交出现过 4.0.5、4.2、5.0、5.1 以及更高版本，但从未出现 4.1。

对四个历史模块 POM 路径的全部版本变更 hunk检查得到 20 个唯一 `hazelcast.version` 值，范围从 4.0 到 6.0.0-SNAPSHOT，其中没有 4.1 或 4.1-SNAPSHOT。精确的全引用正则搜索也返回空集。

提交 `5eacaaed1c525daeada8f0d737739d7c2e249823` 标题为 `Fix the version upgrade related test failure`，但它不是本组 A2。它的父提交已把同一分支的驱动改到 `5.0-SNAPSHOT`，补丁只把默认和 fallback major 从 4 改为 5，minor 仍为 0。它修复的是 Hazelcast 5 升级，不是固定 4.1 时的 minor 断言。全部 `BuildInfoUtils` 历史也没有 `DEFAULT_MINOR_VERSION = 1` 或等价断言。

## 目标修订不可恢复

FSE 记录没有保存客户端 Git 修订。公开堆栈第 59 行对应的测试 blob 为 `7d18077cff5558b24a859c8e6bc67984ecb5daed`，其中断言是 `assertEquals(DEFAULT_MINOR_VERSION, getMinorVersion())`。这个 blob 在 `driver-hazelcast4` 路径出现在 206 个可达提交中，在重命名后的 `driver-hazelcast4plus` 路径出现在 69 个提交中，搬到 `java/` 后又出现在 1,051 个提交中。公开行号和测试名无法唯一恢复 A1 输入。

同一时期两个模块中的 `BuildInfoUtils.java` blob 都是 `05654e31ba3d673c2f72866434e3ed712f8367c0`。它把默认 minor 固定为 0，但实际无参方法读取依赖提供的版本。这进一步确认失败机制，却仍不能把数百个匹配修订缩成一个维护者目标修订。

## 为什么不执行三臂

手工选择任一匹配提交、把 POM 改成 4.1，再把默认 minor 改成 1，可以构造一个会先红后绿的组合，但那是作者制作的修复，不是维护者在固定 4.1 输入下采用的 A2。普通测试只能证明该组合通过；Git 能固定所选端点，版本号能固定依赖，却都不能证明这个组合对应 FSE 的未知目标修订或维护者响应。

这里的具体误标场景是把 2021 年针对 Hazelcast 5 的 major 修复错接到 2020 年的 Hazelcast 4.1 minor 失败上，从而把不同依赖版本、不同分支输入和不同断言值拼成一个虚假的因果三臂。现有准入条件正是为排除这种混接；本 workstream 没有新增冻结合同或门禁。

最终计数：原始候选 2，唯一根仓 1，公开失败观察 2，精确源机制 1，固定目标修订 0，固定 4.1 的维护者 A2 0，重放 0，正式正关系 0，限定负例 0，A3 0。

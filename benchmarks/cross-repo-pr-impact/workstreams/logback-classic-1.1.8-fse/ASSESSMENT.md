# Logback Classic 1.1.8 的 FSE 关系族筛选

更新日期：2026-08-25

## 结论

完整精确版本框共有 3 条候选，按仓库编号和历史重定向去重后仍是 3 个独立客户端根仓。三条都能在 Java 8 下重现同一个初始化失败：客户端只把 Logback Classic 换成 1.1.8、继续保留旧 Logback Core 时，首次底层异常都是缺少 `ch.qos.logback.core.util.StatusListenerConfigHelper`。

相邻源版本对照进一步确认了共同机制。三个客户端在 Classic 1.1.7 与相同旧 Core 的组合下均会触发同一个缺类错误，但 1.1.7 的 `StaticLoggerBinder` 会捕获 `Throwable`，目标测试仍通过；1.1.8 把边界缩为 `Exception` 后，`NoClassDefFoundError` 逃逸，目标测试全部进入错误状态。

三仓的全部可达提交都没有固定 Classic 1.1.8 的维护者恢复。Libcrunch 和 Wro4j Taglib 的实质维护历史在 1.1.8 发布前已经结束；Goodies 后来从 1.1.2 直接跳到 1.2.10。因此本轮是 3 条执行验证的破坏线索、0 条正式正关系、0 条限定负例、0 条 A3，不制造 A2，也不计为完整项目包。

## 完整候选框

| 候选 | 目标模块 | 根仓 | 裁决 |
|---|---|---|---|
| `0002` | `com.twitter:libcrunch` | `twitter-archive/libcrunch` | 无固定 1.1.8 A2 |
| `0004` | `com.orange.wro4j:wro4j-taglib` | `Orange-OpenSource/wro4j-taglib` | 仓库历史早于 1.1.8 |
| `0005` | `org.sonatype.goodies:goodies-testsupport` | `sonatype/goodies` | 后续直接升级到 1.2.10 |

`twitter/libcrunch` 当前重定向到 `twitter-archive/libcrunch`，仓库编号保持为 `8326033`。另外两仓的编号分别为 `6466476` 和 `2698192`，所以三条不存在别名重复。

## 精确源机制

源提交 `58646866d5e5dedfe100b296f03f65791dbd9262` 只修改 `StaticLoggerBinder.java` 一行：初始化边界由捕获 `Throwable` 改为捕获 `Exception`。该提交属于 `v_1.1.8`，不属于 `v_1.1.7`。

三个客户端都显式保留比 1.1.7 更旧的 Core。Classic 1.1.7 和 1.1.8 的 `ContextInitializer` 都调用 Core 中较新的 `StatusListenerConfigHelper`，因此两者都会遇到同一 `NoClassDefFoundError`。差别在于 1.1.7 吞掉这个 `Error` 后仍返回日志上下文，而 1.1.8 让它逃逸。三个根仓的相邻版本对照都呈现这一模式，因此可以归入同一个源机制，而不是仅因共享版本号合并。

精确提交差异保存在 `source-mechanism.patch`。

## 执行结果

| 根仓 | A0：维护者版本 | 1.1.7 对照 | A1：1.1.8 | 首次底层异常 |
|---|---:|---:|---:|---|
| Libcrunch | 1/1 通过 | 1/1 通过 | 1/1 错误 | `StatusListenerConfigHelper` 缺失 |
| Wro4j Taglib | 8/8 通过 | 8/8 通过 | 8/8 错误 | 同上 |
| Goodies Testsupport | 1/1 通过 | 1/1 通过 | 1/1 错误 | 同上 |

1.1.7 对照的“通过”不表示日志初始化正常：Libcrunch 与 Wro4j 的输出明确保留了被捕获的缺类错误。它证明的是目标测试没有因此失败，恰好隔离出 1.1.8 的异常边界变化。

## 历史审计

Libcrunch 的全部分支、标签和拉取请求引用共有 10 个、19 个可达提交；POM 历史始终固定 Classic/Core 1.0.1。Wro4j Taglib 共有 15 个引用、113 个可达提交；POM 历史始终固定 1.0.7。

Goodies 共有 166 个引用、906 个可达提交。全部可达 XML 历史没有 Classic 或 Core 1.1.8；2022 年维护者才由 1.1.2 升到 1.2.10。这个后续升级跨越多个源版本，不能替代固定 1.1.8 下的独立维护者恢复。

## 证据边界

FSE 工件没有给出三个客户端的精确提交。Libcrunch 和 Wro4j 使用其封存历史中的最终版本；Goodies 使用 1.1.8 发布前、已经包含命中测试且仍固定 1.1.2 的维护者提交 `5c3560a63247daa9222e60d8cf09496a7ba1e293`。这些是可重放见证点，不冒充原论文执行时的精确检出提交。

未接纳只表示缺少当前合同要求的维护者 A2，不表示三仓未受影响。机器可读候选和根仓裁决位于本目录；执行报告位于 `results/logback-classic-1.1.8-fse-screening-2026-08-25/`。本工作流没有修改公共候选台账、结果索引或 `.claude`，也没有独立提交。

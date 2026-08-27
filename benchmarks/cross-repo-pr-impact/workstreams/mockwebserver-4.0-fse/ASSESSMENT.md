# MockWebServer 4.0.0 的 FSE 关系族筛选

更新日期：2026-08-25

## 结论

完整同转换框共有 2 条候选、2 个失败观察。按 GitHub 仓库编号去重后，对应 `jasminb/jsonapi-converter`（`52023675`）和 `OpenGamma/JavaSDK`（`81832169`）两个独立根仓。本轮正式接纳 0 条，没有执行客户端 A0、A1、A2，也没有限定负例或 A3。

jsonapi-converter 的全部 130 个 refs 中没有任何提交固定 MockWebServer 4.0.0。JavaSDK 的全部 319 个 refs 中有 2 个固定 4.0.0 的提交，但它们分别只是关闭未合并的 Dependabot PR #117 和 #250，均只改一行版本属性，没有生产代码或测试恢复。严格维护者 A2 仍为 0，因此本组在客户端重放前停止。

## 完整候选框

| FSE 候选 | 目标模块 | 当前版本 | 最后通过探针 | 首个失败探针 | 公开失败 |
|---|---|---:|---:|---:|---|
| `fse2024-behavioral-0178` | `com.github.jasminb:jsonapi-converter` | 3.12.0 | 3.14.9 | 4.0.0 | `RetrofitTest.destroy:55` 空指针 |
| `fse2024-behavioral-0179` | `com.opengamma.sdk:sdk-common` | 3.14.9 | 3.14.9 | 4.0.0 | `ServiceInvoker` 静态初始化缺类 |

完整框按 `previous_version=3.14.9` 与 `breaking_version=4.0.0` 取值，所以 `0178` 虽然项目声明版本为 3.12.0，也不能按 `current_version` 排除。

## 源版本边界

OkHttp 仓库编号为 `5152285`。`parent-3.14.9` 指向 `ad97bd3df34376eec85aa187dc8f45cfde8a2c01`，日期为 2020-05-17；`parent-4.0.0` 指向 `911c5bf5b27e8378f209861a16a9da4cc54cfff7`，日期为 2019-06-26。两者从 `0f87d95c7de96ae028fb403f57ade0c7f8fca33f` 分叉。

因此 FSE 的“3.14.9→4.0.0”是探针顺序，不是发布时间顺序：4.0.0 先发布，3.14.9 后来从 3.x 维护分支发布。不能用线性的 `3.14.9..4.0.0` 全差异冒充单个升级提交。

## 两个精确机制

### jsonapi-converter：MockWebServer 4 与 OkHttp 3 混装

提交 `6d872df83bd9e377c6309e4cb1365faf60fffbd5` 把 MockWebServer 构造期的协议列表从 `Util.immutableList(...)` 改成 Kotlin 顶层 `immutableListOf(...)`。4.0.0 发布 JAR 的 `MockWebServer.class` 因而调用 `okhttp3.internal.Util.immutableListOf(Object[])`；OkHttp 3.12.0 只有 `Util.immutableList`，没有新方法。

目标 POM 先声明 Retrofit 2.5.0，再声明 MockWebServer。Retrofit 带来 OkHttp 3.12.0；只把 MockWebServer 换成 4.0.0 会形成混合类路径。最小探针在对齐的 4.0.0/4.0.0/2.2.2 类路径上完成启动和清理，在混合 4.0.0/3.12.0/1.15.0 类路径上先得到上述 `NoSuchMethodError`，构造赋值未完成，随后无条件 `shutdown()` 得到与工作簿相同的清理空指针。

### JavaSDK：OkHttp 4 与固定 Okio 1 混装

提交 `e2cfcb35ea52b28dc443c24760d1cf2325d60f07` 把 OkHttp 4 分支的 Okio 要求从 1.17.2 升到 2.2.2。4.0.0 发布 JAR 中的 `okhttp3.internal.Util` 静态初始化器链接 `okio.Options.Companion`；该嵌套类和字段在 Okio 1.17.5 中不存在。

JavaSDK 采用 OkHttp 3.14.9 时仍固定 `okio.version=1.17.5`。与 `ServiceInvoker` 三个静态常量相同的探针在 Okio 2.2.2 下连续初始化成功，在 1.17.5 下首次得到 `NoSuchFieldError: okio.Options.Companion`，第二次访问得到 `NoClassDefFoundError: Could not initialize class`。这与公开的 `ServiceInvoker` 外层错误一致。

两个源摘录和可重复探针分别保存在 `source-mechanism-jsonapi.patch`、`source-mechanism-opengamma.patch` 与 `MECHANISM_PROBE.md`。它们证明兼容性机制，不补造客户端修复。

## 目标历史审计

### jsonapi-converter

提交 `221f086e8db7e822d019a670e7558e5da230816e` 在 2019-07-19 同时把 Retrofit 升到 2.5.0、MockWebServer 升到 3.12.0，并保留失败测试的 setup/cleanup 形状。镜像包含 3 个 heads、16 个 tags、111 个 pull refs 和 382 个唯一可达提交。对每个提交的 POM 用 XPath 读取目标 dependency 的版本，固定 4.0.0 的结果为 0。

### JavaSDK

提交 `94ab1dba29bbeea63d985b9ebbfcd9ab869d6408` 在 2020-11-03 采用 3.14.9，同时仍固定 Okio 1.17.5。镜像包含 14 个 heads、29 个 tags、276 个 pull refs 和 658 个唯一可达提交。

完整历史仅发现两个 4.0.0 树：`deb3149b46767e957bdb3a8dd6cf936e972a24b7` 属于 PR #117，从 3.13.1 改到 4.0.0；`05c4c4468de29c0bcbe55f9855836a8edddd7644` 属于 PR #250，从 3.14.9 改到 4.0.0。两者都只修改 `modules/pom.xml`，都由 Dependabot 创建、关闭且未合并，refs 也只包含各自的 pull head。它们是失败输入提案，不是维护者恢复。

后续未合并 PR 尝试过 4.9.3；默认分支直到 2026 年才在更高版本迁移后固定 4.12.0 与 Okio 3.6.0。改变目标版本和依赖组合不能倒推成固定 4.0.0 的 A2。

## 为什么不执行客户端三臂

工作簿没有保存两个目标的 Git 修订。更关键的是，目标历史中没有任何维护者提交在保持 MockWebServer 4.0.0 时修复公开契约。若选择一个方便的旧提交，再升级 Retrofit/OkHttp/Okio 或给 cleanup 加空值保护，会同时制造 A1 输入和 A2。

具体误标场景是把 JavaSDK 关闭的 PR #250 当作“维护者采用 4.0.0”，再把本轮自行升级 Okio 的补丁当作“维护者恢复”。Git、版本号和普通测试可以证明这个人工组合能运行，却不能把关闭的单行机器人提案变成维护者修复。按既定准入顺序，本组只执行源依赖机制测量，不执行客户端 A0/A1/A2。

## 证据边界

本组证明两个独立根仓的公开失败分别来自 OkHttp 3/4 和 Okio 1/2 的二进制混装机制。它不提供精确目标修订或维护者 A2，也不提供限定负例或 A3。机器可读候选、根仓裁决与源证据位于本目录；refs 扫描、机制日志和紧凑结论位于对应 results 目录。

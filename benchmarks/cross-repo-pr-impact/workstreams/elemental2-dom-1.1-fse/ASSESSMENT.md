# Elemental2 DOM 1.0.0-RC1 到 1.1.0 的 FSE 关系族筛选

更新日期：2026-08-25

## 结论

FSE 2024 的完整精确版本框共有 2 条候选、4 个异常观察，分别来自 `TDesjardins/gwt-ol` 和 `intendia-oss/rxjava-gwt`，去重后仍是 2 个独立根仓。本轮正式接纳 0 条，没有执行 A0、A1、A2，也没有限定负例或 A3。

公开工作簿只保留了顶层 `com.google.gwt.core.ext.UnableToCompleteException: (see previous log entries)`。每个仓的第一条记录经过 `JUnitShell.compileForWebMode`，第二条记录从后续的 `JUnitShell.runTestImpl:1343` 抛出；异常明确要求查看此前日志，但此前 GWT 编译诊断不在工作簿中。因此，现有公开失败签名不足以把异常归到 1.1.0 的某个具体 DOM 类型、生成代码变化或传递依赖变化。

两个目标仓的完整可见历史也都没有严格 A2。`gwt-ol` 从未采用 1.1.0；`rxjava-gwt` 虽然后来采用 1.1.0，但同一提交同时更换 Java 目标、GWT、RxJava、Reactive Streams、JUnit 和 GWT Maven 插件，且没有目标代码或测试修订。它是一笔宽泛工具链采用，不是能够在固定 1.1.0 下单独解释公开失败恢复的维护者修复。

## 完整候选框

| FSE 候选 | 目标模块 | 公开测试 | 异常观察 | 根仓 |
|---|---|---|---:|---|
| `fse2024-behavioral-0065` | `com.github.tdesjardins:gwt-ol3` | `ol.ObjectTest:testObject`、`ol.CollectionTest:testCollectionEvents` | 2 | `TDesjardins/gwt-ol` |
| `fse2024-behavioral-0066` | `com.intendia.gwt:rxjava2-gwt` | `RxGwtTest:test_that_interval_works`、`RxGwtTest:test_that_retry_and_trampoline_works` | 2 | `intendia-oss/rxjava-gwt` |

四条原始记录均声明编译作用域、Java 8、旧版 1.0.0-RC1 和替换版 1.1.0。工作簿记录号分别为 `8380`、`8381`、`7253`、`7254`，没有记录目标 Git 修订。

## 公开失败证据的边界

两组栈的共同顶层异常只能证明 GWT 测试编译未完成。第一条记录显示失败经过 Web 模式编译阶段；第二条记录只保留从 `JUnitShell.runTestImpl:1343` 开始的较短后续栈。工作簿中的“see previous log entries”不是具体编译消息，也没有类型名、源文件、行号或编译器错误正文。

因此不能从当前材料断言 1.1.0 的 89 个新增 source-jar 条目、某个生成 DOM 签名或 `jsinterop-annotations` 2.0.0 单独导致了这四次失败。完整诊断只能由原始运行日志、原始环境镜像或严格重放补回；本轮没有下载约 9.96 GB 的 Zenodo 环境归档，也没有用猜测替代缺失日志。

## 源发布边界

`google/elemental2` 的公开 Git 历史没有保留 1.0.0-RC1 标签。当前能恢复的最窄发布边界是：

- `527ebb5ce214d62806313555c48a7cda5f972827` 在 2017-12-14 将 `jsinterop-base` 升到 1.0.0-RC1，是发布文档前最后一个构建输入变化；
- `c147fef4407f511ba65c2f61934331174dfcd784` 随后把 README 的 Maven 版本和制品链接从 beta-3 改成 1.0.0-RC1，公开确认了发布；
- 1.1.0 的注解标签对象为 `e0543dbb7f95199e5719abfa8102817227b56836`，解引用到提交 `1be8301a99cc5f1b4b2a98c2fa644ecc227d1dbc`。

从文档边界到 1.1.0 有 208 个提交，从构建输入边界到 1.1.0 有 209 个提交。对应 source jar 从 420 个条目增至 509 个；POM 还把 `jsinterop-annotations` 从 1.0.2 升至 2.0.0、`jsinterop-base` 从 1.0.0-RC1 升至 1.0.0，并把 `elemental2-core` 和 `elemental2-promise` 从 RC1 升至 1.1.0。

提交 `eb0e3f12bad7f89c77cfdda5b82edbcf18bf02c4` 可以精确解释注解依赖升级，但公开异常没有保存命中该变化的编译消息。把它或任一生成 DOM 变更指定为本组源机制都会越过证据边界。1.0.0-RC1 的精确制品提交同样不能从当前公开 Git 历史进一步收窄。

## 目标历史审计

### `TDesjardins/gwt-ol`

完整镜像在 heads/tags 中有 1329 个唯一可达提交，纳入 pull refs 后有 1598 个。`f0f4db8f546e0b998768a3b373935df5098e8835` 在 2017-12-18 从 beta-3 升到 1.0.0-RC1；RC1 在维护线中一直保留到 `b31a47d9c96be94584b789c1ef2fe04f1e63b401`。

其后 `fd6e2e791367824479e3a9da3b1372f2f5b608b4` 把 Elemental2 Core/DOM 从 RC1 升到 1.0.0，同时把 GWT 2.8.2 升到 2.9.0，并修改两个源文件以适配相关变化。完整历史没有任何 Elemental2 DOM 1.1.0 采用，因此不存在保持 1.1.0 的维护者 A2。

### `intendia-oss/rxjava-gwt`

完整镜像有 95 个唯一可达提交。`e7227bfb809ba872411c471184393c01a979e03b` 首次加入 Elemental2 DOM 1.0.0-RC1，`e06f0c58987736d9edbd439b70b02891367b6e40` 是 1.1.0 采用前主线的最后历史基点。

`516c5d3553ff740e49a4e4323802afb1935ffe23` 首次采用 1.1.0，但同一个 `pom.xml` 提交还完成 Java 1.6 到 11、GWT 2.8.2-rx1 到 2.9.0、RxJava 2.2.10 到 2.2.21、Reactive Streams 1.0.2 到 1.0.3、JUnit 4.11 到 4.13.2 和 GWT Maven 插件 1.0-rc-10 到 1.0.0 的升级。`db97af8c9828dd10ec4128906c3c6198f2451481` 是同父提交、同 tree 的未合并副本。随后 `cb6796e48ef77d7552dc9fcff952444202525a94` 保留 1.1.0，但只调整编译目标、仓库和 README，没有修复公开测试或提供缺失的编译诊断。

所以这里能证明维护者最终采用了一套包含 1.1.0 的新工具链，不能证明其中哪项变化恢复了 FSE 观察，也不存在一个可从宽泛采用中分离出来的严格 A2。

## 为什么不执行三臂

对 `gwt-ol`，任何 1.1.0 下的恢复都必须由数据集作者新写，因为维护者历史从未采用该版本。对 `rxjava-gwt`，若直接把 `516c5d3...` 当作 A2，即使测试变绿，也无法区分恢复来自 GWT 2.9.0、Java 11、测试框架/插件升级、其他库升级还是 Elemental2 相关兼容变化；原始编译错误又已经缺失。

具体误标场景是：选择一个未记录的目标提交合成 A1，再把七组同时变化的依赖和工具链提交作为 A2，最后把绿色测试标签成“维护者在固定 Elemental2 DOM 1.1.0 下修复”。Git 能固定这笔宽泛提交，版本号能证明 1.1.0 在其中，普通测试能证明整套新环境可运行，但三者都不能恢复缺失的编译消息，也不能把维护者修复从同时变化中隔离出来。因此本组在执行前停止，而不是让前置筛选挤占一轮没有可解释结论的重放。

## 证据边界

本组能够证明四条公开失败观察、两个独立目标根仓、1.0.0-RC1 的最窄公开发布边界、精确的 1.1.0 标签提交，以及两个目标的完整可见采用历史。它不能证明 1.0.0-RC1 的唯一制品提交、四条异常的具体 GWT 编译消息、单一源机制或固定 1.1.0 的严格维护者 A2。

机器可读候选、根仓裁决和历史证据分别位于 `candidate-frame.jsonl`、`root-audit.jsonl` 与 `history-evidence.json`。由于准入在执行前即失败，本工作流没有创建运行结果目录。

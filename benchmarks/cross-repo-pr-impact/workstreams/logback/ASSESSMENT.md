# Logback Classic 项目包筛选记录

## 当前结论

Logback Classic 只形成一个单正例三臂锚点，不构成多仓闭集，也没有合格 A3。HTML2POP3 在只升级 Classic、保留旧 Core 时失败，加入维护者实际采用的 Core 协调升级后恢复。Tokendings 与 Kompendium 的构建只声明 Classic，升级后会自动解析配套 Core 与 SLF4J；它们执行的是已经吸收协调的不同依赖图，不能充当 HTML2POP3 同一 A1 输入下的限定负例。

最终正式完整项目包接受数为零。保留 1 个单正例三臂锚点和 2 个依赖解析拓扑对照，不把 15 条绿色或失败命令机械换算成标签。

## 完整候选框

BUMP 固定版本 `324d5513aa5ca40b5cb32de5b816a58fa60bd7bb` 中共有 20 条 Logback Classic 记录、4 个唯一消费仓：

| 消费仓 | 记录数 |
| --- | ---: |
| `alphagov/pay-adminusers` | 7 |
| `feedzai/pdb` | 2 |
| `matteobaccan/html2pop3` | 5 |
| `retest/recheck.cli` | 6 |

`bump-candidate-frame.jsonl` 保留全部记录。另有一条 `pinterest/singer` 的 Logback Core 升级，不属于本项目包源组件。BUMP 的失败分类只作线索，同仓重复升级不乘成独立判断。

## 单正例三臂：HTML2POP3

固定基线为 `matteobaccan/html2pop3@bc401892bc13d8143552dce7c1e8c79f594c680b`。该仓直接声明 Classic 与 Core，基线已使用 SLF4J 2.0.0：

| 臂 | Classic | Core | 结果 |
| --- | ---: | ---: | --- |
| A0 | 1.2.11 | 1.2.11 | 5 项通过 |
| A1 | 1.4.0 | 1.2.11 | 5 项启动后 2 项错误，均为 `EnvUtil.logbackVersion()` 缺失 |
| A2 | 1.4.0 | 1.4.0 | 5 项恢复通过 |

维护历史与这个协调动作一致：PR 291 升级 Classic，PR 290 随后一分多钟合并并升级 Core。A2 不含其他目标代码变化。

其他三个 BUMP 消费仓没有同强度精确恢复。Pay Adminusers 的迁移夹在 Dropwizard 2 到 3 的大升级中；PDB 与 Recheck CLI 没有合并相应的 SLF4J 2 / Logback 1.4 修复。因此不制造第二正例。

## 两个拓扑对照，不是限定负例

Tokendings 固定 `nais/tokendings@1e857fd2b3ccf529f70423c142b79963e3b10990`，执行 `ObservabilityApiTest` 两项。Kompendium 固定 `bkbnio/kompendium@76e6b0a2784d1064b26c33fd1a33128f89688f20`，执行核心模块 50 项测试并保留 3 项待定。两仓测试都真实启动 Ktor 和日志后端，日志表面没有失效。

但两仓只声明 Classic 版本：

| 声明动作 | Tokendings 解析图 | Kompendium 解析图 |
| --- | --- | --- |
| Classic 1.2.11 | Classic/Core 1.2.11、SLF4J 1.7.36 | Classic/Core 1.2.11、SLF4J 1.7.36 |
| Classic 1.4.0 | Classic/Core 1.4.0、SLF4J 2.0.0 | Classic/Core 1.4.0、SLF4J 2.0.0 |

所以它们的绿色结果说明依赖解析能自动带入配套组件，不说明在 HTML2POP3 的 1.4.0/1.2.11 错配输入下无需修改。把它们标成负例会混淆“源声明变化”和“解析后实际输入”，当前只保留为拓扑诊断。

## A3 拒绝

候选为 Classic 1.4.0 到 1.4.1。三个仓的前后主命令都通过，但解析后输入仍不统一：HTML2POP3 显式固定 SLF4J 2.0.0；Tokendings 与 Kompendium 在 1.4.1 后臂解析到 SLF4J 2.0.1。它不是所有仓共享的单一源变化。

覆盖审计也不能挽救这个输入：HTML2POP3 和 Kompendium 执行到 `ContextInitializer` 与 `EnvUtil` 的候选变化行，Tokendings 没有产生可用变化行覆盖。Kompendium 的修复覆盖结果明确标为 `diagnostic_only_graph_differs`。因此 A3 正式接受数为零，不做三次重复。

## 执行结果与边界

最终主轮共完成 3 仓乘 5 配置的 15 条命令。HTML2POP3 唯一非零结果恰好是 A1；Tokendings 两项测试和 Kompendium 50 项测试在五个配置下均通过。每条记录保存实际 Classic、Core、SLF4J 版本、测试数、退出状态与日志表面判断。

机器记录位于：

- `results/logback-project-package-screening-2026-08-24/`
- `results/logback-a3-coverage-repair-2026-08-24/`

重放脚本会在生成紧凑变化行摘要后删除可重建覆盖 XML。首次因系统盘空间、错误 Java 版本和覆盖注入方式产生的尝试目录已删除；最终执行日志、依赖图、测试报告、覆盖执行数据和摘要保留。

## 后续准入条件

1. 新增消费仓必须能在与 HTML2POP3 相同的解析后 A1 输入下执行，不能自动带入 Core 协调升级后再充当负例。
2. 第二正例必须有维护者实际采用且可单独重放的精确恢复，不能从 Dropwizard 或 Spring 大迁移中猜测抽取。
3. A3 必须让所有纳入仓共享同一解析后依赖图，并共同命中真实兼容变化表面。
4. 在这些条件满足前，Logback 只计一个单正例三臂锚点，不进入正式项目包数量。

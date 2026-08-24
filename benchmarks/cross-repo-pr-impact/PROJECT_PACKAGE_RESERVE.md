# 主动项目包长期储备

更新日期：2026-08-24

本文件记录能继续长成主动四臂项目包的来源和候选，不把“候选数量”当成完成度。候选只有在旧组合通过、仅源变化失败、精确目标修复恢复、兼容变化通过，以及相关干扰仓限定负例都具备执行证据后，才进入正式项目包。

## 当前层级

| 层级 | 项目 | 当前证据 | 下一缺口 |
|---|---|---|---|
| 模型质检接受，待人工复核 | Alembic 到六个 OpenStack 消费仓 | 90 条仓库命令，Cinder 三次破坏与恢复，五个限定负例，六仓兼容变化 | 第二位人工盲复核 |
| 永久三臂 | jcabi-aspects 到四个消费仓 | 60 条仓库命令，两个正例、两个限定负例；两轮 A3 覆盖审计均拒绝 | 只保留破坏案例，不计完整项目包 |
| 闭集不完整 | SLF4J 到 Jadler、Password4j、Spotless、RabbitMQ JMS Client | 60 条仓库命令已执行；RabbitMQ 日志行为退化，负标签撤销 | 补可靠第四仓或把 RabbitMQ 正确重标 |
| 历史因果储备 | OpenDev 其余五条强因果关系 | 同任务失败到配套修复成功，已物化失败时点输入 | 扩成含可靠干扰仓与兼容变化的项目包 |
| 单正例锚点 | OpenStack SDK 到 Python OpenStack Client | 字段新增导致输出断言失败，配套修改恢复；17 仓时点输入已完成代码覆盖审计 | 只有一个直接下游消费者；其余仓保持未知，不再为凑四仓主动扩张 |
| 非 Maven 三臂锚点 | escope 到 babel-eslint | Node.js 6 下 A0 通过、A1 复现历史 `visitClass` 异常、PR 244 的 6 行修复使 A2 恢复 | A3 与干扰仓筛选未找到合法负空间；只保留三臂，待重复和独立复核 |
| 非 Maven 单正例四臂锚点 | window-stream 到 Godot | 21 项原生合同下 A0 通过、A1 以期望 10 实际 20 的单一签名失败、一行维护者测试调整使 A2 恢复，A3 两侧通过 | 缺多仓负空间；需三次隔离重复和独立复核，找不到可靠干扰仓时永久保持单正例 |
| 破坏案例成立，A3 拒绝 | terser 到 assetgraph-builder、SAP/ui5-builder、preconstruct、Angular CLI | 统一 4.3.0 后三轮 51 条命令方向与版本 51/51；三个目标适配和 Angular 限定负例成立 | A3 无变化表面证据；Preconstruct 只保留子测试证据 |
| 模型质检接受，待人工复核 | SnakeYAML 到 JClouds、ZIO JSON、YAML JSON、YAML Updater | 60 条命令版本与方向 60/60；两个正例、两个限定负例、四仓共同命中新增 3 MB 判断 | 第二位人工盲复核；超限异常分支不在结论内 |
| 三臂筛选完成 | Plexus Utils 到 pgpverify、license、plexus-io、build-helper | 两个真实破坏与精确恢复，两个执行覆盖明确的限定负例 | 当前相邻兼容变化没有被四仓原生检查共同触及；缺 A3、三次重复和独立复核 |
| 单正例四臂锚点 | Jackson Databind 到 Splunk 等消费仓 | Splunk 精确修复，两个有覆盖的限定负例，四仓兼容变化；2 个源输入、7 个仓库级判断 | 缺第二个高强度正例，不升多正例旗舰包 |
| 三仓高证据锚点 | Log4j Core 到 Neqsim、archifacts、elimu-ai | Neqsim 真实合并三臂，两个限定负例命中同一 `ServiceLoaderUtil` 调用，三仓兼容变化 | 缺第四个可接受仓，不做正式重复 |
| 四仓三臂候选 | AssertJ Core 到 Guava、Vavr、DB、Examples | 两个精确修复正例、两个有覆盖的限定负例 | 两轮 A3 均拒绝，不计完整项目包 |
| 两个单正例三臂锚点 | Commons IO 到 Cucumber Reporting、jcabi Maven Plugin | 两个真实破坏和维护者精确修复；完整搜索框 34 条、25 仓 | 没有可靠负空间与合格 A3，不计完整项目包 |
| 四仓三臂候选 | Checkstyle 到 Gauge、WSS4J、Elementary、Conventional Commit Linter | 两个精确修复正例、两个命中 `FinalClassCheck` 新判定路径的限定负例；完整搜索框 307 条、53 仓 | 10.12.2 到 10.12.3 未进入真实修复路径，A3 拒绝 |
| 两个单正例三臂锚点 | Mockito 到 Apache BVal、junit-quickcheck | 两个不同源输入下的删除接口失败和维护者精确恢复；完整搜索框 55 条、15 仓 | 没有可靠负空间与合格 A3，不计完整项目包 |
| 单正例三臂锚点 | Logback Classic 到 HTML2POP3 | 只升 Classic 后与旧 Core 错配失败，加入 Core 1.4.0 后恢复 | Tokendings 与 Kompendium 会自动连带升级 Core/SLF4J，只作依赖解析拓扑对照；A3 输入也不统一 |
| 筛选拒绝 | Spring Core | 完整框 32 条、7 仓；20 条已复现失败均跨 Java 17 基线，两个可重放仓 A0 通过、A1 在字节码版本处失败 | 失败升级无维护者精确恢复；LPVS 后续 24 文件迁移不能拆成 A2，正式接受数 0 |
| npm 恢复搜索框 | 25 条客户端先恢复记录 | 12 条含真实代码修改，13 条只调整版本；64 条原始记录完整公开 | 逐条核对原生测试、修复精度和独立关系，不把论文标签直接当正式真值 |
| npm 语义拒绝 | test-machinepack 到 test-machinepack-mocha | 2.1.19 的 0/6 失败由源仓 2.1.22 恢复；目标一行修复对 2.1.19 仍为 0/6，且不在真实客户端执行路径上 | 作为恢复归因反例保留，不进入因果案例储备 |
| npm 语义拒绝 | request 到 PolyClay | 三臂重放显示 2.18.0 修复了旧版空响应崩溃，而 PolyClay 1.4.0 删除 Couch 适配器，不是同一合同的恢复 | 公开标签方向被执行证据推翻，不进入因果案例储备 |
| 版本化生态子轨 | 四条 Crater 修复 | 三臂各重复三次 | 不冒充仓库级闭集；继续保留为独立子轨 |

## BUMP 全量来源复核

对 BUMP 固定版本 `324d5513aa5ca40b5cb32de5b816a58fa60bd7bb` 的 571 条可重放记录重新分组。其自带汇总含 175 个依赖坐标；按“可解析源仓、依赖坐标、唯一消费仓”重算后，有 12 个源项目至少关联三个唯一失败消费仓：

| 源项目与坐标 | 唯一消费仓 | 记录数 | 失败类型 |
|---|---:|---:|---|
| FasterXML Jackson Databind | 13 | 33 | 编译、测试、依赖锁、约束检查 |
| SLF4J API | 7 | 36 | 测试 |
| SnakeYAML | 6 | 9 | 编译、测试 |
| Log4j Core | 5 | 7 | 测试 |
| Plexus Utils | 5 | 5 | 编译、测试 |
| Logback Classic | 4 | 20 | 编译、测试 |
| AssertJ Core | 4 | 6 | 编译、约束检查 |
| Checkstyle | 4 | 4 | 约束检查 |
| jcabi-aspects | 4 | 4 | 编译 |
| Spring Core | 3 | 20 | 编译 |
| Mockito Core | 3 | 7 | 编译、测试 |
| Commons IO | 3 | 3 | 编译、测试、警告即错误 |

另有三个至少三仓的坐标缺少可解析源仓，暂不进入项目包储备。BUMP 只收已观察到失败的依赖升级，所以这张表是正例与修复线索的搜索框，不提供干扰仓负标签，也不代表 Maven 生态中的自然发生率。

表内多数行只统计 BUMP 已成功重放的主数据。完整归档漏斗更大：AssertJ 为 12 条、5 仓，其中 6 条已成功重放；Commons IO 为 34 条、25 仓，其中 3 条已成功重放；Checkstyle 为 307 条、53 仓，其中 4 条属于正式重放集；Mockito 为 55 条、15 仓，其中 7 条属于正式重放集。未成功重放记录仍属于搜索框，不能静默丢弃，也不能直接当失败真值。

Jackson、SLF4J、jcabi、Plexus Utils、SnakeYAML、Log4j Core、AssertJ、Commons IO、Checkstyle、Mockito、Logback 和 Spring Core 已完成主动筛选。Plexus Utils、jcabi、AssertJ 与 Checkstyle 都因没有合格兼容变化停在三臂；Log4j Core 因只有三个可接受仓停在高证据锚点；Jackson 保留为单正例四臂锚点；Commons IO、Mockito 与 Logback 只保留单正例锚点；Spring Core 接受数为零。只有 SnakeYAML 与 Alembic 通过当前模型语义质检，仍待第二位人工盲复核。

## 扩展顺序

1. 模型语义质检已完成并撤销 jcabi、terser 的 A3 与 RabbitMQ 负标签；继续安排第二位人工盲复核，同一执行者再次阅读不算独立复核，模型质检也不冒充人工复核。
2. escope 到 babel-eslint 已确认只能作为三臂锚点；window-stream 到 Godot 已形成单正例四臂筛选。后续重复不改变两者缺少可靠多仓负空间的边界。
3. OpenStack SDK 的 17 仓审计已经证明当前搜索空间只有一个直接下游消费者，不再把一般性 SDK 依赖仓或上游服务仓拿来补数量。
4. 按 `NPM_CAUSAL_SOURCE_ASSESSMENT.md` 的 25 条客户端恢复搜索框继续核对真实代码修复；terser 四仓已完成统一 4.3.0 的隔离重复，不把三个目标拆成独立源案例，也不把一个负例解释成完整影响面。`node-minify` 与 `fis3-plugins` 已因缺少变化表面执行覆盖而拒绝，说明无目标修改的依赖升级不能自动成为负标签；`test-machinepack` 已因源仓自修复与目标路径不相关而拒绝，版本调整只能作为兼容动作单独分层。
5. SnakeYAML 已完成三次隔离重复并通过模型质检；Plexus Utils、AssertJ、Checkstyle 和 jcabi 保留三臂结果，不为补 A3 接受未触及变化表面的绿色构建。项目包按关系分路并行，完成一组立即续派下一组；当前执行 Logback 与 Spring Core，并从 npm 恢复框继续选择独立关系。
6. 持续保存 OpenDev 最近窗口，在执行清单和日志失效前完成语义核验。

“首批十个项目包”是用于检查关系隔离、生态覆盖和正式集划分是否可行的中间规模，不是长期目标的终点。即使达到十个，独立复核、保留集、Marshal 实测和可比系统运行仍未完成时，旗舰评测也不能宣告完成。

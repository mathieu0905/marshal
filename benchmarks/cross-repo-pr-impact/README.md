# Marshal 跨仓评测体系

本目录包含两条独立轨道。现有 100 条正式案例是“规范采纳与跨仓适配校准轨道”：评测输入包含源 PR 创建时的差异，以及同一观察截止时间之前各候选仓库的代码版本；隐藏标签保存公开历史中已核验的实现和适配目标。

正在建设的“跨仓破坏影响发现旗舰轨道”只接收真实失败到配套修复的执行对照。两条轨道禁止混合计分或解释。完整任务边界和因果准入条件见 `TASK_DEFINITION.md`，执行证据来源的实测取舍见 `CAUSAL_SOURCE_ASSESSMENT.md`。

校准轨道不是完整因果影响集合。它适合评价候选仓排序和已知适配找回能力，不适合计算误报率或证明某个未标注仓库不受影响。

## 规模与组成

- 100 个唯一源 PR、190 个目标 PR，覆盖 22 个源仓、45 个目标仓和 46 种有向仓库关系；
- 59 条案例有多个目标仓：44 条有 2 个、10 条有 3 个、4 条有 4 个、1 条有 5 个；
- 85 条 GitHub 规范或协议实现案例，来自 Ethereum、OpenTelemetry、OpenContainers、Kubernetes、Python 和 Rust；
- 13 条 OpenDev 非规范案例，覆盖运行时元数据、部署配置、包依赖、服务启用、持续集成变量、客户端与服务校验、共享接口、生成配置、状态模式和跨仓测试所有权；
- 1 条 Cinder 持续集成失败到修复对照，1 条 WanderTracks 固定版本组合执行案例；
- 年份覆盖 2017 至 2026 年。

旧的 99 条“规范仓固定映射到单一实现仓”数据保存在 `cases-spec-retrieval-v1/`，不再进入正式索引。

旗舰轨道当前有 6 个通过初次语义复核的 OpenDev 因果储备：历史回挖保留 2 个，滚动窗口新增 4 个。扩大到 2026-08-01 之后的窗口共检查 394 个变更、20 个依赖转换和 27 个结构通过任务；扣除已复核重复项后，20 个新任务中只有 5 个支持源差异导致的跨仓修复，对应 3 个新案例。Prow 约 90 天预提交历史另扫描 35,805 次执行，从 1,090 个状态窗口收紧到 11 个结构候选，但代码树与失败语义复核后接受 0 个。通用 Prow 历史因此不作为主体来源；完整漏斗见 `results/prow-three-arm-scan-2026-08-23.json`。独立的 Crater 版本化生态破坏子轨已完成 4 条三臂重放，不并入仓库级旗舰分数。

新的 FSE 2024 行为破坏搜索框从 1,043 条真实客户端测试失败记录聚合出 703 个“依赖升级到破坏版本 × 客户端”候选，涉及 323 个源依赖和 471 个客户端制品。它们提供旧版本到破坏版本的执行失败线索，但缺精确仓库修订和维护者修复；完成仓库恢复与 A0/A1/A2 重放前，703 条均不计为因果案例。首条 PowerMock 到 ViSearch 的恢复筛选已执行拒绝：A1 复现论文异常，但维护者删除无代码聚合依赖后 A2 仍以同一异常失败，且严格 A0 还受历史缺失制品阻挡，故接纳 0 条。H2 的精确 `MVCC` 拒绝提交形成 2 条正关系：Database Rider 与 CloudSlang Score 都完成 A0/A1/A2，公开 5 条模块记录按根仓折叠为 2 条；随后 1.4.200 到 2.0.202 的 16 条记录又折叠为 10 个根仓，只有 Fluent JDBC 的 `VALUE` 关键字关系具备精确源提交和维护者恢复。H2 当前共有 3 条正关系输入，但它们共享同一源根仓，且仍无限定负例和 A3，不能拆成多个独立项目包。JUnit 4.11 到 4.12 的八仓历史筛选则只有 PIT 留下一条未重放 A2 线索，其余七仓无维护者恢复，接纳 0 条且没有执行重型三臂。JAX-RS 2.0.1 到 2.1-m08 的 8 条目录记录经根仓去重后只剩 Fastjson 和 Microbule 两条关系；源破坏可隔离到新增抽象 `ResponseBuilder.status(int, String)` 的单一提交，但两个目标仓都没有维护者适配，故同样在重放前接纳 0 条。ANTLR Runtime 4.9.3 到 4.10 的五仓筛选只保留 jStyleParser 机制锚点：完整 182 项测试呈现旧组合通过、序列化版本不兼容失败、重新生成后恢复，但恢复臂是从维护者同步升级生成器和运行时的提交中抽出的混合版本，正式正例仍为 0；其余四仓没有维护者 A2。ANTLR Runtime 3.2 到 3.3 的四条记录又全部来自 OPPL2 同一根仓的四个模块；完整 545 提交历史中的 26 个相关 POM 版本都固定 3.2，从未形成历史 A1 或维护者 A2，因此在重放前拒绝，接纳 0 条。

JUnit 4.13.1 到 4.13.2 的另一组 3 条记录折叠为 3 个根仓。Easy Props 只有硬编码制品名机制但从未采用新版本；Sonar LDAP 的签名错误会被多个无关依赖升级触发；Kinesis 虽有隔离升级和保持 4.13.2 的精确测试修复，但维护者明确将其定性为客户端启动竞争导致的易波动测试，失败路径也未触及 JUnit 4.13.2 的源变化面。三者均不同时具备候选特异的 JUnit 源机制和维护者恢复，因此不执行三臂，正式接纳 0 条。

主动干预的执行完成数不能直接当成语义接受数。未参与执行的模型会话已完成独立质检，但它不是第二位人工标注者。当前模型质检接受 Alembic、SnakeYAML、SLF4J 和 Log4j 四个完整四臂候选；正式人工接受数仍为 0。原五包判断见 `reviews/model-semantic-review-existing-packages-2026-08-24.md`，SLF4J 与 Log4j 的补充复核分别见 `workstreams/slf4j-rabbit-formal-repetitions/SEMANTIC_REVIEW.md` 和 `workstreams/log4j-formal-repetitions/SEMANTIC_REVIEW.md`。

`jcabi-aspects` 的破坏三臂仍成立：两个执行正例、两个命令范围内的限定负例完成三次重复，六次目标破坏均为相同的 `Tv` 缺失签名。原 A3 0.22.2 到 0.22.3 没有触发真实 `HV000151` 分支；替代候选 0.20.1 到 0.20.2 也只有 SimpleDB 命中变化方法。因此当前四仓闭集永久保留为三臂破坏案例，不计完整项目包。评估见 `workstreams/jcabi-a3-repair/ASSESSMENT.md`。

`openstack/requirements` 到六个 OpenStack 消费仓已经完成三次正式重复：90 条命令全部符合方向并核验版本和目标测试执行。三次 Cinder A1 都复现同一 12 表检查约束差异，A2 只应用维护者修复后恢复；五个干扰仓和 A3 两臂稳定通过。模型质检按 MySQL 模型同步合同接受，仍待第二位人工盲复核。

SLF4J 四仓的原 60 条正式命令没有判定 RabbitMQ JMS Client 的日志退化。新增日志提供方合同后，RabbitMQ 的连续维护链形成严格三臂：三轮旧组合均为 115 项通过，三轮仅升级 SLF4J 后都回退到 `NOPLoggerFactory` 且只有新增合同 1 项失败，三轮只应用维护者合并的一行 Logback 1.4.0 更新后均恢复 115 项。1.7.29 到 1.7.30 的兼容控制也完成三轮，每轮前后各 115 项通过并执行同一提供方合同。独立语义复核接受 RabbitMQ 为“固定 SLF4J 2.0.0 且保留测试范围 Logback 提供方”条件下的正例，并把 A3 限定为普通初始化路径控制。当前闭集为 Jadler、RabbitMQ 两个正例和 Password4j、Spotless 两个窄负例；它是异质消费合同闭集，不是统一日志提供方合同的四次重复。原正式摘要位于 `results/slf4j-formal-repetitions-2026-08-24/`，补充三臂和兼容控制分别位于 `results/slf4j-rabbit-contract-formal-repetitions-2026-08-25/` 与 `results/slf4j-rabbit-contract-a3-repetitions-2026-08-25/`。

terser 4.3.0 的共同破坏变化已经完成三次统一版本隔离重复，Assetgraph Builder、UI5 Builder、Preconstruct 分别形成测试期望、生产配置和生成物快照适配，Angular CLI 支持历史构建合同内无需修改。模型质检拒绝 4.2.0 到 4.2.1 的 A3，因为没有证明任何真实变化表面进入测试；Preconstruct 也只能按三个选中用例和 35 个快照的子测试证据计。它保留为破坏案例，不计完整四臂项目包。

SnakeYAML 1.32 到 2.0 的破坏变化和 1.31 到 1.32 的兼容变化已完成四仓三次重复；四仓都覆盖 1.32 新增 3 MB 判断的正常分支。模型质检按当前命令合同接受，超限异常分支不在结论内。

新增筛选没有为了数量强升项目包：Jackson 原有一个版本协调单正例四臂锚点，本轮又从 14 条 FSE 记录、12 个独立根仓中恢复一个不同精确源合同的产品路径单正例；新合同没有限定负例或 A3，不能与原合同拼成多正例项目包。Log4j Core 形成 1 个正例、3 个有变化面覆盖的限定负例和四仓兼容变化，三轮 60 个组合的版本、方向与失败签名全部符合预期，并按 API/Core 多制品版本协调合同通过模型质检；AssertJ 形成 2 个强正例和 2 个限定负例，但三轮 A3 均拒绝；Commons IO 从 34 条、25 仓完整搜索框中形成 2 个单正例三臂锚点，没有可靠负空间与 A3；Checkstyle 从 307 条、53 仓完整框中形成 2 个强正例和 2 个有覆盖限定负例，但 A3 拒绝；Mockito 从 55 条、15 仓完整框中形成 2 个不同源输入的单正例三臂锚点，没有可靠负空间与 A3；Logback 因解析后输入不统一只保留 HTML2POP3 单正例锚点；Spring Core 的 32 条、7 仓完整框没有维护者精确恢复，接受数为 0。除 Log4j 外，这七组正式完整项目包接受数仍为 0。详情见各自 `workstreams/` 评估。

Derby 10.15 制品拆分的 9 条 FSE 记录对应 9 个独立根仓。Susom 已完成精确源提交隔离：同一工具链构建 `5a6efcc` 的父、子制品后，固定目标在父制品通过、子制品因 `EmbeddedDriver` 移入 `derbytools` 而失败、只加入同侧 `derbytools` 后恢复，因此接纳 1 条源提交隔离正关系；MuProcessManager 与 MyBatis CDI 的恢复依赖后续 Derby 发布元数据，均只作版本辅助对照，其余六仓没有维护者精确恢复。该关系仍无限定负例和 A3，不计完整项目包。

Hibernate Validator 6.2.3.Final 到 7.0.0.CR1 对 SmallRye Config 的四项 Validator 合同形成可重放破坏：旧组合 4/4 通过，只升级源版本后 4/4 均为 `NoProviderFoundException`。维护者后续 `Move to Jakarta` 提交和从中抽出的四文件消融都能恢复，但前者是 98 路径的全仓平台迁移，后者不是独立历史修复；正式严格三臂正例因此仍为 0，只保留广泛迁移恢复锚点和最小恢复消融。

HSQLDB 的 21 条 FSE 记录按模块和根仓去重后形成 16 个根仓、17 个“根仓与版本变化”审计单元。SQL Processor 的 2.5.0 到 2.5.1 变化可隔离到时间戳纳秒处理提交，但没有维护者 A2；2.5.2 到 2.6.0 的主体是默认发布物从 Java 8 类文件变为 Java 11 类文件，不能虚构成单一源提交。LanguageTool 与 Embedded DB JUnit 的分类器修复都同时换到其他 HSQLDB 版本，不保持固定 A1 输入。严格 A2 为 0，因此本轮没有运行重型三臂，正式接纳 0 条。

Weld 3.0.0.Final 到 4.0.0.CR1 的 12 条 FSE 失败覆盖两个坐标和 7 个模块，但全部折叠到 `astefanutti/camel-cdi` 一个根仓。上游 `javax.enterprise` 到 `jakarta.enterprise` 的类型与服务描述迁移能精确解释服务发现失败和类型转换异常；目标完整历史却没有 Weld 4、Jakarta 迁移或维护者 A2。该组保留 1 条高质量失败线索，重放前拒绝，正式接纳 0 条。

OpenDev 的 Ironic Python Agent 到 Requirements 关系已补成本地受控三臂：旧源与旧登记表通过，源变化将 `hardware>=0.24.0` 移入受共享规则检查的可选依赖后失败，只应用 Requirements 维护者的两行登记后恢复。历史 Zuul 两臂另外证明真实组合中的同签名失败与恢复。该结论只覆盖共享依赖登记合同，限定负例和 A3 均为 0，因此只进入单正例锚点层。

React Redux 4.1.2 到 4.2.0 删除了 React Redux Provide 5.1.0 直接导入的内部 `isPlainObject` 模块；目标原生六项测试由通过变为在生产导入处失败，只应用维护者的导入替换和 `is-plain-object 2.0.1` 依赖后恢复。4.0.5 到 4.0.6 的独立兼容臂确实改变同一工具模块的原始导出结构，目标导入在两侧都规范化为函数并通过六项测试。它当前是缺少限定负例、三次重复和独立盲审的单正例四臂锚点。

Babel ES2015 Preset 6.13.0 到 6.13.1 改变插件项形态后，Rollup Preset 的模块保留合同从通过转为生成 CommonJS；采用 1.2.0 发布物代码和 `modify-babel-preset` 2.1.1 后恢复。独立七臂重放确认代码或辅助依赖单独都不足，目标自身版本字段没有贡献。Imagemin Optipng 4.1.0 到 4.2.0 则使同一图片输出从 225 字节变为 228 字节，目标原生 8 项测试出现 3 个精确失败，只应用维护者两处期望更新后恢复 8/8。ESLint 4.18.2 到 4.19.0 使 TestCafe 原生质量门在一处控制字符正则上失败，保持 `gulp-eslint` 4.0.2 不变并只应用维护者一行测试夹具修复后恢复。三者都只有一个正目标仓，没有限定负例；Babel 和 ESLint 无 A3，Imagemin 只保留单目标兼容控制，均不计完整项目包。

Backbone PR 2878 的单行 `isNew()` 变化在固定 1.1.0 基线上即可复现发布升级 A1 的同一异常；`backbone-mongo` 与 `backbone-orm` 两个维护者修复必须同时加入才能恢复，任一单独修复或只改版本元数据都失败。因此它只计 1 条链独立、多目标因果锚点，正目标仓为 2 个，不能拆成两条。共享目标上的 MongoDB 1.3.12 到 1.3.13 公开标签则因没有 A1 失败和 A2 恢复而拒绝。该关系族仍无限定负例和 A3，不计完整项目包。

Socket.IO 1.4.0 把内部套接字集合从数组改成对象后，Karma 0.13.18 的原生退出逻辑仍调用 `forEach`。以 Riot 的 91 项 PhantomJS 浏览器合同重放时，A0 正常退出，A1 与只移植对象化源提交的消融臂都在 91 项执行完成后出现历史错误，A2 只应用 Karma 维护者的生产代码适配后恢复；依赖声明更新只负责暴露变化，0.13.19 版本提交只负责发布修复。该关系计 1 条三臂正例，限定负例和 A3 均为 0，不能升为完整项目包。

## 标签依据

`specification_proven` 要求目标 PR 正文直接引用源规范 PR，且人工逐项确认目标确实实现或适配该规范。`implementation_proven` 用于 OpenDev 非规范案例：目标提交说明必须明确解释它消费、暴露或配合的源变化；只有 `Depends-On` 不够。

`ci_contrast_proven` 要求同一任务在缺少目标修复时失败、加入目标修复后通过，并核对实际组合提交。`executed` 要求固定版本本地执行观察到差异。普通协调声明只保留为辅助证据或候选记录。

目标的 `changed_paths` 是目标 PR 的完整改动面，不等于人工筛选的影响位置。只有 `expected_checks` 中的路径、测试和命令才是细粒度真值；当前只有 2 个目标具备这类强标签，因此不进入主指标。

## 输入

`inputs.jsonl` 为每条案例给出：

- 源 PR 创建时的标题、基提交、头提交、修改路径和补丁地址；
- 分生态候选仓目录引用；
- `repository-snapshots.jsonl` 中对应案例的候选仓时点代码引用。

候选仓清单分为 12 个项目或生态目录，每条案例只使用所属目录。时点清单共记录 1078 个“案例与候选仓”组合：1045 个在截止时间前有可获取提交，33 个当时尚未创建，没有抓取失败。每个已知目标仓都有截止时间前版本，每条案例也至少有一个可用的非目标干扰仓。

运行前用 `prepare_case_inputs.py` 下载源补丁并展开所有可用候选仓代码。正式推理阶段关闭网络，且不得读取 `cases/`、`candidates/`、目标 PR、托管平台关系接口、持续集成记录或 `results/`。

```bash
python benchmarks/cross-repo-pr-impact/prepare_case_inputs.py \
  opendev-991000-semantic-impact \
  --output-dir .work/marshal-cross-repo-inputs
```

上述案例已实际准备成功：源补丁 17723 字节，4 个候选仓共展开 8278 个文件。完整输入约束见 `INPUT_SPEC.md`。

## 主指标

主任务是跨仓影响目标仓排序，报告已知目标宏平均召回、平均倒数排名、前 1/3/5 项召回和每案例预测仓数量，并按项目、年份、项目与年份、具体有向仓库关系、关系类型和证据等级分层。

标签不完整，因此不报告精度或 F1。全报候选仓会得到已知目标召回 1.0，所以单独看召回没有意义；必须同时看前 K 项召回、平均倒数排名和预测数量。

三个实测简单策略如下：

| 策略 | 平均倒数排名 | 前 1 项召回 | 前 3 项召回 | 前 5 项召回 | 平均预测仓数 |
|---|---:|---:|---:|---:|---:|
| 按整个数据集统计源仓对应目标频率 | 0.733 | 0.382 | 0.697 | 0.850 | 7.02 |
| 同组织仓优先，其余按名称 | 0.338 | 0.088 | 0.258 | 0.431 | 10.45 |
| 全报所有当时可用候选仓 | 0.319 | 0.083 | 0.259 | 0.417 | 10.45 |

第一项故意读取整个评测集的标签统计，是用于检查静态映射是否仍能饱和任务的诊断上界，不是可与受测系统公平比较的训练外基线。它不再取得前 1 项召回或平均倒数排名满分。结果文件位于 `results/*-baseline-2026-08-23.json`。

## 主要文件

| 文件 | 内容 |
|---|---|
| `INPUT_SPEC.md` | 可见输入、时间边界和网络限制 |
| `TASK_DEFINITION.md` | 校准轨道与因果旗舰轨道的独立任务定义 |
| `CAUSAL_SOURCE_ASSESSMENT.md` | Zuul、Prow、Crater、FSE 2024、GitLab 等执行来源的实测产率与取舍 |
| `ACTIVE_PROJECT_PACKAGE_ASSESSMENT.md` | 主动四臂项目包的候选、执行结果和剩余条件 |
| `PROJECT_PACKAGE_RESERVE.md` | 已执行项目包、OpenDev 储备和 BUMP 多消费仓搜索框 |
| `reviews/` | 独立模型语义质检；不得冒充第二位人工复核 |
| `workstreams/` | 各并发项目包的独立候选框、覆盖判断和拒绝理由 |
| `OPENSTACK_SDK_CLOSED_SET_AUDIT.md` | OpenStack SDK 17 仓时点代码覆盖与不能形成主动闭集的证据 |
| `NPM_CAUSAL_SOURCE_ASSESSMENT.md` | NoRegrets、npm 客户端恢复数据和首个 Node.js 三臂筛选结果 |
| `MARSHAL_EVALUATION_PROTOCOL.md` | 当前配置覆盖与离线多仓审查的分离实测协议 |
| `COMPETITOR_RUNNABILITY.md` | CodeRabbit、Qodo、Greptile、Bito 的输入边界、运行限制和公平比较方式 |
| `schema.json`、`cases/*.json` | 正式案例和隐藏标签 |
| `input-schema.json`、`inputs.jsonl` | 受测系统可见的源输入 |
| `candidate-repositories.json` | 12 个分生态候选仓目录 |
| `repository-snapshots.jsonl` | 每条案例在截止时间前的候选仓提交和源码地址 |
| `prepare_case_inputs.py` | 下载并展开一条或多条完整评测输入 |
| `index.jsonl` | 100 条正式案例索引 |
| `candidates/` | 搜索框、人工决定、时间恢复和证据审计记录 |
| `score.py`、`prediction-schema.json` | 评分器和预测格式 |
| `validate.py`、`test_score.py` | 数据校验和评分判例 |
| `audit.py`、`audit-results.jsonl` | 分层远程复核 |
| `mine_ci_contrasts.py`、`verify_ci_contrasts.py` | 因果候选挖掘、执行组合与时间核验 |
| `review_ci_contrasts.py` | 失败签名、目标修复语义和不稳定任务复核 |
| `causal-pilot/` | 6 条旗舰储备的失败时点输入、隐藏标签和 12 项快照审计 |
| `causal-pilot/blind-review-packet.jsonl` | 6 个接受项与 7 个拒绝项的去结论独立复核材料 |
| `results/prow-three-arm-scan-2026-08-23.json` | Prow 约 90 天预提交历史的完整筛选漏斗与来源决定 |
| `candidates/crater-linked-fix-candidates.jsonl` | 4 条可逐项审计的 Crater 修复候选和当前状态 |
| `collect_fse2024_behavioral_candidates.py` | 从 FSE 2024 去重工作簿构造依赖升级执行失败搜索框 |
| `candidates/fse2024-behavioral-breakage-frame.jsonl` | 703 个待恢复仓库修订与维护者修复的执行失败候选 |
| `results/crater-replay-*.json` | 4 条版本化包三臂重放、可比性、排除尝试和限制 |

## Marshal 当前实测

当前 `CowboyPack` 只对预登记的 Cowboy 仓库、路径和跨仓契约产生目标仓。把 100 条外部校准案例的源仓别名与修改路径交给现有配置后，契约命中为 0/100，已知目标宏平均召回、平均倒数排名和前 1/3/5 项召回均为 0，平均预测仓数为 0。结果位于 `results/current-marshal-score-2026-08-22.json`。

这个数字是“现有配置覆盖”结果，不是完整 Marshal 审查流程的通用能力分数。后者必须读取准备好的全部候选仓时点代码，并通过不含答案的输出适配生成仓库排序；具体限制和可比运行方式见 `MARSHAL_EVALUATION_PROTOCOL.md`。

竞品功能宣传不能直接替代可比运行。当前官方接口调查没有发现能够直接消费本评测离线历史快照目录的完整商业审查产品；CodeRabbit、Qodo 和 Greptile 需要托管仓库接入，Bito 的本地多仓索引可以读取目录但不是完整审查系统。主表、托管沙箱重放和检索组件对照必须分开，证据和运行顺序见 `COMPETITOR_RUNNABILITY.md`。

## 验证

```bash
python benchmarks/cross-repo-pr-impact/validate.py --expected-count 100
python -m unittest discover -s benchmarks/cross-repo-pr-impact -p 'test_*.py' -v
python benchmarks/cross-repo-pr-impact/score.py --self-check
python benchmarks/cross-repo-pr-impact/audit.py --sample-size 20
```

## 解释边界

- 174 项规范实现证据和 13 项非规范实现证据证明已知目标确实需要配合，不构成完整影响集合；
- 规范案例依赖公开历史 PR，存在训练语料污染风险，离线推理不能消除模型记忆；
- GitHub 搜索只覆盖目标 PR 正文中的完整源 PR 链接，不覆盖裸编号、提交说明或间接引用；
- 101 条可恢复 GitHub 候选中只选择 85 条：全部 59 条多目标案例优先保留，单目标案例按仓库关系轮转补齐；
- 100 条校准轨道没有可靠无影响对照，不能评价误报率和停止能力；旗舰主动轨道的限定负例只在各自执行合同内成立；
- Cinder 对照只有一次失败和一次成功，仍可能受持续集成环境漂移影响；
- OpenDev 因果试采只有 6 个通过初次语义复核的储备，且全部来自 2026 年；主动项目包虽已扩到其他生态，但模型质检只接受 4 个完整四臂候选，仍不足以支撑产品优劣结论；
- 13 个去重转换的盲审材料已经生成，但独立复核者尚未提交结果，不能把材料准备当作复核完成；
- Prow 历史扫描从当前仍配置的 104 个多仓预提交任务出发，不包含已退役或改名任务；35,805 次执行没有产生语义成立的因果案例；
- 198 个持续集成候选因历史执行清单归档缺失而无法判断，当前 OpenDev 历史不能直接扩成数百条强因果案例；
- Crater 的 4 条恢复案例证明的是固定包版本受编译器变化破坏并由具体补丁恢复；其中一条依赖闭包与原实验不同，两条补丁尚未合并，四条均未使用原容器，不能外推为目标仓默认分支影响、维护者采纳或 Crater 全体案例产率；
- WanderTracks 执行证据也存在于兄弟数据集，同一报告中不能重复计数。

本目录不修改 Marshal 产品代码。

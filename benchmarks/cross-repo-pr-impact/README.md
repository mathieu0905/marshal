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

主动干预方面，`jcabi-aspects` 多消费者项目包已经形成两个执行正例、两个命令范围内的限定负例，并以 0.22.2 到 0.22.3 作为独立兼容变化 A3。A0、A1、A2、A3 前臂和 A3 后臂均已完成三次隔离重复：共 60 个仓库命令，60 项符合预期方向，60 项保留指定版本解析证据，六次目标破坏均为相同的 `Tv` 缺失签名，且没有重试。两个维护者修复片段和 A3 完整发布的语义边界仍待独立复核，因此它仍不进入正式项目级精度或停止能力结果。评估见 `ACTIVE_PROJECT_PACKAGE_ASSESSMENT.md`，正式合同和原始记录见 `results/jcabi-formal-repetitions-2026-08-24/`。

第二个主动项目包 `openstack/requirements` 到六个 OpenStack 消费仓已经完成三次正式重复：A0、A1、A2、A3 前臂和 A3 后臂共 90 条仓库命令，90 项符合预期方向，90 项核验实际版本并确认目标测试执行。三次 Cinder A1 都复现同一 12 表检查约束差异，A2 只应用维护者修复后恢复；五个干扰仓和 A3 两臂稳定通过。五个干扰仓的 A1/A2 是相同输入的重复确认，不重复计数。该项目包仍待独立语义复核，不进入正式项目级指标。

第三个候选项目包 SLF4J 已完成三次正式重复。四仓在 A0、A1、A2、A3 前臂和 A3 后臂下共执行 60 条仓库命令，60 项符合预期方向，60 项核验了输入版本。Jadler 三次 A1 都在启动 235 项测试后出现相同 5 项错误，原因是 SLF4J 2 忽略 Logback 1.2.11 并回退到空日志工厂；A0、只更新 Logback 的 A2 和 A3 双臂均三次通过 389 项。Password4j 与 RabbitMQ JMS Client 的 15 条命令分别稳定通过 206 项和 114 项。Spotless 正式合同收窄为直接进入 `LoggerFactory` 生产路径的 `FreshMarkStepTest` 与 `SortPomTest` 三项测试，15 条命令均通过；完整 155 项测试的成功与动态依赖缓存失败只作补充环境证据，不计正式结果。正式 Jadler 使用 Maven 3.8.6 与 Java 11，不能与筛选阶段的 Java 8 环境混写。该项目包仍待维护者修复抽取、三个限定负例边界和 A3 语义边界的独立复核，因此不能进入正式项目级指标。正式摘要与日志位于 `results/slf4j-formal-repetitions-2026-08-24/`。

首个非 Maven 四仓候选来自 `terser` 4.3.0 的匿名函数参数括号行为，已经完成三次统一版本隔离重复。Assetgraph Builder 放宽输出断言，UI5 Builder 修改生产压缩配置，Preconstruct 更新生成物快照；Angular CLI 的原生完整差异化构建在 4.2.1 和 4.3.0 下均通过，但后者每轮都在 10 个产物中的 8 个生成 531 处新括号。三轮共 51 条命令，方向与版本核验 51/51。Preconstruct 只支持三个选中用例和 35 个快照的收窄合同，Angular 也只支持该历史构建合同无需目标修改；独立复核尚未完成，因此不进入正式项目级指标。摘要、日志和去结论复核材料位于 `results/terser-unified-430-repetitions-2026-08-24/`，来源筛选见 `NPM_CAUSAL_SOURCE_ASSESSMENT.md`。

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
  --output-dir /tmp/marshal-cross-repo-inputs
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
| `CAUSAL_SOURCE_ASSESSMENT.md` | Zuul、Prow、Crater、GitLab 等执行来源的实测产率与取舍 |
| `ACTIVE_PROJECT_PACKAGE_ASSESSMENT.md` | 主动四臂项目包的候选、执行结果和剩余条件 |
| `PROJECT_PACKAGE_RESERVE.md` | 已执行项目包、OpenDev 储备和 BUMP 多消费仓搜索框 |
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
- 当前没有可靠无影响对照，不能评价误报率和停止能力；
- Cinder 对照只有一次失败和一次成功，仍可能受持续集成环境漂移影响；
- 当前旗舰试采只有 6 个通过初次语义复核的因果储备，且全部来自 2026 年 OpenDev，尚不足以支撑产品优劣结论；
- 13 个去重转换的盲审材料已经生成，但独立复核者尚未提交结果，不能把材料准备当作复核完成；
- Prow 历史扫描从当前仍配置的 104 个多仓预提交任务出发，不包含已退役或改名任务；35,805 次执行没有产生语义成立的因果案例；
- 198 个持续集成候选因历史执行清单归档缺失而无法判断，当前 OpenDev 历史不能直接扩成数百条强因果案例；
- Crater 的 4 条恢复案例证明的是固定包版本受编译器变化破坏并由具体补丁恢复；其中一条依赖闭包与原实验不同，两条补丁尚未合并，四条均未使用原容器，不能外推为目标仓默认分支影响、维护者采纳或 Crater 全体案例产率；
- WanderTracks 执行证据也存在于兄弟数据集，同一报告中不能重复计数。

本目录不修改 Marshal 产品代码。

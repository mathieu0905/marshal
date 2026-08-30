# 跨仓影响评测数据集计划

日期：2026-08-30

## 2026-08-30 完成状态

candidate-bounded strict-E2 数据集构造、组级 split、正式发布和首次冻结运行已经闭环。当前权威集合是 `results/formal-e2-benchmark-50-v2-2026-08-30/`，包含 50 条 verifier-clean strict-E2、15 个隔离组和 30/10/10 split；匹配的 `results/formal-e2-benchmark-50-system-run-v3-2026-08-30/` 完成 50 个断网盲容器和统一揭签后的全量计分复核。两个 verifier 均为 `verified=true`、`blockers=[]`。

后续默认工作从“继续扩采”切换为发布维护：同步专用私有数据仓库 `mathieu0905/cross-repo-breakage-benchmark`，在抽取布局重新验收，并在替换任何 case 时通过单条 skill 后重新生成整个 release。E3、E4、A3 和开放世界仓库发现仍不是当前 E2 主集的补齐目标。

## 2026-08-25 原始决定（保留执行审计）

数据集采用 candidate-bounded 任务：候选仓由数据集提供，系统负责在候选仓内进行目标排序、影响定位和可选执行验证。开放世界仓库发现不进入当前主任务。

现有 100 条历史适配案例保留；已执行三臂、四臂、OpenDev 对照和 FSE 恢复材料保留。变化在于：完整四臂项目包不再是每个强正例的准入条件，A3 和有界负例成为独立证据层。

详细设计见 `CANDIDATE_BOUNDED_DESIGN.md`，任务语义见 `TASK_DEFINITION.md`。

## 已完成资产

1. 100 个源案例、190 个目标 PR、22 个源仓、45 个目标仓和 46 种有向关系。
2. 12 个候选目录、100 条时点清单、1273 个“案例与候选仓”组合，其中 1211 个快照可用、62 个仓在对应截止时间尚未创建；Ethereum、OpenTelemetry 与 Rust 共 71 条案例的目录已按独立来源重建。
3. 离线输入准备器、输入与预测 schema、验证器、评分器和三种简单策略。
4. 6 条 OpenDev 因果储备及盲审材料。
5. 多个真实 A0/A1/A2 锚点、部分 E3 有界负例和部分合格 A3；原始日志与拒绝记录完整保留。
6. Marshal 当前 Cowboy 配置覆盖和单仓接口缺口的实测记录。

## 2026-08-25 当时缺口

### P0：候选目录来源

当前目录由每个项目的已知目标与手工 `DISTRACTORS` 合并生成，不能直接声称标签无关。需要为每个目录补充独立来源规则，或从项目/生态名录重建。

验收：12 个目录都有 provenance；四个单例目录进入开发/敏感性集；正式目录不依赖单条目标标签。

### P1：数据划分

当前 100 条全部标为 `test`。需要按有向关系、源提交族、机制和修复模板形成不可跨 split 的组，再分配 development、evaluation、holdout。

验收：输出组清单、分配理由和分层统计；同一组不跨 split；划分前所有分数标为开发诊断。

### P2：证据迁移

把现有标签和工作流材料迁移到 E0-E4。`ci_contrast_proven`、`executed` 不能仅凭名称自动进入 E2，必须核对 A0/A1/A2。

验收：每个案例有证据层、独立关系单元和支持的最大结论；E2 不因缺少 E3/E4 被排除。

### P3：真实候选代码排序

当前 Marshal 原生命令不读取候选仓目录，也不产生排序。先在 development split 上运行一个不含答案的输出适配，记录代码读取、排序、失败和 `not_assessed`。

验收：至少一个小型目录端到端可准备、离线读取、输出并由现有评分器解析；不使用目标修复和隐藏标签。

## 执行顺序

| 阶段 | 工作 | 产物 | 继续条件 |
|---|---|---|---|
| D0 | 候选目录 provenance 审计 | 12 个目录的来源与处置 | 至少两个多案例目录可无标签构造 |
| D1 | 关系组与 split 提案 | group manifest、split proposal | 人工确认无关系/模板泄漏 |
| D2 | E0-E4 重分类 | evidence manifest、数量与成本 | E1/E2 结论边界可机器汇总 |
| D3 | 小型离线排序试运行 | 可解析预测、运行日志、失败分类 | 系统真实读取候选代码 |
| D4 | development 测量 | 主排序与 E2 分层结果 | 不由全报或标签频率解释 |
| D5 | evaluation/holdout | 固定设置后的正式结果 | 不从正式标签调规则 |

## 暂停事项

- 暂停以 30 至 50 个完整四臂项目包为目标的扩采；
- 暂停为了补 A3 或多仓负空间而筛选新的 FSE 家族；
- 保留低成本、明确 A0/A1/A2 的自然候选，但先登记，不挤占 D0-D3；
- 不新增更多通用持续集成平台扫描，除非它直接补足已知候选目录中的 E2 证据。

## 指标边界

- E1：known-target recall、MRR、Recall@K、预测数量；
- E2：同类排序指标，加检查位置、可运行率和执行结论；
- E3：只有完整 bounded denominator 才启用 precision/specificity；
- E4：空预测率、预测数量和错误升级率；
- 任何层都必须报告输入失败、输出失败、上下文溢出和 `not_assessed`，不能改写为无影响。

## 下一次决策点

D0-D2 完成后，根据以下真实测量决定是否扩采：

- 可进入 E1/E2/E3/E4 的独立关系数；
- 候选目录中标签无关仓库的覆盖；
- 每条 E2 的准备与复核时间；
- development split 上代码读取方法相对非语义策略的增益。

不再用“完整项目包数量”单独决定进度。本计划不新增内容 hash、冻结 contract、baseline 或产品 gate。

## 2026-08-25 D0-D3 实施结果

- D0：12 个目录完成机器审计。Ethereum、OpenTelemetry 与 Rust 已按独立项目来源重建，覆盖 71 条案例；Ethereum 新增 5 个独立来源仓并解析 160 个新增时点状态，OpenTelemetry 新增 `opentelemetry-ruby` 并补齐 35 个时点快照。四个单例目录限制为 development/sensitivity，其他五个多案例目录仍待重建。
- D1：100 条案例按项目 connected component 保守形成 12 组；重建后的 split 提案为 development 46、evaluation 32、holdout 22，关系、源提交族、机制和修复模板键未跨 split。正式启用仍阻塞于 D0。
- D2：190 个目标记录（46 个独立有向关系）进入 E1；只有 requirements -> Cinder 的本地严格 A0/A1/A2 摘要进入 E2。其余 18 个含执行臂或项目包结果的 summary 保持待逐项复核，未按名称或状态词自动升级；E3/E4 当前均为 0。
- D3：`opendev-1001388` sensitivity case 已完成真实候选代码读取。排除源仓后读取三个候选仓，输出通过现有预测解析，已知目标排第 1；该单例结果只证明管线可运行，不作为泛化分数。

该阶段随后在 OpenTelemetry 与 Rust 的 39 条合格 development 材料中，用 archive 复用准备 10 至 15 条切片，再判断是否扩到全部 39 条；这一步已由下方 D4 记录完成。全数据 evaluation/holdout 继续等待其他目录重建。实施产物见 `results/candidate-bounded-foundation-2026-08-25/`、`results/catalog-rebuild-2026-08-25/` 与 `results/candidate-code-pilot-2026-08-25/`。

archive 复用与两项目 smoke 已通过：两条案例实际读取 21 个候选仓和 41,265 个文件，预测均可解析；同切片宏召回和 MRR 为 0.667。该结果位于 `results/candidate-code-eligible-smoke-2026-08-25/`，只清除 D4 管线风险；后续 12 条同切片对照见下节。

## 2026-08-25 D4 development slice

按观察时点和 case ID 等距选择了 8 条 OpenTelemetry 与全部 4 条 Rust 案例；选择器不读取标签。代码排序器在 top-3 预算下得到 MRR 0.444、Recall@1 0.194、Recall@3 0.431，每案例固定返回 3 个仓；同组织/名称顺序与全报目录在该单组织切片上退化为相同顺序，MRR 0.380、Recall@1 0.111、Recall@3 0.139，每案例平均返回 10.9 个仓。额外预测仍记为 `unjudged`，不报告 precision 或 F1。

结果存在明显项目差异：Rust MRR 为 1.0，OpenTelemetry MRR 仅 0.167，后者不高于非语义对照的 0.170。当前决定不是直接扩到 39 条，而是在相同 12 条切片上做有界错误分析和仓库大小归一化消融；成功条件与停止条件见 `results/candidate-code-development-12-2026-08-25/decision.json`。

单次预注册式消融已经结束：用 `score / sqrt(files_read)` 后，OpenTelemetry MRR 从 0.167 升到 0.375，但 Rust MRR 从 1.0 降到 0.125，总体 MRR 降到 0.292。这个结果确认大仓累积是 OpenTelemetry 的一个失败机制，也排除了“对所有项目施加单调大小惩罚”的修复。按预设停止条件不继续在同一批标签上搜索指数；下一阶段先独立规定基于查询词覆盖/特异性的评分规则，再决定新的 development confirmation。

## 2026-08-25 50-case data-ready milestone

Ethereum 目录按 ethereum.org 的 execution/consensus client 表以及 `ethereum/execution-specs` 关联的规范/API 仓重建，成员选择不读取隐藏目标。重建后的 16 仓目录覆盖全部 32 条 Ethereum 案例：512 个时点组合中 478 个可用、34 个在截止时间尚未创建、0 个抓取失败，已知 development 目标缺失为 0。

三个独立目录现覆盖 71 条案例。从中仅按项目、观察时点和 case ID 选出 35 条 OpenTelemetry、4 条 Rust 和 11 条 Ethereum，形成恰好 50 条 data-ready 清单；共 663 个候选仓时点组合，631 个可用、32 个尚未创建、0 个抓取失败。该里程碑完成“构造 50 条数据”，不等于“Marshal 跑了 50 条”；后者必须另接真实 Marshal 执行入口。

## 2026-08-25 final 50 E1 verification

在 71 条独立目录合格池上统一执行最终证据审计。每条案例同时核对独立目录及 observation-time snapshot、源 PR 开场提交与 changed paths、人工语义接纳、持久化目标审计，以及实时 GitHub 的 merged 状态、head commit、changed paths 和目标正文到源 PR 的直接链接。71 条、154 条目标关系全部通过。

最终索引固定 25 条 OpenTelemetry、21 条 Ethereum 和 4 条 Rust，分别进入 development、evaluation 和 holdout，项目不跨 split；50 条共含 107 条已验证目标关系，无失败替补或重复冲突。结果位于 `results/final-dataset-verification-2026-08-25/`。这完成的是 E1 最终数据集验证，不是 Marshal 执行，也不把当前 1 条独立严格 E2 计入这 50 条。

## 2026-08-25 final 50 strict E2 verification

对散落的三臂执行资产按链独立关系重新计数并统一审计：46 条满足 A0 通过、A1 只引入源变化后失败、A2 保持新源输入并加入精确目标修复后恢复。Terser 到 Preconstruct 因同一命令在 A0 与 A2 仍由 39 个无关过期快照导致非零退出，固定为拒绝，未用子测试方向补数。

真实缺口由四条新重放补齐：Jackson YAML 到 SchemaCrawler、nv-i18n 到 jbanking、ASM 到 Byte Buddy、Micrometer 到 RabbitMQ perf-test。四条均保留 A0/A1/A2 日志，退出方向为 `0/1/0`，A1 分别命中链接错误、ISO 国家枚举、类文件版本和 JMX 对象名签名。

最终严格 E2 索引恰好 50 条，位于 `results/final-e2-dataset-50-2026-08-25/`；统一重建/验证入口为 `verify_final_e2_dataset.py`。该集合是开发/诊断 E2 数据集，不是 50 次 Marshal 产品执行，也尚未完成正式候选目录 provenance 与机制/修复模板 split 审计。达到 50 后停止扩采，不再为 A3、限定负空间或四臂包补数。

## 2026-08-26 strict E2 正式化结果

50 条 strict E2 已全部完成候选目录赋值、截止时点快照记录、输入可见性检查和真实离线排序。分组 split 按有向关系、源提交族、机制和修复模板冻结为 30/10/10，四个轴均无跨 split 泄漏。恢复已删除目标仓后，5,650 个候选仓时点中 4,454 个可用、749 个在截止时点尚未创建、447 个当前不可取得，0 个抓取失败。

正式输入口径另行收紧：34 条没有可证明的 PR opening-state 因果输入，37 条仍使用 outcome-conditioned 目录。当前只有 5 条同时满足 opening cutoff 和正式目录，其中 4 条属于 development；holdout 的 `e2-041` 已用 736 仓目录、617 个可用时点快照断网实跑，目标全排名 174，Recall@1/3/5、MRR 和检查位置找回均为 0。该单例是可复现的正式结果，不是 50 条正式总分。

六个其余非 development opening case 的目录路线已完成排查。Mockito 完整反向依赖查询覆盖 25,642 个包和 8,501 个 GitHub 仓，仍缺已知目标；四个 Rust case 的官方 Crater 全量实验能确认 registry 执行对象，但目标均不是顶层仓候选，把回归行用作目录会依赖结果；ASM 的共享 Maven 目录缺目标，单独构造 ASM 目录又无法跨案例复用。因此这六条保留 development/diagnostic，并在 `results/e2-opening-catalog-resolution-2026-08-26/` 留下逐条排除依据。后续只有出现新的标签无关治理/构建目录或完整 Crater 输入到仓库快照的全量映射时，才重新物化新增正式 case。

## 2026-08-30 formal benchmark v2

- 50/50 条通过当前 `build_case.py verify`，均有真实 A0=0/A1!=0/A2=0、排他失败签名、完整维护者 A2 补丁和语义批准。
- 50/50 条目标仓位于标签独立 Domain Pack，opening-cutoff target snapshot 可用；catalog 定义冲突不得靠合并成员解决，只有其他字段完全相同的重建时间差可以确定性归一。
- 50 条按有向关系、source change family、规范化机制和 repair template 形成 15 个连通组，分配为 30 development、10 evaluation、10 holdout，跨 split 泄漏为 0。
- 冻结运行读取 14,367 个候选仓、331,351 个文本文件；50 个容器均断网且不挂载标签，所有预测完成后才统一读取标签，逐例和聚合分数重算一致。
- 非目标候选继续为 `unjudged`，不报告 precision、F1、误报率或 specificity；系统没有提出可运行检查，因此执行结论保持 `not_assessed`。
- marshal commit `7ebe4624` 已提交数据集和冻结运行。专用数据仓库尚停在 2026-08-27 抽取版，完成同步和抽取布局复验前不得把它写成当前权威镜像。

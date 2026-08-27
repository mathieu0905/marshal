# 已知候选仓跨仓评测设计

日期：2026-08-25
状态：当前设计基线

## 一句话定义

给定源仓变更、项目级已知候选仓目录及各仓在观察截止时间的代码，受测系统返回一个候选仓排序；历史适配和因果破坏使用相同输出接口，但按证据层分别计分和解释。

这与 Marshal 原始形状一致：Domain Pack 先给出已知仓库关系和检查位置，再由审查流程判断该变更需要检查什么。评测不要求系统从整个托管平台发现相关仓库。

## 输入与输出

```text
source patch
  + project candidate catalog
  + cutoff-time repository snapshots
  -> reviewed system
  -> ranked candidate repositories
     + optional paths/tests/commands/execution result
```

主输出只有有序候选仓列表。路径、测试、命令和执行结果是次级诊断，不影响没有细粒度真值的案例。

现有 `input-schema.json`、`inputs.jsonl` 和 `repository-snapshots.jsonl` 已经能表达这些输入。现有 `prediction-schema.json` 也足以承载 v1 排序；证据不足或未运行使用 `not_assessed`，当前不增加 `unknown` 或证据引用字段。`no_cross_repo_impact` 只能用于 E3 已完整判定的 bounded universe，不能用于主集中未标注的候选仓。

## 候选目录规则

候选仓由数据集提供，但候选目录不是答案。正式目录必须满足：

1. 由项目组织、规范实现列表、治理清单、构建编排或其他与单条隐藏标签无关的规则生成；
2. 同一目录跨多条案例复用；
3. 记录目录来源、生成时间、纳入规则和每个仓库的纳入理由；
4. 对每条案例固定到观察截止时间，截止时间后才创建的仓库保留 `not_created_by_cutoff`；
5. 至少包含一个已核验目标和一个可用的非目标候选；非目标候选默认是 `unjudged`，不是负例；
6. 单例目录只能进入开发集或敏感性报告，不能进入正式主分数。

### 当前目录的已知缺口

首版 `materialize_impact_discovery_set.py` 用“该项目全部已知目标与手工 `DISTRACTORS` 的并集”生成 12 个目录。2026-08-25 已把 Ethereum、OpenTelemetry 与 Rust 改为从 `catalog-source-snapshots.json` 的独立项目/生态清单生成，覆盖 71 条案例；其他目录仍未证明与标签独立。当前目录规模为 4 至 16 个仓，平均 8.83 个；`drizzle`、`opencontainers-image`、`wandertracks` 和 `zuul` 各只被一条案例使用。

因此现有 100 条案例可以继续承担开发、输入准备和排序接口诊断，但不能整体作为正式无泄漏主分数。三个已重建目录中的 50 条最终 E1 子集已经过逐条证据验证并按项目隔离 split；其发布边界和记录位于 `results/final-dataset-verification-2026-08-25/`。

## 证据层

E0 是非评分的候选线索层。E1 至 E4 是可报告证据层。

| 层级 | 最小证据 | 可支持结论 | 不支持结论 |
|---|---|---|---|
| E0 候选线索 | 协调链接、依赖声明或目录关系 | 值得审查 | 是真实目标或发生破坏 |
| E1 已知适配 | 目标明确引用源变化并经语义确认 | 存在历史采纳或适配目标 | 源变化必然导致失败 |
| E2 可执行因果正例 | A0 通过、A1 仅源变化失败、A2 精确目标修复恢复 | 对固定输入存在跨仓因果破坏 | 其他候选仓无影响 |
| E3 有界负例 | 候选任务消费变化表面且 A0/A1 均通过 | 在该命令和输入范围内未观察到影响 | 仓库整体不受影响 |
| E4 兼容变化 | 独立源变化进入相同消费表面且前后通过 | 可测量系统对兼容变化的克制 | 每个 E2 都必须有 A3 |

E1 和 E2 使用相同的仓库排序接口，但必须分别计分和表述。E1 的高召回不能替代“发现真实破坏”的 E2 结论。E3、E4 是可叠加子集，不是 E2 的准入条件。

### 现有标签迁移

| 现有证据字段 | 迁移结果 | 附加要求 |
|---|---|---|
| `specification_proven` | E1 | 保留现有语义复核 |
| `implementation_proven` | E1 | 保留现有语义复核 |
| `coordination_proven` | E0 | 单独不能进入 E1/E2 |
| `ci_contrast_proven` | E2 候选 | 重核 A0/A1/A2 组合、失败签名和目标修复 |
| `executed` | E2 候选 | 重核三个干预臂；普通双版本差异不足 |
| 既有工作流限定负例 | E3 | 单独 execution manifest |
| 既有合格 A3 | E4 | 单独 execution manifest |

当前 case schema 不需要立刻容纳 E3/E4。先用独立、可审计的 execution manifest 盘点真实数量；出现稳定消费者后再决定 schema v2。

## 数据组成

### E1 历史适配排序层

现有 100 条案例是可运行材料。完成候选目录审计和关系隔离划分后，用于测量：

- known-target macro recall；
- mean reciprocal rank；
- Recall@1/3/5；
- 平均预测仓数和召回-工作量关系；
- 按项目、年份、有向关系、证据类型和候选目录规模分层。

标签不完整。额外预测一律记为 `unjudged`，不报告 precision、F1、accuracy、AP、false-positive rate 或 specificity。

### E2 可执行因果层

吸收所有通过三臂复核的 OpenDev 对照、主动重放和历史锚点。没有限定负例或 A3 的严格 A0/A1/A2 仍是有效 E2 正例。

报告目标找回、检查位置找回、可运行检查率、失败/恢复判断和 `not_assessed` 比例。端到端分母包含所有 E2 目标；漏报目标不能从执行准确率分母中删除。

### E3 有界负例层

只在真实执行并证明消费变化表面的命令范围内成立。如果一个 bounded universe 内正负候选都完整判定，可以报告 precision/specificity；否则只报告 false-alarm、abstention 和预测数量。

### E4 兼容变化层

独立报告已有合格 A3。它测量 change-level abstention，不负责给 E2 正例补资格。

## 划分设计

当前 `index.jsonl` 的 100 条全部标为 `test`，不能据此进行正式调参与评测。新划分按组进行：

1. 折叠仓库别名、迁移仓和多模块记录；
2. 共享同一有向源仓到目标仓关系的案例并为一组；
3. 共享源提交族、兼容性机制或目标修复模板的组继续合并；
4. 在组级分配 development、evaluation、holdout；
5. 单例候选目录只进入 development 或 catalog-sensitivity；
6. 以关系组数量为主要平衡目标，案例数、年份和目录规模作为次要平衡项。

同一组不得跨 split。正式划分形成前，标签频率策略只作泄漏诊断，所有运行都称为开发结果。

## 指标与基线

主表至少包含：

- random/order baseline；
- same-owner/name baseline；
- label-frequency diagnostic upper bound，明确标为读取标签、不可公平比较；
- flat multi-repo code search/review；
- Marshal 当前 Cowboy 配置覆盖，单独标为 applicability；
- Marshal 候选代码读取与排序适配。

全报候选仓的召回为 1.0，因此召回必须与 MRR、Recall@K 和预测数量同时出现。

## 构造准入与停止规则

新案例的最低准入按目标层决定：

- E1：候选目录规则成立、时点输入可取得、至少一个语义确认目标；
- E2：另需 A0/A1/A2 和对应失败机制；
- E3：另需同输入消费证明与范围内稳定通过；
- E4：另需兼容变化真实进入消费表面。

停止继续恢复某条候选的条件是：找不到目标时点提交、没有维护者精确 A2、环境无法恢复或机制无法归因。停止只影响它能否进入 E2，不妨碍其作为搜索框、拒绝记录或 E1 材料保留。

当前暂停以“30 至 50 个完整四臂项目包”为规模目标。下一次扩采决定必须先基于现有材料的 E1-E4 重分类数量、根仓数量、每例准备耗时和候选目录审计结果。

## 下一步

1. 为 12 个现有候选目录建立 provenance 审计，优先处理四个单例目录。
2. 生成关系组并提出 development/evaluation/holdout 划分；在人工确认前不改正式索引。
3. 将现有案例和工作流按 E0-E4 重分类，E2 不再等待 E3/E4。
4. 在小型 development split 上运行首个真正读取候选代码的排序流程。
5. 根据实测结果决定是否需要 prediction schema v2；当前不改 schema。

本设计不修改 Marshal 产品代码，也不新增产品 gate、冻结 contract、固定 baseline 或内容 hash。

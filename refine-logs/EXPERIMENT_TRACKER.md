# 实验任务表

日期：2026-08-25

| 编号 | 阶段 | 目的 | 输入 | 输出 | 状态 |
|---|---|---|---|---|---|
| N001 | D0 | 候选目录来源审计 | 12 个目录、生成脚本、项目名录 | provenance 与目录处置 | 完成；OpenTelemetry、Rust 已按独立来源重建，2 个目录可进入 development 测量 |
| N002 | D0 | 单例目录敏感性处置 | drizzle、opencontainers-image、wandertracks、zuul | development/sensitivity 清单 | 完成；4 个均限制为 development/sensitivity |
| N003 | D1 | 根仓与关系分组 | 100 条 case、46 种有向关系 | group manifest | 完成；保守形成 12 个 project connected groups |
| N004 | D1 | split 提案 | group manifest | development/evaluation/holdout 统计 | 提案完成；46/32/22，正式启用阻塞于目录重建 |
| N005 | D2 | E1 迁移 | specification/implementation labels | E1 manifest | 完成；190 个关系记录进入 E1 |
| N006 | D2 | E2 复核 | OpenDev、执行锚点、workstreams | 三臂复核 manifest | 部分完成；1 个严格 A0/A1/A2 关系进入 E2，18 个含执行臂或项目包结果的 summary 待逐项复核 |
| N007 | D2 | E3/E4 盘点 | 限定负例和合格 A3 日志 | execution evidence manifest | 初步盘点完成；当前 0 个自动准入，未用文件名或状态词升级 |
| N008 | D3 | 小型离线排序 | development 输入 | 可解析 prediction 与失败记录 | 完成；1 个 sensitivity case，读取 3 仓代码，目标 rank=1 |
| N009 | D4 | development 测量 | baselines、Marshal 适配 | 分层指标与失败分析 | 12 条主测量与单次大小归一化消融完成；全局大小惩罚失败，停止调参并转入新评分规则设计 |
| N010 | D5 | evaluation/holdout | 固定系统设置 | 正式分层结果 | 仍阻塞于其余五个多案例目录 provenance 与正式 split 启用 |
| N011 | D0 | 50 条数据就绪 | 第三个独立目录、时点快照、确定性清单 | 50-case data-ready manifest | 完成；Ethereum 重建后合格池 71 条，清单固定 50 条，Marshal 执行为 0 条 |
| N012 | release verification | 50 条最终 E1 数据集 | 71 条独立目录候选、本地证据、实时 GitHub 记录 | 最终索引、逐项审计与项目隔离 split | 完成；71/71 候选和 154/154 目标关系通过，发布 50 条、107 个目标关系，Marshal 执行为 0 条 |

## 已有资产

| 资产 | 状态 | 新设计中的位置 |
|---|---|---|
| 100 条历史适配案例和时点快照 | 完成 | E1 development material，待 N001-N005 |
| 6 条 OpenDev 因果储备 | 已物化，待独立复核 | E2 candidates |
| Alembic、SnakeYAML、SLF4J、Log4j 等执行材料 | 日志保留 | N006-N007 重分类 |
| jcabi、terser、AssertJ、Checkstyle 等三臂或 A3 拒绝材料 | 日志保留 | E2/E3 或拒绝记录，不再因缺 A3 整体淘汰 |
| Marshal 当前配置覆盖 | 完成 | applicability diagnostic |
| Marshal 十四仓原生接口诊断 | 完成 | 证明当前入口不读取候选代码 |

旧 R001-R047 的逐候选状态保存在 `EXPERIMENT_TRACKER_20260823_235036.md` 及各 workstream，不删除、不重写；从本表开始按 candidate-bounded 设计推进。

## 2026-08-25 D0-D3 实施记录

- 基础审计与清单：`benchmarks/cross-repo-pr-impact/results/candidate-bounded-foundation-2026-08-25/`
- 代码读取试运行：`benchmarks/cross-repo-pr-impact/results/candidate-code-pilot-2026-08-25/`
- 目录重建：`benchmarks/cross-repo-pr-impact/results/catalog-rebuild-2026-08-25/`
- 当前决定：Ethereum、OpenTelemetry 与 Rust 的 71 条材料具备独立目录 provenance，其中 50 条已进入 data-ready 清单；全数据 evaluation/holdout 不启用。其余九个目录仍保留重建前或敏感性状态。
- 当前下一步：独立规定一个基于查询词覆盖/特异性的评分规则，不在已完成的 12 条标签上继续搜索大小归一化参数；其间可继续人工复核 18 个含执行臂或项目包结果的 summary，但不得按文件名批量提升到 E2-E4。
- D4 smoke：`benchmarks/cross-repo-pr-impact/results/candidate-code-eligible-smoke-2026-08-25/`；两条案例读取 21 个候选仓，宏召回与 MRR 均为 0.667，结果只证明两项目执行路径，不作为 development 主结果。
- D4 development slice：`benchmarks/cross-repo-pr-impact/results/candidate-code-development-12-2026-08-25/`；12 条案例、131 个候选仓时点组合、276,013 个文件。代码排序 top-3 的 MRR/Recall@1/Recall@3 为 0.444/0.194/0.431，非语义全排序对照为 0.380/0.111/0.139。Rust 有明显增益，OpenTelemetry MRR 未超过对照，因此不直接扩到 39 条。
- D4 analysis-lite：同切片 `sqrt(files_read)` 归一化使 OpenTelemetry MRR 0.167→0.375，但 Rust 1.0→0.125，总体 0.444→0.292。复合成功条件失败；不再在这 12 条标签上搜索其他指数，后续评分设计必须把仓库大小留作诊断而非单调惩罚。
- 50-case data-ready：`benchmarks/cross-repo-pr-impact/results/ethereum-catalog-rebuild-2026-08-25/`。Ethereum 独立目录重建成功，三个目录的合格池增至 71；固定清单为 35 OpenTelemetry + 4 Rust + 11 Ethereum，共 50 条、663 个时点组合、0 fetch failure。该记录显式标记 `marshal_execution_completed=false`。
- Final 50 E1 verification：`benchmarks/cross-repo-pr-impact/results/final-dataset-verification-2026-08-25/`。统一审计 71 条候选和 154 条目标关系，全部通过本地与实时记录对照；最终发布 25 OpenTelemetry + 21 Ethereum + 4 Rust，共 50 条、107 条目标关系，项目不跨 split。该集合只支持 E1 历史采纳/适配，不支持 50 条 E2 或 Marshal 实跑结论。

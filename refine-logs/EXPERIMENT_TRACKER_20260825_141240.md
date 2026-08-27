# 实验任务表

日期：2026-08-25

| 编号 | 阶段 | 目的 | 输入 | 输出 | 状态 |
|---|---|---|---|---|---|
| N001 | D0 | 候选目录来源审计 | 12 个目录、生成脚本、项目名录 | provenance 与目录处置 | 待执行 |
| N002 | D0 | 单例目录敏感性处置 | drizzle、opencontainers-image、wandertracks、zuul | development/sensitivity 清单 | 待执行 |
| N003 | D1 | 根仓与关系分组 | 100 条 case、46 种有向关系 | group manifest | 待执行 |
| N004 | D1 | split 提案 | group manifest | development/evaluation/holdout 统计 | 待执行 |
| N005 | D2 | E1 迁移 | specification/implementation labels | E1 manifest | 待执行 |
| N006 | D2 | E2 复核 | OpenDev、执行锚点、workstreams | 三臂复核 manifest | 待执行 |
| N007 | D2 | E3/E4 盘点 | 限定负例和合格 A3 日志 | execution evidence manifest | 待执行 |
| N008 | D3 | 小型离线排序 | development 输入 | 可解析 prediction 与失败记录 | 待执行 |
| N009 | D4 | development 测量 | baselines、Marshal 适配 | 分层指标与失败分析 | 待执行 |
| N010 | D5 | evaluation/holdout | 固定系统设置 | 正式分层结果 | 阻塞于 N001-N009 |

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

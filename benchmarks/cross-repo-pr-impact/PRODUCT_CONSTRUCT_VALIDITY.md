# 数据集与 Marshal 产品构念对齐

日期：2026-08-31

## 结论

50 条 strict-E2 仍是可信的因果正例集，但原冻结运行只测到了候选仓排序。它不能单独代表 Marshal 的因果验证层。产品级评测现在拆为四个相互独立的轨道：候选选择、真实因果执行、克制面和逃逸棘轮。任何总结果都必须同时给出各轨道的分母与 `not_assessed`，不能再用标签层的 A0/A1/A2 真实性代替受测系统的执行成绩。

## 当前实测状态

| 轨道 | 数据 | 当前可报告结果 | 仍缺什么 |
|---|---|---|---|
| 候选选择 | 50 条 E2，30/10/10 关系隔离 | 目标仓排序、MRR、Recall@K、检查位置 | 生态与 mechanism 分布不均，不能外推领域无关性 |
| 因果执行 | 同 50 条 E2；执行结果由 evaluator 单独写入 | 已新鲜重放 1 条，A0/A1/A2 为 0/1/0；50 条分母上的严格执行准确率 0.02，`not_assessed` 率 0.98 | 当前主仓材料仅 1/50 可直接新鲜重放；独立发布包 0/50 闭包 |
| 克制面 | 3 个完整 bounded project pack，10 条 E3 | 10/10 经原始证据解析验证；每条三次 A0=0/A1=0 | 尚未对这三个 pack 运行受测系统；主 E2 集的非目标仍是 `unjudged` |
| 逃逸棘轮 | 3 条 strict-E2 派生顺序任务 | 当前 Marshal 登记率 1.0、复发调度率 0、端到端棘轮率 0 | `InvariantRegistry` 中新登记的检查没有进入 `Orchestrator.plan` 的调度来源 |

对应机器产物：

- `results/formal-e2-benchmark-50-v2-2026-08-30/execution-materials-audit.json`
- `results/product-execution-smoke-2026-08-31/product-score.json`
- `results/restraint-e3-10-v1-2026-08-31/independent-verification.json`
- `results/ratchet-sequences-v1-2026-08-31/current-marshal-score.json`

## 为什么执行结果必须独立

`score_product_evaluation.py` 不读取预测里的自报 `execution_result`。受测系统先冻结候选排序和执行请求，随后 evaluator 才能用数据集固定命令产生 `execution-results.jsonl`。缺结果就是 `not_assessed`；不能把历史标签证据复制成受测系统成绩。证据卡还必须包含实际命令和逐臂日志引用。

这条分离解决一个具体失败场景：系统可以在完全没有运行命令时把每个目标都写成 `fail_without_companion_pass_with_companion`，旧 `score_e2.py` 会把它算作执行判断正确。Git 提交、版本号、JSON Schema、类型和普通单元测试只能证明记录形状与源码版本，不能证明该系统在本次冻结预测之后真的执行了三臂，因此产品级 scorer 必须使用 evaluator-owned 结果。

## E3 克制面的边界

首批十条 E3 来自三个同源、混合正负候选的完整项目包：

- OpenStack requirements / Alembic：1 个破坏仓、5 个命令级 E3；
- SnakeYAML 2.0：2 个破坏仓、2 个命令级 E3；
- SLF4J 2.0：1 个破坏仓、3 个命令级 E3。

每条 E3 都要求同一固定目标提交、三次隔离 A0/A1、实际版本探针、执行过的相关原生命令和明确的 claim ceiling。只有这三个完整 bounded universe 可以报告 evidence-backed precision/specificity；50 条 E2 主集仍不允许报告这些指标。

## 目录规则的修正口径

“本样本只引用一次”与“为一个隐藏目标量身构造”不是同一件事。正式目录禁止的是后者。一个目录即使在当前 50 条中只被观察一次，只要其成员来自独立组织、生态索引或构建编排，生成过程不读标签，设计上可复用于未来同类源事件，且包含真实候选压力，就不是单例答案目录。

`construct-validity-diagnostics.json` 单列所有 observed-once 目录、成员数、selection rule 和准入理由；不再用案例引用次数代替 provenance 判断。

## 分布与记忆风险

客观分层为：44 条 OpenStack、4 条 GitHub JVM、2 条其他 OpenDev；development 的 30 条中 29 条是 requirements constraint。按时间为 19 条 2025 年以后、26 条 2021–2024、5 条 2020 年以前。

因此当前结果只支持这些已观察生态和机制。报告必须同时给出 ecosystem、replay adapter、split 和 recent/middle/legacy 分层。案例年龄只作为潜在前视记忆的可审计代理，不主观给案例贴“著名”或“冷门”标签，也不据年龄直接断言模型记忆。

## 发布状态

可以发布“50 条 strict-E2 标签集”和“候选选择任务”。不能把当前套件描述成已经完整评估 Marshal 因果验证产品：新鲜执行闭包仍是 1/50，独立分发闭包是 0/50，E3 尚无真实系统判断，棘轮当前实测不通过。后续工作是补齐其余 replay material、运行三个 restraint pack，并在新生态形成独立关系组；这些工作不降低 strict-E2 难度，也不改变主集非目标的 `unjudged` 语义。

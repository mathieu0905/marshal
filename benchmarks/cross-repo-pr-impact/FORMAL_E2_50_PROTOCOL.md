# 50-case formal strict-E2 benchmark protocol

日期：2026-08-26

## 目标

重新采集 50 条正式 strict-E2 案例。现有 50 条只保留为 development/diagnostic，不能进入新集合的 evaluation 或 holdout。

正式案例必须同时满足：候选目录与目标标签独立且跨案例复用；输入是源变更首次公开时可见的 opening diff 与候选仓代码；A0/A1/A2 真实执行方向为通过、失败、恢复；Marshal 在读取隐藏标签前保存预测；关系、源提交族、机制和修复模板不跨 split。

## 固定执行顺序

1. **目录先行**：从治理清单、生态依赖或构建编排生成目录，记录来源与成员；不得读取目标仓、目标 PR、失败结果或修复结果。
2. **源事件入池**：只记录 source opening 的 base/head、diff、路径、时间和目录引用。排除与旧 50 条共享源变化族的事件。
3. **输入物化与盲跑**：解析目录内各仓在 opening cutoff 的代码；受测 Marshal 断网运行，只能读取 `INPUT_SPEC.md` 允许的字段，预测写入独立文件。
4. **标签揭示与三臂重放**：之后才读取目标修复线索，执行 A0/A1/A2。失败或不可恢复的候选进入拒绝记录，不能替换盲跑预测。
5. **关系折叠与 split**：累计超过 50 条后，先按有向关系、源提交族、机制和修复模板合组，再从完整组选择 50 条并分配 development/evaluation/holdout。
6. **一次性计分**：evaluation/holdout 不用于调整目录、输入、排序器或阈值。非目标候选仍为 `unjudged`，不报告 precision、F1、误报率或 specificity。

## 工作文件边界

- 可公开的 catalog 和 source frame 不包含目标仓、目标 PR、A1 失败签名或 A2 修复位置。
- 未计分前的目标线索与三臂结果放在未发布的 private label store；Marshal 进程无权读取该目录。
- 预测文件一旦生成，只允许追加运行诊断，不因后续标签调整排序。
- 不使用内容 hash 或额外冻结 contract；时间顺序、文件隔离、Git 提交和最终发布记录足以表达本流程。

## 首选采集面

优先使用能够同时提供 opening revision、跨仓协调关系和可复用目录的 OpenDev/Gerrit 项目：

- OpenStack requirements 或 governance 管理的项目集合；
- StarlingX manifest 中的构建仓集合；
- Zuul/OpenDev 明确的租户或构建编排集合。

OpenDev 当前 `Depends-On` 历史的前 6,000 条合并变更中有 2,999 个链独立 source lead，足以作为候选漏斗。`Depends-On` 只用于标签阶段定位可能的 A2；目录成员不得由这些目标链接生成。

## 发布条件

正式发布需要恰好 50 条 eligible case、零旧数据重叠、零 split group 泄漏、50 条盲跑预测、50 条机器解析三臂证据、50 条 opening-time 输入，以及干净环境下可重复的计分结果。任何未满足项都按真实数量报告，不用 development 案例补齐。

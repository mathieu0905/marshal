# Marshal Gate Decision Benchmark

这是一个新的 Marshal-native 评测轨。它不复用旧 `cross-repo-pr-impact` 的候选仓排序
任务，也不把通用 review 评论当成主任务。

任务定义见 [TASK_DEFINITION.md](TASK_DEFINITION.md)。

## 当前状态

- `mgd-dev-001`：规则编写与端到端打通样例；真实 A0/A1/A2 为 `0/1/0`；不能进入正式
  evaluation/holdout。
- `mgd-cand-007`：同一生成规则在另一目标仓上的泛化诊断，但复用了规则编写时已见过的
  source event，因此仍固定为 `development`，不能进入 evaluation/holdout。
- `mgd-cand-009`、`mgd-cand-011`：未读取结果标签的 Domain Pack 生成规则恰好覆盖了全部
  已执行 invariant，当前为 `case_ready_for_pool`。
- `mgd-cand-002` 至 `006`、`008`、`010`：生成规则漏掉 gold test，或生成了尚未完整执行的
  invariant，已原样拒绝；没有手工缩小 Pack。

规则编写时使用过的 source commit 单独记录在 `rule-authoring-sources.json`。verifier 会据此
强制 development split，不能只靠案例自身把 `rule_authoring_case` 改成 `false` 进入池中。

首条 Pack 生成器只读取：

- `openstack/requirements` 源基线的 `upper-constraints.txt`；
- Cinder 截止提交下的 Python 测试源码；
- 测试中的直接 import；
- 既有 `stestr` 命令形状。

它不会读取 A1 日志、失败签名、目标修复或目标 PR。生成的 development Pack 当前包含
43 个依赖契约和 737 条测试不变量；`tooz` 变化只命中其中一条，而不是把 gold 单独写进
Pack。

## 运行首条样例

```bash
python benchmarks/marshal-gate-decision/run_current_marshal.py \
  benchmarks/marshal-gate-decision/cases/mgd-dev-001/public/case.json \
  --output benchmarks/marshal-gate-decision/results/mgd-dev-001/current-marshal-prediction.json

python benchmarks/marshal-gate-decision/score_prediction.py \
  benchmarks/marshal-gate-decision/results/mgd-dev-001/current-marshal-prediction.json \
  benchmarks/marshal-gate-decision/cases/mgd-dev-001/private/gold.json \
  --output benchmarks/marshal-gate-decision/results/mgd-dev-001/score.json

python benchmarks/marshal-gate-decision/verify_case.py \
  benchmarks/marshal-gate-decision/cases/mgd-dev-001/public/case.json \
  benchmarks/marshal-gate-decision/cases/mgd-dev-001/private/gold.json \
  --current-prediction \
  benchmarks/marshal-gate-decision/results/mgd-dev-001/current-marshal-prediction.json
```

当前 Marshal 的真实结果是：

- tier：命中；
- contract set：命中；
- invariant set：命中；
- route：正确路由到 `openstack/cinder`；
- execution：当前 reporter 不会切换到异仓，记录 `not_run`；
- verdict：当前为 `escalate`，而真实候选组合检查失败的完整能力 gold 为 `block`。

因此这条样例不会给当前系统一个虚假的“全链路通过”；它会准确显示已具备的配置选择和
路由，以及尚未具备的异仓组合执行。

## 测试

```bash
pytest -q benchmarks/marshal-gate-decision/test_marshal_gate_decision.py
```

## 发布边界

`private/`、旧排序结果、A2 修复和三臂日志不得挂载给受测系统。正式集合还需满足任务定义
中的 pass/block/escalate、近邻不触发、本地/异仓路由及关系组隔离要求。单条 verifier
通过不等于集合已经可发布。

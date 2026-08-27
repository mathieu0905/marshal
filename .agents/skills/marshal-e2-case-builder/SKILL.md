---
name: marshal-e2-case-builder
description: Build, resume, inspect, and verify one candidate-bounded Marshal strict-E2 benchmark case from source-opening inputs through isolated blind prediction, real A0/A1/A2 replay, semantic adjudication, scoring, and a formal-pool-ready package. Use for “打通一条 E2”, constructing a benchmark case, or diagnosing where a case-construction run stopped; do not use for bulk harvesting before one case passes end to end.
---

# Marshal strict-E2 单条构造器

一次只处理一条关系。目标不是筛出“可能相关”的记录，而是产出一个能够进入正式池的完整 case package。

每次任务和交接先声明：

`任务性质：依赖兼容性数据集构建。目标机制：<本条真实兼容性机制>。范围：仅本地构建、测试、版本差分和结果记录；不进行漏洞复现或攻击性操作。`

## 入口

从 Marshal checkout 解析路径：

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
SKILL="$REPO_ROOT/.agents/skills/marshal-e2-case-builder"
PIPELINE="$SKILL/scripts/build_case.py"
```

先读 [references/workflow.md](references/workflow.md)。创建或修改 manifest 时再读
[references/manifests.md](references/manifests.md)。项目的语义口径仍以
`benchmarks/cross-repo-pr-impact/{CANDIDATE_BOUNDED_DESIGN.md,TASK_DEFINITION.md,INPUT_SPEC.md}`
为准。

运行一条完整流水线：

```bash
python "$PIPELINE" run \
  --public-manifest <public-case.json> \
  --private-manifest <private-label.json> \
  --output-dir <new-output-dir>
```

若 blind 容器已成功退出并写完隔离证据，但在第一次读取 private manifest 之前因
本地验证器错误中止，可在修复并测试验证器后继续，不重跑昂贵的完整目录扫描：

```bash
python "$PIPELINE" resume-after-blind \
  --public-manifest <public-case.json> \
  --private-manifest <private-label.json> \
  --output-dir <existing-output-dir>
```

该入口只接受 `private/` 尚不存在、stored public manifest 与传入 manifest 完全一致、
且现有 blind package 重新验证通过的目录；标签已经揭示或 blind 未完成时不能使用。

复核已有输出：

```bash
python "$PIPELINE" verify --output-dir <output-dir>
```

当 label-independent catalog 很大且 public snapshots 已经审计完成时，先用
`prepare_case_inputs.py --archives-only --archive-cache <root> <case-id>` 缓存并校验
所有 `available` 精确提交归档，再把该 root 作为 public manifest 的
`snapshot_archive_root`；不能只缓存目标仓或 blind top-k。

若现有共享目录不含目标，不能把目标手工并入目录。对于有生态坐标的 source，可用
`scripts/build_component_catalog.py` 从该 source package 的全部 dependent-package
分页结果构造新的可复用目录；该过程只读取 source 坐标，不读取 E2 标签。生成后仍需
在 source-opening cutoff 解析每个成员并缓存所有 `available` 快照。

## 不可降级的准入语义

- 正式目录必须与单条标签独立、记录 provenance、跨 source event 复用；目标在目录中不等于目录由目标生成。
- blind 子进程只能看到 opening code diff、public input、cutoff snapshots、候选 Git mirrors 或按 snapshot commit 命名的精确源码归档，以及 runner code。使用 Docker allowlist mounts、只读根文件系统和 `--network none`；不能仅靠 `labels_read: false` 自我声明。
- 揭示标签必须发生在 prediction 已落盘且容器退出之后。
- A0/A1/A2 使用同一条目标仓既有维护者测试或构建命令；A0 是旧源+旧目标，A1 只换新源，A2 在 A1 上只加入维护者目标修复。
- 目标仓已有命令直接比较相邻 source checkout 时，使用 `cross_repo_command`；三臂保持同一目录布局和命令参数，并解析每臂实际检查数。
- A0=0、A1!=0、A2=0，A1 失败签名在 A0/A2 中不存在。模拟退出码、后加断言、token/行匹配和仅有协调链接都不能成为 E2。
- 机器三臂通过后仍需语义审查：源变化确实导致该失败，A2 精确消除同一机制，且目标修改不是靠删测试、跳过测试或无关宽迁移恢复。
- E3/E4 不属于 E2 准入条件。额外候选仓是 `unjudged`，不报告 precision、F1、误报率或 specificity。

## 状态口径

只使用以下三种完成表述：

- `machine_strict_e2`：三臂和失败签名机器通过，但语义尚未批准。
- `case_ready_for_formal_pool`：单条 public/blind/replay/semantic/score/verify 全部通过；尚未完成组级 split。
- `formal_benchmark`：只有集合层完成关系、源族、机制和修复模板隔离 split 并正式发布后才能使用。

不要把 source 数、筛选数、启动的 replay 数或机器候选数写成正式完成数。

## 批量化条件

在至少一条 `case_ready_for_formal_pool` 之前，不启动新的批量采集。首条通过后，批量化只能循环同一个 manifest 驱动入口；若新生态需要新的 replay adapter，先用一条 case 做同等端到端验证，再扩大。

## 50 条集合发布

达到 50 条后，把选中的 50 个单条输出目录逐行写入 JSONL：

```json
{"output_dir":"benchmarks/cross-repo-pr-impact/results/single-case-pipeline-..."}
```

再执行：

```bash
python "$SKILL/scripts/release_formal_pool.py" \
  --case-list <50-case-list.jsonl> \
  --output-dir <new-release-directory>
```

发布器会重新运行全部 50 条单例 verifier，而不是信任旧 `case-report.json`；随后按
有向关系、source change family、规范化机制和规范化 repair template 求连通组，只按
组做确定性的 30/10/10 分配。无法精确分配、存在重复关系、catalog 定义冲突、任一条
不再满足 strict-E2 或 blind 隔离时，发布整体失败。集合输出中的非目标候选仍为
`unjudged`，不生成 precision、F1、误报率或 specificity。

冻结集合后，再运行正式系统预测；该入口在 50 个断网容器全部退出并写入统一 boundary
之前不会读取 `final-index.jsonl` 或 expected locations：

```bash
python "$SKILL/scripts/run_frozen_benchmark.py" \
  --release-dir <release-directory> \
  --output-dir <new-system-run-directory> \
  --workers 8
python "$SKILL/scripts/verify_frozen_benchmark.py" \
  --release-dir <release-directory> \
  --output-dir <system-run-directory>
```

集合发布和正式推理必须分别运行 `verify_formal_release.py` 与
`verify_frozen_benchmark.py`。前者重解析 50 条三臂和分组；后者重解析 50 份隔离证据、
预测、标签揭示时间以及逐条和聚合分数。

# Marshal 项目级跨仓评测数据集

## 用途

这是一组可机器读取、可批量准备和可实际运行的跨仓评测数据。它把同一上游变化及其消费仓组织为项目，而不是把每个依赖升级当作互不相关的单仓任务。

当前版本包含：

- 4 个项目级任务；
- 11 个唯一仓库；
- 7 个消费仓案例；
- 14 个待运行的仓库组合状态；
- 3 个已发布依赖的多消费仓扩散任务；
- 1 个未合并候选版本协同任务。

本目录不修改或调用 Marshal 产品实现。`runner.py` 只负责数据校验、Git 工作树准备和案例命令执行。

## 文件

| 文件 | 内容 |
|---|---|
| `index.jsonl` | 项目索引和数据划分 |
| `cases/*.json` | 项目、仓库、版本、依赖、命令和预期结果 |
| `schema.json` | 案例格式 |
| `result-schema.json` | 运行结果格式 |
| `runner.py` | 校验、准备和批量运行入口 |
| `licenses.json` | 数据来源和各仓库许可证 |
| `results/*.jsonl` | 已执行的结构化结果 |
| `CANDIDATE_CASE_ASSESSMENT.md` | 未发布候选版本案例的纳入与排除依据 |

## 案例语义

`released_dependency_fanout` 表示已发布依赖升级：

- `before` 是消费仓父提交和旧上游版本；
- `after` 是依赖升级提交和新上游版本；
- 预期是升级前通过、升级后以指定类别失败。

`candidate_version_coordination` 表示尚未合并时的跨仓组合：

- WanderTracks 的两个状态使用同一个前端候选提交；
- `before` 配上 API 仓父提交，跨仓测试 6 项全部跳过；
- `after` 配上 API 仓候选提交，跨仓测试 6 项实际执行并通过；
- 因此退出码之外，还用 `output_contains` 确认候选版本确实被消费。

同一项目的不同消费仓可以从不同旧版本升级。例如两个 slf4j 消费仓分别从 1.7.36 和 1.7.32 升到不同的 2.0 版本。数据格式不会把项目级任务错误简化为一对全局旧、新版本。

## 运行

校验数据：

```bash
python benchmarks/cross-repo-project/runner.py validate
```

从空目录准备并运行全部案例：

```bash
python benchmarks/cross-repo-project/runner.py all \
  --workspace .work/cross-repo-project/eval \
  --results benchmarks/cross-repo-project/results/local-run.jsonl
```

只运行一个项目：

```bash
python benchmarks/cross-repo-project/runner.py all \
  --workspace .work/cross-repo-project/wandertracks \
  --project opendev-wandertracks-mapstyle-coordination \
  --results .work/cross-repo-project/wandertracks-results.jsonl
```

也可以先执行 `prepare`，检查工作树后再执行 `run`。`all` 要求工作目录为空，避免旧构建产物影响结果。每条命令都以参数数组执行，不经过命令行解释器。

## 环境

BUMP 案例要求 Java 11 和 Maven，WanderTracks 案例要求 Node.js 22 和 npm。运行器会从 `JAVA_HOME_11`、`JDK_11_HOME`、系统 Java 目录，以及 `NODE_HOME_22`、当前可执行文件和 nvm 安装目录中寻找对应版本。它不负责安装运行时。

测试日志保存在工作目录的 `logs/<run_id>/`。仓库中的结果文件只保存结构化摘要，不复制第三方源码或大体积日志。

## 数据划分

当前 7 例全部属于 `test`。样本来自已经公开的真实故障和协调变更，规模太小且上游高度相关，不适合作为训练集，也不拆分一个缺乏统计意义的开发集。后续增加案例时应按上游仓库分组划分，避免同一上游变化同时出现在训练和测试中。

## 首次完整重放

2026-08-22 的首次 BUMP 端到端重放使用 OpenJDK 11.0.31、Maven 3.9.8 和 Git 2.43.0：

- 6 个升级前状态全部通过；
- 6 个升级后状态全部按预期失败；
- 失败包括 3 个编译失败、2 个测试失败和 1 个依赖锁失败；
- 12 条结果全部与预期一致。

WanderTracks 候选组合使用 Node.js 22.23.2、npm 10.9.8 和 Git 2.43.0：上游父提交组合的 6 项跨仓测试全部跳过，上游候选提交组合的 6 项全部执行并通过，两条结果均与预期一致。

完整合并结果见 `results/replay-2026-08-22.jsonl`。原始日志和准备记录位于仓外工作目录 `/home/zhihao/hdd/marshal-dataset-work/benchmark-e2e-20260822-v2`。

## 许可与边界

本目录只保存仓库地址、Git 版本、公开变更链接、命令和结果摘要，不分发第三方源码。BUMP 元数据为 MIT；运行时克隆的各仓库继续受自身许可证约束，详见 `licenses.json`。

前三个项目使用已经发布的 Maven 产物，能测共同上游的影响扩散，但不能证明未发布产物替换。WanderTracks 项目直接把另一个候选仓工作树作为测试输入，专门覆盖候选版本是否被实际消费。当前候选组合只有一组，不应据此计算总体准确率。

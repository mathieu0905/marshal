# 跨仓审查数据集调研

**核验日期**：2026-08-22

## 选择结论

首轮选择 [BUMP](https://github.com/chains-project/bump)，但把任务重组为 provider-side update pack：一个 provider 的相同 `(GAV, old, new)` 变化对应多个 consumer snapshots。首轮只覆盖 Maven dependency updates，不混入 wire/schema/runtime 等无动态真值任务。

## 数据集比较

| 数据集/来源 | 可执行动态 oracle | 多 consumer | Green truth | 适合用途 | 结论 |
|---|---:|---:|---:|---|---|
| [BUMP](https://zenodo.org/records/10041883) | 是，pre-pass/after-fail Docker pair | 可按重复 update tuple 重组 | 原始集没有，需要另行挖掘并重放 | 主评测 positives | 首选 |
| [Breaking Bad](https://zenodo.org/records/5221840) | 否，主要是静态 API/client 分析 | 是 | 否 | 找 provider-client 候选、补 green candidates | 辅助，不能独立做真值 |
| [Maracas](https://github.com/alien-tools/maracas) / [BreakBot](https://github.com/alien-tools/breakbot) | 工具输出，不是独立 oracle | 是 | 否 | Java API-change 工具对照 | 不用其标签验证同类能力 |
| [LibEvolutionEval](https://github.com/amazon-science/LibEvolutionEval) | 版本相关代码补全，不是 consumer build truth | 否 | 否 | library evolution completion | 不适合首轮 |
| OpenDev/Gerrit + [Zuul](https://zuul-ci.org/docs/zuul/latest/gating.html) | 可从历史 CI/depends-on 重建 | 是 | 需自行构建 | coordinated-ref 外部案例 | 第二阶段 case study |

## BUMP 可用规模

对 BUMP repo commit `324d5513aa5c` 的 `data/benchmark/*.json` 做本地确定性统计：

- 571 个可重现 breaking dependency update cases；
- 153 个唯一 consumer repositories；
- 39 个重复 `(groupId, artifactId, old, new)` groups，覆盖 104 cases；
- 只保留 `COMPILATION_FAILURE` / `TEST_FAILURE` 并排除 build plugin updates：30 groups / 82 cases；
- 再要求真实 GitHub provider compare URL：28 groups / 78 cases；
- 这 78 cases 来自 11 个 provider repos，包括 35 compilation failures 和 43 test failures。

该统计只用于候选池，不等于最终 benchmark。最终规模取决于 replay 与 green controls。

## Update Pack 定义

一个 pack 包含：

- provider repo 与 old/new source diff；
- `(GAV, old, new)`；
- 2-4 个 failing consumer pre-state snapshots；
- 2-4 个对完全相同 update 的 verified-green consumer snapshots；
- hidden oracle commands/results；
- failure category 与可用 file oracle。

受测系统只看到 provider diff、consumer pre-state、公开 manifests/源码和其条件允许的 graph/tools；看不到 BUMP JSON、failureCategory、reproduction logs、PR title/body/comments/status、最终 fix 或后续 commits。

## Green Controls

优先级：

1. 完全相同 GAV old-to-new 的真实 green Dependabot/Renovate PR；
2. 不足时，从 Breaking Bad/client graph 找 old-version consumers，在历史 snapshot 上合成相同升级。

接受条件：

- pre 与 candidate 各 `2/2` pass；
- effective POM / dependency tree 确认 candidate version 实际解析；
- 使用相同隔离环境和命令；
- 网络、infra、flaky 或 dependency override 不算 green。

不能使用：

- BUMP unsuccessful reproduction；
- Maracas 没有报告 break；
- 只看 CI status、没有可重放命令；
- dependency management 实际仍锁在旧版本的“假绿”。

## Split 与泄漏控制

构造 provider-repo ↔ consumer-repo 二部图，按 connected components 分配约 15% calibration、20% development、65% held-out test。同 provider 的全部 artifacts/version series、相同 consumer、fork 必须在同一 split。

held-out run 前记录并保持不变：prompt、tool budget、consumer ordering policy、condition order、输出后处理和 unsupported-pass 判定。每 pack/condition 运行 3 次 fresh session，条件顺序 Latin-square 轮换。

## License 与发布

- BUMP 工具/Zenodo 元数据标为 MIT；Docker 内第三方源码仍按各上游许可证，不能整体按 MIT 再发布。
- Breaking Bad 数据为 CC BY 4.0；使用时需要 attribution。
- 新挖 GitHub code/PR 受对应 repo license 和平台条款约束。
- 首轮内部运行。公开时只发布原创 case manifest、URL/commit/GAV、派生标签和复现脚本；不打包源码、PR dump、Docker layers，除非逐项确认许可。
- BUMP tar 约 149.9 GB，官方提示完整 load 至少 250 GB；首轮按 case 使用 GHCR images，避免加载全量 tar。

## 主要风险

最大的风险不是模型，而是能否获得足够 verified greens。D0 如果在 2 engineer-days 内无法让至少 2/3 packs 各获得 2 个 green controls，就停止 balanced benchmark 路线，降级为 case study，不通过增加更多机制掩盖数据不足。

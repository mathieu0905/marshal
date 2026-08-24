# ANTLR Runtime 3.2 到 3.3 的 FSE 关系族历史筛选

评估日期：2026-08-25

## 裁决

四条 FSE 记录全部来自 `owlcs/OPPL2` 的四个 Maven 模块。去重后只有 **1 个唯一根仓审计单元**，不能拆成四条跨仓关系。该根仓没有可恢复的历史 A1 提交，也没有在 ANTLR Runtime 3.3 输入下的维护者精确 A2，因此在重放前拒绝，正式接纳 **0 条**。

没有为了复现公开失败而手工把目标 POM 改到 3.3，也没有根据失败栈合成 parser 或测试修复。这样做最多能重现外部依赖实验，不能产生数据集要求的维护者因果链。

## 完整候选框与去重

从 `fse2024-behavioral-breakage-frame.jsonl` 精确筛选 `org.antlr:antlr-runtime` 3.2 到 3.3，共得到四条候选、14 个失败观察：

| 候选 | 根仓模块 | 制品 | 失败观察数 |
|---|---|---|---:|
| `fse2024-behavioral-0283` | `oppl2` | `oppl2-oppl2` | 6 |
| `fse2024-behavioral-0284` | `oppl2patterns` | `oppl2-oppl2patterns` | 6 |
| `fse2024-behavioral-0285` | `oppl2templates` | `oppl2-oppl2templates` | 1 |
| `fse2024-behavioral-0286` | `oppl2testcase` | `oppl2-oppl2testcase` | 1 |

四个目录提示都以 `owlcs_OPPL2` 开头，四个制品也是同一父 POM 的 reactor 模块。当前父 POM 仍同时列出这些模块，并统一声明 `antlr` 与 `antlr-runtime` 3.2。故统计口径为：4 条原始模块记录、1 个唯一根仓、1 个源变化输入、最多 1 条关系，而不是 4 条关系。

完整逐模块测试合同和源工作簿行号保存在 `candidate-frame.jsonl`。

## 历史证据

远程镜像覆盖 `owlcs/OPPL2` 所有分支与标签，共 545 个可达提交，时间从 2010-03-15 到 2020-10-27。对所有历史对象去重后共有 134 个不同 POM blob，其中 26 个声明 `antlr-runtime`；26 个全部使用 3.2，使用 3.3 的数量为零。当前远程头 `29f5419366cc5cd9a5db921b8cd7d8a7aed8cf79` 和 Maven Central 发布的 `oppl2-parent:5.0.0` 也仍使用 3.2。

远程共有四个 pull request，内容分别是一个 issue 修复和三次 JUnit 更新；没有 ANTLR 3.3 的 pull request 或 issue。公开失败中的主要测试方法可在仓库历史中找到，但仓库从未把它们与 3.3 一起提交，因此这些方法只能确认 FSE 实验确实打到了本仓的 parser 合同，不能提供历史 A1 或 A2。

## 为什么不重放

FSE 工作簿记录了把依赖从 3.2 更新到 3.3 后的执行失败，却不包含目标仓修订号。即使以远程头为近似目标，再将 POM 手工改为 3.3，也只能得到数据集作者制造的 A1。更关键的是，完整目标历史中没有任何保持 3.3 输入的维护者修复；后续代码始终固定在 3.2。缺少精确 A2 时继续重放无法改变准入结果，只会制造一个无恢复臂的失败线索。

因此本轮保留：

- 4 条模块级公开失败线索；
- 1 个链独立根仓审计单元；
- 14 个测试失败观察；
- 0 个可重放三臂候选；
- 0 条正式关系。

机器可读计数与远程证据分别保存在 `root-audit.jsonl`、`history-evidence.json` 和 `results/antlr-3.3-fse-history-screening-2026-08-25/summary.json`。

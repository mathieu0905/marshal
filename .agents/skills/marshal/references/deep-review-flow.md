# 流 A-deep — Codex 深审（$marshal deep）

常规审查是每个 lens 一次检查；deep 将它替换为“变更闭包 → scout 假说 → prove 证真/证伪”。它购买的是严谨度，不是无上限召回，只对 high-tier、共识面、经济守恒、跨仓签名或用户显式要求的改动使用。

## 1. 分级与 lens 选择

- cli classify --repo <r> --paths … 得到 tier、review_dimensions、security_hazards。
- cli review-lenses --repo <r> --paths … --ratchet-top <N> 得到 base、hazards、ratchet、all。
- 从 all 中选 3–4 个与风险最相关的 lens：对症的 base + 1–2 个 ratchet。若 all 少于 3 个，用 review-orchestration 中的通用 correctness、spec、test-validity prompt 补到 3 个并标为 fallback；空逃逸史只表示没有历史探针，不是 degraded。不要全量扇出。

## 2. 构造变更闭包

派一个 context-builder subagent。对每个改动 hunk 收集 PR head（本地模式则当前工作树）的完整外层函数；Markdown/配置等非代码文件收集完整所属章节；再加 1 跳调用方/被调用方，以及命中的 contract 和 invariant 正文，形成中立、不预判 bug 的 closure bundle。

- 上限约 1500 行；超出时按执行、存储和共识风险优先。
- 任何截断都必须显式记录。
- 后续 scout/prove 使用同一份闭包，避免各自读取不同版本。

## 3. Scout 假说枚举

按选定 lens 并行派出 medium-effort subagent。每个 agent 只枚举失败假说，不做最终判断：

    {title, claim, where, invariant_broken, priority}

claim 必须采用“if <状态/输入> then <不变量如何破坏>”的可检查形式。每个 lens 至少给出 6 条，包括看似无聊的边界条件。

## 4. 完整性闸

所有预定 scout lens 返回后才允许去重和 prove。不得按“先回的前 N 个”提前收敛。

- lens 崩溃或超时：标 degraded(lens-incomplete)，列出缺席 lens，GateDecision 至少 escalate。
- 当前会话没有并行 subagent 能力时，可顺序执行同一组 lens；不能省略。

## 5. 去重与上限

跨 lens 按 where + claim 邻近去重。每个 lens 最多保留 6 条，全局最多约 18 条。若截断，记录原始数、保留数和丢弃数。不同 scout 的 priority 标度不可直接比较，排序应回到具体风险内容。

## 6. Prove 证真/证伪

每条存活假说交给一个 fresh high-effort subagent。它必须返回：

- confirmed：给出具体 inputs/state → wrong output/halt/fork 触发路径。
- refuted：给出实际挡住路径的 guard、前置条件或设计事实。
- uncertain：既构造不出触发，也无法排除；保留并标 degraded。

没有具体触发不得 confirm。demonstrated > asserted。

## 7. 聚合与判决

将 confirmed/uncertain 转为结构化 findings，运行：

    "$PY" -m marshal_core.cli review-quorum --findings-json '<findings>' --proximity 10

prove 已内建证伪，所以 confirmed/escalate 可以跳过常规二段 skeptic；advisory 仍需列出。

GateDecision 与流 A 相同：不变量 fail → block；确认的 high finding → escalate；闭包、lens 或 prove 不完整 → escalate + degraded；否则 pass。报告中的 confirmed finding 必须附触发路径。

## 降级纪律

闭包建不成、任何预定 lens 未返回、prove 超预算或工具失败时，明确标记 degraded 和缺失步骤。整体 deep 无法运行时回退常规流 A，但不得声称已经完成 deep review。

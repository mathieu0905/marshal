---
type: concept
concept_id: execution
parent: node
importance: high
part_of: []
depends_on: [pvm, storage]
anchors:
  - {repo: node, path: execution/src/execution/engine.rs, symbol: ExecutionEngine, kind: implements}
spec_refs: [CIP-1, CIP-3]
status: authoritative
last_updated: 2026-07-26
---

# 执行引擎（Execution）

块执行的主入口。`ExecutionEngine` 逐笔分派交易（System / Actor 指令）、校验 basefee、扣 gas、burn/tip 分账，并驱动 PVM handler。子模块含 basefee 管理、双 gas 计量、runner/token 指令处理。

代码权威：`node/execution/src/execution/engine.rs`（`ExecutionEngine`）。子概念：actor-model / continuation / speculative-execution / timer-mechanism / dual-gas-model。

---
type: concept
concept_id: actor-model
parent: execution
importance: high
part_of: []
depends_on: [pvm]
anchors:
  - {repo: node, path: types/src/execution.rs, symbol: Actor, kind: implements}
  - {repo: node, path: types/src/execution.rs, symbol: Message, kind: implements}
spec_refs: [CIP-1]
status: authoritative
last_updated: 2026-07-26
---

# Actor 模型

Cowboy 核心计算抽象：每个链上合约是一个 Actor（独立状态 + PVM Python 代码 + 独立邮箱），仅通过消息通信，无共享内存。`send_message` 异步入 mailbox，`call_actor` 同步递归（最深 32 层）。

代码权威：`node/types/src/execution.rs`（`Actor` / `Message`）。**drift**：CIP-1 v1 §3 描述 "Timer-then-Tx"，代码实为 "Tx-then-Timer"（已由 CIP-5 revision native 化，drift.md E-1）。

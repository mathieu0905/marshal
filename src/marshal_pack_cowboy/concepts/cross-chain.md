---
type: concept
concept_id: cross-chain
parent: ""
importance: mid
part_of: []
depends_on: [vrf-runner-selection, settlement-slashing]
anchors: []
spec_refs: [CIP-25]
status: draft
last_updated: 2026-07-26
---

# 跨链架构（Cross-Chain，CIP-25）

把 Cowboy 跨链能力分成三个正交层：L1 状态锚定（BlockCommitment + Merkle 证明原语）、L2 消息（mailbox，exactly-once + 单调序）、L3 应用（asset bridge / oracle / generic call）。L1 信任后端可插拔（runner committee / ZK / optimistic / native LC），swap 不破坏 L2/L3 不变量。

**drift**：CIP-25 为 Draft（2026-04-23），纯架构层 spec，代码未实装，故 `status=draft` 无锚点。Runner committee 后端复用 CIP-2 的 VRF 选择与 slashing。

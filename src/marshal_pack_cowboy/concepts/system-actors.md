---
type: entity
concept_id: system-actors
parent: node
importance: high
part_of: []
depends_on: []
anchors:
  - {repo: node, path: runner/src/system_actors.rs, symbol: SystemActorAddresses, kind: implements}
  - {repo: node, path: types/src/constants.rs, symbol: GOVERNANCE_SYSTEM_ACTOR, kind: implements}
spec_refs: [CIP-2, CIP-12]
status: authoritative
last_updated: 2026-07-26
---

# 系统 Actor（保留低位地址）

Genesis 初始化、拥有特权操作的协议级 Actor。代码已实装部署型 `0x01`–`0x0C`（`SystemActorAddresses` 12 个常量）+ 虚拟拦截型 `0x1D`（Event Subscription）。

**drift**：CLAUDE.md 旧列 `0x91-0x95` 已被 CIP-2/CIP-23 supersede 为 `0x01-0x05`。`0x0D`–`0x13`（Route/Gateway/Receipt/Container/PaymentGate/StreamKey/Bank Registry）为 spec-only，代码未实装（drift.md V-1）。代码权威：`node/runner/src/system_actors.rs`、`node/types/src/constants.rs`。

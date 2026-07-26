---
type: concept
concept_id: governance
parent: economics
importance: mid
part_of: []
depends_on: [settlement-slashing]
anchors:
  - {repo: node, path: types/src/constants.rs, symbol: GOVERNANCE_SYSTEM_ACTOR, kind: implements}
spec_refs: [CIP-12]
status: draft
last_updated: 2026-07-26
---

# 链上治理（CIP-12，部分实装）

`0x09 GOVERNANCE` 系统 Actor 承载治理参数。CIP-12 完整设计是双院投票（质押 CBY + 验证者一人一票）+ Security Council + Tier 0-4 提案分类，属 Draft/spec-only。

**代码已落地面**：`SettlementConfig`、`Proposal` 表、`SubmitProposal/CastVote/ExecuteProposal`（opcode 45/46/47）、`DrainRelay`/`AutoDrainPolicy`（opcode 85/86）—— demo 用"每地址 1 票"简化路径。代码权威：`node/types/src/constants.rs`（`GOVERNANCE_SYSTEM_ACTOR=0x09`）、`node/execution/src/execution/system_instruction.rs`。完整双院/Tier/Council 未实现，故 `status=draft`。

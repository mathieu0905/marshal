---
type: concept
concept_id: settlement-slashing
parent: economics
importance: constitutional
part_of: [runner]
depends_on: [dual-gas-model]
anchors:
  - {repo: node, path: runner/src/types.rs, symbol: SettlementConfig, kind: implements}
  - {repo: node, path: execution/src/runner/verifier.rs, symbol: verify_chain_root, kind: implements}
spec_refs: [CIP-2, CIP-3, CIP-13]
status: authoritative
last_updated: 2026-07-26
---

# Settlement 与 Slashing

Runner 任务的经济结算与惩罚。Tip（basefee 以上部分）按 `SettlementConfig{runner_percent, burn_percent, treasury_percent}`（存 `0x09`，`UpdateSettlementConfig` opcode 40，仅 `0x09` 可改）分配；basefee 部分 100% burn。Slash 默认 50% Treasury / 50% Burn，stake 跌破 `MIN_STAKE` 则 reputation=0。

代码权威：`node/runner/src/types.rs`（`SettlementConfig`）、`node/execution/src/runner/verifier.rs`（`verify_chain_root` 及 slash 路由）。Dispute window `DISPUTE_WINDOW_BLOCKS=75`。**drift**：CIP-14 v2 的 `target_pool` 多池枚举（V-9）与 CIP-13 v2 的委托 slash 级联均 spec-only。

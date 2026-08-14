---
type: concept
concept_id: basefee
parent: economics
importance: constitutional
part_of: []
depends_on: [gas]
anchors:
  - {repo: node, path: execution/src/basefee.rs, symbol: DualBasefee, kind: implements}
  - {repo: node, path: execution/src/basefee.rs, symbol: BasefeeConfig, kind: implements}
  - {repo: node, path: types/src/constants.rs, symbol: MIN_BASEFEE, kind: implements}
spec_refs: [CIP-3, CIP-5]
status: authoritative
last_updated: 2026-07-26
---

# Basefee 更新（EIP-1559 双市场）

Cycles 与 Cells 各维护独立 basefee，每块按几何反馈规则更新（`Δ = basefee × |used−target| / target / ALPHA`，双向 clamp）。状态持久化在系统 Actor `0x06`（DUAL_BASEFEE）；basefee 部分 100% burn，tip 按 SettlementConfig 分配。

代码权威：`node/execution/src/basefee.rs`（`DualBasefee` / `BasefeeConfig`）、`node/types/src/constants.rs`（`MIN_BASEFEE=10_000`）。**drift**：代码 `BLOCK_CYCLES_TARGET=20_000_000` / `BLOCK_CELLS_TARGET=4_000_000`，与 CLAUDE.md 记的 10M/500K 及白皮书 α=8 均已漂移（drift.md A-1/A-2/A-3）。

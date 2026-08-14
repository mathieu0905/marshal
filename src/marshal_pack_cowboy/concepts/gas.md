---
type: concept
concept_id: gas
parent: economics
importance: constitutional
part_of: []
depends_on: []
anchors:
  - {repo: node, path: execution/src/gas.rs, symbol: GasCosts, kind: implements}
  - {repo: node, path: execution/src/gas.rs, symbol: DualGasMeters, kind: implements}
  - {repo: node, path: execution/src/gas.rs, symbol: GasReport, kind: implements}
spec_refs: [CIP-3]
status: authoritative
last_updated: 2026-07-26
---

# Gas 计量（Dual Meters）

CIP-3 双计量：`GasCosts` 定义所有 per-op 常量，`DualGasMeters` 分别累计 Cycles（计算）与 Cells（数据），`GasReport` 给分类明细。改动它牵动全链数值守恒，故 importance=constitutional。

代码权威：`node/execution/src/gas.rs`（`GasCosts` / `DualGasMeters` / `GasReport`）。`STORAGE_READ_CYCLES` 在 PVM 执行后按 `ActorStorageCache` 的 read_count 批量补扣；calldata/return data 各 1 Cell/byte。

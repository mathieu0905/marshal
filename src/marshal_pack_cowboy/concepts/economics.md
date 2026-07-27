---
type: concept
concept_id: economics
parent: ""
importance: high
part_of: []
depends_on: []
anchors:
  - {repo: node, path: execution/src/gas.rs, symbol: GasCosts, kind: implements}
spec_refs: [CIP-3]
status: authoritative
last_updated: 2026-07-26
---

# 经济系统（Economics）

Cowboy 的费用、gas、结算与惩罚顶层域：双计量 gas（Cycles + Cells）、EIP-1559 basefee、tip 分配、runner 结算与 slashing、治理可调参数。所有链上稀缺资源定价与价值守恒都归此域。

代码权威：`node/execution/src/gas.rs`（`GasCosts` 全部 per-op 常量）。子概念：gas / basefee / dual-gas-model / settlement-slashing / governance。

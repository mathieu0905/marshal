---
type: concept
concept_id: dual-gas-model
parent: execution
importance: constitutional
part_of: [economics]
depends_on: [basefee]
anchors:
  - {repo: node, path: execution/src/gas.rs, symbol: GasReport, kind: implements}
  - {repo: node, path: execution/src/basefee.rs, symbol: BLOCK_CYCLES_TARGET, kind: implements}
spec_refs: [CIP-3]
status: authoritative
last_updated: 2026-07-25
---

# 双计量 Gas 模型(Dual-Metered Gas）

Cowboy 分离**计算(Cycles)**与**数据(Cells)**两种稀缺资源,各自独立 EIP-1559
basefee 市场。改动它牵动全链数值守恒,故 importance=constitutional。

代码权威:`node/execution/src/gas.rs`(GasReport 分类)、`node/execution/src/basefee.rs`
(BLOCK_CYCLES_TARGET 等)。规格与代码历史漂移见 drift 记录(种子自 refs/analysis 修正案)。

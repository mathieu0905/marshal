---
type: concept
concept_id: runner-delegation
parent: runner
importance: mid
part_of: [economics]
depends_on: [settlement-slashing, vrf-runner-selection]
anchors: []
spec_refs: [CIP-13]
status: draft
last_updated: 2026-07-26
---

# Runner Stake 委托（CIP-13 v2）

CBY 持有人锁定委托给 Runner，提升其有效质押（`effective_stake = self_stake + total_active`，直接进 VRF 权重与最大 Job 价值），换取结算分成。协议只实现最小 hook（注册/分账/slash 级联/解绑）；tranche 记账、per-epoch slash cap（500 bps）、24h unbonding 均在 spec。

**drift**：CIP-13 v2 为 Draft，`Requires CIP-12`，协议未实现——delegation opcodes 与代码 52-57（CIP-8 Session）撞号，激活时需重号到 ≥87 free range（drift.md V-3）。故 `status=draft` 无锚点。

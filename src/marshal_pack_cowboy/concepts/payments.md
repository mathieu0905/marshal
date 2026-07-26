---
type: concept
concept_id: payments
parent: gateway
importance: mid
part_of: [economics]
depends_on: [dns-addressable-actors]
anchors: []
spec_refs: [CIP-18]
status: draft
last_updated: 2026-07-26
---

# Payments（CIP-18）

给 CIP-14 actor 补外部付款入口：Gateway 边缘强制 + 链上 `PaymentGate (0x11)` 统一结算 + 四种付款模型（per-request / actor-funded / prepaid pass / epoch subscription）+ 双 wire（MPP 主、x402 兼容，normalize 成同一 PaymentIntent）+ 多资产（CBY + CIP-20 + 桥接稳定币）。

**drift**：CIP-18 r2 为 Draft；`PAYMENT_GATE=0x11`、`payment.gate`/`bridge.facilitate.evm` entitlement、EVM bridge facilitator 均为 precondition，代码未实装（drift.md V-15/V-16）。故 `status=draft` 无锚点。

---
type: concept
concept_id: mpp-session
parent: economics
importance: mid
part_of: [runner]
depends_on: [settlement-slashing, runner-verification]
anchors:
  - {repo: node, path: types/src/session.rs, symbol: Session, kind: implements}
spec_refs: [CIP-8]
status: authoritative
last_updated: 2026-07-26
---

# MPP Session（支付通道）

「链上托管 + 链下累积 voucher + 链上结算」通道模型，把 N 次 Runner 微调用的链上开销从 N 笔摊到 3 笔（Open/Settle/Finalize）。对接 Stripe/Tempo 的 Machine Payment Protocol；voucher 用 EIP-712 cumulative 金额，Settle 按 89/10/1 分账（复用 `SettlementConfig`）。

代码权威：`node/types/src/session.rs`（`Session`）；`SESSION_ACTOR=0x0C`、opcodes 52-57、链下 voucher 库均已实装（CIP-8 为追认 CIP）。**drift**：`COWBOY_SESSION_CHAIN_ID=1` 为 PoC 值，mainnet 前需定源（drift.md V-13）。

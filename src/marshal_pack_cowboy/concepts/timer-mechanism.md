---
type: concept
concept_id: timer-mechanism
parent: execution
importance: mid
part_of: []
depends_on: [basefee, actor-model]
anchors:
  - {repo: node, path: execution/src/timer_config.rs, symbol: TimerConfig, kind: implements}
  - {repo: node, path: execution/src/pvm_host.rs, symbol: schedule_timer_ex, kind: implements}
spec_refs: [CIP-1, CIP-5]
status: authoritative
last_updated: 2026-07-26
---

# Timer 机制

Actor 用 `schedule_timer` / `schedule_timer_ex` 注册未来块高触发的回调。CIP-5 revision（2026-04-20）升级为收费 + 有 TTL + 显式 `fee_payer` 模型：每次 fire 按 basefee 预扣 `max_cost` 再退还差额，三路退出（natural fire / TTL expiry / insufficient-funds self-destruct）。

代码权威：`node/execution/src/timer_config.rs`（`TimerConfig`）、`node/execution/src/pvm_host.rs`（`schedule_timer_ex`，拒绝第三方 fee_payer）。opcodes 48/49/50（cancel/update-config/extend）已在代码。**drift**：CIP-1 v2 早稿曾推荐 opcode 70-72，已撤销（drift.md）。

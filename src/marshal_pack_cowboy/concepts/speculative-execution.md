---
type: concept
concept_id: speculative-execution
parent: execution
importance: high
part_of: [storage, consensus]
depends_on: [timer-mechanism]
anchors:
  - {repo: node, path: storage/src/speculative.rs, symbol: SpeculativeResult, kind: implements}
  - {repo: node, path: storage/src/blockchain_storage.rs, symbol: SpeculativeBatch, kind: implements}
spec_refs: []
status: authoritative
last_updated: 2026-07-26
---

# 投机执行（Speculative Execution）

propose/verify 阶段执行进 WriteBuffer（可回滚），report 阶段才 `apply_cached_batch` 落盘 QMDB。块内流程：begin_batch → execute_txs → fire_timers → sweep_deferred → compute_roots → cache → rollback。gas 按 lane 分区（USER/RUNNER/TIMER/SYSTEM）避免 priority inversion。

代码权威：`node/storage/src/speculative.rs`（`SpeculativeResult`）、`node/storage/src/blockchain_storage.rs`（`SpeculativeBatch`）。Deferred tx 受 `MAX_PENDING_DEFERRED_PER_ACTOR=64` / `DEFERRED_TX_MAX_AGE_BLOCKS=1000` 约束。

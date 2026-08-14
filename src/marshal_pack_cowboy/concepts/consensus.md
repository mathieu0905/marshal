---
type: concept
concept_id: consensus
parent: node
importance: high
part_of: []
depends_on: []
anchors:
  - {repo: node, path: chain/src/application.rs, symbol: Application, kind: implements}
  - {repo: node, path: chain/src/mempool.rs, symbol: Mempool, kind: implements}
spec_refs: []
status: authoritative
last_updated: 2026-07-26
---

# 共识（Consensus，Simplex BFT）

Cowboy 用 Simplex BFT。`Application` 实现三阶段回调：Leader `propose` 块、验证者 `verify`（独立重放比对 Merkle roots）、多数通过后 `report` 提交。`Mempool` 维护 per-account nonce 队列。

代码权威：`node/chain/src/application.rs`（`Application`）、`node/chain/src/mempool.rs`（`Mempool`）。执行如何在此三阶段间投机/回滚见 speculative-execution。

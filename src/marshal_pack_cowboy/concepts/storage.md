---
type: concept
concept_id: storage
parent: node
importance: high
part_of: []
depends_on: []
anchors:
  - {repo: node, path: storage/src/blockchain_storage.rs, symbol: BlockchainStorage, kind: implements}
spec_refs: [CIP-4]
status: authoritative
last_updated: 2026-07-26
---

# 存储层（Storage）

QMDB 支撑的链上状态：账户、actor、actor storage、mailbox、timer、receipt。`BlockchainStorage` 提供批量执行、写缓冲、Merkle root 计算、gas lane 分区与 burn/tip 分配。

代码权威：`node/storage/src/blockchain_storage.rs`（`BlockchainStorage`）。**drift**：CIP-4 的 MPT 统一 state root 尚未实现（当前分别算 accounts/actors/receipts root）。

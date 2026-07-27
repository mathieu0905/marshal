---
type: concept
concept_id: verifiable-state-read
parent: gateway
importance: mid
part_of: []
depends_on: [dns-addressable-actors]
anchors: []
spec_refs: [CIP-17, CIP-4]
status: draft
last_updated: 2026-07-26
---

# Verifiable State Read RPC（GET_STATE，CIP-17）

加一条 RPC `GET /state/{actor}/{key}?prove=true` 返回 `(value, merkle_proof, state_root, block_height)`，客户端本地验证 Merkle 证明再信任 value（零 PVM cycles）。是 CIP-15 v2 Gateway 路由缓存与 CIP-19 `tools/list` 派生的唯一硬阻塞 RPC；复用 CIP-4 已有 MPT trie 原语，估计 <200 行。

**drift**：CIP-17 为 Draft（2026-05-11）；现有 `/actors/{address}/storage` RPC 无 proof，CIP-17 在其上加 Merkle 证明尚未实装（drift.md V-17 已收口 spec 但代码待跟进）。故 `status=draft` 无锚点。

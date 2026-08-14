---
type: entity
concept_id: node
parent: ""
importance: high
part_of: []
depends_on: []
anchors:
  - {repo: node, path: chain/src/engine.rs, symbol: Engine, kind: implements}
  - {repo: node, path: chain/src/application.rs, symbol: Application, kind: implements}
spec_refs: []
status: authoritative
last_updated: 2026-07-26
---

# Cowboy Node（主链节点）

Cowboy L1 全节点（独立 Rust workspace `node/`），跑 Simplex BFT 共识与投机执行。顶层协调器 `chain::Engine` 串起 mempool、执行引擎与共识回调（`Application` 的 propose/verify/report 三阶段）。

代码权威：`node/chain/src/engine.rs`（`Engine`）、`node/chain/src/application.rs`（`Application`）。子系统见 execution / storage / consensus / pvm / system-actors。

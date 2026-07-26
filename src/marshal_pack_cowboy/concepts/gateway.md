---
type: entity
concept_id: gateway
parent: ""
importance: mid
part_of: []
depends_on: []
anchors: []
spec_refs: [CIP-14, CIP-15, CIP-16]
status: draft
last_updated: 2026-07-26
---

# Gateway（Ingress 节点角色，spec-only）

CIP-14 v2 引入的第一个 ingress 节点角色（与 Runner/Validator/Relay 并列），负责 TLS 终止、DNS 解析、read-only `read_handler` 执行、command 路径 `IngressDispatch` 中介、静态资产 serving。

**drift**：Gateway Registry `0x0E` 及 Route/Receipt Registry（`0x0D`/`0x0F`）在 `node/runner/src/system_actors.rs` 尚未实装（代码止于 `0x0C`）；全域 spec-only，故 `status=draft` 无代码锚点。见 refs/wiki/drift.md V-1。

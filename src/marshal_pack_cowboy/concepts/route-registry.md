---
type: entity
concept_id: route-registry
parent: gateway
importance: mid
part_of: []
depends_on: []
anchors: []
spec_refs: [CIP-14, CIP-16]
status: draft
last_updated: 2026-07-26
---

# Route Registry（系统 Actor `0x0D`，spec-only）

CIP-14 v2.r2 的 ingress 命名权威：维护 FQDN → actor 规范映射（注册/续费/转让/反查），CIP-16 v2 扩展到三类命名空间（`cowboy.network` / `.cow`|`.cowboy` / 外部 FQDN），用 `DomainBinding` 结构（`RouteRegistration` 的超集）。方法均为到 `0x0D` 的 ActorMessage，唯一新 SystemInstruction 是 `ExternalDomainCallback`（opcode 67）。

**drift**：`0x0D` 在 `node/runner/src/system_actors.rs` 尚未声明常量（代码止于 `0x0C=SESSION_ACTOR`，v2.r2 后移让位），故 `status=draft` 无锚点（drift.md V-1）。

---
type: concept
concept_id: dns-addressable-actors
parent: gateway
importance: mid
part_of: []
depends_on: [route-registry]
anchors: []
spec_refs: [CIP-14]
status: draft
last_updated: 2026-07-26
---

# DNS-Addressable Actors（CIP-14 v2）

让 Cowboy actor 经 HTTP 可达的 ingress 路由层。核心：`ingress.http` entitlement、Route Registry（`0x0D`）、Gateway Registry（`0x0E`）、Receipt Registry（`0x0F`）；请求分 read-only 路径（`read_handler` RPC，无共识，mutating syscall 全 trap）与 command 路径（`IngressDispatch` opcode 65，共识）。

**drift**：CIP-14 v2.r2 为 Draft；`0x0D`–`0x0F` 系统 actor、`ingress.http` entitlement、opcode 65/66 均为 precondition，代码未实装（drift.md V-1/V-2/V-3）。故 `status=draft` 无锚点。

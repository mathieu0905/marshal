---
type: concept
concept_id: public-asset-hosting
parent: gateway
importance: mid
part_of: []
depends_on: [dns-addressable-actors]
anchors: []
spec_refs: [CIP-15, CIP-9]
status: draft
last_updated: 2026-07-26
---

# Public Asset Hosting（CIP-15 v2）

扩展 CIP-14，让 Gateway 从 CIP-9 public volume 直接服务静态文件（HTML/CSS/JS/图片），绕过 actor 的 `http.request` handler（zero PVM cycles）。核心是存于 `STORAGE_MANAGER (0x0A)` 的 route manifest，声明哪些 URL 路径走 static vs dynamic；严格优先级 `min(dynamic.priority) > max(static.priority)`。

**drift**：CIP-15 v2 为 Draft；`ingress.static` entitlement + CIP-9 amendments（`GET_MANIFEST` / `ManifestCommitted` 事件 / canonical BLAKE3 Merkle pin）为 precondition，代码未实装。故 `status=draft` 无锚点。

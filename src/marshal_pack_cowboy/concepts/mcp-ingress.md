---
type: concept
concept_id: mcp-ingress
parent: gateway
importance: mid
part_of: []
depends_on: [dns-addressable-actors, payments]
anchors: []
spec_refs: [CIP-19]
status: draft
last_updated: 2026-07-26
---

# Gateway MCP Ingress（CIP-19）

让每个 CIP-14 actor 自动成为 MCP server：Gateway 在 `/_cowboy/mcp` terminate MCP streamable HTTP，`tools/list` 从 CIP-15 路由表自动派生（每个 method route 一个 tool），`tools/call` 翻译成 CIP-14 query/command dispatch，付款复用 CIP-18 wire。Actor handler 代码零改动（仍只看 `HttpRequestEnvelope`）。

**drift**：CIP-19 为 Draft；`ingress.mcp` entitlement 为新 registry 条目（drift.md V-15），依赖未实装的 CIP-14/15/18 栈。故 `status=draft` 无锚点。

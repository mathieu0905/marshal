---
type: concept
concept_id: custom-domains
parent: gateway
importance: mid
part_of: []
depends_on: [dns-addressable-actors, runner-verification]
anchors: []
spec_refs: [CIP-16]
status: draft
last_updated: 2026-07-26
---

# Custom Domains & First-Party TLDs（CIP-16 v2）

扩展 Route Registry 到两类命名：协议自有 `.cow` / `.cowboy` TLD，与外部 FQDN（如 `api.example.com`，经 DNS TXT 挑战证明控制）。外部域绑定用 CIP-2 multi-runner verifier 的 `MajorityVote` + `DnsTxtRecordMatch`/`DnsCnameMatch`（各查 ≥3 独立 resolver），完成后经 `ExternalDomainCallback`（opcode 67，sender 必须 `0x03`）激活。

**drift**：CIP-16 v2 为 Draft；v1 曾错用 `Deterministic` DNS 模式与 `421` 状态码，v2 改 `MajorityVote` + `503`。全套依赖未实装的 Route Registry `0x0D` 与新 verifier check。故 `status=draft` 无锚点。

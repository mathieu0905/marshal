---
type: concept
concept_id: tee-attestation
parent: runner
importance: mid
part_of: []
depends_on: [runner-verification]
anchors: []
spec_refs: [CIP-23, CIP-24]
status: draft
last_updated: 2026-07-26
---

# TEE Execution & Composite Attestation（CIP-23 v2）

把 `Deterministic + tee_required` 从字段存在性检查升级为密码学强制。引入 Composite Attestation Envelope（CAE）绑定 CPU TEE quote（TDX/SEV-SNP/Nitro）+ NVIDIA NCC GPU report + service signature，由 TEE Verifier `0x05` 跑 7 步验证流水线（Freshness→Replay→Cert chain→Measurement→Binding→Service sig→NRAS）。

**drift**：CIP-23 v2 为 Draft；代码 `0x05` 现仅有 trusted-key 表 + attestation 记录（CIP-24 opcodes 60-63），完整 CAE 流水线未实装（`VerifyCae` 等激活时落 ≥87 free range，drift.md V-3/V-7）；`CANONICAL_TEE_TYPES` 缺 `nitro`（V-6）。故 `status=draft` 无锚点。

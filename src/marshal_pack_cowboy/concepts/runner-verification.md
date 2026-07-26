---
type: concept
concept_id: runner-verification
parent: runner
importance: high
part_of: []
depends_on: [settlement-slashing]
anchors:
  - {repo: node, path: execution/src/runner/verifier.rs, symbol: verify_chain_root, kind: implements}
  - {repo: node, path: runner/src/types.rs, symbol: RunnerResult, kind: implements}
spec_refs: [CIP-2, CIP-16, CIP-23]
status: authoritative
last_updated: 2026-07-26
---

# Runner 验证模式（VerificationMode）

每个 Job 声明验证策略，Result Verifier（`0x03`）据此判定结果可信度：None / EconomicBond / MajorityVote / StructuredMatch / Deterministic（TEE + 字节级）/ SemanticSimilarity。MajorityVote/StructuredMatch 用 commit-reveal 防抄袭。

代码权威：`node/execution/src/runner/verifier.rs`（`verify_chain_root` 等）、`node/runner/src/types.rs`（`RunnerResult`）。**drift**：白皮书 §5 只列 4 种模式（缺 StructuredMatch/SemanticSimilarity，ZK-Proof 未实现，drift.md D）；CIP-23 v2 的 CAE 强制与 CIP-2 v2 的 DNS verifier check 为 spec-only。

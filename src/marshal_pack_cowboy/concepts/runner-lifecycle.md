---
type: entity
concept_id: runner-lifecycle
parent: runner
importance: high
part_of: []
depends_on: [vrf-runner-selection, runner-verification, settlement-slashing]
anchors:
  - {repo: node, path: runner/src/types.rs, symbol: RunnerRegistration, kind: implements}
  - {repo: node, path: runner/src/types.rs, symbol: RateCard, kind: implements}
spec_refs: [CIP-2]
status: authoritative
last_updated: 2026-07-26
---

# Runner 生命周期

7 阶段：Registration（stake ≥ 10,000 CBY，每活跃 Job 占 1.5× max_job_value）→ Job Discovery（VRF 选择）→ Off-chain Execution（LLM/HTTP/MCP，secp256k1 签名）→ Result Submission & Verification → Dispute Window（75 块）→ Settlement → Slashing（异常）。

代码权威：`node/runner/src/types.rs`（`RunnerRegistration` / `RateCard`）；链上面 `node/execution/src/runner/{registry,dispatcher,verifier}.rs`。TEE attestation-first 注册（CIP-23 v2）与委托（CIP-13 v2）为 spec-only 扩展阶段。

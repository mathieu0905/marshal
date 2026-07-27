---
type: concept
concept_id: runner
parent: ""
importance: high
part_of: []
depends_on: []
anchors:
  - {repo: node, path: runner/src/types.rs, symbol: RunnerRegistration, kind: implements}
spec_refs: [CIP-2]
status: authoritative
last_updated: 2026-07-26
---

# Runner（链下计算市场）

Cowboy 链下计算子系统：注册质押的 Runner 节点执行 LLM/HTTP/MCP 任务，链上系统 Actor（`0x01`–`0x03`）负责选择、验证、结算与惩罚。链上面在 `node/execution/src/runner/`，链下守护进程在独立 `runner/` repo。

代码权威：`node/runner/src/types.rs`（`RunnerRegistration`）。子概念：runner-lifecycle / runner-verification / vrf-runner-selection / runner-delegation / tee-attestation。

---
type: concept
concept_id: vrf-runner-selection
parent: runner
importance: high
part_of: []
depends_on: [runner-verification]
anchors:
  - {repo: node, path: execution/src/runner/dispatcher.rs, symbol: v3_runner_weight, kind: implements}
  - {repo: node, path: execution/src/runner/dispatcher.rs, symbol: tee_candidate_eligible, kind: implements}
spec_refs: [CIP-2, CIP-13, CIP-23]
status: authoritative
last_updated: 2026-07-26
---

# VRF + Stake-Weighted Runner 选择

Job Dispatcher（`0x02`）用确定但不可预测的算法从 Runner 池选 N 个：先过滤（能力、stake ≥ 1.5× max_job_value、未冻结），按 `weight = floor(log₂(stake/MIN_STAKE + 1)) + 1` 对数化权重，用 `seed = VRF(prev_block_hash ‖ job_id ‖ epoch)` 驱动 Fisher-Yates 洗牌抽取。

代码权威：`node/execution/src/runner/dispatcher.rs`（`v3_runner_weight` 权重、`tee_candidate_eligible` TEE 资格过滤）。2026-03-05 用 Fisher-Yates 替换旧 ring-buffer 以降关联；无 `skip_task` 机制。

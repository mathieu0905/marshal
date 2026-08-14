---
type: entity
concept_id: pvm
parent: node
importance: high
part_of: []
depends_on: []
anchors:
  - {repo: node, path: execution/src/pvm_executor.rs, symbol: PvmExecutor, kind: implements}
  - {repo: node, path: execution/src/pvm_executor.rs, symbol: validate_actor_code, kind: implements}
  - {repo: node, path: execution/src/pvm_host.rs, symbol: CowboyHost, kind: implements}
spec_refs: [CIP-6]
status: authoritative
last_updated: 2026-07-26
---

# PVM — Python Virtual Machine

基于 RustPython 的确定性 Python 运行时（`node/pvm/`，workspace-excluded）。`PvmExecutor::execute_handler` 加载 actor 代码 + checkpoint、注入 `INT_GUARD_PREAMBLE`、enforce `max_cycles`；`CowboyHost` 实现 host API（state_get/set、send_message、call_actor、submit_job、schedule_timer 等）。

代码权威：`node/execution/src/pvm_executor.rs`（`PvmExecutor` / `validate_actor_code`）、`node/execution/src/pvm_host.rs`（`CowboyHost`）。**已知限制**：裸字面量 `2**10000` 在 VM 字节码路径绕过整数 guard。

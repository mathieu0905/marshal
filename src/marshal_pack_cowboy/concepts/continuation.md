---
type: concept
concept_id: continuation
parent: execution
importance: mid
part_of: [pvm]
depends_on: [pvm, actor-model]
anchors:
  - {repo: node, path: pvm/crates/vm/src/vm/checkpoint.rs, symbol: save_checkpoint, kind: implements}
spec_refs: [CIP-6]
status: authoritative
last_updated: 2026-07-26
---

# Continuation 机制

当 Actor 发起异步操作（跨 Actor 调用、Runner 任务、Timer）时，Python 函数用 Checkpoint 挂起并在结果回来后恢复。支持函数级（F-checkpoint，保存局部变量 + 指令指针）与 Block Stack（try/finally/loop 上下文）两层；序列化用 CBOR Canonical（避免 pickle 任意代码执行）。

代码权威：`node/pvm/crates/vm/src/vm/checkpoint.rs`（`save_checkpoint` 等）。恢复时校验 actor code hash 未变且 continuation 未超龄。

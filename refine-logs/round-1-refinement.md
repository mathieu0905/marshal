# Round 1 Refinement

## Problem Anchor

- **Bottom-line problem**：Marshal 需要从“单个 PR 的问题检测”扩展为“同一大型项目内多个相互依赖仓库的联合审查”，能够回答一个变化会影响哪些仓库、应该验证哪组仓库版本，以及哪些结论有真实执行证据。
- **Must-solve bottleneck**：当前运行单位仍是单 `repo/ref`；跨仓 invariant 在自动 reporter 中会被记为 `not_run`，手工流程又默认在目标仓 tip 上执行，因此可能测试错误的仓库组合并产生假绿或假红。
- **Non-goals**：不建立永久企业知识图谱；不自动修改或合并协调 PR；不默认新增 hash、冻结 baseline、通用 contract 或 project gate；不把依赖关系命中直接当作 bug；不在首轮追求所有语言和构建系统。
- **Constraints**：保留 Marshal 现有 checkout 校验、零测试检测和降级语义；关系扫描不能替代真实构建、测试或模拟；第一阶段应 run-local、只读、advisory；仓库身份使用 `owner/repo`；拿不到真实组合时必须报告 unknown。
- **Success condition**：相较单仓审查和“只增加跨仓上下文”，该方案在真实可复现的跨仓破坏上显著提高受影响仓库召回与故障检测，同时在兼容升级和带协调修复的 change set 上保持可接受的误报，并能展示执行过的准确 repo/ref 组合。

## Anchor Check

- **Original bottleneck**：当前流程无法把多仓候选变化组成一个准确、被真实消费的验证组合，因此单仓通过或异仓 tip 上的通过不能证明跨仓兼容。
- **Why the revised method still addresses it**：修订后只保留一个中心规则：跨仓 `passed` 必须绑定 intended composition 的 consumption proof；没有 proof 就是 `not_assessed`，而不是通过。
- **Reviewer suggestions rejected as drift**：不把 BUMP 的 Maven 任务扩写成 wire/schema/runtime 的通用结论；不把 Zuul 式 merge scheduler 或永久 dependency catalog 纳入首轮。

## Simplicity Check

- **Dominant contribution after revision**：面向跨仓 AI review 的 evidence semantics，即“proof-bound pass”。
- **Components removed or merged**：自动关系发现、CI checkout discovery、wire/schema/deploy adapter、有界传递影响和 LLM 自由规划均退出 V0。
- **Reviewer suggestions rejected as unnecessary complexity**：不新增 artifact hash；V0 通过本次运行的空 Maven local repository、provider 本次构建和 resolved path 来排除旧 cache。
- **Why the remaining mechanism is still the smallest adequate route**：显式 change set、单向 edge、一个 composition adapter 和一份证据报告已经足以复现错误组合与未消费候选 provider 的失败场景。

## Changes Made

### 1. 收窄主张

- **Reviewer said**：主贡献被 change set、关系发现、执行和 benchmark 分散。
- **Action**：把主张收窄为 proof-bound pass；change set 是输入，关系是前提，benchmark 只是验证工具。
- **Reasoning**：CodeRabbit/Qodo 已覆盖 linked context 与 companion refs，Zuul 已覆盖跨项目组合执行；单独声称这些能力没有辨识度。
- **Impact on core method**：是否有消费证明成为唯一决定 `passed` 的必要条件。

### 2. 把 V0 落到 Maven/BUMP

- **Reviewer said**：composition 和 consumption proof 缺少可执行定义。
- **Action**：V0 只支持显式或 Maven manifest 导出的 `consumer -> provider` 一跳关系，并规定隔离依赖仓、解析确认和真实命令测量。
- **Reasoning**：BUMP 提供可重放 pre-pass/after-fail，是当前最强的动态 oracle。
- **Impact on core method**：首轮结论只适用于可 materialize 的 Maven dependency updates。

### 3. 约束 LLM

- **Reviewer said**：LLM planner 仍是口号。
- **Action**：LLM 只提出 typed `ObligationCandidate`，不选择 ref、不判定执行、不提供 compatibility oracle；V0 可完全删除 LLM 而运行。
- **Reasoning**：repo/ref、依赖解析、exit code 和测试数必须由工具给出。
- **Impact on core method**：前沿模型成为可消融的检索/规划层，而不是正确性的依赖。

## Revised Proposal

# 研究与产品方案：Proof-Bound Cross-Repository Review

## Problem Anchor

- **Bottom-line problem**：Marshal 需要从“单个 PR 的问题检测”扩展为“同一大型项目内多个相互依赖仓库的联合审查”，能够回答一个变化会影响哪些仓库、应该验证哪组仓库版本，以及哪些结论有真实执行证据。
- **Must-solve bottleneck**：当前运行单位仍是单 `repo/ref`；跨仓 invariant 在自动 reporter 中会被记为 `not_run`，手工流程又默认在目标仓 tip 上执行，因此可能测试错误的仓库组合并产生假绿或假红。
- **Non-goals**：不建立永久企业知识图谱；不自动修改或合并协调 PR；不默认新增 hash、冻结 baseline、通用 contract 或 project gate；不把依赖关系命中直接当作 bug；不在首轮追求所有语言和构建系统。
- **Constraints**：保留 Marshal 现有 checkout 校验、零测试检测和降级语义；关系扫描不能替代真实构建、测试或模拟；第一阶段应 run-local、只读、advisory；仓库身份使用 `owner/repo`；拿不到真实组合时必须报告 unknown。
- **Success condition**：相较单仓审查和“只增加跨仓上下文”，该方案在真实可复现的跨仓破坏上显著提高受影响仓库召回与故障检测，同时在兼容升级和带协调修复的 change set 上保持可接受的误报，并能展示执行过的准确 repo/ref 组合。

## Current Failure Point

Marshal 已经有跨仓线索，但没有跨仓证明链：

- `NormalizedEvent` 和 `DispatchJob` 只携带一个 repo/ref（`src/marshal_core/contracts.py:6-20`）。
- reporter 遇到 `location_repo != repo` 会直接写入 `not_run`（`src/marshal_core/executor/reporter.py:121-130`）。
- Cowboy `Contract` 只有 repo 集合、路径触发和 invariant，没有方向或 ref 组合（`src/marshal_pack_cowboy/pack.py:165-178`）。
- 手工 skill 对异仓 invariant 使用目标仓 `origin/devnet` / `origin/main` tip（`.agents/skills/marshal/references/gate-flow.md:34-40`）。

一个可复现的机制级失败是：wallet PR 触发 `tx-encoding` contract，而 invariant 位于 node。自动 reporter 不执行；手工流程即使在 node tip 上跑绿，也可能只验证 node 自己生成并消费的编码，并未消费 wallet PR 生成的字节。Git SHA 能标识 wallet 和 node 的源码，却不能证明运行中的 node 实际观察了 wallet 的候选产物。

## Method Thesis

> Marshal 只有在执行证据证明 consumer 实际消费了 intended provider snapshot 或其产物时，才允许把跨仓 obligation 标为 `passed`；否则必须保留为 `not_assessed` 或 `not_run`。

这称为 **proof-bound pass**。Project Change Set、方向 edge 和 LLM review 都服务于这条语义，不单独构成主贡献。

## Contribution Focus

- **Dominant contribution**：跨仓 AI review 的 proof-bound evidence semantics。
- **Supporting contribution**：一份同时展示 exact repo/ref composition、impact path、执行事实和 coverage gap 的 advisory report。
- **Evaluation artifact, not contribution**：BUMP update-pack benchmark protocol。
- **Explicit non-contributions**：自动 dependency graph、通用 contract DSL、CI scheduler、merge gate、模型训练、所有语言 adapter。

## V0 Scope

V0 是研究原型，不是完整产品承诺，只支持：

1. 一次运行内显式列出的 `owner/repo@ref` 组合；
2. 显式输入或 Maven manifest 可确认的一跳 `consumer -> provider` edge；
3. 一个 Maven composition adapter；
4. 一份只读 advisory evidence report。

自动 relation discovery、transitive traversal、CI checkout、Cargo、wire/schema、generated code、deploy relation 和 project gate 全部后移。

## Run-Local Interfaces

以下是设计字段，不是新增的永久 contract；V0 不写数据库。

### Project change set

| Field | Meaning | Source |
|---|---|---|
| `repository` | canonical `owner/repo` | explicit input |
| `root` | local checkout | explicit input |
| `candidate_revision` | Git commit/ref or labeled dirty worktree | Git / caller |
| `base_revision` | diff base when the repo changed | PR metadata / Git |
| `role` | changed provider or candidate consumer | explicit input |
| `edge` | `consumer -> provider` and dependency kind | explicit input / Maven manifest |
| `edge_evidence` | POM path, GAV selector, source location | parser output |

干净状态直接用 Git commit；dirty worktree 明确不可重放。V0 不生成内容 hash，也不把输入持久化为新 contract。

### Typed obligation candidate

LLM 可选地产生以下字段：consumer、provider、changed boundary、target file/symbol、adapter capability、existing command reference、rationale。确定性 planner 只接受已存在的 repo、已支持的 adapter 和可解析命令。LLM 不能选择 ref、改写 dependency truth、声明执行成功或给出 `passed`。

固定 Maven obligation 在没有 LLM 时也能产生，因此可以直接做 deletion check。

### Evidence record

| Field | Required observation |
|---|---|
| Composition | exact `owner/repo -> revision` map |
| Edge | consumer/provider、GAV、manifest path |
| Selection | why each ref/version was selected |
| Isolation | fresh run-local Maven repository or explicit reason unavailable |
| Resolution | `dependency:tree`/effective POM shows selected GAV and resolved file path |
| Execution | cwd、argv、exit code、relevant output |
| Measurement | compile target observed or non-zero related tests/simulations |
| Consumption | provider artifact was built/selected in this run and consumer resolved it |
| Gap | any repo, edge, ref, adapter, command or proof not covered |

## Maven Composition Adapter

### Released-version path used by BUMP

1. Checkout consumer pre-update snapshot in a disposable worktree.
2. Apply only the known old-to-new dependency selector inside that disposable checkout.
3. Resolve dependencies and record effective POM plus `dependency:tree`.
4. Verify that the selected GAV is the new version; if dependency management overrides it, stop as `not_assessed`.
5. Run the same compile/test command used for the pre-state.
6. A compile obligation requires an observed compile phase; a test obligation additionally requires at least one related test.

### Unreleased-provider path reserved for later product validation

1. Build the explicit provider candidate into an empty, run-local Maven repository.
2. Point the disposable consumer checkout at that repository and candidate coordinate.
3. Confirm the resolved path is inside the run-local repository and was produced by this run.
4. Execute the consumer check.

This path avoids a new artifact hash. A concrete stale-cache failure exists when two provider commits share the same GAV/SNAPSHOT: Git SHA identifies source, `dependency:tree` reports the same version, and ordinary tests may unknowingly consume an old `~/.m2` JAR. A fresh local repository plus in-run provider build and resolved path prevents that failure using existing Git/version/filesystem facts. If isolation is impossible, the result is not proof-bound and cannot be `passed`.

## Status Semantics

Impact and assessment remain separate:

- **Impact**：`affected | not_affected | unknown`
- **Assessment**：`passed | failed | not_run | not_assessed`

Rules:

- `affected` requires a sourced path from changed provider to consumer; absence of a discovered edge does not imply `not_affected`.
- `passed` requires valid consumption proof plus a relevant successful measurement.
- `failed` means the relevant check failed after the intended composition was consumed; it does not by itself prove causality.
- `not_run` means a runnable plan existed but checkout, tool, environment or command execution failed before a relevant observation.
- `not_assessed` means no supported adapter, unresolved ref/edge, or missing consumption proof.
- `incompatibility_found` requires either a pre-state pass/new-state fail control or diagnostics tied to the changed boundary.
- `verified_for_planned_scope` means all planned obligations are proof-bound passes; it never means global compatibility.
- everything else aggregates to `incomplete` with explicit coverage gaps.

No project-level `pass/block` verdict is introduced.

## Exact Role of the LLM

The LLM receives only: provider diff/boundary summary, one sourced edge, available adapter capabilities, and bounded consumer file/command metadata. It proposes ranked typed obligations and explains resulting evidence.

The LLM is not the oracle for identity, ref resolution, dependency resolution, command execution, test count, consumption proof or status. If deleting the LLM and using a fixed Maven obligation performs equally, V0 should keep the simpler deterministic route.

## Failure Handling

| Failure | Detection | Result |
|---|---|---|
| edge direction unknown | no manifest/explicit directional evidence | impact `unknown` |
| companion ref missing | explicit candidate cannot resolve | `not_assessed` |
| old dependency still resolved | effective POM/tree disagrees | `not_assessed` |
| shared cache may supply stale artifact | no run-local isolation/in-run production | `not_assessed` |
| command exits 0 with no relevant work | no compile observation or zero tests | `not_run` |
| repository already broken | pre-state control also fails | failure un-attributed; aggregate `incomplete` |
| candidate composition fails | pre passes, candidate fails after proof | `failed`, aggregate `incompatibility_found` |
| relation fan-out is large | V0 one-hop explicit bound | out-of-scope repos listed as gaps |

## Competitive Positioning

Public documentation establishes:

- CodeRabbit and Qodo already support linked repositories, automatic/manual relationships and companion branch/PR targeting.
- Greptile provides all-to-all read-only repo-cluster context.
- Bito provides cross-repository knowledge-graph impact context.
- Zuul already models cross-project `Depends-On` DAGs and performs speculative testing on composed changes.

Therefore Marshal must not claim novelty for multi-repo context, companion refs, dependency graphs or execution alone. The defensible product position is narrower: a review finding can only claim cross-repo verification when its evidence shows what combination ran and how the consumer consumed the candidate provider; uncovered paths remain explicit. This is a positioning hypothesis based on public docs, not proof that competitors have no internal equivalent.

## Claim-Driven Validation

### Claim C1: Direction plus real composition improves provider-side impact review

- **Scope**：only reproducible Maven dependency updates.
- **Task**：given provider old-to-new diff and a set of consumer pre-state repositories, rank consumers that will fail after adopting the update and classify `no impact / compilation / test`.
- **Conditions**：single repo; flat multi-repo context; directional edge without execution; full composition plus proof-bound execution.
- **Evidence**：pack-macro MAP/Recall@5, repo F1/MCC, failure macro-F1, green false-positive rate and execution cost.

### Claim C2: proof-bound semantics prevents unsupported compatibility conclusions

- **Scope**：same Maven packs plus verified green controls and deliberately unresolved/wrong-resolution cases.
- **Evidence**：false-compatible rate on breaking cases, proof validity audit, assessment coverage, `not_assessed` precision and executable-evidence rate.
- **Anti-claim**：improvement is not merely from seeing more repositories; flat context and directional-no-execution isolate this.

BUMP cannot validate wallet/node wire compatibility, runtime/deploy relations or coordinated PR scheduling. Those remain external case studies after the Maven result is positive.

## Evaluation Data Boundary

At BUMP repository commit `324d5513aa5c`, local deterministic counting finds:

- 571 reproducible cases across 153 consumer repositories;
- 39 repeated `(GAV, old, new)` groups covering 104 failing consumers;
- after keeping compilation/test failures and excluding plugin updates: 30 groups / 82 cases;
- after additionally requiring a real provider compare URL: 28 groups / 78 cases, from 11 provider repositories, including 35 compilation and 43 test failures.

The pilot starts from those 28 candidate groups, then retains only packs with at least two independently replayed green consumers for the exact update. No result is claimed before that negative-control construction succeeds.

## Phased Decision

1. **D0 data feasibility**：replay 3 packs; verify positive and green-control construction.
2. **D1 research pilot**：run the four conditions on development packs; do not change Marshal product code.
3. **D2 held-out evaluation**：only after data leakage and oracle checks pass.
4. **P1 product design validation**：if the effect is material, replay one real Marshal/Cowboy wallet-to-node artifact handoff using explicit refs.
5. **P2 expansion**：only then consider Cargo, CI checkout discovery, wire/schema adapters and bounded traversal.

Research go/no-go criteria decide whether to invest further; they are not product gates and create no frozen baseline.

## Remaining Risks

- Verified green controls may be expensive or unavailable for enough exact update tuples.
- BUMP measures dependency updates, not the full Cowboy architecture.
- LLM pretraining may contain old source history despite information hiding.
- A failing candidate build may require careful attribution to the provider change.
- Public competitor documentation does not establish implementation absence.

These risks are reasons to keep the first claim narrow, not reasons to add more mechanisms.

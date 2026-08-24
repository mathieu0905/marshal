# Round 2 Refinement

## Problem Anchor

- **Bottom-line problem**：Marshal 需要从“单个 PR 的问题检测”扩展为“同一大型项目内多个相互依赖仓库的联合审查”，能够回答一个变化会影响哪些仓库、应该验证哪组仓库版本，以及哪些结论有真实执行证据。
- **Must-solve bottleneck**：当前运行单位仍是单 `repo/ref`；跨仓 invariant 在自动 reporter 中会被记为 `not_run`，手工流程又默认在目标仓 tip 上执行，因此可能测试错误的仓库组合并产生假绿或假红。
- **Non-goals**：不建立永久企业知识图谱；不自动修改或合并协调 PR；不默认新增 hash、冻结 baseline、通用 contract 或 project gate；不把依赖关系命中直接当作 bug；不在首轮追求所有语言和构建系统。
- **Constraints**：保留 Marshal 现有 checkout 校验、零测试检测和降级语义；关系扫描不能替代真实构建、测试或模拟；第一阶段应 run-local、只读、advisory；仓库身份使用 `owner/repo`；拿不到真实组合时必须报告 unknown。
- **Success condition**：相较单仓审查和“只增加跨仓上下文”，该方案在真实可复现的跨仓破坏上显著提高受影响仓库召回与故障检测，同时在兼容升级和带协调修复的 change set 上保持可接受的误报，并能展示执行过的准确 repo/ref 组合。

## Anchor Check

- **Original bottleneck**：跨仓 reviewer 可能检查错误 ref 或运行未消费 provider 变化的测试，却仍给出兼容结论。
- **Why the revised method still addresses it**：所有实验结构、命令和状态都围绕“何时有资格声明跨仓兼容已验证”。
- **Reviewer suggestions rejected as drift**：不为追求论文分数加入模型训练、自动图发现或通用多语言层；这些不解决 proof 缺失。

## Simplicity Check

- **Dominant contribution after revision**：proof-bound pass semantics。
- **Components removed or merged**：V0 完全删除 LLM；`TypedObligationCandidate` 仅保留为 V1 的实验性接口草案。
- **Reviewer suggestions rejected as unnecessary complexity**：不定义稳定 API/数据库 schema，不新增内容 hash，不建立冻结基线或项目 gate。
- **Why the remaining mechanism is smallest**：一个显式输入、一个确定性 Maven obligation、一个证据记录即可测试核心问题。

## Changes Made

### 1. 给出实验性机器可读结构

- **Reviewer said**：缺少可执行 schema 和完整例子。
- **Action**：增加三个 JSON 例子及字段约束；明确它们仅供 D0 harness 使用，不是冻结 contract。
- **Impact**：工程师可以据此实现实验 harness，同时产品接口仍可在测量后变化。

### 2. 固定 Maven observation sequence

- **Reviewer said**：缺少 exact argv、解析字段和判断边界。
- **Action**：固定 effective POM、dependency tree、consumer command 和 observation rules；BUMP 隐藏 oracle 与受测系统严格分离。
- **Impact**：`passed/not_assessed` 可以机械判定。

### 3. 固定四个实验条件与 D0 决策标准

- **Reviewer said**：context-only 和 directional-no-execution 仍可能成为 strawman，green controls 可得性不明。
- **Action**：四组使用同一 repo 集、模型、提示和预算，只改变 edge 与 composition capability；D0 设定 pack、consumer、时间和淘汰标准。
- **Impact**：先验证数据可行性，失败就停止扩大产品范围。

## Revised Proposal

# 研究与产品方案：Proof-Bound Cross-Repository Review

## Problem Anchor

- **Bottom-line problem**：Marshal 需要从“单个 PR 的问题检测”扩展为“同一大型项目内多个相互依赖仓库的联合审查”，能够回答一个变化会影响哪些仓库、应该验证哪组仓库版本，以及哪些结论有真实执行证据。
- **Must-solve bottleneck**：当前运行单位仍是单 `repo/ref`；跨仓 invariant 在自动 reporter 中会被记为 `not_run`，手工流程又默认在目标仓 tip 上执行，因此可能测试错误的仓库组合并产生假绿或假红。
- **Non-goals**：不建立永久企业知识图谱；不自动修改或合并协调 PR；不默认新增 hash、冻结 baseline、通用 contract 或 project gate；不把依赖关系命中直接当作 bug；不在首轮追求所有语言和构建系统。
- **Constraints**：保留 Marshal 现有 checkout 校验、零测试检测和降级语义；关系扫描不能替代真实构建、测试或模拟；第一阶段应 run-local、只读、advisory；仓库身份使用 `owner/repo`；拿不到真实组合时必须报告 unknown。
- **Success condition**：相较单仓审查和“只增加跨仓上下文”，该方案在真实可复现的跨仓破坏上显著提高受影响仓库召回与故障检测，同时在兼容升级和带协调修复的 change set 上保持可接受的误报，并能展示执行过的准确 repo/ref 组合。

## Research Question and Thesis

**Research question**：AI code review 在什么条件下有资格声称一个跨仓兼容性 obligation 已被验证？

**Thesis**：只有当结构化证据证明 consumer 的相关构建、测试或模拟实际消费了 intended provider snapshot/产物时，Marshal 才能标记 `passed`；缺少 ref、执行或消费证明时必须显式 `not_assessed` / `not_run`。

这不是普通 CI hygiene：CI 的退出码只能说明某条命令的结果，proof-bound semantics 还要求把该命令绑定到一条方向 impact path、一个准确 repo/ref composition 和一个可观察的消费事实。

## Source-Backed Current Gap

- 核心输入/任务是单 `repo/change_ref`：`src/marshal_core/contracts.py:6-20`。
- 自动 reporter 不执行异仓 invariant：`src/marshal_core/executor/reporter.py:121-130`。
- Cowboy `Contract` 没有方向和 ref 组合：`src/marshal_pack_cowboy/pack.py:165-178`。
- 手工异仓验证回退到目标仓 tip：`.agents/skills/marshal/references/gate-flow.md:34-40`。
- GitHub adapter 丢失 owner：`src/marshal_core/adapters/github.py:7-18`。

因此 wallet 变更触发 node invariant 时，当前自动路径是 `not_run`；手工路径在 node tip 自测成功也不能证明 node 消费了 wallet 候选产物。

## Contribution Boundary

- **Only dominant contribution**：proof-bound cross-repository review semantics。
- **Supporting product surface**：run-local change set 与 evidence report。
- **Evaluation artifact**：BUMP update packs + verified green controls。
- **Not claimed**：multi-repo context、companion PR awareness、dependency graph、speculative CI、自动关系发现、通用 wire/schema/deploy support。

## V0: Deterministic Maven Research Slice

V0 没有 LLM，只有：显式 repo/ref、显式或 POM 导出的单向 edge、确定性 Maven composition adapter 和 advisory report。这样先验证 evidence mechanism；如果固定 obligation 已经足够，就没有理由增加 LLM。

### Experimental ProjectChangeSet example

这是 D0 harness 的可变输入形状，不是产品 public contract：

```json
{
  "mode": "advisory",
  "repositories": [
    {
      "repo": "qos-ch/slf4j",
      "root": "/workspace/provider",
      "revision": {"kind": "git", "value": "v_2.0.0"},
      "base_revision": "v_1.7.36",
      "changed": true
    },
    {
      "repo": "s4u/sign-maven-plugin",
      "root": "/workspace/consumer",
      "revision": {"kind": "git", "value": "pre-update-parent"},
      "changed": false
    }
  ],
  "edges": [
    {
      "consumer": "s4u/sign-maven-plugin",
      "provider": "qos-ch/slf4j",
      "kind": "maven",
      "selector": "org.slf4j:slf4j-api",
      "old_version": "1.7.36",
      "candidate_version": "2.0.0",
      "evidence": {"source": "pom", "path": "pom.xml"}
    }
  ]
}
```

Required rules:

- `repo` is canonical `owner/name`; a bare name is not accepted as identity.
- clean revisions resolve to Git commits/tags; dirty worktrees are labeled non-replayable.
- an edge is always `consumer -> provider`; an undirected Cowboy Contract cannot become an edge without more evidence.
- a missing candidate ref/version is `unknown`, never silently replaced by default branch/tip.

### Experimental TypedObligationCandidate example

V0 creates this deterministically; V1 may let an LLM propose the same fields:

```json
{
  "consumer": "s4u/sign-maven-plugin",
  "provider": "qos-ch/slf4j",
  "boundary_kind": "maven_dependency_update",
  "adapter": "maven_released_update",
  "selector": "org.slf4j:slf4j-api",
  "expected_observation": "consumer resolves 2.0.0 and executes its validated build command",
  "consumer_command_ref": "prepared-case:build-command",
  "rationale": "consumer POM directly declares the changed provider artifact"
}
```

An LLM, if later enabled, cannot populate repo refs, execution results, test counts or final assessment. Invalid repo/adapter/command references are rejected before execution.

### Experimental EvidenceRecord example

```json
{
  "composition": {
    "qos-ch/slf4j": "v_2.0.0",
    "s4u/sign-maven-plugin": "pre-update-parent"
  },
  "edge": {
    "consumer": "s4u/sign-maven-plugin",
    "provider": "qos-ch/slf4j",
    "selector": "org.slf4j:slf4j-api"
  },
  "resolution": {
    "requested_version": "2.0.0",
    "effective_version": "2.0.0",
    "dependency_tree_match": "org.slf4j:slf4j-api:jar:2.0.0",
    "isolated_local_repository": "/run/m2"
  },
  "execution": {
    "cwd": "/run/consumer",
    "argv_ref": "prepared-case:build-command",
    "exit_code": 1,
    "compile_observed": true,
    "tests_observed": 12
  },
  "consumption": {
    "status": "proved",
    "evidence": ["effective-pom.xml", "dependency-tree.txt", "build.log"]
  },
  "impact": "affected",
  "assessment": "failed",
  "attribution": "candidate_failed_after_pre_state_passed",
  "coverage_gaps": []
}
```

Evidence files are ordinary run outputs. V0 does not add a content hash, persistent database row or frozen contract.

## Exact Maven Adapter Sequence

The harness provides a case-local `RUN_ROOT`, an empty `RUN_M2`, a disposable consumer checkout, GAV coordinates and a validated repository build command. The reviewed system never sees hidden BUMP labels/logs.

1. Materialize only the known old-to-new selector in the disposable checkout using the case's one-line POM change or a structured Maven Versions operation. Reject the case if the diff changes anything outside the target selector.
2. Resolve the effective model:

   ```text
   mvn -B -ntp -Dmaven.repo.local=<RUN_M2> help:effective-pom -Doutput=<RUN_ROOT>/effective-pom.xml
   ```

3. Resolve the selected dependency:

   ```text
   mvn -B -ntp -Dmaven.repo.local=<RUN_M2> dependency:tree -Dverbose -Dincludes=<GROUP>:<ARTIFACT> -DoutputType=text -DoutputFile=<RUN_ROOT>/dependency-tree.txt
   ```

4. Parse exact fields: requested GAV, effective version, dependency-tree selected version, omitted/conflict markers, and whether resolution completed from the isolated repository. If the candidate version is absent or overridden, `consumption.status=not_proved` and assessment is `not_assessed`.
5. Execute the prepared repository command with the same `-Dmaven.repo.local=<RUN_M2>` injected. Store cwd, argv, exit code and log. A compilation obligation needs an observed compiler phase; a test obligation needs a non-zero test count.
6. For positive attribution, execute the same command on the pre-state under an equivalent isolated repository. Only pre-pass/candidate-fail supports `candidate_failed_after_pre_state_passed`.

For an unreleased provider using an unchanged GAV/SNAPSHOT, a later adapter must build the explicit provider checkout into a fresh empty Maven repository and verify the consumer resolves inside it. This concrete stale-JAR scenario is why Git SHA, version string and ordinary tests alone can be insufficient. V0 does not solve it with a new hash; it uses isolation, in-run production and resolved path. If those facts are unavailable, it does not claim pass.

## Status Semantics

- **Impact**：`affected | not_affected | unknown`。
- **Assessment**：`passed | failed | not_run | not_assessed`。
- `passed` requires `consumption.status=proved` plus relevant work observed and exit 0.
- `failed` requires proved consumption and a relevant command failure; causality is reported separately.
- `not_run` means a valid plan existed but infrastructure/checkout/command failed before a relevant observation.
- `not_assessed` means no adapter, unresolved composition or missing consumption proof.
- lack of an edge is not `not_affected`.
- project aggregate is only `incompatibility_found | verified_for_planned_scope | incomplete`.

This remains advisory and never maps to the existing `GateDecision pass/block`.

## Four Controlled Conditions

All conditions use the same model, prompt, consumer set, source snapshots, total token/tool/wall-time budget and fresh session. Consumer ordering is randomized and the condition order is Latin-square rotated.

| Condition | Visible repositories | Direction edge | Repo-local commands | Candidate composition | Purpose |
|---|---|---|---|---|---|
| C0 single-repo | provider only | no | provider only | no | current single-PR ceiling |
| C1 flat-context | provider + identical consumer set | no | yes, but only current consumer state | no | value of more code/context |
| C2 directional-no-exec | same as C1 | yes, sourced GAV edge | same as C1 | no | value of direction/routing without execution |
| C3 proof-bound | same as C1/C2 | same as C2 | yes | yes, via Maven adapter | incremental value of intended composition and proof |

C1 may search and run current consumer tests, so it is not artificially weak. It cannot call those current-state results cross-repo verification because no candidate provider is materialized. C2 receives exact edges but no candidate-composition capability. C3 differs from C2 only by that capability and proof-bound result semantics.

Primary task: predict per consumer `no impact / compilation / test`, rank affected consumers, cite files/symbols and report evidence. Unsupported “compatible/pass” statements count as false-compatible on known breaking cases.

## D0 Data Feasibility Decision

D0 is a research investment decision, not a product gate or frozen baseline.

### Minimum input

- 3 update packs from 3 provider repositories;
- at least one compilation-failure pack and one test-failure pack;
- each pack has at least 2 BUMP failing consumers;
- target 2 verified green consumers for the identical `(GAV, old, new)` tuple per pack.

### Acceptance evidence

- every positive has pre-pass/candidate-fail on a fresh replay;
- every green has pre and candidate states pass `2/2` and resolves the candidate version;
- no accepted build relies on live mutable CI/PR state;
- positive/green label is decided by the hidden oracle, never by the reviewed system.

### Resource bounds

- maximum 30 minutes per image/command attempt and 60 minutes per case pair;
- maximum 30 candidate green PRs screened per pack;
- maximum 2 engineer-days for the 3-pack D0;
- infrastructure/network/flaky results get one controlled retry, then are excluded with reason.

### Decision outcomes

- **Proceed**：all 3 packs replay, at least 6 positives total, and at least 2 packs obtain 2 green controls each.
- **Narrow case study**：positives replay but fewer than 2 packs obtain green controls; report detection examples, do not claim balanced benchmark performance.
- **Stop this dataset route**：positive replay attrition exceeds 20%, no pack obtains 2 green controls, or median pair time exceeds the resource bound.

These outcomes do not block merges or releases; they only decide whether the research evaluation is credible enough to continue.

## Main Evaluation Boundary

Candidate pool at BUMP commit `324d5513aa5c`:

- 571 reproducible cases / 153 consumer repos;
- 39 repeated GAV+old+new groups / 104 failing cases;
- core compilation/test non-plugin subset: 30 groups / 82 cases;
- real provider compare URL subset: 28 groups / 78 cases from 11 providers, with 35 compilation and 43 test failures.

After green-control validation, target 18-24 packs, 2-4 positive and 2-4 green consumers per pack. Split by connected components of provider repo and consumer repo so the same provider family, consumer, fork or release series never crosses calibration/development/test.

Primary claims remain narrow:

1. C3 reduces false-compatible/unsupported-pass conclusions on reproducible Maven dependency updates relative to C0-C2.
2. Directional routing and composition improve affected-consumer detection and evidence quality under a fixed budget.

Consumer ranking is secondary. BUMP does not validate Cargo, wire/schema, runtime/deploy or coordinated merge scheduling. A Cowboy wallet/node artifact handoff is a separate post-GO product case study, not part of the BUMP claim.

## Competitive Boundary

- CodeRabbit/Qodo: direct context/impact competitors with linked repos and companion refs.
- Greptile/Bito: context/graph competitors.
- Zuul: strong adjacent baseline for explicit cross-project DAG and speculative execution.
- Sourcegraph Batch Changes/Moderne: adjacent multi-repo change and modernization systems.

Marshal should not claim any one of context, graph, companion refs or execution as novel. Its proposed distinction is the review-time rule that a compatibility `passed` statement must cite the actual composition and consumption evidence, while unresolved coverage remains visible. Public documentation can support positioning, not proof of competitor absence.

## Deferred Work

- automatic relation discovery;
- transitive impact traversal;
- LLM obligation proposal/explanation;
- Cargo and Cowboy wire artifact adapters;
- coordinated PR auto-discovery;
- persistent storage, caching, content hashes, frozen baselines or project gates.

Only measured D0/main-evaluation failures may justify adding one of these later.

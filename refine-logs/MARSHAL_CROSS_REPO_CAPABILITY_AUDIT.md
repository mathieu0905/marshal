# Marshal 现有跨仓能力审计

**核验日期**：2026-08-22  
**核验对象**：分支 `feat/cross-repo-project-review`，当前代码版本 `71d91c1`  
**范围**：只读审计现有代码、配置、技能说明和测试；未修改 Marshal 产品代码。

## 一、结论

“Marshal 已经能做跨仓，只是需要配置”只成立一部分。

现有 Marshal 已经具备三项跨仓骨架：

1. CowboyPack 可以根据一个仓库的改动路径命中预先登记的跨仓契约；
2. 计划结果可以指出检查位于另一个仓库；
3. 手工技能流程可以进入另一个本地仓库执行检查。

但它还不能把“一组带独立候选版本的相关仓库”作为一次结构化审查任务。自动执行器不会执行异仓检查；手工流程对异仓检查使用目标仓当前分支顶端；现有结果也不能证明消费仓实际使用了上游候选版本。

因此，当前能力更准确的定义是：

> 已有“跨仓契约命中和检查位置路由”，尚无“多仓候选版本组合与联合验证”。

这不是简单补一份现有配置就能完全解决的问题。不过，在提出任何产品设计前，可以先利用现有骨架完成原样评测，测清实际缺口。

## 二、能力矩阵

| 能力 | 现有即可使用 | 需要配置 | 现有不能表达 | 结论 |
|---|---:|---:|---:|---|
| 已登记 Cowboy 跨仓契约命中 | 是 |  |  | 根据被审仓库和路径命中固定契约 |
| 指出检查位于哪个仓库 | 是 |  |  | `location_repo` 可路由检查位置 |
| 手工读取多个本地仓库 | 是 | 是 |  | 技能流程可按多个 Git 根分别审查 |
| 自动执行异仓检查 |  |  | 是 | 自动报告器将其记为未运行 |
| 每个仓库指定独立候选版本 |  |  | 是 | 事件和任务都只有一个仓库、一个版本 |
| 表达有方向的依赖关系 |  |  | 是 | 契约只有仓库列表，没有消费方、提供方和版本 |
| 识别任意项目的跨仓依赖 |  |  | 是 | 当前只有 CowboyPack 的固定规则 |
| 验证消费仓使用了上游候选版本 |  |  | 是 | 没有组合构建或消费证据 |
| 明确报告异仓检查未运行 | 是 |  |  | 自动流程降级并升级为人工判断 |
| 区分影响未知与确认无影响 |  |  | 是 | 现有结果没有独立影响状态 |
| 使用完整 `owner/repo` 仓库身份 |  |  | 是 | GitHub 事件只保留裸仓库名 |

## 三、代码证据

### 1. 审查输入只有一个仓库和一个版本

`src/marshal_core/contracts.py:6-21` 中：

- `NormalizedEvent` 只有一个 `repo` 和一个 `change_ref`；
- `DispatchJob` 只有一个 `target_repo` 和一个 `change_ref`；
- 没有相关仓库列表、每仓版本或仓库间关系字段。

`src/marshal_core/modules/invariant_gate.py:6-23` 又把事件直接转换成单仓范围和单目标任务。因此主计划接口无法通过配置提交一组仓库候选版本。

### 2. CowboyPack 能命中固定跨仓契约

`src/marshal_pack_cowboy/pack.py:166-218` 定义了 `tx-encoding`、`runner-types` 等契约。每条契约包含：

- 参与仓库列表；
- 各仓库的触发路径；
- 需要验证的不变量。

`src/marshal_pack_cowboy/pack.py:936-944` 按“当前仓库 + 改动路径”命中契约；`src/marshal_pack_cowboy/pack.py:723-767` 再把契约对应的不变量加入计划。

这说明 Marshal 确实已有跨仓知识，但该知识是 CowboyPack 中预先写入的固定映射，不是从任意项目配置或依赖清单自动获得。

### 3. `location_repo` 是检查位置，不是依赖方向

`src/marshal_core/domain_pack.py:7-18` 的 `InvariantDef` 可以指定 `location_repo`。`src/marshal_core/modules/orchestrator.py:38-47` 会把该字段交给执行器。

例如 wallet 的编码路径变化会返回位于 node 的检查。这能回答“去哪里检查”，但不能回答：

- node 是消费方还是提供方；
- wallet 和 node 分别应使用哪个候选版本；
- node 的检查是否真的使用了 wallet 的候选产物。

`Contract.repos` 只是无方向仓库列表，也没有版本或产物信息。

### 4. 自动执行器明确不执行异仓检查

`src/marshal_core/executor/reporter.py:107-130` 的执行入口只接收当前 `repo` 和 `change_ref`。当 `location_repo != repo` 时，它不会切换仓库，而是把检查加入 `not_run`：

```text
lives in repo '<目标仓>'; this reporter runs in '<当前仓>' and cannot execute it
```

`src/marshal_core/modules/invariant_gate.py:59-70` 会把有具体失败的结果判为失败；没有具体失败但执行器降级或含未运行项时，结论为 `escalate`，不会假报通过。

这部分行为是安全的，但也直接证明自动跨仓执行目前不存在。

### 5. 手工技能可以跨仓执行，但使用目标仓顶端

`.agents/skills/marshal/references/gate-flow.md:9` 允许把本地多个 Git 顶层目录分别分组审查。

`.agents/skills/marshal/references/gate-flow.md:33-44` 规定：

- 被审仓使用 PR 版本或当前工作树；
- 异仓检查使用目标仓的 `origin/devnet` 或 `origin/main` 顶端；
- 然后在对应仓库工作树中运行命令。

因此手工流程能执行另一个仓库里的检查，但它验证的是“被审候选版本 + 目标仓当前顶端”，不是显式给定的多仓候选组合。若两个仓库有协调变更，这个默认组合可能与实际拟合并组合不同。

### 6. 深度审查任务仍然是单仓任务

`src/marshal_core/worker.py:56-100` 只为一个 `repo/change_ref` 创建工作树。`src/marshal_core/worker.py:146-181` 的提示也只描述当前仓库或单个 PR。

它可以在审查过程中自行读取其他本地仓库，但任务输入没有为其他仓库指定候选版本，也没有结构化记录实际使用了哪些仓库版本。

### 7. `repo_roots` 不是跨仓审查配置

仓库中确实存在可重复传入的 `--repo-root repo=path`。但从 `src/marshal_core/cli.py:637-701` 和 `src/marshal_core/plangate/service.py:15-45` 可见，它用于：

- 概念页锚点验证；
- 计划成本分析；
- 不变量目录对账。

`src/marshal_core/concept/anchor.py:44-59` 只检查符号是否在对应仓库文件中定义。它不参与 PR 事件、跨仓依赖组合或异仓执行，不能作为项目级联合审查的现有配置入口。

### 8. GitHub 事件丢失组织名

`src/marshal_core/adapters/api.py:45-64` 在请求 GitHub 文件列表时使用 `repository.full_name`，但 `src/marshal_core/adapters/github.py:7-18` 构造事件时只保存 `repository.name`。

这意味着事件进入核心后只剩裸仓库名。同名仓库或 fork 无法仅靠该字段区分，也不适合作为通用多仓项目的稳定身份。

### 9. 未知项目没有可执行跨仓规则

`src/marshal_pack_cowboy/pack.py:723-767` 只为 Cowboy 已知仓库和路径选择不变量。未知仓库仍会获得通用审查视角，但不会获得不变量。

这意味着 BeyondSWE、DepBench 和 BUMP 的仓库不能直接通过“改仓库名配置”获得对应的依赖关系和执行计划。它们仍可用于原样测量通用审查部分，但机械跨仓验证需要额外的数据映射；本阶段不实现该映射。

## 四、运行核验

### 1. 已登记跨仓契约

执行：

```bash
.venv/bin/python -m marshal_core.cli classify \
  --repo wallet --paths src/lib/cbor.js
```

结果：

- 风险级别为高；
- 命中 `tx-encoding`；
- 审查视角包含跨仓检查。

执行：

```bash
.venv/bin/python -m marshal_core.cli invariants \
  --repo wallet --paths src/lib/cbor.js
```

结果返回两条位于 node 的检查：

- `contract.tx_encoding_roundtrip`；
- `contract.sys_opcode_uniqueness`。

这证明契约命中和异仓检查位置路由可用。

### 2. 未知项目

执行：

```bash
.venv/bin/python -m marshal_core.cli classify \
  --repo external-project --paths src/api.py
.venv/bin/python -m marshal_core.cli invariants \
  --repo external-project --paths src/api.py
```

结果：

- 获得通用的中等风险分类和三个审查视角；
- 不变量列表为空。

这证明核心可以接受任意仓库名，但现有领域包不能为任意项目提供跨仓依赖和动态检查。

### 3. 相关测试

执行：

```bash
.venv/bin/python -m pytest \
  tests/test_cowboy_contracts.py \
  tests/test_planner.py \
  tests/test_reporter.py::test_cross_repo_invariant_is_not_run_and_degrades \
  tests/test_cli.py::test_invariants_cross_repo_contract -q
```

结果为 `15 passed`。这些测试覆盖：

- wallet 和 node 路径命中同一跨仓契约；
- 计划返回异仓检查位置；
- 自动报告器不执行异仓检查并如实降级；
- 未知仓库的计划为空。

## 五、对数据评测的直接影响

### BeyondSWE

可以测试通用审查是否会寻找仓外信息，但不能直接测试 Marshal 的 CowboyPack 跨仓契约，因为 BeyondSWE 仓库没有对应规则。其任务也只有一个目标仓库版本。

### 公开版 DepBench

可以测试单消费仓中的依赖升级问题识别。当前 Marshal 不会从依赖清单自动生成上游关系，也不能直接把上游候选仓加入同一次任务。

### BUMP

可以提供最强的升级前成功、升级后失败证据。把同一依赖升级的多个消费仓组织到一起后，可以测量 Marshal 是否能分别识别影响；但当前结构化执行仍会把它们视为多个独立单仓任务。

## 六、下一步判断

下一阶段应先核验和重放现成评测集，而不是立刻修改 Marshal。

原样评测需要分别记录：

1. 通用审查能否识别问题；
2. 固定 Cowboy 跨仓契约能否正确路由；
3. 自动流程在哪一步因异仓执行或候选组合缺失而降级。

只有实际样本反复表明“能找到相关仓库，但测试了错误版本组合”时，才有充分证据把后续设计收敛到多仓候选版本组合与消费证明。

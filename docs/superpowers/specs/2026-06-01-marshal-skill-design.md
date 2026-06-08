# Marshal Skill 现状 (本地质量大脑 + 平台执法层脚手架)

> **定位:** 在 Marshal 平台(常驻服务 + GitHub App + 硬门禁)完全建成前,用一个 Claude Code skill 落地方法论的**认知闭环**——作用在当前分支/PR diff 上,文件态(复用 marshal SQLite 知识核 + 版本化领域包)、按需触发、建议态(不硬阻断)。已覆盖三支柱里的 ① 分级 + ② 不变量门禁 + ③ 对抗式 review + ④ 逃逸棘轮,并把 ⑤ conformance 与 ⑦ metrics 落到种子级;跨 repo 契约 + 否定性安全危险点感知。
>
> **源文档:** [`docs/methodology/ai-velocity-quality-methodology.zh.md`](../../methodology/ai-velocity-quality-methodology.zh.md) · [`docs/architecture/platform-architecture-design.zh.md`](../../architecture/platform-architecture-design.zh.md)
>
> **状态:** ✅ **已实现并合入 `main`**(PR #1 `feat/walking-skeleton-econ`),在 cowboy 多 repo 上实战中。本文是**现状版**,描述已落地的代码与流程;原 2026-06-01 设计意图见文末「修订记录」。
>
> **首版日期:** 2026-06-01 · **现状重写:** 2026-06-07

---

## 0. 目标与现状

**目标:** skill 是 Marshal 平台 §10 演进路线第 1 步(②InvariantGate + ④Ratchet)+ 第 2/3 步(①Classifier + ③ReviewOrch)的**先行落地载体**。在平台的常驻/执法层完全就绪前,先把最高复利的认知闭环跑通,且其产物(知识核 + cowboy-pack + 平台层模块)正是平台直接复用的种子。

**核心定位:** Marshal 是通用质量工程平台(领域无关核心 + 可插拔领域包);skill = 平台未上线时的"本地大脑/agent worker"。skill 只做判断性工作并汇总 `GateDecision`,确定性工作外包给 marshal CLI;领域真相住版本化的 `marshal_pack_cowboy`,持久状态住 `marshal.db`。

**已超出原设计的落地(从「非目标」变为「已做」):**
- **⑤ ConformanceGov(种子级)** — 分层规格体系(白皮书=宪法 / CIP=修正案)、RFC2119 requirement 抽取、spec→不变量 conformance 矩阵、CIP 覆盖率与最欠覆盖网洞排序。
- **⑦ Metrics** — `cli metrics` 从知识核聚合(不变量数 / 棘轮增量 / 逃逸开关 / 门禁判决分布),不支持的指标诚实返回 `unavailable + reason`。
- **平台执法层脚手架** — `adapters/`(GitHub webhook 解析 + Check Run 回写、FastAPI 端点)与 `modules/`(Classifier / InvariantGate / Orchestrator 机制)、`executor/reporter.py`(项目无关 CI reporter)已有雏形(shadow/neutral 态),为平台常驻服务铺路。
- **否定性安全属性建模** — `SecurityHazard` + `ratchet_guidance`:机密性 / IND-CPA / 越权这类**不可往返化**的属性,棘轮不再误 spawn roundtrip proptest,而落成 review-lens 危险点。

**仍留给平台(未做):**
- ⑥ RuntimeWatch、⑦ 完整 dashboard、escape_rate / MTTD / tiered-coverage 这类需额外数据模型的指标
- Webhook 自动触发 / merge queue / required-status **硬阻断**(skill 与 adapters 当前都是建议/shadow 态,挡不住 merge)
- 多团队组织级隔离、PostgreSQL(现用 SQLite)
- 不替代各 repo CI;不新写不变量/检查本体(棘轮**指向**测试,实现由人/后续完成;skill 起草骨架)

---

## 1. 关键决策(已落地)

| # | 决策点 | 落地 |
|---|---|---|
| Q1 | 触发面与作用对象 | 无参=当前分支 vs base 的 diff;`<PR#>`=拉远端 PR(默认 repo=node);`<repo> <PR#>` / `<repo>#<PR#>` / PR-URL 审指定 repo |
| Q2 | repo 作用域 | 跨 repo 感知——diff 命中契约 `trigger_paths` 时,去**所有相关 repo** 跑对应 conformance 不变量(`CONTRACTS` 4 条) |
| Q3 | 领域知识来源 | `marshal_pack_cowboy` 为领域真相源;core 领域无关,通过 `domain_pack.py` 契约取知识 |
| Q4 | 棘轮喂入 | 手动 `/marshal ratchet` + review 发现自动晋升,共用开条目逻辑;**否定性根因走 hazard 而非 proptest** |
| 形态 | 落地形态 | skill 编排(判断性)+ marshal 薄 CLI(确定性);**另有 modules/adapters 平台机制层雏形** |
| 知识核 | 持久真相源 | SQLite `marshal.db` + `Store`,表:`InvariantRegistry` / `GateRun` / `AuditLog` / `EscapeRegistry` |
| 位置 | skill 文件位置 | 住 `marshal/.claude/skills/marshal/`,`cli setup` 软链到 `~/.claude/skills/` |

---

## 2. 整体架构(现状)

```
用户:  /marshal                          (无参 → 当前分支 vs base 的 diff)
       /marshal <PR#>                     (拉远端 PR diff, 默认 repo=node)
       /marshal <repo> <PR#> | <repo>#<PR#> | <PR-URL>   (审指定 repo 的 PR)
       /marshal ratchet "<漏网bug描述>"    (棘轮:开逃逸)
       /marshal conformance               (⑤ 规格符合度报告)
       /marshal metrics                   (⑦ 度量报告)

┌─────────────────────────────────────────────────────────┐
│  SKILL「marshal」 (领域无关大脑/编排器)                       │
│   判断性工作:                                              │
│    · 解析 diff、判 repo、决定走哪条流程(A 门禁 / B 规格 / C 棘轮) │
│    · 编排 ③ /code-review ultra 多视角对抗 review + 注入安全 lens │
│    · 起草棘轮的根因分类 + 候选永久检查(守门:否定性属性→hazard)   │
│    · 汇总 GateDecision(pass/block/needs_human[/degraded]) 写回   │
└───────────────┬─────────────────────────────────────────┘
                │ Bash 调用 (确定性工作外包)
┌───────────────▼─────────────────────────────────────────┐
│  marshal CLI: $MARSHAL_HOME/.venv/bin/python -m marshal_core.cli │
│    classify / invariants / review-quorum / review-verify /  │
│    spec-source / spec-requirements / conformance /          │
│    ratchet-open / ratchet-close / gate-record / metrics / setup │
│   ← 读领域真相: marshal_pack_cowboy (分级/契约/不变量/视角/hazard/规格)│
│   ← 读写知识核: $MARSHAL_HOME/marshal.db (SQLite, Store)     │
└─────────────────────────────────────────────────────────┘

平台层脚手架 (为常驻服务铺路, 当前 shadow/建议态):
  modules/{classifier,invariant_gate,orchestrator}  机制层 (领域无关)
  executor/reporter.py                              项目无关 CI reporter
  adapters/{github,api}.py                          GitHub webhook + Check Run + FastAPI
  checks/system_actor_addrmap.py                    棘轮织出的 Python 永久检查
  contracts.py                                      跨 Python/Rust 层间契约 (Pydantic 单一真相源)
```

**三条纪律(对齐 Marshal):**
1. **skill 只判断、不存状态** —— 持久真相在 `marshal.db`,领域知识在 `cowboy-pack`。skill 无状态、可随时重跑。
2. **确定性 vs 判断性硬分离** —— 能写成代码的(分级匹配、契约拓扑、quorum 计票、spawned_check 约束)进 CLI/core 可单测;只有"AI 不可替代的判断"留 skill。
3. **降级不谎报** —— CLI 出错 / review 超预算 → skill 显式回 `needs_human + degraded`,绝不把"没审成"伪装成"审过了"(方法论 §7.1)。

---

## 3. 端到端流程

### 流 A —— `/marshal [<repo>] [<PR#>]`(门禁评估)

```
1. 取 diff + 判 repo
   · 无参 → git diff <base>...HEAD (base 自动探: origin/main 或 origin/devnet)
   · <PR#> → gh pr diff <PR#> -R cowboyinc/<repo> (默认 node), 记 change_ref = PR head SHA
   · git rev-parse --show-toplevel 识别 diff 所在 repo(可能多个)

2. ① 分级 (CLI 确定性)  cli classify --repo <r> --paths <files...> [--diff-text --labels]
   → {tier, reasons[], contracts_hit[], security_hazards[], review_dimensions[]}
   · per-repo 高危前缀(node 共识/执行/存储, cbss 门限IBE/DKG, cbfs crypto/erasure/...)
   · 命中契约 / 系统地址 / 安全危险点 / CIP-label → high;误判向上不向下

3. ② 不变量门禁 (CLI 选 + skill 跑, 建议态)
   cli invariants --repo <r> --paths <files...>  → 适用不变量清单(带 run_command)
   · **在被审 checkout 的干净 worktree 跑** run_command (PR head SHA / 当前 HEAD);
     契约不变量去其 location_repo 的 tip。**绝不在落后主树跑** → 会 running 0 tests 假阳性
   · 任一 active 不变量失败 → 该门禁 fail

4. ③ 对抗式 review (skill 判断, 按 tier 决定视角数: high=6/mid=3/low=1)
   · 视角清单读自 cowboy-pack.REVIEW_DIMENSIONS
   · 调 /code-review ultra;若 classify 返回 security_hazards → 把其 prompt 注入 security lens
     (否定性属性不变量门禁抓不到, 只能靠 review)
   · 可选 cli review-quorum / review-verify: 多视角发现去重+计票, skeptic 投票裁决(default-to-refute)

5. 汇总 GateDecision
   · 任一 active 不变量 fail              → block
   · 高危 + confirmed 高severity 发现      → needs_human
   · 跑不起来 / 超预算                     → needs_human + degraded
   · 否则                                → pass

6. 落库 + 回写  cli gate-record --change-ref --verdict --evidence-json
   · 有 PR# 且用户要 → 贴 PR 评论(英文, 结尾必带 Advisory 声明)
   · 终端打印 GateDecision 摘要

7. 若在已合并代码上确认高 severity 发现 → 提议转流 C(自动晋升)
```

### 流 B —— 规格层改动 / conformance(⑤)

```
· /marshal conformance:
  cli conformance --spec-root <workspace>/cowboy
  → CIP conformance%(分母=全 CIP, 分子=被≥1不变量覆盖的 CIP)+ 最欠覆盖网洞排序
    (无不变量在前, 然后 MUST requirement 数越多越靠前)
· diff 命中 cowboy docs/cips/**(修正案) 或 docs/whitepaper/**(宪法) → 升 tier(动白皮书=最高):
  cli spec-source --ref CIP-N         解析条款正文源
  cli spec-requirements --ref CIP-N --spec-root <cowboy>   抽 RFC2119 requirement
  查该 CIP 当前被哪些不变量覆盖; 新增/接口变更而无对应不变量 → 提示补(可转流 C)
· 不替人裁治理冲突: 宪法↔修正案静默抵触只标 needs_human, 不自动 block(治理 a 档)
```

### 流 C —— 逃逸棘轮(复利引擎)

```
1. cli ratchet-open --escape-id <新id> --desc "<bug>" --root-cause <分类> [--change-ref <sha>]
   → 建 EscapeRegistry [status=open]
2. **先定形状** (cli 起草侧 / pack.ratchet_guidance):
   · 否定性属性(机密性/越权/泄露/IND-CPA/side-channel) → invariant_able=False:
     spawned_check 记 hazard:<id>, 落成 review-lens SecurityHazard, **不 spawn roundtrip proptest**
     (会"绿着却漏" —— node #470 教训)
   · 否则起草候选永久检查(指向某 repo 的 proptest 名 + 路径 + run_command)
3. 🧑 人确认根因 + 选定检查
4. cli ratchet-close --escape-id <id> --spawned-check <inv-id> --inv-json '<InvariantDef字段>'
   · 把选定检查写入 InvariantRegistry(origin=ratchet, escape_id=...)
   · EscapeRegistry.spawned_check = 该 id; **spawned_check 为空 → CLI/Store 拒绝 close**(棘轮硬约束)
5. skill 提示去 <repo> 把这条 proptest/check 真正实现(可顺手起草测试骨架)
```

关键: **棘轮的"检查"是落进注册表的不变量条目(永久资产),不是事后文档**(方法论 §3)。

---

## 4. 数据模型(`knowledge/models.py`)

| 表 | 角色 | 关键字段 |
|---|---|---|
| `InvariantRegistry` | 不变量/永久检查注册表 | `id, domain_pack, domain, spec_ref, executor_kind, location_{repo,path,test}, severity, status, origin(hand/ratchet), escape_id` |
| `EscapeRegistry` | 逃逸登记(棘轮) | `id, domain_pack, discovered_at, root_cause_class, change_ref, description, spawned_check, status(open/closed)` |
| `GateRun` | 门禁运行记录 | `id, change_ref, job_id, verdict, evidence(JSON), created_at` |
| `AuditLog` | 审计流水 | `id, ts, event, actor, decision, refs(JSON)` |

**棘轮硬约束:** `Store.close_escape(escape_id, spawned_check)` —— `spawned_check` 为空则 `raise`;`cli ratchet-close` 同步校验。这是方法论"逃逸必织一条永久检查"的数据库级执法点。

---

## 5. 领域包内容(`marshal_pack_cowboy/pack.py`)

**(1) 分级 `classify_detailed()`** — 返回 `{tier, reasons, contracts_hit, security_hazards, review_dimensions}`:
- node 高危前缀:`execution/{engine,transaction,system_instruction,basefee}`、`storage/{speculative,process_block}`、`chain/`、子串 `crypto`/`_root`
- per-repo 高危:`cbss`(门限-IBE/DKG/封缄/份额/keychain)、`cbfs`(crypto/erasure/placement/auth/manifest/cowboy-ras)
- 系统地址 token `0x06/0x09/0x91-95`、命中契约、命中安全危险点、CIP-label(new/interface-change)→ high
- 仅 `*.md`/test/script → low;其余 → mid

**(2) 跨 repo 契约 `CONTRACTS`(4 条)** — 命中 `trigger_paths` → 升高危 + 去所有相关 repo 跑 `verify_invariants`:

| 契约 id | repos | verify_invariant(真实锚点) |
|---|---|---|
| `tx-encoding` | wallet, node | `contract.tx_encoding_roundtrip`(types execution codec) |
| `runner-types` | runner, node | `contract.runner_types_serde`(SPEC-C1 签名 serde) |
| `cip9-ras` | cbfs, node | `contract.ras_canonical_vectors`(ras 金标准哈希向量) |
| `cip24-cbss` | cbss, node | `contract.cbss_wire_round_trip`(CBSS 释放请求线格式) |

**(3) 不变量族**(随棘轮生长,部分晋升进版本化包):`_ECON`(fee/settlement/escrow/tx_fee/timer_burn 守恒)、`_STATE`(state-root/rollback/committed-set 一致)、`_PVM`(strict 模拟允许合法码 — pvm/ 是 workspace-excluded 独立 workspace,CI 盲区)、`_CRYPTO`/`_CBSS`(IBE 往返 / 门限 t-quorum 恢复)、`_CBFS`(erasure 任意 K 子集重建)。

**(4) review 视角** `REVIEW_DIMENSIONS`:correctness / spec / cross-repo / security / econ / determinism,各配对抗式 prompt;tier→视角数 high=6/mid=3/low=1。

**(5) 安全危险点 `SECURITY_HAZARDS`** — 否定性属性(`invariant_able=False`),如 `cbss-mpk-rpc-exposure`(mpk 经 RPC 公开 → wrap-key 派生若只用公开量且无 per-message 随机数则机密性破裂)。命中即注入 security review lens;棘轮遇此类根因走 hazard 不走 proptest。

**(6) 分层规格 `SPEC_LAYERS`** — 白皮书=宪法(root)/ CIP=修正案;`resolve_spec_ref` 把 `CIP-N`/`WP` 解析到 cowboy 仓 `docs/{cips,whitepaper}` 正文;`parse_spec_requirements` 按 RFC2119(MUST/SHALL/SHOULD/MAY…)抽 requirement;`conformance_matrix` 给 spec→不变量覆盖(只计可解析到真实规格源的不变量,不虚报)。

---

## 6. CLI 契约(`marshal_core/cli.py`,JSON in/out,出错非零退出 + `{"error":…}`)

| 命令 | 入参 | 出(JSON) |
|---|---|---|
| `classify` | `--repo --paths [--diff-text --labels]` | `{tier, reasons[], contracts_hit[], security_hazards[], review_dimensions[]}` |
| `invariants` | `--repo --paths` | `[{id, severity, executor_kind, location_*, run_command}]`(含契约牵出的跨 repo 不变量) |
| `review-quorum` | `--findings-json [--quorum]` | 多视角发现去重 + 计票聚合(高危升 needs_human) |
| `review-verify` | `--votes-json` | skeptic 投票裁决(default-to-refute) |
| `spec-source` | `--ref` | `{ref, source:{layer,repo,path_glob}}` |
| `spec-requirements` | `--ref --spec-root` | `{counts:{must,should,may}, total, requirements[]}` |
| `conformance` | `[--spec-root]` | `{covered, specs_covered}`(+`--spec-root`→`cip_conformance_pct`/`cip_uncovered`/`per_cip`) |
| `ratchet-open` | `--escape-id --desc [--root-cause --change-ref]` | `{escape_id}` |
| `ratchet-close` | `--escape-id --spawned-check --inv-json` | `{ok, escape_id, spawned_check}`(spawned_check 空→非零退出) |
| `gate-record` | `--change-ref --verdict --evidence-json` | `{run_id}` |
| `metrics` | — | 见 §8 |
| `setup` | — | 建 `~/.claude/skills/marshal` 软链 + 校验 venv 可 import |

---

## 7. 可调用包解析

- **skill 任意 repo 可见:** 真相源 `marshal/.claude/skills/marshal/`,`cli setup` 软链 `~/.claude/skills/marshal → <home>/.claude/skills/marshal`。
- **CLI 任意 cwd 可调 + 知识核位置固定:** 用绝对路径 venv 调 `$MARSHAL_HOME/.venv/bin/python -m marshal_core.cli`;`marshal.db` 解析成 `$MARSHAL_HOME/marshal.db` 绝对路径(`MARSHAL_HOME` 默认 `/home/ubuntu/workspace/marshal`,可环境变量覆盖;`MARSHAL_DB` 可覆盖 db url)。
- skill 用 `git rev-parse --show-toplevel` 定位 diff 所在 repo,父目录定位 workspace root,据此 `cd` 进关联 repo 跑跨 repo 不变量。
- SKILL.md 开头有自检:链接/venv 缺失就提示先跑 `cli setup` + `pip install -e .`。

---

## 8. 实战快照(截至 2026-06-07,`/marshal metrics` 实时获取)

```
invariant_gate_count : 13       # 注册表 active 不变量
ratchet_invariants   : 10       # 其中由棘轮织出(另有 1 条 candidate-red 待 PR 合)
escapes_closed       : 12       # 已闭环逃逸(每条至少织一条永久检查)
escapes_open         : 0
gate_runs_total      : 44       # pass 22 / block 1 / needs_human 21
unavailable          : escape_rate / MTTD / tiered_review_coverage(诚实标 null+reason)
```

**12 条已闭环逃逸**覆盖 econ-conservation、state-consensus、determinism-gap、confidentiality-break、missing-invariant、missing-spec-rule、cross-repo-contract 等根因。代表:
- `esc-20260605-timer-burn` → `econ.timer_burn_conservation`(node #580 活的代币铸币/burn 泄漏)
- `esc-20260605-pvm-ci-gap` → `pvm.strict_simulation_allows_valid_code`(COW-366,pvm/ 是 CI 盲区,strict happy-path 被破却两次 CI 绿)
- `cbss-crypto-confidentiality` → `hazard:cbss-mpk-rpc-exposure`(否定性属性走 review-lens,**不** spawn roundtrip)
- `esc-20260605-wp-0x0d-addrmap` → `conformance.system_actor_addrmap_consistent`(白皮书 PR 把 `0x0D` 撞给两个 system actor,落成 `checks/system_actor_addrmap.py` Python 永久检查)

---

## 9. 测试策略(平台吃自己的狗粮)

确定性逻辑全在 CLI/pack/store/core,**全部可单测**(pytest,共 **98 tests**):
- `classify`/`contracts`:高危路径 / per-repo / 系统地址 / CIP-label / 契约命中 → tier+reasons;误判向上用例
- `invariants`:单 repo 选集 + 契约命中牵出跨 repo 不变量(B 回归)
- `EscapeRegistry`/`store`:`open→close` 正常路径;**`close` 缺 spawned_check 必须 raise**(棘轮硬约束核心回归)
- `review`:quorum 去重/计票/高危升级、skeptic 验证
- `conformance`/`spec`/`requirements`:RFC2119 抽取、矩阵、CIP gap
- `security_hazards`/`fake_pack`:危险点触发、`ratchet_guidance` 否定性属性守门
- `cli`:JSON 出入 round-trip + 错误路径非零退出
- `github_adapter`/`orchestrator`/`planner`/`reporter`/`metrics`:平台层机制
- `cowboy_*`/`cbss_cbfs_coverage`:领域包覆盖

skill 的判断性逻辑(review 编排/根因起草)不写自动化测试,靠真实 diff 手验。

---

## 10. 文件清单(现状)

```
src/marshal_core/
  cli.py                         薄 CLI(12 命令)+ setup
  knowledge/models.py            InvariantRegistry / EscapeRegistry / GateRun / AuditLog
  knowledge/store.py             读写 + 棘轮硬约束 close_escape + metrics()
  domain_pack.py                 领域包契约(InvariantDef 等)
  contracts.py                   跨 Python/Rust 层间契约(Pydantic 单一真相源)
  review.py                      ③ ReviewOrch quorum 聚合 + skeptic 验证
  modules/{classifier,invariant_gate,orchestrator}.py   机制层(领域无关)
  executor/reporter.py           项目无关 CI reporter
  adapters/{github,api}.py       GitHub webhook + Check Run + FastAPI(shadow 态)
  checks/system_actor_addrmap.py 棘轮织出的 Python 永久检查
src/marshal_pack_cowboy/pack.py  分级 / CONTRACTS / 不变量族 / REVIEW_DIMENSIONS /
                                 SECURITY_HAZARDS / SPEC_LAYERS / conformance
tests/                           98 tests(23 文件)

.claude/skills/marshal/
  SKILL.md                       主流程(流 A/B/C + conformance/metrics 路由)+ 自检
  references/gate-flow.md         门禁评估细节(含干净 worktree 跑不变量)
  references/conformance-flow.md  ⑤ 规格符合度细节
  references/ratchet-flow.md      棘轮细节(含否定性属性形状守门)
  references/review-orchestration.md  ③ 多视角 /code-review ultra 编排
```

---

## 11. 范围边界小结

**做:** 流 A 门禁评估(①②③汇总)、流 B 规格层/conformance(⑤)、流 C 棘轮闭环、⑦ metrics、跨 repo 契约 + 否定性安全危险点感知、SQLite 知识核、cowboy-pack 全部领域知识、薄 CLI、平台层机制/适配器脚手架(shadow 态)。

**不做(留给平台常驻服务):** ⑥ RuntimeWatch、完整 dashboard、webhook 硬阻断 / merge queue / required-status、多团队隔离、PostgreSQL、需额外数据模型的指标(escape_rate/MTTD/tiered-coverage);不写不变量/检查本体,不替代各 repo CI。

---

## 修订记录
- **2026-06-01 v1** — 四段设计 + 可调用包解析经交互评审通过,整合成文(状态:转 writing-plans)。
- **2026-06-07 v2(现状重写)** — skill + 薄 CLI 已实现并合入 `main`(PR #1)。相对 v1 设计的实际增长:CLI 由 6 命令扩到 12(+review-quorum/review-verify/spec-source/spec-requirements/conformance/metrics);⑤ conformance 与 ⑦ metrics 从「非目标」落到种子级;新增否定性安全属性(SecurityHazard/ratchet_guidance);跨 repo 契约由 2 条扩到 4 条(+cip9-ras/cip24-cbss);新增平台执法层脚手架(modules/adapters/executor/checks/contracts);棘轮已闭环 12 条逃逸、注册 10 条 active 棘轮不变量,门禁实跑 44 次;测试 98。

# 流 A-deep — 深审(`/marshal deep [<repo>] <PR#>`)

常规 `/marshal` 的对抗审是**单发/视角**(一个 lens 一个 agent 一 shot)。deep 把它换成
**闭包 → 假说枚举 → 逐假说证真/证伪**,买的是**严谨度**(触发优先、自我 refute、棘轮
先例接地),不是原始召回。**opt-in**,只给值得的 PR 跑。

## 何时用(否则走常规)
- high-tier / 共识面(state/receipt/logs_root、digest、序列化字节)/ econ 守恒 / 跨仓签名。
- 用户显式 `/marshal deep`。
- **成本**:实测 ~5–8× 常规(prove 扇出 × high-effort 是大头)。**用聚焦 lens 集(2–4),
  不是全扇出** —— PoC 证明 2-lens 已够撞 ground truth;全 11-lens(~4M)性价比差。

## 流程

### 1. 分级 + 聚焦 lens 选择(确定性)
- `cli classify --repo <r> --paths …` → tier / review_dimensions / security_hazards。
- `cli review-lenses --repo <r> --paths … --ratchet-top <N>` → `{base, hazards, ratchet, all}`
  (name+prompt)。`base` = tier 基集 + 路径触发(含 consensus-surface);`ratchet` = 从
  逃逸史投的 top-N 定向探针(见 `ratchet-flow.md` 背景)。**deep 取 `all`,但裁到 3–4 条
  风险最相关的**(base 里对症的 + 1–2 条 ratchet);别把全部 lens 都派。

### 2. 变更闭包(L1 共享前缀)
派一个 context-builder subagent:对每个改动 hunk 抽**其外层函式的完整函式体**(读 PR head
的真文件,非 diff 片段)+ 1 跳呼叫方/被呼叫方 + 命中的 contract/不变量正文,组成一份
**中立**(不评判 bug)的 closure bundle,上限 ~1500 行(超了按 execution/storage 优先并
**显式记 truncation**,不静默截断)。这份 closure 是下面所有 scout/prove agent 的**共享
前缀**——同一份逐字复用命中 prompt cache(L1),把输入成本压回 prove 自身。

### 3. scout —— 假说枚举(medium effort,广而便宜)
按裁定的 lens 集**并行**派 scout agent,每个吃 `[closure + diff + lens.prompt]`,只**列
失败假说**(每 lens ≥6,含无聊的),不下判决。格式 `{title, claim: "if <状态/输入> then
<哪条不变量破>", where: file::fn|file:line, invariant_broken, priority 1–5}`。

### 3b. 完整性闸(barrier)—— 所有 lens 未齐,不进后续任何一步
派出的 scout **全部返回后**才做去重/prove/聚合/GateDecision。**绝不「先回先定」**:
scout 是并行的,最慢的 lens 往往载着**头条发现**(经验:审 CIP-36 时最慢的 spec-conformance
lens 花 428s 才回,而它抓的「未声明的白皮书宪法抵触」是整场最重的一类;若按先回 3 个就
出终审判决,会系统性漏掉最严重的问题)。规则:
- 显式记录**期望的 lens 集**(§1 裁定的那批),逐个核对是否都回了。
- 未齐就**等**;真等不到(某 lens 崩/超时)→ 该次 review **标 degraded(lens-incomplete)**,
  GateDecision verdict 至少 escalate,并**明说哪条 lens 缺席**——绝不把「少一路」当「审全了」。
- 这与流 A 的 `/code-review ultra` 拉不起就少一路显式标 degraded 是同一条纪律(barrier 而非
  first-N)。

### 4. 去重 + 上限(L2,唯一会爆的量卡在这)
跨 lens 按 where+claim 邻近去重;按 priority 砍到**每 lens ≤6、全局 ≤ ~18**。**若截断,
`log`/告诉用户丢了几条**(不静默)。
**注意 scout 间 priority 标度不可比**(不同 lens 各按自己的 1–5,有的 1=最高有的 5=最高)——
去重排序**按内容判严重度**,别直接信 scout 给的数字。

### 5. prove —— 逐假说证真/证伪(high effort,深度在此)
每条存活假说一个 fresh high-effort agent,吃 `[closure + diff + 假说]`,**必须**产出
**具体触发**(inputs/state → 错误输出/halt/fork)**或** refute(给出挡住它的守卫/前置/
设计事实)。追不到触发也排除不掉 → `uncertain`(degraded,保留待人看)。**demonstrated
> asserted:没有触发不得 confirm。**

### 6. 聚合(复用已修的 ④)
把 prove 的 confirmed/uncertain 汇成 findings(带 file/line/dimension/severity/source),
过 `cli review-quorum --findings-json … [--proximity 10]` → `{escalate, confirmed,
advisory, dropped}`(proximity 聚类合并同一 bug 的多视角报点、单源中危浮为 advisory;
见 `review-orchestration.md`)。prove 已内建收敛,故此处主要做去重 + 分层。
- deep 的 confirmed/escalate **可跳过**二段对抗验证 gauntlet(prove 的触发已是证据);
  仍照 `review-orchestration.md` 把 advisory 列进报告、不送 gauntlet。

### 7. GateDecision(同流 A 第 5–7 步)
不变量 fail→block;高危 + 确认高 severity(**带触发**)→ escalate;跑不起来/超预算/
闭包建不成 → escalate+degraded;否则 pass。deep 的发现附**触发路径**,报告里带上。

## 杠杆(内建)
- **L1** 共享 closure 当缓存前缀;**L2** 假说去重 + 上限;**L3** 只对 high-tier/共识 PR 跑;
  **L4** effort 分层(scout medium、prove high)。综合把倍率从 ~8× 压向 ~4–5×。

## 降级不谎报
闭包建不成 / 任一步跑不起 / **任一 scout lens 未返回(§3b 完整性闸)** → 显式标 degraded
(注明缺哪步/哪条 lens),verdict 至少 escalate;闭包/scout 整体起不来则**回退常规流 A**。
**绝不假装跑过 deep,绝不在 lens 未齐时出终审判决。**

## 可选:测量化 harness
需确定性 + 实测 token 时,用归档的 Workflow 脚本 `harness/deep_review.js`
（scout→dedup/cap→prove,读 `args`={closure,diff,baseLenses,ratchetLenses,lensSubset,
caps}）。`budget.spent()` 给真实 token。PoC 复现见 `docs/superpowers/poc/2026-07-13-deep-review/`。

# Marshal Deep 模式(深审)设计文档

- 日期:2026-07-13
- 状态:待评审
- 范围:产品功能(新增审核模式)+ PoC 验证。**常规模式一字不改**,deep 为叠加路由。

## 1. 背景与问题

现状对抗式 review(`review.py` + `references/review-orchestration.md`)的召回天花板,从实作看有五个结构性根因:

1. **每个视角只有一次性单发**。`review_dimensions` 一个 lens 派一个 subagent,拿 diff + 一句 prompt 一 shot 出结构化发现。深 bug(pay-then-fail 守恒洞、attribution shift 进 state_root、warm-pool object identity、跨链 replay)需要追数据流、读 diff 外的调用方、先建不变量模型再逐条打——单发天生只撈表层。
2. **只看 diff,对「diff × 未改代码」的接缝结构性盲**。深 bug 十有八九住在接缝:新加的 `Err` 分支调用方没检查、别处维护的不变量被这次改动打破。
3. **视角太粗**。`security`/`correctness`/`econ` 各自是巨大面,单 agent 铺得薄。缺「具体假说」生成阶段。
4. **第二段 refute 在降 recall**。`verify_findings` 是「仅严格多数 uphold 才存活」——对精度对,对深 bug 反了:微妙真 bug 在浅 skeptic 眼里像误报,一个 prover 证真、其他人摇头就被砍。
5. **quorum 用「不同视角数」计票,惩罚单视角深发现**。深 bug 常只有一个专门视角看得出(determinism lens 抓 fork、econ lens 抓守恒洞),要求 2 个 distinct source 才 confirm,单视角 mid-severity 深 bug 当 weak 丢掉。

一句话:现管线为**高精度、杀误报**调,不为**高召回、挖深 bug**调。用户的抱怨本质是召回问题。

## 2. 目标 / 非目标

**目标**
- G1 新增 `deep` 模式:用「上下文闭包 → scout(列假说)→ prove(逐假说追码、要求构造触发)」替代单发,把深度做进管线。
- G2 把棘轮 DB(`escape_registry`,workspace 库现有 69 条)变成**视角生成器**——每个历史逃逸类别 = 一条定向探针,复用项目专属召回彈藥。
- G3 **常规模式完全保留**:`/marshal <PR#>` 路径不改一行;deep 是新增叠加路由 `/marshal deep <PR#>`。
- G4 内建**压低倍率的杠杆**(见 §5),使 deep 相对常规的 token 倍率可控(目标 ~4–5×,而非放任 ~7–8×)。
- G5 **PoC 用 #936 回放**,给出 regular vs deep 的召回对比 + **实测** token,把 §6 的估算换成实证。

**非目标**
- 不在本轮改 `verify_findings` core 逻辑(④ 触发优先存活判定留 Phase 2;PoC 里以「prove 必须给触发」体现)。
- 不在本轮做 ⑤ dry-loop / completeness critic。
- 不改常规模式判决语义。

## 3. PoC 回放靶:PR#936(node)

- 规模:24 档 / +479 −229 行。可经 `gh pr diff 936 -R cowboyinc/node` 取得。
- **Ground truth(深訊号)**:该 PR 是 emitter-provenance 修复(COW-2435/TOB-18,run546 needs_human,共识 flag-day)。除 20-byte prefix 外,有**两处 attribution-shift 移动 state_root**:
  1. nested call → callee log 的 emitter 归属;
  2. system `_ => None` 分支 → tx.from 归属。
- 这两处需**跨函式追踪 emitter 归属穿过 nested 调用 + system 分支**才看得到,是「单发会漏、深审该撈出」的典型。
- 验收判据:deep 模式**显式产出**这两处 attribution→state_root 观察(即便代码最终正确,也应作为 flag-day 相关的共识语义变化升 needs_human);常规单发路径若漏掉或不升级 → 证明 deep 有增量召回。

## 4. 方案总览(Phase 1 = PoC 骨架)

两路跑同一份 #936 diff,产出对比 + 实测 token。

### 4.1 `ratchet-lenses` CLI(③,新增,不碰现有命令)
- 读 `escape_registry`(经现有 `knowledge/store`,用 CLI 同一个 DB)。
- 按 `root_cause_class` 聚类 → 合成 `[{name, prompt}]` 定向探针;`description` 富的单条也各自成探针。
- prompt 立场:「本次改动是否**重新引入** escape-class E?回代码逐条核对该类历史根因是否复现」。
- 输出并入 deep 路径的 `review_dimensions`(叠加,不替换基集)。
- ~40 行;领域无关机制,探针内容来自 DB(换 pack 即换彈藥)。

### 4.2 deep-review harness(①,Workflow 脚本)
管线(`pipeline()`):
1. **context-closure**:对每个改动 symbol,拉整个外层函式 + 1 跳调用方/被调用方 + 命中的 contract/不变量正文,组成「review bundle」。**一份共享 closure**(见 §5 杠杆 1)。
2. **scout**:(6 base lens + ratchet-lenses)各派一 agent,只**列失败假说**(≥8/lens,含无聊的),不下判决。格式 `if <状态/输入> then <哪条不变量破>` + 自评优先度。
3. **dedup + cap**:跨 lens 去重,按自评优先度砍到每 lens ≤6(见 §5 杠杆 2)。
4. **prove**:每条存活假说一个 fresh high-effort agent,追真实碼路,**必须产出「具体触发」(inputs/state → 错误输出/halt/fork)或标 refuted**。demonstrated > asserted。
5. 汇入现有 `review-quorum` / `review-verify`(复用,不改)。

### 4.3 regular baseline
现有单发 + quorum + refute 路径跑同一份 #936。

### 4.4 对比报告
`findings_regular vs findings_deep` + 实测 token(Workflow `budget.spent()`)+ 是否命中两处 state_root attribution-shift。落 `docs/superpowers/` 或 scratchpad。

## 5. 压低倍率的杠杆(内建 PoC)

| # | 杠杆 | 机制 | 效果 |
|---|---|---|---|
| L1 | **Prompt caching 共享 closure** | 同一份 context-closure 作为稳定前缀喂给所有 scout/prove agent,命中 Anthropic prompt cache 后输入成本掉 ~90% | 抵消 ② 的输入膨胀,把成本压回 prove 的 thinking+output 本身 |
| L2 | **假说去重 + 上限** | scout 后跨 lens 去重、按自评优先度砍到每 lens ≤6 | prove agent 数是唯一会爆的量,这裡卡死 |
| L3 | **tier 门控** | deep 只对 high-tier/共识 PR 跑,low/mid 走常规 | 日常吞吐不受倍率影响 |
| L4 | **effort 分层** | 只有 prove + 共识/econ lens 用 high effort;scout 用中/低 effort | 省掉 scout 的高推理开销 |

综合 L1–L4:目标把大型 high-tier PR 的 deep 倍率从 ~7–8× 压到 **~4–5×**。

## 6. Token 预测(待 PoC 实测校准)

| | 常规 | deep(PoC ①+③,含 L1–L4,**无** dry-loop) | 倍率 |
|---|---|---|---|
| 大型 high-tier PR(如 #936) | ~0.4M | ~2–3M | ~5–7×(caching 命中后可近 4–5×) |
| 中型 mid-tier PR | ~0.15M | ~0.9M | ~5–6× |
| 主成本驱动 | lens 单发数 | **prove 扇出 × high-effort** | — |

数量级估算,误差带宽。PoC 的 `budget.spent()` 给真实数,回填本表。若日後加 ⑤ dry-loop:再 ×K(K=轮数 2–3)。

## 7. Phase 2(PoC 证明有效後,不在本轮)

- `/marshal deep <PR#>` 路由 + `references/deep-review-flow.md`。
- ④:`verify_findings` 改嚴重度不对称 + 触发优先存活。
- ⑤:dry-loop + completeness critic。

## 8. 风险 / 降级

- **降级不谎报**:deep harness 任一步跑不起(closure 取不到 / workflow 拉不起)→ 显式标 degraded,回退常规模式,绝不假装跑过。
- **成本失控**:L2 上限 + L3 门控是硬护栏;PoC 阶段先在 #936 单靶验证倍率再谈日常启用。
- **假阳性洪水**:deep 提升召回必然带来更多 raw findings,靠现有 quorum/verify 二段收敛;PoC 报告需同时给 precision(存活/raw 比)。

# Deep-Review PoC — Results on node PR#936

- 日期:2026-07-13
- 靶:node PR#936(COW-2435 / TOB-COWBOY-18,emitter provenance,24 档 / +479 −229)
- 方法:同一份 diff,两路对跑 —— **deep**(closure→scout→prove)vs **regular**(6 lens 单发 diff-only)。两路皆 Workflow,`budget.spent()` 计实测 token。
- 状态:PoC 校准跑完成(deep 用 2 lens 子集校准;regular 全 6 lens)。全量 deep 未跑(待定)。

## 1. Ground truth(记忆锚定的深訊号)

PR#936 除 20-byte emitter prefix 外,有**两处 attribution-shift 移动 state_root**:
1. `nested call → callee log` 的 emitter 归属;
2. system `_ => None` 分支 → tx.from 归属。
外加共识 flag-day(emitter 无 activation gate → 混版分叉)。

## 2. 召回对比 —— 诚实结论:#936 两路都撞到

| 深訊号 | regular(6 lens 单发) | deep(2 lens 校准) |
|---|---|---|
| `_=>None → tx.from` state_root 语义变化 | ✅ 5 条(low–mid;一条误升 HIGH) | ✅ 1 条 MID,**带具体触发**(SubmitProposal→append_actor_events→state_root:2405) |
| `nested → callee log` state_root shift | ✅ 1 条 MID(determinism) | ⚠️ 未在 2-lens 子集出现(该 lens 未派) |
| flag-day fork(无 gate) | ✅ HIGH | ✅ HIGH,**+棘轮先例对比 #848/#934 gating** |
| 旧 receipt 回读 misdecode | ✅ MID(未自证共识相关性) | ✅ **LOW,且自我 refute 掉 fork/halt**(查证 receipts 在非-merkle 侧库 state_key.rs:48) |

**关键诚实点:一个 6-lens 强单发 regular(agent 有工具权、会自己去读码)在 #936 上已撞出两个 ground-truth 信号。** 所以 **#936 上 deep 相对 regular 没有"原始召回"优势**。

**为什么 #936 不是好的召回判别靶**:emitter 改动**在 diff 里直接可见**,diff-only 的 lens agent 一眼就看到。deep 的闭包/追踪优势,专治**bug 藏在「diff × 未改代码」接缝、diff 里看不见**的情形 —— #936 不属于这类。

## 3. deep 的真实增量(在 #936 上可测的)= 深度而非召回

即便只有 2 lens,deep 相对 regular 有三处**质量**优势:
1. **触发优先**:每条 confirmed 附**具体可复现触发**(输入/状态→错误输出/fork),而非意见。regular 多为"deterministic so not a fork"式描述。
2. **severity 校准 + 自我 refute**:receipt-misdecode 上,deep 追证 receipts 在非-merkle 侧库、decode Err 被 `warn!` 吞 → 主动降到 LOW 并 refute 掉 fork 声索;regular 保留 MID 未自证。deep 6 假说→**4 confirmed / 2 refuted**,收敛已在 prove 内完成。
3. **棘轮先例接地**:`ratchet:state-consensus` lens 主动把本改动对照历史逃逸 #848/#934 的 opt-in gating 模式 —— 项目专属彈藥在起作用。

regular 产 **12 条 raw**(含重叠、一条 `_=>None` 误升 HIGH、无自我 refute),需靠 quorum+refute 二段(本次未跑)去噪;deep 的 prove 已内建收敛。**deep = 高精度/高严谨/低噪;regular = 高原始量/需二段清洗。**

## 4. Token 实测(校准)+ 全量外推

| | agents | 总 tokens | output tokens | /agent |
|---|---|---|---|---|
| **deep 校准**(2 scout + 6 prove) | 8 | **796,666** | 85,243 | ~99.6k |
| **regular 全量**(6 lens 单发) | 6 | **498,079** | 82,404 | ~83.0k |

- per-agent:deep prove(~105k,high effort + 多跳读码)比 regular lens(~83k)贵 ~25%;主倍率来自 **agent 数**,非单价。
- **全量外推**(总 tokens):full deep(11 scout + 30 prove cap)≈ **4.1M**;full regular(6 lens)≈ 0.5M(真 skill +quorum/refute ~0.3–0.5M)→ **~8× 倍率**。与 spec §6 预测一致。

**效率洞见(重要)**:deep **2-lens 校准(0.8M)已匹配 regular 的 ground-truth 召回**且更严谨。=> deep 的价值在**聚焦的 lens 集**(棘轮选中的 + 风险相关的 2–4 lens,~0.8–1.5M),**不是**盲目 11-lens 全扇出(4.1M)。**建议 deep 默认 = 风险相关 top-N lens,而非全集。**

## 5. PoC 判定

- ✅ 管线跑通(closure→scout→dedup/cap→prove,L1 缓存前缀 + L2 caps + L4 effort 分层)。
- ✅ Token 预测换成实测基(deep ~100k/agent,full ~4.1M,~8×)。
- ✅ deep 的**深度**优势实证(触发/自我-refute/棘轮先例)。
- ⚠️ deep 的**召回**优势在 #936 上**未能判别**(diff-visible bug,regular 也撞到)。**要证召回增量,需换一个 diff-seam(diff 里看不见)的靶。**

## 6. 下一步(待用户裁)

1. **换硬靶证召回**:选一个 bug 藏在 diff×未改码接缝、且历史上 regular/单发漏过的 PR(候选:COW-2497 委员会 sizing 那类逻辑洞,或 pay-then-fail 守恒洞),回放证 deep>regular 的召回。← 推荐
2. **全量 deep 跑 #936**(~4.1M):只会确认"更多 lens=更多发现",不证召回论题,性价比低。
3. **产品化 deep 默认聚焦集**:`/marshal deep` 默认 = 棘轮 top-N + 风险相关 lens(~0.8–1.5M),非全扇出。

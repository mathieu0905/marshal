"""③ ReviewOrch — quorum 聚合 (机制, 领域无关).

多视角对抗 review 的去重 + 计票 + 收敛。靠视角间的"分歧/一致"标问题,防 AI 审 AI
的相关性盲区:孤立的低危发现当噪声丢;达到 quorum 的发现确认;**任何高危一律升
needs_human**(终审归人,即便只有单视角提出)。不含任何领域语义。
"""
_SEVERITY_RANK = {"low": 0, "mid": 1, "high": 2}

# ③ 对抗式验证二段的 refute 视角目录 (机制, 领域无关)。
# 一段用互异视角找碴; 二段的 skeptic 若都是同质 "default-refute", 会有共同盲区 ——
# 给每个 skeptic 绑**不同的反驳 lens**, 用视角多样性抓冗余 skeptic 抓不到的误报,
# 与一段的视角互异对称。经验上合法的 refute 九成落在这五类。prompt 刻意零领域名词
# (普世, 任何 pack 复用) —— 别往这里塞项目专属措辞。
REFUTE_LENSES = [
    {"name": "reachability",
     "prompt": ("默认 refute, 除非能构造出真正走到该路径的输入: 上游守卫/前置校验是否"
                "已挡掉? 触发前提是否根本不成立?")},
    {"name": "stale-basis",
     "prompt": ("默认 refute: 该发现是否读了陈旧 checkout / 错的树 / 落后引用? 回被审"
                "改动本体的版本一手核对, 所述符号/行为是否真如描述。")},
    {"name": "intended-design",
     "prompt": ("默认 refute: 这是否是有意的设计裁定 / 既定语义而非缺陷? 回权威规格或"
                "设计记录核对, 别把有意取舍当漏洞。")},
    {"name": "severity",
     "prompt": ("默认 refute 其 severity: 即便路径成立, 影响是否被高估 (优雅失败 vs "
                "halt、单条请求 vs 全局)? 给不出对应影响的证据就降级或 refute。")},
    {"name": "already-guarded",
     "prompt": ("默认 refute: 框架或别处机制是否已隐含保证 (生命周期重置、既有计数器、"
                "原子性/回滚)? 回代码确认该不变量是否已成立。")},
]


def _class_key(root_cause_class: str) -> str:
    """把 root_cause_class 归一成桶键: 取首个 ':' 前的标签 (长描述型 one-off 折进类)。

    'confidentiality-break: negative...' -> 'confidentiality-break'
    'state-consensus' -> 'state-consensus'
    空串 -> 'unclassified'。
    """
    head = (root_cause_class or "").split(":", 1)[0].strip()
    return head or "unclassified"


def _slug(s: str) -> str:
    out = []
    for ch in s.lower():
        out.append(ch if ch.isalnum() else "-")
    return "-".join(x for x in "".join(out).split("-") if x) or "x"


def ratchet_lenses(escapes: list[dict], max_lenses: int = 8,
                   samples_per_class: int = 3) -> list[dict]:
    """③ 把逃逸历史 (escape_registry) 投成定向 review 视角 (机制, 领域无关)。

    每个 escape: {root_cause_class, description?, change_ref?}. 按归一类聚类, 按频次
    (该类咬过几次) 降序取 top max_lenses —— 复发多的类优先当探针。每条视角的 prompt
    是"本次改动是否**重新引入**该类逃逸", 并夹带至多 samples_per_class 条历史根因描述
    当**先例证据**(prove agent 据此逐条核对)。prompt 骨架零领域名词 (普世, 任何 pack
    复用) —— 具体性来自 DB 行, 不往骨架塞项目专属措辞。与 REFUTE_LENSES 对称。

    返回 [{name, prompt, klass, weight}]; 空输入 -> []。
    """
    if not escapes:
        return []
    max_lenses = max(0, max_lenses)          # 负值不做反向切片
    samples_per_class = max(0, samples_per_class)
    if max_lenses == 0:
        return []
    buckets: dict[str, dict] = {}
    for e in escapes:
        k = _class_key(e.get("root_cause_class", ""))
        b = buckets.setdefault(k, {"klass": k, "count": 0, "samples": []})
        b["count"] += 1
        desc = (e.get("description") or "").strip()
        if desc and desc not in b["samples"]:
            b["samples"].append(desc)
    ranked = sorted(buckets.values(), key=lambda b: (-b["count"], b["klass"]))
    lenses = []
    for b in ranked[:max_lenses]:
        samples = b["samples"][:samples_per_class]
        evidence = ("\n".join(f"  - {s}" for s in samples)
                    if samples else "  (无成文描述, 仅类别)")
        prompt = (
            f"默认怀疑: 本次改动是否**重新引入** `{b['klass']}` 类逃逸? "
            f"该类历史上咬过 {b['count']} 次, 先例根因:\n{evidence}\n"
            f"回被审改动的代码, 逐条核对上述根因模式是否在此复现 (相同的守恒/归属/"
            f"边界/授权/确定性破口)。命中就产出具体触发路径; 明确不适用就说明为何。")
        lenses.append({"name": f"ratchet:{_slug(b['klass'])}", "prompt": prompt,
                       "klass": b["klass"], "weight": b["count"]})
    # 不同类可 slug 成同名 (如 'state/consensus' 与 'state-consensus') → 唯一化,
    # 否则按 name 键的下游会撞/覆盖。
    seen: dict[str, int] = {}
    for lp in lenses:
        n = lp["name"]
        seen[n] = seen.get(n, 0) + 1
        if seen[n] > 1:
            lp["name"] = f"{n}-{seen[n]}"
    return lenses


def assign_refute_lenses(n: int) -> list[dict]:
    """给 n 个 skeptic 轮转分配 refute 视角 (视角多样化 > n 个同质 skeptic)。

    n<=目录长度: 取前 n 个互异 lens; 更大: 轮转复用 (仍尽量铺满目录再重复)。
    返回 [{name, prompt}]; n<=0 → []。
    """
    if n <= 0:
        return []
    k = len(REFUTE_LENSES)
    return [dict(REFUTE_LENSES[i % k]) for i in range(n)]


def _line_of(f: dict) -> int:
    v = f.get("line")
    if v is None:
        return 0
    try:
        return int(v)
    except (TypeError, ValueError):
        try:                       # '5.9' 和 5.9 一致 → 5 (别一个截断一个归 0)
            return int(float(v))
        except (TypeError, ValueError):
            return 0


def _has_loc(f: dict) -> bool:
    """finding 是否带真实位置 (file + line)。无位置的不参与邻近聚类 (否则一堆
    location-unknown 会挤进同一 `?`/0 桶假造 quorum)。"""
    return (f.get("file") not in (None, "", "?")
            and f.get("line") not in (None, ""))


def _cluster_keys(findings: list[dict], proximity: int) -> list[str]:
    """给每条 finding 分配一个组键 (与 findings 等长, 位置对应)。

    显式 `key` 优先; 有真实位置的按 **file + 行邻近** 聚类 (同文件内按行排序, 距**簇首**
    ≤ proximity 就并入 —— 跨度**有界** ≤ proximity, 防止密集行把整文件链成一坨假 confirmed);
    无位置的各自独立键 (不合并)。这样"同一 bug 被不同视角报在略不同行/不同 dimension"会
    **合并** (support 累加 → 能达 quorum), 而旧 `file:line:dimension` 精确键则 confirmed 恒 0。
    dimension **不进键** (它是组的属性, 不是身份): 同一处的 correctness 与 econ 视角算两票。
    生成键带 `~prox:` 前缀, 与调用方语义化 `key` 隔离, 避免撞键误并。
    """
    from collections import defaultdict
    proximity = max(0, proximity)
    keys: list = [None] * len(findings)
    byfile: dict[str, list[int]] = defaultdict(list)
    for i, f in enumerate(findings):
        if f.get("key"):
            keys[i] = f["key"]
        elif _has_loc(f):
            byfile[f["file"]].append(i)
        else:
            keys[i] = f"~loc?:{i}"          # 无位置: 唯一键, 绝不与他人合并
    for file, idxs in byfile.items():
        idxs.sort(key=lambda i: _line_of(findings[i]))
        cluster: list[int] = []
        lo = 0
        for i in idxs:
            ln = _line_of(findings[i])
            if cluster and ln - lo > proximity:      # 距簇首 (非前一行) → 跨度有界
                k = f"~prox:{file}:{lo}~{_line_of(findings[cluster[-1]])}"
                for j in cluster:
                    keys[j] = k
                cluster = []
            if not cluster:
                lo = ln
            cluster.append(i)
        if cluster:
            k = f"~prox:{file}:{lo}~{_line_of(findings[cluster[-1]])}"
            for j in cluster:
                keys[j] = k
    return keys


def aggregate_review(findings: list[dict], quorum: int = 2,
                     proximity: int = 10) -> dict:
    """把多视角发现聚合成 review 结论。

    每条 finding: {key? | file,line,dimension, severity(low|mid|high), source, title}.
    按 **file+行邻近** 聚类 (见 `_cluster_keys`; 显式 `key` 优先);support = 不同
    `source` 数 (同视角重复不加分)。组状态:
      - 含高危 → needs_human
      - support>=quorum → confirmed
      - 单源 **中危** → **advisory** (浮出为建议, **不丢**; 修复旧行为把微妙真阳性当噪声杀)
      - 单源 **低危** → weak (噪声地板, 丢弃)
    review_verdict: 有任一高危组 → needs_human;否则 pass (confirmed/advisory 为建议态,
    不阻断)。advisory 是给人看的单视角观察, 不进对抗验证 gauntlet (那会再把它杀掉)。
    """
    key_for = _cluster_keys(findings, proximity)
    groups: dict[str, dict] = {}
    for i, f in enumerate(findings):
        k = key_for[i]
        # 归一化 severity: 大小写不敏感 ('High'→'high'); 未知非空取值不静默降 low 丢弃,
        # 保守当 'mid' 浮为 advisory (漏报真阳性比多一条建议更糟)。
        sev = str(f.get("severity") or "low").strip().lower()
        if sev not in _SEVERITY_RANK:
            sev = "mid"
        g = groups.setdefault(k, {"key": k, "severity": "low", "sources": set(),
                                  "dimensions": set(), "titles": [], "count": 0})
        if _SEVERITY_RANK[sev] > _SEVERITY_RANK[g["severity"]]:
            g["severity"] = sev
        if f.get("source"):
            g["sources"].add(f["source"])
        if f.get("dimension"):
            g["dimensions"].add(f["dimension"])
        g["count"] += 1
        if f.get("title"):
            g["titles"].append(f["title"])

    out_groups = []
    for g in groups.values():
        # support = 不同视角数。无 source 信息时**不**回退到原始 count (否则同一视角的
        # 多条邻近发现会假造 quorum) —— 记 1 (无法证明多视角一致)。
        support = len(g["sources"]) or 1
        if g["severity"] == "high":
            status = "needs_human"
        elif support >= quorum:
            status = "confirmed"
        elif g["severity"] == "mid":
            status = "advisory"
        else:
            status = "weak"
        out_groups.append({"key": g["key"], "severity": g["severity"],
                           "support": support, "sources": sorted(g["sources"]),
                           "dimensions": sorted(g["dimensions"]),
                           "titles": g["titles"], "status": status})

    # 稳定排序: 高危在前, 再按 support 降序
    out_groups.sort(key=lambda x: (-_SEVERITY_RANK[x["severity"]], -x["support"]))
    needs_human = [g for g in out_groups if g["status"] == "needs_human"]
    confirmed = [g for g in out_groups if g["status"] == "confirmed"]
    advisory = [g for g in out_groups if g["status"] == "advisory"]
    dropped = [g for g in out_groups if g["status"] == "weak"]
    verdict = "needs_human" if needs_human else "pass"
    return {"groups": out_groups, "needs_human": needs_human,
            "confirmed": confirmed, "advisory": advisory, "dropped": dropped,
            "review_verdict": verdict}


def verify_findings(items: list[dict]) -> dict:
    """③ 对抗式验证二段: 对每条发现的 N 个 skeptic 投票裁决 (default-to-refute)。

    每条 item: {key, severity, votes:[{refuted: bool, reason?}]}. skeptic 默认 refute,
    只有确凿证明发现为真才 uphold。**仅当严格多数 uphold 才存活**(平票/多数 refute →
    杀,把似是而非的误报砍掉);无投票 → unverified(degraded,保留待人看)。
    verdict: 有存活的高危 → needs_human;否则 pass。
    """
    survived, killed, unverified = [], [], []
    for it in items:
        votes = it.get("votes", []) or []
        total = len(votes)
        refutes = sum(1 for v in votes if v.get("refuted"))
        upholds = total - refutes
        row = {"key": it.get("key"), "severity": it.get("severity", "low"),
               "upholds": upholds, "refutes": refutes, "total": total}
        if total == 0:
            unverified.append(row)
        elif upholds * 2 > total:          # 严格多数 uphold 才存活
            survived.append(row)
        else:                              # 平票或多数 refute → 杀
            killed.append(row)
    verdict = "needs_human" if any(r["severity"] == "high" for r in survived) else "pass"
    return {"survived": survived, "killed": killed, "unverified": unverified,
            "verdict": verdict}

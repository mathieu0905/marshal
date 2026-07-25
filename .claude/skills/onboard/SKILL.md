---
name: onboard
description: Use to onboard a repo's HEAD into a Marshal concept registry (Phase 0 snapshot) — dry-run cost gate, deterministic detect, agent-drafted concept pages, tech-debt report, human acceptance. Triggers — "/onboard <repo-path>", "onboard this repo", "跑一次 onboard".
---

# Onboard Skill — Phase 0 HEAD 快照

你是 onboard 的编排器。确定性工作外包给 `marshal_core.cli`;概念抽取是你(agent)的判断工作。

## 前置
    PY="${MARSHAL_HOME:-/home/ubuntu/workspace/marshal}/.venv/bin/python"
    CLI() { "$PY" -m marshal_core.cli "$@"; }

## 流程(严格按序,估价门不过不动手)

1. **估价门(先做):** `CLI onboard-estimate --repo <repo>` → 把 est_usd/tokens/calls + method 摆给用户。
   **显式确认**是否继续(§6.3:成本先摆出来再花)。用户不同意 → 停。

2. **探测:** `CLI onboard-detect --repo <repo>` → 得抽取简报(languages/doc_inventory/module_map/candidate_seeds)。

3. **抽取(你的判断工作,agent fan-out):** 按简报, 对每个 candidate_seed / 关键 doc, 起草概念页 markdown
   写进 `<concepts-out-dir>`(一个**新目录**, 不覆盖已策展的 pack)。每页遵守 S0 `concept-schema.md`:
   - frontmatter 必含 `concept_id`/`importance`/`status`;anchors **必须指向 detect 见过的真实符号定义**
     (H1:无真实定义锚点的概念别硬塞 anchor, 让它自然落为 doc_only, 别谎报锚定)。
   - importance 由你按架构判断给先验;**宁少勿多**(§3.0:只在跨 3+ 源或有矛盾时建概念页)。
   - 树要浅、节点数目标 20–40(§8 S1 验收)。

4. **派生 + 报告:** `CLI onboard-report --domain-pack <p> --concepts-dir <out> --repo-root <repo>=<path>`
   - **`<p>` 必须是本次 onboarding 的全新 pack 名, 与任何已策展 pack 明确不同(绝不用 `cowboy`)。**
     `derive_db` 是 **overwrite-style**(重建前先删掉该 pack 的 concepts/edges/anchors)——
     复用已策展的 pack 名会清零真实概念缓存。`--domain-pack` 现为必填、无默认, 正是为堵此坑。
   - 得技术债信号:`unanchored_high` / `orphans` / `over_fragmented` / `dangling_parent` /
     **`dangling_refs`(边指向尚未建页的概念 —— onboard 最常见的真债, 优先看)**。

5. **人审接受门(硬门, §8 S1 + 深审 Q②):**
   - 概念树交**第二人或盲抽样**评:概念/父子/重要性正确率 **≥70%** 才算通过;记抽样比例 + 不接受项。
   - **禁止**自评放水;未达标 → 回步骤 3 调抽取, 不放宽门槛。
   - 对高重要性概念**人眼扫语义是否名副其实**(S4 挂羊头 lens 未上线前的临时兜底)。

## 铁律
- **估价门不过不动手**;成本诚实, 不谎报精度。
- **抽取的准确率靠人审门兜底**, 不假装 CLI 能验证语义。
- 概念页写进**新目录**, 不覆盖 refs/wiki 手工策展的种子(除非用户明确要 re-onboard)。

# 概念页规约(Concept Page Protocol)

Marshal 自有的概念真相源。每个 `concepts/<slug>.md` 是一个概念节点;人审改这里,
DB 只从这里单向派生(不反向)。种子一次性来自 refs/wiki + refs/analysis 修正案,
导入后与 refs 无运行时依赖。

## Frontmatter(必填字段)

    ---
    type: concept | entity
    concept_id: <kebab-slug>          # 唯一 id,= 文件名去 .md
    parent: <concept_id | "">         # 主父(单 primary_parent);根为空串
    importance: constitutional | high | mid | low   # = 优先级 = 架构判断
    part_of: [<concept_id>, ...]      # 次要归属(多父,不定层级)
    depends_on: [<concept_id>, ...]   # 依赖边(DAG)
    anchors:                          # 代码锚点(H1:必须真实存在)
      - {repo: <r>, path: <p>, symbol: <sym>, kind: implements|named_after}
    spec_refs: [<CIP-N>, ...]         # 规格来源(挂到概念)
    status: authoritative | draft | stale | doc-only
    last_updated: YYYY-MM-DD
    ---

## 权威与派生

- 真相源 = 本目录 markdown;`marshal.db` 是**只读派生缓存**(单向)。
- `confidence` 由代码锚定程度决定,不由文档描述决定:无任何 anchor 通过校验的
  概念标 `doc_only`、confidence 封顶,gate 不得据以给高置信判决(H1)。
- 重要性(importance)是人审定的架构判断,不用 PageRank 自动定。

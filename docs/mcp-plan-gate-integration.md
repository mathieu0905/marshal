# Plan-Gate MCP 接入指南(marshal_plan_review)

把 Marshal 的**概念预算 plan gate** 作为一个 MCP tool 接进任意 agent(Codex / Claude Code / Opencode),
让"每次 plan 完让 Marshal 过一下"成为工具调用。tool 只报**中性成本**,绝不建议做/不做。

## 接入配置

MCP client 的 `.mcp.json`(Claude Code)或等价 Codex/Opencode 配置:

```json
{
  "mcpServers": {
    "marshal-plan-gate": {
      "command": "/home/ubuntu/workspace/marshal/.venv/bin/python",
      "args": ["-m", "marshal_core.mcp_server"]
    }
  }
}
```

前置:`pip install -e ".[mcp]"`(装 mcp SDK)。server 走 stdio。

## 工具

`marshal_plan_review(concepts_dir, domain_pack, touches, repo_roots?)`

- **调用方 agent 的职责**:把你的 plan 映射成 `touches` —— `[{concept_id, op:"add"|"redefine", importance?, est_scope?}]`。
  这一步是 agent(LLM)的判断,tool 不做(marshal 核无 LLM)。
- **返回(中性成本画像)**:`weighted_concept_cost`(=grounded+hinted,**无单位相对权重,非工期**)、
  `grounded_cost`(redefine,树算,不可 gaming)、`hinted_cost`(add,你的 est_scope 估,需核对)、
  `blast_radius`(传递受影响概念)、`impacted_repos`、`highest_tier_touched`、`unknown_redefines`/`unknown_ops`。
  `verdict` 恒 `cost-only`——**从不建议做/不做**。

## 已验证(真 stdio 协议端到端)

用真 MCP client 生出 `python -m marshal_core.mcp_server` 进程、走完整协议:

- `initialize` + `tools/list` → `['marshal_plan_review']`,描述中性(无 recommend/should)。
- `tools/call marshal_plan_review`(对真实 cowboy 概念树:redefine gas+dual-gas-model + add cell-rent large)
  → `isError=False`,`verdict=cost-only`,`cost=68`(grounded 32 + hinted 36),`tier=constitutional`,`blast=13 概念`。
- 畸形 touch(缺 `op`)经协议 → `isError=True` + 清晰错误("each touch needs 'concept_id' and 'op'"),非 server crash。

> 只读隔离:tool 每次派生进隔离内存 DB,**绝不 mutate 共享 marshal.db**(概念页 markdown 是真相源)。

## 剩余(需真人)

真实接入 Codex/Opencode 并由团队("想法多"的人)试用、收 ≥3 条反馈——这是 §8 S3 验收门的人参与部分,配置与协议已就绪。

"""Marshal Plan-Gate MCP server —— 把确定性概念预算暴露为一个 MCP tool, 供任意 agent
(Codex / Claude Code / Opencode) "每次 plan 完让 Marshal 过一下"。

薄 wrapper: plan→touches 的映射是**调用方 agent** 的判断(见 tool 描述), 本 tool 只跑
确定性 concept_budget。中性: 只报成本, 绝不建议做/不做。
"""
from mcp.server.fastmcp import FastMCP

from marshal_core.plangate.service import plan_review

mcp = FastMCP("marshal-plan-gate")


@mcp.tool()
def marshal_plan_review(concepts_dir: str, domain_pack: str, touches: list[dict],
                        repo_roots: dict[str, str] | None = None) -> dict:
    """Run a NEUTRAL concept-budget cost review of a plan before you implement it.

    First map your plan to concept `touches`: a list of
    {concept_id, op:"add"|"redefine", importance?, est_scope?:"small"|"medium"|"large"}.
    Use "redefine" for existing concepts, "add" for new ones (give importance + est_scope).
    Then call this. Returns a cost picture:
      - weighted_concept_cost: a UNITLESS relative weight (grounded_cost + hinted_cost),
        NOT hours/days — use it to compare plans, not to quote a schedule.
      - grounded_cost (redefine, computed from the real concept tree — cannot be gamed)
      - hinted_cost   (add, from YOUR est_scope hints — cross-check they are honest)
      - blast_radius  (concepts transitively affected), impacted_repos, highest_tier_touched
      - unknown_redefines / unknown_ops (surfaced, never silent)

    Marshal only puts the cost on the table. It NEVER tells you whether to do the work —
    that is your call against your own budget.
    """
    return plan_review(concepts_dir, repo_roots or {}, domain_pack, touches)


def main() -> None:
    mcp.run()   # stdio transport


if __name__ == "__main__":
    main()

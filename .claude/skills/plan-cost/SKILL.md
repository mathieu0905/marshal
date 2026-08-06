---
name: plan-cost
description: Use to get a NEUTRAL concept-budget cost picture for a plan before implementing it — maps the plan to concept touches, computes deterministic weighted cost + blast radius, and adds agent day-estimates. Never recommends do/don't. Triggers — "/plan-cost <plan-file>", "过一下这个 plan 的成本", "concept budget".
---

# Plan-Cost Skill — 概念预算(中性成本门)

你是 plan-cost 的编排器。确定性成本外包给 `marshal_core.cli plan-cost`;plan→touches 的映射与工期估算是你(agent)的判断。

> **MCP 形态(S3):** 同一确定性预算也暴露为 MCP tool `marshal_plan_review`
> (`python -m marshal_core.mcp_server`),供 Codex / Opencode 等**非 Claude-Code** agent
> 直接调用。Claude Code 里用本 skill(CLI)或 MCP tool 均可, 二者走同一 `plan_review` 核心。

## 前置
    # marshal-bootstrap:start
    HOST_SKILL="$HOME/.claude/skills/plan-cost"
    REPO_SKILL=".claude/skills/plan-cost"
    if [ -n "${MARSHAL_PYTHON:-}" ]; then
      PY="$MARSHAL_PYTHON"
    else
      if [ -n "${MARSHAL_HOME:-}" ]; then
        :
      elif REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" &&
           [ -f "$REPO_ROOT/$REPO_SKILL/SKILL.md" ] &&
           [ -f "$REPO_ROOT/src/marshal_core/cli.py" ] &&
           SKILL_DIR="$(cd -P "$REPO_ROOT/$REPO_SKILL" && pwd)"; then
        MARSHAL_HOME="$(cd "$SKILL_DIR/../../.." && pwd -P)"
      elif [ -L "$HOST_SKILL" ] && SKILL_DIR="$(cd -P "$HOST_SKILL" 2>/dev/null && pwd)"; then
        MARSHAL_HOME="$(cd "$SKILL_DIR/../../.." && pwd -P)"
      else
        echo "Marshal checkout not found; run setup or set MARSHAL_HOME/MARSHAL_PYTHON." >&2
        return 1 2>/dev/null || exit 1
      fi
      PY="$MARSHAL_HOME/.venv/bin/python"
    fi
    # marshal-bootstrap:end
    CLI() { "$PY" -m marshal_core.cli "$@"; }

## 流程

1. **读 plan + 当前概念树:** `CLI concept-tree --domain-pack <p> --concepts-dir <pack/concepts> --repo-root <r>=<path>`。

2. **映射 plan → touches(你的判断):** 判断这份 plan 会**新增**哪些概念(op=add,给 importance +
   est_scope small/medium/large 的**规模提示**)、**重定义**哪些既有概念(op=redefine)。写到一个
   **临时/scratch 路径**(别污染 repo):`TOUCHES="${TMPDIR:-/tmp}/plan-cost-touches.$$.json"`,
   内容 `[{concept_id, op, importance?, est_scope?}]`。**宁少勿多**;拿不准的概念别硬塞。

3. **算确定性成本:** `CLI plan-cost --domain-pack <p> --concepts-dir <...> --repo-root <...> --touches "$TOUCHES"`
   → 得 weighted_concept_cost / blast_radius / impacted_repos / highest_tier_touched / unknown_redefines。

4. **补工期估算(你的判断,诚实标注):** 给 est_impl_days / est_debt_weeks,**必带 confidence + "这是估算"**,
   不谎报精度(§6.3)。相对排序比绝对数值重要(深审 M-estimate)。

5. **组装中性报告并呈给用户:** 摆出成本画像 + 你的工期估算。**绝不说"该做/不该做"**
   (说话人2:Marshal 不知道你的预算,不替你决定)。只呈"这些改动触及最高 X 级、加权成本 N、
   会波及 [blast_radius]、你可能要 D 天 + 未来 W 周还债——你自己判断值不值"。

## 铁律
- **中性**:verdict 恒 cost-only;不含 go/no-go。
- **诚实分离**:确定的成本(CLI)与 agent 的工期猜测(你)分开标注,别混成一个"精确数字"。
- **hinted_cost 是你标的、可被玩弄**:交叉核对——若某 `add` 的名字/描述明显对应一个大子系统
  (如 payments/banking),别标 small;`grounded_cost`(redefine)才是不可 gaming 的锚。呈报时
  **显式区分 grounded vs hinted**,别把 hinted 当既成事实。
- **unknown_redefines 非空** → 提示用户:这些概念名在树里不存在(笔误?还是其实是 add?)。

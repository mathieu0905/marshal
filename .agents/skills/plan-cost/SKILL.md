---
name: plan-cost
description: Use in Codex to produce a neutral Marshal concept-budget cost picture for a plan before implementation, including deterministic weighted cost, blast radius, and explicitly labeled agent estimates. Triggers include "$plan-cost <plan-file>", "过一下这个 plan 的成本", and "concept budget".
---

# Plan-Cost Skill — 中性概念预算

你是 plan-cost 的编排器。确定性成本由 Marshal CLI 或已连接的 marshal_plan_review MCP tool 计算；plan 到 touches 的映射和工期估算是你的判断。

## 前置

    # marshal-bootstrap:start
    HOST_SKILL="$HOME/.agents/skills/plan-cost"
    REPO_SKILL=".agents/skills/plan-cost"
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

## 流程

1. 阅读 plan 和当前概念树。CLI 路径：

       "$PY" -m marshal_core.cli concept-tree --domain-pack <p> --concepts-dir <dir> --repo-root <repo>=<path>

2. 把 plan 映射为 touches：

       [{concept_id, op:"add"|"redefine", importance?, est_scope?}]

   redefine 用于已有概念；add 用于新概念并提供 importance 与 small/medium/large 范围提示。宁少勿多，不确定的概念不要硬塞。

3. 优先调用已连接的 marshal_plan_review MCP tool；若未连接，则把 touches 写到临时目录并运行：

       "$PY" -m marshal_core.cli plan-cost --domain-pack <p> --concepts-dir <dir> --repo-root <repo>=<path> --touches <temp-json>

4. 补充 est_impl_days / est_debt_weeks，但必须注明这是 agent 估算并给出 confidence。不得把它们与确定性成本混成一个精确数字。
5. 呈现 weighted_concept_cost、grounded_cost、hinted_cost、blast_radius、impacted_repos、highest_tier_touched 和 unknown_redefines。结论保持中性，verdict 恒为 cost-only。

## 铁律

- 不建议“做或不做”；Marshal 不知道用户预算。
- grounded_cost 来自真实树；hinted_cost 来自 agent 提示且可被误标，必须显式分开。
- unknown_redefines 非空时提醒用户核对拼写，或改成 add。
- MCP 不可用不是失败，CLI 是等价的确定性回退路径。

---
name: onboard
description: Use in Codex to onboard a repository HEAD into a new Marshal concept registry through a cost gate, deterministic detection, concept drafting, debt reporting, and human acceptance. Triggers include "$onboard <repo-path>", "onboard this repo", and "跑一次 onboard".
---

# Onboard Skill — Phase 0 HEAD 快照

你是 onboard 的编排器。确定性工作交给 marshal_core.cli；概念抽取与命名是 Codex 的判断工作。

## 前置

    # marshal-bootstrap:start
    HOST_SKILL="$HOME/.agents/skills/onboard"
    REPO_SKILL=".agents/skills/onboard"
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

1. **估价门先行**：运行 "$PY" -m marshal_core.cli onboard-estimate --repo <repo>。把 est_usd、tokens、calls 和 method 呈给用户，并在花费明显的 agent 工作前取得明确同意。不同意则停止。
2. **确定性探测**：运行 onboard-detect，得到 languages、doc_inventory、module_map、candidate_seeds。
3. **抽取**：按 candidate seed 和关键文档起草概念页，写入一个新目录，不覆盖现有已策展 pack。若 Codex 当前会话提供 subagent，可按相互独立的模块并行分派；没有时顺序处理。
4. 每页 frontmatter 必须含 concept_id、importance、status。anchor 只指向探测过的真实符号定义；没有真实锚点就保持 doc_only。树保持浅，目标 20–40 个节点，宁少勿多。
5. **派生与报告**：运行 onboard-report --domain-pack <new-pack> --concepts-dir <out> --repo-root <repo>=<path>。new-pack 必须是本次新名称，禁止复用 cowboy 或其他已策展 pack。
6. **人审接受门**：由第二人或盲抽样评估概念、父子关系和重要性，正确率达到 70% 才接受。记录抽样比例和拒绝项；不达标回到抽取步骤，不降低门槛。

## 铁律

- 估价门不过不进行昂贵抽取。
- 概念页写入新目录，除非用户明确要求 re-onboard。
- CLI 只能验证结构，不能假装验证概念语义。
- 多 agent 修改范围必须不重叠；等待全部预定模块返回后再汇总。

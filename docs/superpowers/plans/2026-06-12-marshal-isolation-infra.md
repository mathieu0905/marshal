# Marshal 隔离基建(阶段 0–3)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 marshal 能在不中断日常 `/marshal` gate 的前提下做重构级升级——冻结一份稳定版供日常用,隔离一条 dev 通道供重构,并用金标语料回归做"行为不变"的客观验收闸。

**Architecture:** 两份独立 marshal home——稳定版(`~/marshal-stable`,冻结 tag 的独立 clone + 独立 venv + 权威 db,`/marshal` 指向它)与 dev 通道(git worktree + 独立 venv + 独立 db,`/marshal-dev` 指向它),靠 `MARSHAL_HOME`/`MARSHAL_DB` 两个 env 切。金标语料 = 一批历史 PR 的冻结输入 + 稳定版录制的输出快照,`pytest` 回放比对。db 移出版本库消除二进制噪音。本计划只做基建(阶段 0–3);实际重构(阶段 4)是另一份载荷 spec。

**Tech Stack:** Python 3.12 / pytest / SQLAlchemy(单文件 sqlite)/ git worktree / Claude Code skills(符号链接);`gh` CLI(录制语料时拉 PR diff)。

**设计依据:** `docs/superpowers/specs/2026-06-12-marshal-refactor-isolation-design.md`

**与设计文档的偏离(已采纳的简化):**
- 设计 §10 阶段1 原计划"扩 `cli setup --name marshal-dev`"。本计划改为**直接手工生成** `~/.claude/skills/marshal-dev/`,不动生产 CLI——更 YAGNI、零仓库污染、切换时秒删。

**前置约定(全计划通用路径):**
- 主仓库:`/home/ubuntu/workspace/marshal`(当前 `main` @ `ba14502`)
- 稳定版:`/home/ubuntu/marshal-stable`
- dev worktree:`/home/ubuntu/workspace/marshal/.claude/worktrees/refactor-isolation`(`.gitignore` 已含 `.claude/worktrees/`)
- dev 分支:`refactor/isolation`
- venv python:`python3.12`(系统已装 3.12.3)
- ⚠️ **危险动作**(重指 prod skill 软链)集中在 Task 0.4,执行到那一步前必须先验证稳定版可用(Task 0.3),且该步**自带回退命令**。

---

## File Structure

本计划新建/修改的文件:

| 路径 | 责任 |
|---|---|
| `/home/ubuntu/marshal-stable/`(新 clone) | 冻结的生产部署;`/marshal` 的真实后端 |
| `/home/ubuntu/marshal-stable/.claude/skills/marshal/SKILL.md`(本地改 1 行) | 把 `MARSHAL_HOME` 默认指向自身 |
| `~/.claude/skills/marshal-dev/SKILL.md`(新,仓外) | dev skill;硬编 dev `MARSHAL_HOME`/`MARSHAL_DB`/name |
| `src/marshal_core/config.py`(新) | 单一 db-url 解析(`db_url()`),供 cli.py + api.py 共用 |
| `src/marshal_core/cli.py`(改) | `_db_url()` 改为转调 `config.db_url()` |
| `src/marshal_core/adapters/api.py`(改) | db 引擎默认改走 `config.db_url()`,消除 cwd 相对路径坑 |
| `tests/test_config.py`(新) | `config.db_url()` 单元测试 |
| `tests/golden/cases/*.json`(新,录制产出) | 每条历史 PR 的冻结输入 + 稳定版输出快照 |
| `tests/golden/record.py`(新) | 录制工具:拉 PR diff → 跑稳定版 CLI → 写 case |
| `tests/test_golden_corpus.py`(新) | 回放每个 case,断言当前 CLI 输出 == 快照 |
| `.gitignore`(改) | 加 `marshal.db`、`marshal-dev.db` |

---

## 阶段 0 — 冻结 prod(可回退基线就位)

### Task 0.1：给当前 main 打冻结 tag

**Files:**
- 无文件改动(纯 git)

- [ ] **Step 1：打 tag**

```bash
cd /home/ubuntu/workspace/marshal
git tag prod-stable-2026-06-12 ba14502
```

- [ ] **Step 2：验证 tag 指向正确 commit**

Run: `git rev-parse prod-stable-2026-06-12`
Expected: 输出 `ba14502...`(与 `git rev-parse HEAD` 一致)

### Task 0.2：建稳定版独立 clone + venv + 权威 db

**Files:**
- Create: `/home/ubuntu/marshal-stable/`(整目录)

- [ ] **Step 1：从本地仓库 clone 出冻结副本**

```bash
git clone /home/ubuntu/workspace/marshal /home/ubuntu/marshal-stable
cd /home/ubuntu/marshal-stable
git checkout prod-stable-2026-06-12
```

- [ ] **Step 2：建独立 venv 并 editable 安装**

```bash
cd /home/ubuntu/marshal-stable
python3.12 -m venv .venv
.venv/bin/pip install -q -e '.[ci]'
```

Expected: 安装无报错(`.[ci]` 带 zizmor,保 CI gate 不降级)

- [ ] **Step 3：把"活的"权威 marshal.db 复制进稳定版**

clone 带来的是 tag 时刻的 db;权威知识核(最新不变量/棘轮历史)是主仓工作树里那份。覆盖之:

```bash
cp /home/ubuntu/workspace/marshal/marshal.db /home/ubuntu/marshal-stable/marshal.db
```

- [ ] **Step 4：验证稳定版 CLI 自洽**

Run:
```bash
cd /home/ubuntu/marshal-stable
MARSHAL_HOME=/home/ubuntu/marshal-stable .venv/bin/python -m marshal_core.cli metrics
```
Expected: 打印 JSON,`invariants` 数 > 0(与主仓 `metrics` 一致,证明权威 db 带过来了)

### Task 0.3：让稳定版 skill 默认指向自身

稳定版 clone 的 `SKILL.md` 仍硬编旧路径 `/home/ubuntu/workspace/marshal`。改成指向自身,这样 `/marshal`(不带 env)就跑稳定版。

**Files:**
- Modify: `/home/ubuntu/marshal-stable/.claude/skills/marshal/SKILL.md`(第 14 行附近)

- [ ] **Step 1：改 MARSHAL_HOME 默认值**

把该文件里这一行:
```
    MARSHAL_HOME=${MARSHAL_HOME:-/home/ubuntu/workspace/marshal}
```
改为:
```
    MARSHAL_HOME=${MARSHAL_HOME:-/home/ubuntu/marshal-stable}
```

- [ ] **Step 2:验证稳定版 skill 自检命令用自身路径能跑**

Run:
```bash
MARSHAL_HOME=/home/ubuntu/marshal-stable \
  /home/ubuntu/marshal-stable/.venv/bin/python -m marshal_core.cli classify --repo node --paths README.md
```
Expected: `{"tier": "low", ...}`(无报错)

### Task 0.4:⚠️ 重指 prod skill 软链到稳定版(危险动作,自带回退)

**Files:**
- Modify: `~/.claude/skills/marshal`(符号链接目标)

- [ ] **Step 1:记录当前软链目标(回退用)**

Run: `readlink ~/.claude/skills/marshal`
Expected: 当前指向 `/home/ubuntu/workspace/marshal/.claude/skills/marshal`(记下来)

- [ ] **Step 2:重指到稳定版**

```bash
ln -sfn /home/ubuntu/marshal-stable/.claude/skills/marshal ~/.claude/skills/marshal
```

- [ ] **Step 3:验证软链已切**

Run: `readlink ~/.claude/skills/marshal`
Expected: `/home/ubuntu/marshal-stable/.claude/skills/marshal`

- [ ] **Step 4:回退命令(若稳定版有任何问题,立即执行恢复原状)**

```bash
# 回退:指回主仓
ln -sfn /home/ubuntu/workspace/marshal/.claude/skills/marshal ~/.claude/skills/marshal
```
(此步不执行,仅作为出问题时的逃生口记录在案。)

- [ ] **Step 5:人工冒烟(执行者请在新的 Claude Code 对话里实测)**

在新对话跑 `/marshal`(当前分支 diff,或 `/marshal node <某真实PR#>`),确认产出正常 GateDecision。
**这是阶段 0 的验收点:`/marshal` 走稳定版且行为如常。** 不过则用 Step 4 回退并排查。

---

## 阶段 1 — 建 dev 通道(隔离的重构工作区)

### Task 1.1:建 dev worktree + 分支 + venv + 独立 db

**Files:**
- Create: `/home/ubuntu/workspace/marshal/.claude/worktrees/refactor-isolation/`(worktree)

- [ ] **Step 1:建 worktree + 分支**

```bash
cd /home/ubuntu/workspace/marshal
git worktree add .claude/worktrees/refactor-isolation -b refactor/isolation
```

- [ ] **Step 2:验证 worktree 就位**

Run: `git worktree list`
Expected: 两行,含 `.../refactor-isolation  ... [refactor/isolation]`

- [ ] **Step 3:dev venv + editable 安装**

```bash
cd /home/ubuntu/workspace/marshal/.claude/worktrees/refactor-isolation
python3.12 -m venv .venv
.venv/bin/pip install -q -e '.[dev,ci]'
```
Expected: 无报错(`dev` 带 pytest/ruff)

- [ ] **Step 4:建独立 dev db(从稳定版权威 db 复制)**

```bash
cp /home/ubuntu/marshal-stable/marshal.db \
   /home/ubuntu/workspace/marshal/.claude/worktrees/refactor-isolation/marshal-dev.db
```

- [ ] **Step 5:验证 dev CLI 用独立 db 能跑**

Run:
```bash
cd /home/ubuntu/workspace/marshal/.claude/worktrees/refactor-isolation
MARSHAL_DB="sqlite:///$PWD/marshal-dev.db" .venv/bin/python -m marshal_core.cli metrics
```
Expected: JSON,`invariants` 数 > 0

### Task 1.2:手工生成 dev skill(仓外,零污染)

直接在 `~/.claude/skills/marshal-dev/` 造一份独立 skill:复制 worktree 的 SKILL.md,改 3 处(name、MARSHAL_HOME、注入 MARSHAL_DB),references 仍指向 worktree。

**Files:**
- Create: `~/.claude/skills/marshal-dev/SKILL.md`

- [ ] **Step 1:复制并改造**

```bash
WT=/home/ubuntu/workspace/marshal/.claude/worktrees/refactor-isolation
mkdir -p ~/.claude/skills/marshal-dev
cp "$WT/.claude/skills/marshal/SKILL.md" ~/.claude/skills/marshal-dev/SKILL.md

# 改 frontmatter name: marshal → marshal-dev
sed -i '0,/^name: marshal$/s//name: marshal-dev/' ~/.claude/skills/marshal-dev/SKILL.md
# 改触发词 "/marshal" → "/marshal-dev"(仅 description 行的触发器)
sed -i 's#"/marshal"#"/marshal-dev"#g' ~/.claude/skills/marshal-dev/SKILL.md
# MARSHAL_HOME 默认指向 worktree
sed -i "s#MARSHAL_HOME:-/home/ubuntu/workspace/marshal}#MARSHAL_HOME:-$WT}#" ~/.claude/skills/marshal-dev/SKILL.md
```

- [ ] **Step 2:在 dev SKILL.md 的自检段注入独立 MARSHAL_DB**

手工编辑 `~/.claude/skills/marshal-dev/SKILL.md`,在 `PY="$MARSHAL_HOME/.venv/bin/python"` 行**下面**加一行(让 dev 所有 CLI 调用走 dev db):
```
    export MARSHAL_DB="sqlite:///$MARSHAL_HOME/marshal-dev.db"
```

- [ ] **Step 3:让 references 解析到 worktree**

确认 dev SKILL.md 内引用 references 的相对路径仍能定位(它们走 `$MARSHAL_HOME/.claude/skills/marshal/references/...`,而 `$MARSHAL_HOME` 已是 worktree,worktree 自带 `.claude/skills/marshal/references/`)。
Run: `ls /home/ubuntu/workspace/marshal/.claude/worktrees/refactor-isolation/.claude/skills/marshal/references/`
Expected: 列出 `gate-flow.md`、`ratchet-flow.md` 等

- [ ] **Step 4:验收 — dev 与 prod 完全独立**

在新 Claude Code 对话:
1. 跑 `/marshal-dev node <某真实PR#>` → 命中 dev venv/db,正常出 GateDecision。
2. 在 worktree 里改一行 dev 代码(如 classifier 加个无害注释),`/marshal`(不带 dev)输出**不变**;`/marshal-dev` 走改动后的代码。
**这是阶段 1 验收点。**

---

## 阶段 2 — 金标语料回归(验收闸)

> 全部在 dev worktree 内开发。先做确定性层(可精确 diff、自动化)。判断层(重跑 skill 比对 verdict)是人工抽样流程,见 Task 2.4。

### Task 2.1:定 case schema + 候选 PR 清单

**Files:**
- Create: `tests/golden/README.md`(说明 schema)
- Create: `tests/golden/fixtures.json`(候选 PR 清单)

- [ ] **Step 1:写 schema 说明**

创建 `tests/golden/README.md`:
````markdown
# 金标语料(golden corpus)

每个 case = 一条历史 PR 的**冻结输入** + **稳定版录制的 CLI 输出**。
回放(`test_golden_corpus.py`)用冻结输入跑当前 CLI,断言输出逐字 == 快照。

case 文件 `cases/<repo>-<pr>.json`:
```json
{
  "repo": "node",
  "pr": 660,
  "head_oid": "<PR head 提交>",
  "input": { "paths": ["..."], "diff_text": "<冻结 diff>", "labels": [] },
  "golden": {
    "classify": { "tier": "...", "reasons": [], "contracts_hit": [], "...": "..." },
    "invariants": { "...": "..." }
  }
}
```
有意改动:某 case 的输出在新版应当变化时,在 case 加 `"expected_change": "<原因>"`,
回放跳过该 case 并打印说明(见 test_golden_corpus.py)。
````

- [ ] **Step 2:列候选 PR(8–12 条,覆盖不同判决路径)**

创建 `tests/golden/fixtures.json`:
```json
[
  {"repo": "node", "pr": 599, "note": "假阳 retract 案例"},
  {"repo": "node", "pr": 646, "note": "Message codec trailing-key"},
  {"repo": "node", "pr": 649, "note": "CI 安全 self-hosted-runner"},
  {"repo": "node", "pr": 660, "note": "Almanax 核对差距"},
  {"repo": "node", "pr": 665, "note": "reflection guard 绕过"},
  {"repo": "node", "pr": 651, "note": "PVM entrypoint 共识回归"},
  {"repo": "node", "pr": 630, "note": "CIP-12 opcode 撞号"},
  {"repo": "node", "pr": 681, "note": "ManifestCommitted 事件入 receipt_root"},
  {"repo": "node", "pr": 677, "note": "FSM stdlib lenient"},
  {"repo": "runner", "pr": 92, "note": "SemanticSimilarity 闭环"}
]
```
（执行者可按 `gh` 可达性增删;目标 ≥8 条、含至少 1 个 block / 1 个 needs_human / 1 个 pass 路径。）

- [ ] **Step 3:提交**

```bash
cd /home/ubuntu/workspace/marshal/.claude/worktrees/refactor-isolation
git add tests/golden/README.md tests/golden/fixtures.json
git commit -m "test(golden): corpus schema + candidate PR fixtures"
```

### Task 2.2:写录制工具 record.py

**Files:**
- Create: `tests/golden/record.py`

- [ ] **Step 1:写 record.py**

创建 `tests/golden/record.py`:
```python
"""录制金标语料:对 fixtures.json 每条 PR,拉冻结 diff,跑稳定版 CLI,写 cases/<repo>-<pr>.json。

用法(在 dev worktree):
    STABLE_PY=/home/ubuntu/marshal-stable/.venv/bin/python \
    python tests/golden/record.py
需要 gh 已认证、能访问 cowboyinc/<repo>。
"""
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = HERE / "cases"
STABLE_PY = os.environ.get("STABLE_PY", "/home/ubuntu/marshal-stable/.venv/bin/python")
STABLE_HOME = "/home/ubuntu/marshal-stable"


def _gh(args: list[str]) -> str:
    return subprocess.run(args, capture_output=True, text=True, check=True).stdout


def _cli(subcmd: list[str]) -> dict:
    # 用稳定版录制,绝对 MARSHAL_HOME,只读不写本地 gate_run 的命令(classify/invariants)
    env = {**os.environ, "MARSHAL_HOME": STABLE_HOME}
    out = subprocess.run([STABLE_PY, "-m", "marshal_core.cli", *subcmd],
                         capture_output=True, text=True, check=True, env=env).stdout
    return json.loads(out)


def record_one(fx: dict) -> None:
    repo, pr = fx["repo"], fx["pr"]
    R = f"cowboyinc/{repo}"
    head_oid = _gh(["gh", "pr", "view", str(pr), "-R", R,
                    "--json", "headRefOid", "-q", ".headRefOid"]).strip()
    paths = [p for p in _gh(["gh", "pr", "diff", str(pr), "-R", R,
                             "--name-only"]).splitlines() if p]
    diff_text = _gh(["gh", "pr", "diff", str(pr), "-R", R])
    inp = {"paths": paths, "diff_text": diff_text, "labels": []}
    classify = _cli(["classify", "--repo", repo, "--paths", *paths,
                     "--diff-text", diff_text])
    invariants = _cli(["invariants", "--repo", repo, "--paths", *paths])
    case = {"repo": repo, "pr": pr, "head_oid": head_oid, "input": inp,
            "golden": {"classify": classify, "invariants": invariants}}
    CASES.mkdir(exist_ok=True)
    out = CASES / f"{repo}-{pr}.json"
    out.write_text(json.dumps(case, ensure_ascii=False, indent=2))
    print(f"recorded {out.name}: tier={classify.get('tier')}")


def main() -> int:
    fixtures = json.loads((HERE / "fixtures.json").read_text())
    for fx in fixtures:
        try:
            record_one(fx)
        except subprocess.CalledProcessError as e:
            print(f"SKIP {fx['repo']}#{fx['pr']}: {e.stderr[:200]}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2:确认稳定版 `invariants` 子命令签名匹配 record.py 的调用**

Run: `/home/ubuntu/marshal-stable/.venv/bin/python -m marshal_core.cli invariants --help`
Expected: 接受 `--repo` 和 `--paths`。若签名不同,改 record.py 的 `_cli(["invariants", ...])` 对齐(不要改生产 CLI)。

- [ ] **Step 3:提交工具**

```bash
git add tests/golden/record.py
git commit -m "test(golden): recorder pulls PR diff + records stable CLI output"
```

### Task 2.3:写回放测试 + 录制 + 锁定

**Files:**
- Create: `tests/test_golden_corpus.py`
- Create: `tests/golden/cases/*.json`(录制产出)

- [ ] **Step 1:先写回放测试(此时还没 case,应当 0 收集或 skip)**

创建 `tests/test_golden_corpus.py`:
```python
"""金标语料回放:用冻结输入跑当前 CLI,断言输出 == 稳定版录制的快照。

跨版本回归网——重构后新版必须复现稳定版判决(确定性层)。
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

CASES = sorted((Path(__file__).parent / "golden" / "cases").glob("*.json"))


def _cli(subcmd: list[str]) -> dict:
    out = subprocess.run([sys.executable, "-m", "marshal_core.cli", *subcmd],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


@pytest.mark.parametrize("case_path", CASES, ids=[p.stem for p in CASES])
def test_golden_reproduces(case_path):
    case = json.loads(case_path.read_text())
    if "expected_change" in case:
        pytest.skip(f"有意改动: {case['expected_change']}")
    repo = case["repo"]
    inp = case["input"]
    got_classify = _cli(["classify", "--repo", repo, "--paths", *inp["paths"],
                         "--diff-text", inp["diff_text"]])
    assert got_classify == case["golden"]["classify"], \
        f"{case_path.stem}: classify 输出漂移(非有意改动)"
    got_inv = _cli(["invariants", "--repo", repo, "--paths", *inp["paths"]])
    assert got_inv == case["golden"]["invariants"], \
        f"{case_path.stem}: invariants 输出漂移(非有意改动)"
```

- [ ] **Step 2:跑空套件,确认无收集错误**

Run: `cd <worktree> && .venv/bin/python -m pytest tests/test_golden_corpus.py -q`
Expected: `no tests ran`(cases 还没录)——无 import/collection 错误

- [ ] **Step 3:录制 cases(需 gh 认证 + 网络)**

```bash
cd /home/ubuntu/workspace/marshal/.claude/worktrees/refactor-isolation
STABLE_PY=/home/ubuntu/marshal-stable/.venv/bin/python \
  .venv/bin/python tests/golden/record.py
```
Expected: 每条 fixture 打印 `recorded node-660.json: tier=...`;`tests/golden/cases/` 出现 ≥8 个 json。

- [ ] **Step 4:回放,确认稳定版录的快照在稳定版上 100% 绿(自洽性)**

把语料 + 测试复制到稳定版,用稳定版自身回放(录制环境=回放环境,必须 100% 自洽):
```bash
STABLE=/home/ubuntu/marshal-stable
mkdir -p "$STABLE/tests/golden"
cp tests/test_golden_corpus.py "$STABLE/tests/"
cp -r tests/golden/cases "$STABLE/tests/golden/"
"$STABLE/.venv/bin/python" -m pytest "$STABLE/tests/test_golden_corpus.py" -q
```
Expected: 全 PASS。若有 fail,说明 classify/invariants 输出含非确定字段(时间戳/顺序),需在 record.py 录制前剔除该字段后重录。
（自洽校验后可删掉稳定版里这两份临时拷贝:`rm -rf "$STABLE/tests/golden" "$STABLE/tests/test_golden_corpus.py"`)

- [ ] **Step 5:在 dev worktree 回放(当前=dev 代码,此刻应等于稳定版 → 全绿)**

Run: `cd <worktree> && .venv/bin/python -m pytest tests/test_golden_corpus.py -q`
Expected: 全 PASS(dev 尚未重构,行为=稳定版)

- [ ] **Step 6:提交语料 + 测试**

```bash
git add tests/test_golden_corpus.py tests/golden/cases
git commit -m "test(golden): record corpus from stable + replay regression net"
```

### Task 2.4:判断层抽样比对(人工流程,文档化)

**Files:**
- Create: `tests/golden/JUDGMENT_LAYER.md`

- [ ] **Step 1:写判断层流程文档**

创建 `tests/golden/JUDGMENT_LAYER.md`:
````markdown
# 判断层抽样(verdict 复现)

确定性层(test_golden_corpus.py)只覆盖纯 CLI。最终 `GateDecision`(verdict /
needs_human / 对抗 review 结论)来自 Claude 编排器,无法逐字快照,故用人工抽样:

**何时跑:** 每个重构里程碑节点 + 切换前(cutover gate)。
**抽样:** 从 fixtures.json 取 ≥4 条(至少含 1 block、1 needs_human、1 pass)。
**流程:**
1. 对每条 PR:`/marshal <repo> <pr#>`(稳定)与 `/marshal-dev <repo> <pr#>`(dev)各跑一遍。
2. 记录两侧 verdict + 触发的不变量集合到下表。
3. **通过标准:verdict 等价。** 若 dev verdict 不同 → 必须人工判定是"改进"(可接受)
   还是"回归"(不可接受,阻断切换)。表述差异不算回归,结论降级才算。

| PR | stable verdict | dev verdict | 不变量集差异 | 结论(改进/回归/等价) |
|----|----------------|-------------|--------------|------------------------|
| node#660 | | | | |
| ... | | | | |
````

- [ ] **Step 2:提交**

```bash
git add tests/golden/JUDGMENT_LAYER.md
git commit -m "docs(golden): judgment-layer sampling procedure for verdict reproduction"
```

---

## 阶段 3 — DB 解耦(消除二进制噪音 + 填 cwd 老坑)

### Task 3.1:把 db-url 解析收敛到单一 config 模块(TDD)

`cli.py` 有正确的绝对路径解析(`_db_url`);`adapters/api.py:15` 却用 cwd 相对 `sqlite:///marshal.db`(老坑:测试副作用曾清零仓库根 db)。抽出共享 `config.db_url()`,两处共用。

**Files:**
- Create: `src/marshal_core/config.py`
- Create: `tests/test_config.py`
- Modify: `src/marshal_core/cli.py:23-33`(`_marshal_home`/`_db_url`)
- Modify: `src/marshal_core/adapters/api.py:15`

- [ ] **Step 1:写失败测试**

创建 `tests/test_config.py`:
```python
import os
from pathlib import Path

from marshal_core.config import marshal_home, db_url


def test_db_url_honors_explicit_env(monkeypatch):
    monkeypatch.setenv("MARSHAL_DB", "sqlite:////tmp/explicit.db")
    assert db_url() == "sqlite:////tmp/explicit.db"


def test_db_url_is_absolute_under_home_when_unset(monkeypatch, tmp_path):
    monkeypatch.delenv("MARSHAL_DB", raising=False)
    monkeypatch.setenv("MARSHAL_HOME", str(tmp_path))
    url = db_url()
    # 绝对路径(在 MARSHAL_HOME 下),非 cwd 相对的 "sqlite:///marshal.db"
    assert url == f"sqlite:///{tmp_path / 'marshal.db'}"
    assert url.startswith("sqlite:////")  # 四斜杠 = 绝对路径前缀(tmp_path 以 / 开头)


def test_marshal_home_env_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("MARSHAL_HOME", str(tmp_path))
    assert marshal_home() == tmp_path
```

- [ ] **Step 2:跑测试,确认失败**

Run: `cd <worktree> && .venv/bin/python -m pytest tests/test_config.py -q`
Expected: FAIL（`ModuleNotFoundError: marshal_core.config`)

- [ ] **Step 3:写 config.py**

创建 `src/marshal_core/config.py`:
```python
"""单一 db/home 解析,供 cli 与 api 共用。db 路径恒为绝对 $MARSHAL_HOME/marshal.db,与 cwd 无关。"""
import os
from pathlib import Path


def marshal_home() -> Path:
    env = os.environ.get("MARSHAL_HOME")
    if env:
        return Path(env)
    # config.py 在 <home>/src/marshal_core/config.py
    return Path(__file__).resolve().parents[2]


def db_url() -> str:
    explicit = os.environ.get("MARSHAL_DB")
    if explicit:
        return explicit
    return f"sqlite:///{marshal_home() / 'marshal.db'}"
```

- [ ] **Step 4:跑测试,确认通过**

Run: `cd <worktree> && .venv/bin/python -m pytest tests/test_config.py -q`
Expected: 3 passed

- [ ] **Step 5:cli.py 改为转调 config(不改行为)**

在 `src/marshal_core/cli.py`,把现有 `_marshal_home`/`_db_url` 两个函数体替换为转调:
```python
from marshal_core.config import marshal_home as _marshal_home, db_url as _db_url
```
并删除原来 `def _marshal_home()` / `def _db_url()` 两个定义(第 23–33 行)。保留所有调用点 `_marshal_home()`/`_db_url()` 不变。

- [ ] **Step 6:api.py 默认改走 config(填 cwd 坑)**

在 `src/marshal_core/adapters/api.py`,把:
```python
_engine = create_engine(os.environ.get("MARSHAL_DB", "sqlite:///marshal.db"))
```
改为:
```python
from marshal_core.config import db_url
_engine = create_engine(db_url())
```
（`import os` 若不再被 api.py 其它处使用则一并删除——先 grep 确认。）

- [ ] **Step 7:全套件回归(确认零行为变化)**

Run: `cd <worktree> && .venv/bin/python -m pytest -q && .venv/bin/python -m ruff check src tests`
Expected: 与基线同样的 114 passed(+新增 test_config 3 条 + golden N 条),唯一已知 fail 仍是 `test_system_actor_addrmap`(先前就有,与本改无关);ruff 绿

- [ ] **Step 8:提交**

```bash
git add src/marshal_core/config.py tests/test_config.py src/marshal_core/cli.py src/marshal_core/adapters/api.py
git commit -m "refactor: single db_url() source; fix api.py cwd-relative MARSHAL_DB default"
```

### Task 3.2:把 marshal.db 移出版本库

**Files:**
- Modify: `.gitignore`
- 删除追踪:`marshal.db`

- [ ] **Step 1:确认 db 当前被追踪**

Run: `git ls-files --error-unmatch marshal.db && echo TRACKED`
Expected: `TRACKED`

- [ ] **Step 2:停止追踪(保留本地文件)**

```bash
cd /home/ubuntu/workspace/marshal/.claude/worktrees/refactor-isolation
git rm --cached marshal.db
```

- [ ] **Step 3:gitignore db 文件**

在 `.gitignore` 追加两行:
```
marshal.db
marshal-dev.db
```

- [ ] **Step 4:确认 db 不再出现在 git status 的追踪改动里**

Run: `git status --short marshal.db marshal-dev.db`
Expected: 空(被 ignore;`marshal.db` 显示为 `D`(staged 删除追踪)是预期)

- [ ] **Step 5:提交**

```bash
git add .gitignore
git commit -m "chore: untrack marshal.db (local-only state); stop binary-diff noise commits"
```

- [ ] **Step 6:记录后续(非本计划范围)**

阶段 3 完成后,主仓那个"自动提交 marshal.db"的仓外进程应当**停掉**(db 已 ignore,它将无可提交;若它仍硬 `git add -f` 需另查)。在切换(阶段 5)合并本分支到 main 后,该噪音源终结。把此条记入切换清单。

---

## 阶段 0–3 完成验收(对照设计 §9)

- [ ] `/marshal` 走稳定版、行为=冻结版(Task 0.4 Step 5 已验,随机抽 3 个真实 PR 复验)
- [ ] `/marshal-dev` 与 `/marshal` 完全独立(Task 1.2 Step 4 已验)
- [ ] `tests/golden/` 语料存在,`test_golden_corpus.py` 在稳定版 100% 绿(Task 2.3 Step 4)
- [ ] `marshal.db` 不再 TRACKED(Task 3.2)
- [ ] `config.db_url()` 单源、api.py cwd 坑已填(Task 3.1)
- [ ] 回退演练:执行 Task 0.4 Step 4 的回退命令能一键回到冻结版(切换前再演练一次)

> 阶段 4(实际 core/DomainPack 解耦重构)与阶段 5(切换/回退)是后续 spec,不在本计划内。本计划交付"安全重构所需的全部基建 + 验收闸"。

---

## Self-Review 记录

- **Spec 覆盖:** 设计 §4(隔离架构)→阶段 0+1;§5(金标语料两层)→阶段 2(2.1–2.3 确定性层 + 2.4 判断层);§6(db 解耦,4 条)→阶段 3(3.1 填 cwd 坑+单源、3.2 untrack);§8 回退→Task 0.4 Step 4 + 验收单。§7 日常工作流是运行期约定,无需建造。阶段 4/5 明确划出范围。
- **危险动作:** 仅 Task 0.4(重指 prod 软链)一处,自带回退命令 + 人工冒烟验收,且其前置(稳定版可用)已在 0.2/0.3 验证。
- **类型一致:** `config.marshal_home()`/`config.db_url()` 在 cli.py(转调)、api.py、test_config 三处签名一致;golden case schema 在 README/record.py/test 三处字段一致(`input.{paths,diff_text,labels}`、`golden.{classify,invariants}`、`expected_change`)。
- **占位符:** 无 TODO/TBD;候选 PR 清单是真实编号(来自历史判过案例),执行者按 gh 可达性微调属正常数据采集,非占位。

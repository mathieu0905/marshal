# Marshal

通用质量工程平台。Marshal 把任意项目的质量工程内容收拢为可插拔的
Domain Pack,再用确定性的 CLI、知识核和执行器把它落到合并前门禁里。
Cowboy 是当前仓库内置的第一个 Domain Pack,但不是平台本身的边界。

核心闭环:

- 风险分级: 根据 repo、diff 路径、标签和工作流全文判断变更风险。
- 不变量门禁: 从 Domain Pack 选择本次改动必须执行的检查。
- AI 对抗式 review: 聚合多视角发现,按 quorum 和 skeptic 投票裁决。
- 逃逸棘轮: 漏过的 bug 必须登记为 escape,关闭时必须生成永久检查。
- 知识核: 用 SQLite 记录不变量、escape、gate run、audit 和指标。

## 快速开始

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,ci]"
pytest -q
```

安装 Claude Code 的 `/marshal` skill:

```bash
python -m marshal_core.cli setup
```

`setup` 会把仓库内 `.claude/skills/marshal` 链接到
`~/.claude/skills/marshal`,并检查 Python import 和 `zizmor` 是否可用。

## 常用命令

所有命令都通过薄 CLI 执行,输入输出为 JSON:

```bash
python -m marshal_core.cli <command> [options]
```

| 命令 | 用途 |
|---|---|
| `classify --repo node --paths ...` | 对变更做风险分级,输出 `high` / `mid` / `low` 和 review 维度 |
| `ci-scan --paths .github/workflows/ci.yml` | 用 `zizmor` 审计 GitHub Actions 工作流;缺少工具时降级为 `needs_human` 信号 |
| `invariants --repo node --paths ...` | 列出本次变更适用的不变量和可执行命令 |
| `review-quorum --findings-json ...` | 聚合多视角 review 发现,低置信噪声会被丢弃,高危结论会升级 |
| `review-verify --votes-json ...` | 对每条发现做 skeptic 投票裁决 |
| `spec-source --ref CIP-3` | 把规格引用解析到领域源码位置 |
| `spec-requirements --ref CIP-3 --spec-root <repo>` | 从规格正文提取 RFC2119 requirement |
| `conformance [--spec-root <repo>]` | 输出规格到不变量的覆盖矩阵;带 spec root 时给出 CIP 覆盖率和缺口 |
| `ratchet-open --escape-id ... --desc ...` | 登记一次质量逃逸 |
| `ratchet-close --escape-id ... --spawned-check ... --inv-json ...` | 关闭逃逸,并注册对应永久检查 |
| `gate-record --change-ref ... --verdict pass` | 持久化一次门禁结果 |
| `metrics` | 汇总知识核中的质量指标 |
| `setup` | 安装本机 skill 链接并做基础健康检查 |

示例:

```bash
python -m marshal_core.cli classify \
  --repo node \
  --paths execution/src/execution/transaction.rs

python -m marshal_core.cli invariants \
  --repo wallet \
  --paths src/lib/cbor.js

python -m marshal_core.cli ratchet-open \
  --escape-id esc-001 \
  --desc "encoding roundtrip missed malformed CBOR" \
  --root-cause determinism-gap
```

## GitHub Action

仓库提供一个 composite action,用于被纳管 repo 在 CI 中向 Marshal brain
拉取适用不变量并回报执行结果。当前设计是影子安全模式:记录和报告,不直接阻断。

```yaml
jobs:
  marshal:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: shawhanken/marshal@main
        with:
          brain-url: https://marshal.example.com
          repo: node
```

`base-ref` 可选;不传时 action 默认比较 `HEAD~1...HEAD`。

## 仓库布局

| 路径 | 内容 |
|---|---|
| `src/marshal_core/` | 领域无关核心:CLI、契约、知识核、review 聚合、GitHub adapter、orchestrator、invariant gate、reporter |
| `src/marshal_pack_cowboy/` | Cowboy Domain Pack:风险分级规则、不变量目录、规格解析、CI 安全检查 |
| `.claude/skills/marshal/` | Claude Code `/marshal` skill 及门禁、review、conformance、ratchet 流程说明 |
| `.agents/skills/marshal/` | Codex/agents 侧同名 skill 副本 |
| `marshal.db` | 默认 SQLite 知识核 |
| `action.yml` | 被纳管 repo 使用的 GitHub composite action |
| `docs/` | 方法论、架构蓝图和实施计划 |
| `tests/` | CLI、Domain Pack、知识核、门禁、reporter、CI 安全等测试 |

## 配置

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `MARSHAL_HOME` | 当前源码仓库根目录 | 查找 `.claude/skills/marshal` 和默认数据库的位置 |
| `MARSHAL_DB` | `sqlite:///$MARSHAL_HOME/marshal.db` | SQLAlchemy 数据库 URL |

`ci-scan` 需要 `zizmor`。推荐安装 `.[ci]`;没有安装时命令会返回非零并输出
`degraded: true`,让上层门禁进入人工判断,避免假通过。

## 开发维护

```bash
pip install -e ".[dev,ci]"
pytest -q
ruff check src tests
```

README 是入口文档;更完整的方法论、架构和实施计划见
[`docs/`](docs/README.md)。

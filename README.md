# marshal

通用质量工程平台

> 核心领域无关,把任意项目的质量工程内容收拢为可插拔的领域包(Domain Pack);Cowboy 是第一个领域包。

在 Claude Code 里以 `/marshal` 提供合并前质量门禁:**风险分级 + 不变量门禁 + AI 对抗式 review + 逃逸棘轮**,并附 conformance 与 metrics 报告。

## 用法

日常:`/marshal`(当前分支 diff)· `/marshal <repo> <PR#>` · `/marshal <PR-URL>` · `/marshal conformance` · `/marshal metrics`。

`/marshal ratchet <bug>` 把漏过的 bug 上棘轮。

## 仓库布局

| 目录 | 内容 |
|---|---|
| `src/marshal_core/` | 领域无关核心:薄 CLI(skill 的确定性执行器)、知识核(SQLAlchemy)、review 聚合、平台执法层脚手架(adapters/modules/executor) |
| `src/marshal_pack_cowboy/` | 第一个领域包:Cowboy 的不变量目录、分级规则、规格解析 |
| `.claude/skills/marshal/` | `/marshal` skill(本机全量 db) |
| `marshal.db` | 知识核(不变量/逃逸登记 + gate/audit 流水) |
| `docs/` | 方法论 + 架构蓝图 |

## 维护侧

- 开发:`pip install -e .`(或 `.venv`);测试 `pytest -q`,lint `ruff check src tests`。

📖 深入文档见 [`docs/`](docs/README.md) —— 方法论(为什么)+ 架构蓝图(怎么建)。

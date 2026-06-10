# marshal

通用质量工程平台

> 核心领域无关,把任意项目的质量工程内容收拢为可插拔的领域包(Domain Pack);Cowboy 是第一个领域包。

在 Claude Code 里以 `/marshal` 提供合并前质量门禁:**风险分级 + 不变量门禁 + AI 对抗式 review + 逃逸棘轮**,并附 conformance 与 metrics 报告。

## 团队成员:安装即用

通过 Claude Code plugin 分发(只读消费,详见 [安装指南](docs/plugin-install.md) / [English](docs/plugin-install.en.md)):

```
/plugin marketplace add shawhanken/marshal
/plugin install marshal
/marshal          # 首跑自动装 uv、建环境、seed 不变量快照
```

无 GitHub 也可:解压发布 zip 后 `/plugin marketplace add <解压目录>`,或直接 `claude --plugin-dir <…>/plugins/marshal`。

日常用法:`/marshal`(当前分支 diff)· `/marshal <repo> <PR#>` · `/marshal <PR-URL>` · `/marshal conformance` · `/marshal metrics`。

> 边界:plugin 为**单向只读**——本地 `/marshal ratchet` 不回流团队;团队级不变量由维护侧统一发版,`/plugin update` 获取。

## 仓库布局

| 目录 | 内容 |
|---|---|
| `src/marshal_core/` | 领域无关核心:薄 CLI(skill 的确定性执行器)、知识核(SQLAlchemy)、review 聚合、平台执法层脚手架(adapters/modules/executor) |
| `src/marshal_pack_cowboy/` | 第一个领域包:Cowboy 的不变量目录、分级规则、规格解析 |
| `.claude/skills/marshal/` | 维护侧 skill(本机全量 db) |
| `plugins/marshal/` | **生成物**:消费侧 plugin(bundled 包 + 只读快照 + doctor 自举),由打包脚本从 `src/` 同步,勿手改 |
| `scripts/build_plugin.py` | 发版打包:导出快照 + 同步包 + uv 冒烟校验 |
| `marshal.db` | 维护侧知识核(不变量/逃逸登记 + gate/audit 流水) |
| `docs/` | 方法论 + 架构蓝图 + 安装/发版指南 |

## 维护侧

- 开发:`pip install -e .`(或 `.venv`);测试 `pytest -q`,lint `ruff check src tests scripts`。
- 发版 plugin(bump 版本 → 打包 → 推 main):见 [`docs/release-plugin.md`](docs/release-plugin.md)。

📖 深入文档见 [`docs/`](docs/README.md) —— 方法论(为什么)+ 架构蓝图(怎么建)+ 安装/发版指南。

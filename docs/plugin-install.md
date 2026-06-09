# 用上 Marshal(团队成员 · 异机只读)

    /plugin marketplace add shawhanken/marshal
    /plugin install marshal
    /marshal                 # 首次运行自动装 uv、建环境、seed 不变量快照

随后照常:`/marshal`、`/marshal <repo> <PR#>`、`/marshal <PR-URL>`。
更新不变量:`/plugin update`(维护侧发版后)。

硬前提(doctor 无法自动修复时会提示):python3 ≥ 3.11、Claude Code 版本需注入 `${CLAUDE_PLUGIN_ROOT}`。
边界:本地 `/marshal ratchet` 只进你自己的 db,不回流团队;新不变量由维护侧统一发版。

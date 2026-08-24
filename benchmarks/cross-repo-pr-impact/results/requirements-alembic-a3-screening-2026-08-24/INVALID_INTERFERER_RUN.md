# 五个干扰仓的首次 A3 批次无效

2026-08-24 首次调用 `run_requirements_a3_screening.sh` 时，脚本没有进入各目标仓工作目录，Tox 实际从 Marshal 仓库根目录解析配置并运行。因此本目录下所有以 `heat-`、`ironic-`、`keystone-`、`nova-` 和 `placement-` 开头的日志、退出状态与耗时文件均不得用于 A3 结论。

该错误批次在 `keystone after` 期间被中止，后续输出同样无效。错误表现包括退出状态为零但目标仓 `.tox` 环境不存在、无法读取实际 Alembic 版本，以及日志内容对应 Marshal 自身测试。

本目录中的 `cinder-before-*` 与 `cinder-after-*` 文件来自此前分别在 Cinder 工作目录中执行的两条独立命令，不属于上述错误批次，仍是有效的单次筛选证据。修正后的五仓批次写入新的结果目录，不覆盖本目录。

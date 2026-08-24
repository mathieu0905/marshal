# requirements 项目包 A3 五仓筛选合同

日期：2026-08-24

## 目的与层级

这是辅助筛选实验，不是正式重复。它接续原目录中已经有效完成的 Cinder A3 前后双臂，检验 Heat、Ironic、Keystone、Nova 和 Placement 在相同 Alembic 相邻发布下的定向 MySQL 模型同步命令。

零假设：Alembic 1.17.2 到 1.18.0 的变化会使至少一个固定干扰仓的原生命令失败。

备择假设：五仓前后两臂都通过，且每个 Tox 环境内实际 Alembic 版本与指定臂一致。

本轮结果只回答这些固定提交和命令是否通过，不证明 Alembic 的一般兼容性，也不能单独产生限定负标签。

## 固定输入

- 执行根目录：`/tmp/marshal-cinder-pilot.XSm5CH`；
- 约束基底：requirements `b8de3b00af9dd2ffc1a85bf836cf3c7ee9e8bac7` 的完整 `upper-constraints.txt`；
- 前臂：Alembic 1.17.2；
- 后臂：Alembic 1.18.0；
- 数据库：MariaDB 10.2.44，容器 `marshal-cinder-mariadb-20260824`，本机端口 33317；
- Python：各仓 Tox `py313` 或 `functional-py313` 环境；
- 隔离 Tox：`/tmp/marshal-cinder-pilot.XSm5CH/runner-venv/bin/tox`；
- 每条命令都以 `-r` 重建目标仓自己的 Tox 环境；
- 不重试失败命令。

固定提交、Tox 环境和测试选择由 `run_requirements_a3_screening.sh` 记录到每条结果的 `*-context.txt`。

## 执行命令

```bash
CINDER_A3_EXEC_ROOT=/tmp/marshal-cinder-pilot.XSm5CH \
CINDER_A3_TOX_RUNNER=/tmp/marshal-cinder-pilot.XSm5CH/runner-venv/bin/tox \
CINDER_A3_RESULT_ROOT=/home/zhihao/hdd/marshal/benchmarks/cross-repo-pr-impact/results/requirements-alembic-a3-screening-corrected-2026-08-24 \
benchmarks/cross-repo-pr-impact/run_requirements_a3_screening.sh
```

## 接受条件

十条命令必须同时满足：退出状态为零；实际 Alembic 版本等于对应臂；日志显示目标仓测试被执行；Tox 环境位于对应目标仓的 `.tox` 目录。任一条件不满足都先归因，不能写成仓库受 Alembic 变化影响或不受影响。

## 故障隔离

首次五仓批次因脚本未切换工作目录而无效，证据和说明保留在 `requirements-alembic-a3-screening-2026-08-24/INVALID_INTERFERER_RUN.md`。本轮使用新目录，不覆盖该批次，也不重复已经有效的 Cinder 两条命令。

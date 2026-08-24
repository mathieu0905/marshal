# Keystone 基础环境修复后重跑合同

首次真实 Keystone 前后臂都在 Tox 安装阶段失败，失败位置相同：项目声明的 `.[ldap]` 依赖构建 `python-ldap` 时找不到 `lber.h`。测试未启动，两个空的版本文件也不能证明实际 Alembic 版本。

当前账号不能安装系统包。为保持 Keystone 原生 Tox 依赖不变，本次从 Ubuntu 24.04 软件源下载 `libldap-dev` 2.6.10，并解压到 `/tmp/marshal-cinder-pilot.XSm5CH/system-deps/libldap-dev/root`。该版本与系统已安装的 `libldap2` 2.6.10 相同；临时目录提供开发头文件和未版本化链接入口，运行库仍使用系统文件。两臂使用完全相同的系统依赖修复。

只重跑 Keystone 前后两臂，不重复已经执行到测试并通过的其他八条命令。结果写入本目录下 `keystone-system-deps-retry1/`，不覆盖首次失败。

```bash
CFLAGS=-I/tmp/marshal-cinder-pilot.XSm5CH/system-deps/libldap-dev/root/usr/include \
LDFLAGS=-L/tmp/marshal-cinder-pilot.XSm5CH/system-deps/libldap-dev/root/usr/lib/x86_64-linux-gnu \
CINDER_A3_REPOS=keystone \
CINDER_A3_EXEC_ROOT=/tmp/marshal-cinder-pilot.XSm5CH \
CINDER_A3_TOX_RUNNER=/tmp/marshal-cinder-pilot.XSm5CH/runner-venv/bin/tox \
CINDER_A3_RESULT_ROOT=/home/zhihao/hdd/marshal/benchmarks/cross-repo-pr-impact/results/requirements-alembic-a3-screening-corrected-2026-08-24/keystone-system-deps-retry1 \
benchmarks/cross-repo-pr-impact/run_requirements_a3_screening.sh
```

接受条件与主筛选合同相同。若重跑通过，只能把首次失败归为缺失系统构建依赖；不能删除或改写首次失败记录。

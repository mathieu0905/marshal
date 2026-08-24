# requirements 到 Cinder 受控重放试验合同

日期：2026-08-24

## 目的

验证第二项目包的最小受控路径能否在本地重放：固定 Cinder 提交不变，只切换 requirements 在观察时点给出的完整约束文件，确认 Alembic 1.18.5 下 MySQL 模型同步测试通过、1.19.1 下同一测试以历史检查约束差异失败，再只应用维护者 Cinder 修复确认恢复。

这只是项目包准备试验，不是三次正式重复，也不产生四个干扰仓的负标签。

## 固定输入

- Cinder：`b5b763129e2bde5077c0cf3a5eb434021abaa6e0`
- A0 约束：requirements `b8de3b00af9dd2ffc1a85bf836cf3c7ee9e8bac7`，Alembic 1.18.5
- A1 约束：requirements `978799539e019141d8b0710d09bf91c956976079`，Alembic 1.19.1
- A2 修复：Cinder 变更 1000516 补丁集 3，只改 `cinder/tests/unit/db/test_migrations.py`
- 定向测试：`cinder.tests.unit.db.test_migrations.TestModelsSyncMySQL.test_models_sync`
- 运行入口：`tox -e py313 -- <测试标识>`
- Python：3.13

每个臂使用新的 Cinder 副本和新的 Tox 环境。约束文件采用对应 requirements 提交的完整 `upper-constraints.txt`，不能只在当前依赖环境里单独替换 Alembic。

## 数据库环境

使用本机已有 `mariadb:10.2` 容器建立临时数据库实例和 `openstack_citest` 管理用户，通过 `OS_TEST_DBAPI_ADMIN_CONNECTION` 把测试显式指向隔离端口。原 Zuul 节点是 Debian 13.6 在 2026-08-15 安装的发行版 MariaDB；两者版本不完全相同，因此本试验若复现失败可证明机制可迁移，若不复现则不能反推历史标签错误。

## 判定

- A0 通过且实际解析 Alembic 1.18.5，才继续 A1；
- A1 必须实际解析 Alembic 1.19.1，并出现与历史相同的 `remove_constraint`/检查约束模型差异，才继续 A2；
- A2 只应用维护者修复。若测试通过且 A1 签名消失，最小三臂路径可进入正式重复设计；
- 安装失败、数据库连接失败和测试发现失败属于环境问题，不得写成因果结果；
- 若 MariaDB 10.2 不表现该反射行为，下一步改用与 Zuul 更接近的 MariaDB 版本或原容器环境，不通过修改测试制造失败。

## 预期输出

每个臂保存完整 Tox 日志、退出状态、解析的 Alembic 版本、Cinder 提交、约束提交、数据库版本和耗时。临时数据库与工作副本不是长期证据，摘要和日志保存在本目录。

## 实测结果

三个臂均按合同执行一次且没有重试：

| 臂 | Alembic | 退出状态 | 定向测试 | 关键结果 |
|---|---:|---:|---|---|
| A0 | 1.18.5 | 0 | 通过 | 1 项通过，23.772 秒 |
| A1 | 1.19.1 | 1 | 失败 | 复现 12 个检查约束的 `remove_constraint` 差异，25.634 秒 |
| A2 | 1.19.1 | 0 | 通过 | 只应用维护者 44 行修复后，同一失败签名消失，6.181 秒 |

运行使用 Python 3.13.11、SQLAlchemy 2.0.51、PyMySQL 2.2.8 和 MariaDB 10.2.44。源侧两个完整约束文件的差异只有 Alembic 一行。机器可读结果和结论边界见 `summary.json`。

这使最小三臂路径达到可执行状态，但不把本轮升级为正式项目包：这里只有一次试验，尚无 A3，也没有对干扰仓做主动重复。

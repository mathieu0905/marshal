# Ironic Python Agent 到 Requirements 的共享依赖登记

评估日期：2026-08-24

## 当前结论

这条关系形成 **1 条链独立的高证据因果正例**：`openstack/ironic-python-agent` 把已有的 `hardware>=0.24.0` 从未受共享规则检查的 `plugin-requirements.txt` 移入 `pyproject.toml` 可选依赖后，`requirements-check` 会要求 `openstack/requirements` 登记该包。旧登记表下同一检查失败，只加入维护者在 Requirements 变更 1000669 中提交的两行登记后恢复。

结论严格限制为“跨仓共享依赖登记合同”。它不证明 `hardware` 版本在运行时破坏 Ironic Python Agent，也不证明其余 OpenStack 仓库受到运行时影响。

本包的限定负例为 **0**，A3 为 **0**。现有 13 个干扰仓没有执行目标侧的共享登记职责，不能因未出现配套修改而标成无影响。

## 源变化与目标响应

源变更 1000668 的基提交为 `ec807558924906ae902dfb14ce880e94b69402e1`，补丁集 1 为 `64c25a49ea0e7a9eba9a08d2c7f8fadba77af5f9`。代码变化只有两部分：删除 `plugin-requirements.txt` 中的 `hardware>=0.24.0`，并把相同要求加入 `pyproject.toml` 的 `extra-hardware` 可选依赖。

补丁集 2 为 `142dbd615432a10c567154789b7870789533bab6`。两个补丁集的 Git 树均为 `a7e2849ad63e0e1695e0bf485e7b7821ad4f0a26`，代码完全相同；补丁集 2 只在提交说明新增 `Depends-On: https://review.opendev.org/1000669`。因此补丁集切换只负责让 Zuul 组合目标变更，不能被解释为第二次源代码干预。

目标变更 1000669 的补丁集 2 为 `c9b6a0d3a18e212d4adb5f9c4a31e0136e97cdd6`。相对其父提交，它只执行维护者响应：

- 在 `global-requirements.txt` 加入 `hardware`；
- 在 `upper-constraints.txt` 加入 `hardware===0.32.0`。

本地 A2 把这两行精确应用到失败时的 Requirements 提交 `377f367109c44aaaefc73aa8776e314810e3ad37`，没有带入目标分支同期的其他约束更新。抽取补丁保存在 `maintainer-repair.patch`。

## 历史持续集成证据

失败和成功两臂都运行 `requirements-check`，底层任务使用 Python 3.12.3，安装当次组合中的 `openstack_requirements`，然后执行：

```text
python3 openstack/requirements/playbooks/files/project-requirements-change.py \
  openstack/ironic-python-agent master
```

历史失败构建 `d6b05d233d1b47a9b51694b4da905ab1` 只组合源补丁集 1，Requirements 保持 `377f367109c44aaaefc73aa8776e314810e3ad37`。日志确认检查进入 `extra-hardware`，随后以返回码 1 报告：

```text
Requirement(package='hardware', specifiers='>=0.24.0') not in openstack/requirements
```

历史成功构建 `d4ae4729550b426c8bc23320b05bbd94` 组合源补丁集 2 与目标补丁集 2。工作区合并清单明确记录先合并 Requirements `refs/changes/69/1000669/2`，再合并 IPA `refs/changes/68/1000668/2`。同一检查进入 `extra-hardware` 后输出 `Updated requirements match openstack/requirements.`，返回码为 0。

远程证据目录分别为：

- 失败：`https://storage.gra.cloud.ovh.net/v1/AUTH_dcaab5e32b234d56b626f72581e3644c/zuul_opendev_logs_d6b/openstack/d6b05d233d1b47a9b51694b4da905ab1/`；
- 成功：`https://storage.bhs.cloud.ovh.net/v1/AUTH_dcaab5e32b234d56b626f72581e3644c/zuul_opendev_logs_d4a/openstack/d4ae4729550b426c8bc23320b05bbd94/`。

原始 `job-output.txt`、结构化任务日志和 `workspace-repos.json` 保存在 `results/ipa-requirements-historical-2026-08-24/`。历史证据说明真实 Zuul 组合由失败转为成功；它与下面的本地因果隔离分别记录。

## 本地三臂重放

本地使用历史 Requirements 提交中的同一 `project-requirements-change.py`、Python 3.12.3 和同一 `master` 分支参数。三臂定义为：

| 臂 | 源代码 | Requirements 输入 | 结果 |
|---|---|---|---|
| A0 | `ec807558...` | `377f367...` | 通过；旧 `plugin-requirements.txt` 不进入共享规则 |
| A1 | `64c25a49...` | `377f367...` | 失败；`extra-hardware` 中的要求未登记 |
| A2 | 与 A1 完全相同 | `377f367...` 加维护者两行登记 | 通过；同一失败签名消失 |

A0、A1 和 A2 的退出方向分别为 0、1、0。A1 与 A2 使用同一个源工作树；A2 唯一输入差异是目标维护者补丁。日志、退出码、版本和实际补丁保存在 `results/ipa-requirements-local-three-arm-2026-08-24/`，重放入口为 `run_three_arm.sh`。

## 负空间与 A3

离线输入目录中的 14 个候选仓来自失败时点执行清单和同生态干扰项。除 Requirements 外的 13 仓并不承担“在共享全局表登记 IPA 新依赖”的职责，也没有在本次任务中以目标身份执行同一登记规则。运行普通单元测试、安装 `hardware`，或确认没有配套变更，都不能回答这条目标侧合同，因此全部保持未判定。

当前材料也没有独立的兼容源变化，无法构造让所有纳入仓共同观察同一真实变化的 A3。为补 A3 搜索另一条普通绿色依赖调整，会改变源输入和候选空间；本轮不这样扩张，正式保留三臂正例。

## 统计与准入边界

- 链独立因果正例：1；
- 正目标仓：1；
- 限定负例：0；
- A3：0；
- 历史持续集成对照：1 组 A1 到 A2；
- 本地受控三臂：1 组 A0、A1、A2。

现有主语义复核已经接受源要求、失败签名和目标登记之间的对应关系，但它不是独立盲审。本包可进入高证据因果正例储备；进入正式保留集前仍需由未参与构造的复核者确认标签边界。缺少限定负例和 A3 不否定三臂因果关系，但意味着本包不能单独支持误报率、停止能力或兼容变化结论。

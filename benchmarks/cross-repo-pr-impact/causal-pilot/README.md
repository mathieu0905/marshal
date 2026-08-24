# 因果旗舰轨道试采输入

本目录保存 6 条通过初次语义复核的失败到修复案例。它们用于验证旗舰轨道的输入协议和采集产率，尚未组成正式评测集。原 `causal-opendev-1001103` 经重新审查后移除：目标补丁修复的是外部 Rocky 镜像变化，不是源差异造成的破坏。历史回挖保留 2 条，滚动采集新增 4 条。

## 输入规模

| 案例 | 源仓 | 目标仓 | 候选仓数 |
|---|---|---|---:|
| `causal-opendev-999031` | `opendev/system-config` | `opendev/grafyaml` | 5 |
| `causal-opendev-1000542` | `openstack/magnum-tempest-plugin` | `openstack/magnum-capi-helm` | 26 |
| `causal-opendev-1000668` | `openstack/ironic-python-agent` | `openstack/requirements` | 14 |
| `causal-opendev-1000682` | `openstack/openstacksdk` | `openstack/python-openstackclient` | 17 |
| `causal-opendev-1001023` | `openstack/requirements` | `openstack/cinder` | 13 |
| `causal-opendev-1001168` | `openstack/neutron` | `openstack/neutron-tempest-plugin` | 11 |

共 86 个候选仓时点快照，全部可用。其中 39 个提交由失败任务的执行清单直接给出，47 个不在执行清单中的干扰仓取失败构建开始前默认分支最后提交。清单提交中包含 1 个 GitHub 托管仓库，其余为 OpenDev 仓库。

`inputs.jsonl` 和 `repository-snapshots.jsonl` 是可见输入，`labels.jsonl` 是隐藏标签。正式推理不得读取 `labels.jsonl`、成功构建、目标修复或 `../candidates/`。

### 输入可见性复核

2026-08-24 对六条 `source.patch` 的邮件格式提交说明逐条复核后发现，因果证据合格不等于检索输入合格：

- `causal-opendev-999031`、`causal-opendev-1000542` 和 `causal-opendev-1001168` 的提交说明直接包含目标变更地址或 `Depends-On`，违反离线规格，当前不能进入仓库检索分数；
- `causal-opendev-1001023` 的提交说明直接点名 Cinder，虽未泄漏目标变更，但属于必须单独披露的目标名称捷径；
- `causal-opendev-1000668` 未发现目标线索，可作为原生接口开发实测输入；
- `causal-opendev-1000682` 只引用了非目标仓 `neutron-lib`，未泄漏标注目标。

逐例记录见 `input-visibility-audit.jsonl`。正式输入应统一提供代码差异而非邮件格式提交包络，不能只对命中答案的三条做临时字符串删除。上述三条仍保留为强因果证据储备，但在输入转换完成并重新审计前不参与检索评测。

## 时间语义

观察截止时间固定为失败构建开始时间。源差异使用失败臂的源补丁集；若候选仓出现在失败执行清单中，输入采用该任务实际检出的提交，而不是事后按默认分支回溯。目标修复提交只保存在隐藏标签和证据记录中。

## 审计与展开

`audit_causal_pilot.py` 对每条案例固定核验一个目标仓和一个干扰仓，共 12 个快照：

- 远程提交与清单提交一致；
- 提交时间不晚于失败构建开始时间；
- 执行清单来源的提交重新核对清单；
- 默认分支来源的提交重新查询截止前最后提交；
- 12 个源码归档均可实际打开并包含文件。

结果为 12/12 通过，详见 `audit-results.jsonl`。抽查范围包含 GitHub 托管的 `novnc/novnc`，同时覆盖执行清单提交和截止前默认分支提交。

`prepare_case_inputs.py` 已实际展开 `causal-opendev-999031`：源补丁 1273 字节，5 个候选仓共 5597 个文件，展开后约 44 MB。执行命令：

```bash
python benchmarks/cross-repo-pr-impact/prepare_case_inputs.py \
  causal-opendev-999031 \
  --dataset-dir benchmarks/cross-repo-pr-impact/causal-pilot \
  --output-dir /tmp/marshal-causal-pilot
```

滚动新增的 `causal-opendev-1001168` 也已完整展开：源补丁 5794 字节，11 个候选仓连同输入元数据共 14155 个文件，约 157 MB。

扩大窗口新增的三条案例均已完整展开：

| 案例 | 源补丁 | 候选仓文件数 | 展开大小 |
|---|---:|---:|---:|
| `causal-opendev-1000542` | 18792 字节 | 32803 | 313 MB |
| `causal-opendev-1000668` | 1048 字节 | 24614 | 223 MB |
| `causal-opendev-1000682` | 3834 字节 | 24230 | 223 MB |

三条合计展开 57 个候选仓和 81647 个文件，约 759 MB。物化器按执行清单中的真实托管平台处理提交，因此 GitHub 干扰仓与 OpenDev 仓可以在同一案例中准备。

## 独立复核材料

`blind-review-packet.jsonl` 将当前全部 6 个接受项和 7 个语义拒绝项整理为 13 个去重转换、29 个任务。材料保留源与目标补丁、两臂日志、执行清单和时间证据，但移除了初次决定、理由、影响类型和失败签名。复核者按 `BLIND_REVIEW_PROTOCOL.md` 工作，并用 `blind-review-response-schema.json` 输出。当前只有材料，尚没有独立复核结果。

## 尚未完成

- 当前语义复核由数据集作者完成，不等于独立盲复核；
- 6 条案例都来自 2026 年 OpenDev，项目和时间分布远不足以支撑旗舰结论；
- 候选仓数量从 5 到 26 不等，难度不同，跨案例数字不可直接比较；
- 其他候选仓没有可靠无影响标签，不能计算精度、误报率或停止能力；
- 尚未运行 Marshal 或可比系统。
- 已用不含目标线索的 `causal-opendev-1000668` 运行 Marshal 原生确定性入口；原生命令没有读取十四个候选仓或输出仓库排序，三个审查提示中还有两个是 Cowboy 专用表述，因此尚无完整 Marshal 检索成绩。运行记录见 `../results/current-marshal-offline-development-2026-08-24.json`。

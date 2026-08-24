# 未发布候选版本案例评估

## 已纳入：WanderTracks 地图样式协同变更

上游变更是 `wandertracks/wandertracks` 的 OpenDev 变更 1001388，候选提交为 `78030e484d568e65d2bcc98c3971efb6ee4b7fb2`。它新增五份地图样式 JSON。

消费仓变更是 `wandertracks/wandertracks-web` 的 OpenDev 变更 1001389，候选提交为 `21ced27563422baead2cd1b5e82cb51a6af93d70`。它新增跨仓一致性测试，并在 Zuul 中把 API 仓声明为必备项目。

本地从公开 Git 版本重放得到：

| API 仓版本 | 前端仓版本 | 命令 | 结果 |
|---|---|---|---|
| 父提交 `c0976d4` | 候选 `21ced27` | `npm exec --workspace wandertracks-studio-tests -- vitest run mapstyle-parity.test.ts` | 退出码 0，但 6 项全部跳过 |
| 候选 `78030e4` | 候选 `21ced27` | 同上 | 退出码 0，6 项全部执行并通过 |

OpenDev 的原始记录也显示该组合通过了 `wandertracks-studio-test`。由于单看退出码会把“全部跳过”误判为验证通过，正式案例同时检查测试摘要。

## 不纳入本数据集：OpenStack requirements 与 Cinder

OpenDev 变更 1001023 把 Alembic 升级到 1.19.0。补丁集 1 的 `cross-cinder-py313` 失败，任务编号为 `a910bfbc663642c7b7bd5e3dab0c11c2`。补丁集 2 增加对 Cinder 变更 1000516 的 `Depends-On` 后，同一任务通过，任务编号为 `6929808c35ff466080f9d39934e26125`。

这组证据能说明真实的候选组合关系：

- requirements 候选提交：`477af6b620bab5010fd8db17e5ae2d2b2a2817ad`；
- Cinder 父提交：`849ddb6cef2b06084b7b116cb2ae5ce7da610e1b`；
- Cinder 修复候选：`913fa91a8eee20bf852387fe8c01a2d3d45cb87e`；
- 失败由 Alembic 新增的约束比较暴露，修复在 Cinder 迁移测试中过滤既有检查约束。

失败测试依赖 Zuul 的 `cross-cinder-py313` 环境和数据库服务，目前没有整理出与官方任务等价的自包含本地配方，因此它不进入本目录的本地重放 `index.jsonl`。

这组公开流水线证据已经作为 `../cross-repo-pr-impact` 中的 `opendev-1001023-cinder-impact` 纳入，并标为 `ci_contrast_proven`，不是本地 `executed`。两套数据用于同一报告时按各自证据口径统计，不能把它当成本目录新增的本地重放样本。

## 暂不纳入：WanderTracks 后续前端切换

OpenDev 变更 1001406 同样依赖 API 变更 1001388，但它已经删除前一变更中的跨仓一致性测试。现有前端单元测试不能单独证明运行时使用了 API 候选仓，因此不把它作为第二个候选组合案例。

## 判断

本轮评估了三组公开协调变更，只有一组同时满足公开 Git 版本、明确依赖方向、自包含命令和本地可观察的候选版本消费证据。其余两组不作为本目录的本地重放案例；Cinder 只在影响数据集中按历史流水线对照口径统计。

WanderTracks 的同一次本地执行同时被 `../cross-repo-pr-impact` 引用。跨数据集汇总时只能计入一个总体结论，避免重复使用同一证据。

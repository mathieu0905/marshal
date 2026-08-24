# Mockito 项目包筛选

更新日期：2026-08-24

## 结论

Mockito 暂不构成完整项目包，也不进入正式重复。固定 BUMP 版本提供了两个可保留的单正例三臂锚点：Apache BVal 暴露了旧参数读取方法被删除后的编译失败，junit-quickcheck 暴露了旧 JUnit 运行器包被删除后的编译失败；两者都能仅应用真实维护者修改而恢复。

本轮没有把普通绿色构建或 BUMP 未成功复现记录改标为负例，也没有找到同一候选目录内经过变化表面证明的 A3。因此正式完整项目包数为零，保留两个独立源输入、两个正仓标签。五条 Mockito 5.x 记录中四条来自同一个消费仓和同一种失败，不能重复计数。

## 完整搜索框

`collect_bump_candidate_frame.sh` 在 BUMP 固定版本 `324d5513aa5ca40b5cb32de5b816a58fa60bd7bb` 上同时扫描 `benchmark` 与 `unsuccessful-reproductions`，得到 55 条唯一提交记录、15 个唯一消费仓：

- 7 条记录属于 BUMP 已复现失败集；
- 48 条属于未成功复现集，只保留为未知候选；
- 7 条失败记录只涉及 Apache BVal、Gax Java 和 junit-quickcheck 三个消费仓；
- junit-quickcheck 占 5 条，其中 4 条是从 4.11.0 升到不同 Mockito 5.x 版本的重复探测。

候选记录跨越多个起止版本，不能仅因依赖坐标相同就合并为同一个源变化。五条 junit-quickcheck 记录也不能当成五个独立案例。

## 锚点一：删除旧参数读取方法

源范围是 Mockito 1.10.19 到 5.1.1。上游提交 `dff5510cb3e97dae414e58ba85825ad01b273c72`（PR 404）删除了已弃用的 `InvocationOnMock.getArgumentAt(int, Class)`。消费仓 `apache/bval` 的测试仍调用该方法。

| 臂 | 输入 | 结果 |
|---|---|---|
| A0 | BUMP 父版本，Mockito 1.10.19 | 全项目构建成功；各测试模块合计 1313 项，0 失败、0 错误、17 跳过 |
| A1 | 只把 Mockito 改为 5.1.1 | `DefaultMessageInterpolatorTest` 在测试编译阶段精确报告 `getArgumentAt` 不存在，构建失败 |
| A2 | 保持 A1，只应用维护者提交 `901c849a...` 中 `getArgumentAt` 改为 `getArgument` 的一行 | 全项目 1313 项测试，0 失败、0 错误、17 跳过，构建成功 |

维护者提交 `901c849ab0c0eacf76807bc9b033027ebd70b786` 同时升级依赖并修改这一行。主动 A2 已包含升级后的依赖，只抽取与失败符号对应的一行，没有带入版本修改或其他仓库变化。

这个锚点具有确定的 A0/A1、真实维护者修复和全项目恢复。它仍缺少同一源输入下经执行路径核验的负空间和独立 A3。

## 锚点二：删除旧 JUnit 运行器包

源范围是 Mockito 3.12.4 到 4.1.0。上游提交 `caf35b24e2764df0498469526ecb3e7ec68a0430`（PR 2418）删除了长期弃用的 `org.mockito.runners` 包，并要求使用 `org.mockito.junit.MockitoJUnitRunner`。消费仓 `pholser/junit-quickcheck` 的 `RegisterGeneratorsByConventionTest` 仍导入旧包。

| 臂 | 输入 | 结果 |
|---|---|---|
| A0 | BUMP 父版本，Mockito 3.12.4 | 全项目 1114 项测试，0 失败、0 错误、20 跳过，构建成功 |
| A1 | 只把 Mockito 改为 4.1.0 | 测试编译精确报告 `org.mockito.runners` 不存在和 `MockitoJUnitRunner` 无法解析，构建失败 |
| A2 | 保持 A1，只应用维护者提交 `f4091d8b...` 对该测试的修改 | 全项目 1114 项测试，0 失败、0 错误、20 跳过，构建成功 |

维护者提交 `f4091d8be84155aec678fbce36cad809c8e3f344` 的说明是“remove to-be-removed mockito class”，发生在失败升级 PR 381 关闭后一周；随后仓库在同一天合入 Mockito 4.2.0。该提交只修改这一个测试：去掉旧运行器和两个模拟对象，改用真实随机源与真实生成状态。主动 A2 原样移植这份维护者修改，没有带入两次提交之间的其他依赖更新。

## 其余已复现失败

Gax Java 的 Mockito 4.11.0 到 5.1.0 升级臂可重复失败，包含两个与 Mockito 参数匹配行为相关的断言差异，也混有四个 500 毫秒超时。对应 PR 1957 未合并，维护者因 Java 8 支持边界关闭升级，没有可验证的恢复提交，因此只保留为失败线索。

junit-quickcheck 从 4.11.0 升到 5.1.1、5.3.1 和 5.4.0 的三个有效前后臂都在同一 `CompositeGeneratorTest` 上得到 `expected [3, 6] but was []`；它们是同一消费仓、同一失败模式的版本链重复。5.2.0 记录的原臂自身在随机性质测试中失败，不满足 A0，直接拒绝。Mockito 5.x 升级也没有维护者恢复提交：维护者明确表示在放弃 Java 8 前暂缓升级。

## 执行说明

BUMP 镜像的默认命令使用 `mvn ... | tee` 且没有开启 `pipefail`，容器退出码不能表示 Maven 结果。`run_bump_archive_screening.sh` 分别记录容器退出码和日志末尾的 `BUILD SUCCESS` 或 `BUILD FAILURE`。Gax 变化镜像首次因镜像仓库连接中断返回 125，重试后得到真实 Maven 失败；结果文件已记录重试后的状态。

BVal 的 A1 在 `bval-jsr` 测试编译阶段停止，因此变化镜像没有缓存后续 TCK 所需的 OpenWebBeans 4.0.0 历史快照；该快照现已从远端仓库下架。`run_bval_a2_screening.sh` 从同一 A0 镜像复制其原有 Maven 缓存后运行完整原生命令，最终 1313 项测试恢复。这个步骤只恢复历史构建输入，不改变代码或依赖版本。

原始日志位于：

- `results/mockito-bump-archive-screening-2026-08-24/`
- `results/mockito-a2-screening-2026-08-24/`

## 后续准入条件

1. 两个锚点必须按各自源变化建立候选目录，不能因都属于 Mockito 而合并。
2. 限定负例必须证明相关测试或编译实际触及 `getArgumentAt` 删除或旧运行器删除的变化表面；普通绿色构建和未成功复现记录不够。
3. A3 必须选择独立真实兼容变化，并证明候选仓检查进入对应变化代码。
4. 只有负空间与 A3 均成立后，才运行三次正式重复并进入独立语义复核。

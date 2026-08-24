# Spring Core 项目包筛选

更新日期：2026-08-24

## 结论

Spring Core 暂不构成完整项目包，也没有可接纳的单正例三臂锚点。固定 BUMP 版本中的 20 条已复现失败都属于 Spring 5.3.x 升级到 6.0.x，且对应升级 PR 无一合并；当前找不到维护者提交的精确恢复修改。三个消费仓里可本地重放的两个仓都在编译阶段撞到 Spring 6 的 Java 17 字节码基线，并未进入更具体的 Spring Core API 行为。

因此本轮正式接受数为零：强正例 0、限定负例 0、A3 0、完整项目包 0。Future Converter 和 LPVS 的失败只保留为“Java 17 基线变化”线索，不提升为跨仓影响标签。

## 完整搜索框

`collect_bump_candidate_frame.sh` 在 BUMP 固定版本 `324d5513aa5ca40b5cb32de5b816a58fa60bd7bb` 上同时扫描 `benchmark` 与 `unsuccessful-reproductions`，得到 32 条唯一提交记录、7 个唯一消费仓：

- 20 条属于 BUMP 已复现失败集，分布在 IDS Messaging Services、LPVS 和 Future Converter 三个仓；
- 12 条属于未成功复现集，分布在 Togglz、Sauron、Mycat2、XOOM Designer 和 IDS Messaging Services 五个仓；
- 已复现失败集的 20 个升级 PR 中，19 个关闭未合并，1 个仍开放，合并数为零；
- 未成功复现集的 12 个 PR 中，5 个合并、4 个关闭未合并、3 个仍开放。合并只说明维护者接受了依赖更新，不能替代 A0/A1/A2 或变化表面证据。

所有 20 条已复现失败都是同一大版本边界的重复探测，不能当成 20 个独立源变化。LPVS 和 IDS 各自的连续 Dependabot PR 也不能重复计数。

## 三仓代表重放

为避免把同一失败重复执行十余次，本轮选择三个正式仓各自的 6.0.2 记录作为代表。执行脚本使用机械盘上的仓库和 Maven 缓存，保留原始日志、退出码和汇总表。

| 消费仓 | A0 | A1 | 判定 |
|---|---|---|---|
| Future Converter | 提交 `60f8e83e...` 构建通过 | 只把 Spring Core 5.3.19 升为 6.0.2 后失败 | Java 11 编译器拒绝版本 61 的类文件 |
| LPVS | 提交 `2932c4f8...` 构建通过，85 项测试成功 | 只把 Spring Core 5.3.23 升为 6.0.2 后失败 | Java 11 编译器拒绝版本 61 的类文件 |
| IDS Messaging Services | 当前无法解析历史私有仓依赖 | 同样无法解析历史私有仓依赖 | 不能用当前失败覆盖 BUMP 的历史结果 |

Future Converter 的 A1 是提交 `70e13f6b...`，只修改依赖版本。LPVS 的 A1 是提交 `c1fc16b4...`，也只修改依赖版本。两者都稳定报告 `class file has wrong version 61.0, should be 55.0`。这证明 Spring 6 要求 Java 17 的兼容边界，但没有证明某个 Spring Core API 删除或语义改变使消费代码失败。

IDS 的历史 BUMP 日志记录了 A0 可构建、A1 出现相同的类文件版本错误；当前重放则在更早阶段因 `maven.iais.fraunhofer.de` 已不可用而停止。当前远程依赖故障不能改写成原始变化标签。

## 为什么没有 A2

20 个正式失败 PR 无一合并。Future Converter 没有后续 Spring 6 迁移提交，IDS 的后续 Spring 6 PR 仍未合并。

LPVS 后来通过 PR 400 合并 Spring Boot 3.2 迁移，提交为 `bdbb46ac0386edf00bd444d78b0f6675f0475a54`。该提交同时完成 Java 11 到 17、Spring Boot 2.7 到 3.2、`javax.*` 到 `jakarta.*`、多项依赖和测试调整，共修改 24 个文件。它是维护者真实恢复，但不是能与本轮失败一一对应的精确 A2，不能据此生成标签。

## 未成功复现记录

未成功复现集里合并的五条包括 Togglz 的 6.0.7 到 6.0.8、Sauron 两个模块的 5.1.3 到 5.3.18，以及 IDS 的两个 5.3.x 补丁升级。它们没有提供“升级后失败，再由维护者修复”的证据。

这些记录也不能直接组成 A3：版本范围和真实变化不同，Sauron 的两条来自同一个消费仓，其他补丁升级各自只有一个消费仓。仅验证升级前后都绿色，会测到普通依赖兼容性，不能证明多个仓共同覆盖某个真实 Spring Core 变化表面。

Mycat2、XOOM Designer 和其余 Sauron PR 的未合并或未成功复现状态同样只保留为未知候选，不产生限定负例。

## 证据位置

- 完整候选框：`workstreams/spring-core/bump-candidate-frame.jsonl`
- PR 状态审计脚本：`workstreams/spring-core/audit_candidate_prs.sh`
- 三仓重放脚本：`workstreams/spring-core/run_major_break_screening.sh`
- PR 状态结果：`results/spring-core-pr-status-2026-08-24/candidate-pr-status.jsonl`
- 重放日志：`results/spring-core-major-break-screening-2026-08-24/`

## 后续准入条件

1. 若继续沿 Spring 5.3 到 6.0 边界挖掘，A2 必须来自维护者真实提交，并能把 Java 17 基线调整与更宽的 Spring Boot、Jakarta 迁移拆开验证。
2. 限定负例必须执行到同一真实变化面；普通绿色构建、仅安装依赖或 BUMP 未成功复现记录都不够。
3. A3 必须由多个独立消费仓共同覆盖同一个可定位的 Spring Core 兼容变化，不能把不同补丁版本或同仓不同模块拼在一起。
4. 在满足上述条件前，不运行三次正式重复，也不把本工作流计入旗舰因果数据集条数。

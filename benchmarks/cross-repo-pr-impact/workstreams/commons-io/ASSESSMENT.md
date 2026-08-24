# Commons IO 项目包筛选

更新日期：2026-08-24

## 结论

Commons IO 暂不构成完整项目包，也不进入正式重复。固定 BUMP 版本提供了两个可保留的单正例三臂锚点，但两者来自不同源变化；当前没有经过变化表面核验的限定负例，也没有四仓共同触及真实兼容变化的 A3。第三条已复现失败是自动化工具把 2.11.0 回退到 2005 年旧版本，不是可信的上游演化案例。

因此本轮正式接受数为零。保留两个锚点，是为了后续与其他 Commons IO 消费仓组成各自独立的候选目录；不得把它们合并成一个多目标源案例。

## 完整搜索框

`collect_bump_candidate_frame.sh` 在 BUMP 固定版本 `324d5513aa5ca40b5cb32de5b816a58fa60bd7bb` 上同时扫描 `benchmark` 与 `unsuccessful-reproductions`，得到 34 条唯一提交记录、25 个唯一消费仓：

- 3 条记录属于 BUMP 已复现失败集；
- 31 条属于未成功复现集；
- 版本组合共有 13 种，不能按依赖坐标直接合并为一个源输入；
- 31 条未成功复现记录只保留为候选，不产生负标签。

此前储备表中的“三个消费仓、三条记录”只统计了已复现失败子集，不是完整候选框。

## 锚点一：异常类型变化

源变化范围是 Commons IO 2.7 到 2.11.0。上游提交 `0cee29aa4c1818963ed1a55058219282e89d7488` 将 `FileUtils` 对大部分非法输入的处理统一为 `IllegalArgumentException`；`FileUtils.copyFile` 因此会在源路径是目录时抛出这一异常，而不是落入消费者原有的 `IOException` 处理。

消费仓为 `damianszczepanik/cucumber-reporting`：

| 臂 | 输入 | 结果 |
|---|---|---|
| A0 | 提交 `12684ee6...` 的父版本，Commons IO 2.7 | 345 项测试，0 失败、0 错误、2 跳过，构建成功 |
| A1 | 只把 Commons IO 改为 2.11.0 | 345 项测试中 1 项错误；`ReportBuilderTest` 向 `copyFile` 传入目录后收到 `IllegalArgumentException`，构建失败 |
| A2 | 保持 A1，只应用维护者 PR 1140 的异常处理修改 | 345 项测试，0 失败、0 错误、2 跳过，构建成功 |

维护者 PR 1140 同时升级依赖并把 `catch (IOException)` 改为 `catch (IOException | IllegalArgumentException)`。主动 A2 已有升级后的 A1 输入，因此只抽取这一行目标修复，没有带入七个月后的其他仓库变化。失败签名与维护者说明一致。

这个锚点具备受控 A0/A1/A2 和真实维护者修复，可保留为一个源输入、一个正仓标签。它仍缺少同一输入下经执行路径核验的负空间和独立 A3。

## 锚点二：弃用警告成为编译错误

源变化范围是 Commons IO 2.11.0 到 2.13.0。上游提交 `7ecca22f175c644da3096940a4ce899be5b33740` 为文件过滤器增加构建器并弃用旧构造器。消费仓 `jcabi/jcabi-maven-plugin` 直接调用 `new WildcardFileFilter(mask)`，并将编译警告提升为错误。

| 臂 | 输入 | 结果 |
|---|---|---|
| A0 | 提交 `1053033e...` 的父版本，Commons IO 2.11.0 | 4 项测试，0 失败、0 错误、2 跳过，构建成功 |
| A1 | 只把 Commons IO 改为 2.13.0 | 精确报告旧构造器弃用，并因 `-Werror` 编译失败 |
| A2 | 保持 A1，只应用维护者提交 `84fd8602...` 中改用构建器的三行修改 | 4 项测试，0 失败、0 错误、2 跳过，构建成功 |

维护者修改与失败符号一一对应，但发生在 2026 年且所在提交还包含其他构建调整。主动 A2 只抽取 `WildcardFileFilter` 的相关片段，证明修复充分；它不能证明该提交在 2023 年就是对失败 PR 的直接响应。因此这一锚点的历史响应强度低于 Cucumber 锚点，不提升为正式项目包。

同版本范围的三条未复现线索是 WorldwideChat、AWS Lambda Powertools 和 Heroku Maven Plugin。至少已核对的 WorldwideChat 与 Heroku PR 都未合并；BUMP 未成功复现本身也不说明它们覆盖了弃用构造器或无需适配。三条继续保持未知，不标负例。

## 拒绝项：旧版本回退

`codehaus-plexus/plexus-archiver` PR 259 把 Commons IO 从 2.11.0 改为 `20030203.000550`。A0 的 185 项测试通过；变化臂因旧发布缺少 `BoundedInputStream`、`NullPrintStream`、`ThresholdingOutputStream` 等现代 API 而出现 15 个编译错误。

这是真实可重复的失败，但不是 Commons IO 的后续源变化。PR 正文也写明目标版本发布于 2005 年，且 PR 未合并。它只能作为依赖自动化错误的反例，不进入跨仓影响真值。

## 执行说明

BUMP 镜像的默认命令使用 `mvn ... | tee`，没有开启 `pipefail`，所以六个容器退出码均为零，包括三个 Maven 失败臂。结果解析必须读取日志中最后一个 `BUILD SUCCESS` 或 `BUILD FAILURE`；`run_bump_archive_screening.sh` 已分别记录容器退出码与 Maven 结果，避免把容器零退出误判为测试通过。

原始日志位于：

- `results/commons-io-bump-archive-screening-2026-08-24/`
- `results/commons-io-cucumber-a2-screening-2026-08-24/`
- `results/commons-io-jcabi-a2-screening-2026-08-24/`

## 后续准入条件

1. 为两个源变化分别建立候选目录，不能按“都来自 Commons IO”合并关系。
2. 限定负例必须证明相关编译或测试实际覆盖对应变化表面；普通绿色构建和 BUMP 的未复现状态都不够。
3. A3 必须选择独立真实兼容变化，并证明同一候选目录的检查进入变化代码；仅在相邻版本两侧通过不够。
4. 只有负空间与 A3 均成立后，才运行三次正式重复并进入独立语义复核。

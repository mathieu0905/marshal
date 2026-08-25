# AssertJ Core 项目包筛选记录

## 当前结论

AssertJ Core 原有 3.22.0 到 3.23.0 闭集形成了两个强因果正例和两个限定合同负例，但还不是正式项目包。三轮兼容变化筛选都未满足 A3：3.24.1 到 3.24.2 只有一个消费仓执行到真实行为变化，3.21.0 到 3.22.0 有一个消费仓前臂失败，3.23.1 到 3.24.0 虽然四仓两侧全通过，但行为修复同样没有四仓共同覆盖。因此当前完整项目包接受数仍为 0，不能用普通绿色构建或等价重构补齐。另有一条来自 FSE 2024 搜索框的 AssertJ 3.19.0 到 Brave 单仓正关系，版本合同和消费仓均不同，只作为独立三臂锚点，不拼入原闭集。

## 完整失败候选框

BUMP 固定版本 `324d5513aa5ca40b5cb32de5b816a58fa60bd7bb` 中共有 12 条 AssertJ Core 记录，覆盖 5 个唯一消费仓。其中 6 条来自正式 benchmark，6 条来自 unsuccessful-reproductions：

| 消费仓 | 记录数 | 观察到的版本对 |
| --- | ---: | --- |
| `assertj/assertj-guava` | 1 | 3.22.0 到 3.23.0 |
| `assertj/assertj-vavr` | 1 | 3.22.0 到 3.23.0 |
| `pac4j/dropwizard-pac4j` | 2 | 3.18.1 到 3.23.0、3.23.1 |
| `s4u/pgpverify-maven-plugin` | 2 | 3.23.1 到 3.24.0、3.24.1 |
| `timpeeters/spring-boot-graceful-shutdown` | 6 | 3.21.0 到 3.22.0、3.23.0、3.23.1、3.24.0、3.24.1、3.24.2 |

搜索框由 `collect_bump_candidate_frame.sh` 生成，原始记录保存在 `bump-candidate-frame.jsonl`。这些记录只是失败线索，不自动产生标签。

FSE 2024 另有 8 条 AssertJ Core 记录，折叠后是 6 个可辨识根仓和 1 条无法恢复的历史；其中两个 Brave 目录提示属于同一迁移历史，只计一条关系。本轮逐条恢复公开历史后，JTransfo、Hiccup、Bundler 和 XChange Stream 都没有在破坏版本下的维护者 A2，AssertJ Guava 跳过 3.21.0 后由上游后续版本恢复，WampSpring 的目标历史无法恢复；只有 Brave 进入三臂。逐条裁决保存在 `fse-candidate-audit.jsonl`。

## 两个强因果正例

统一破坏变化为 AssertJ Core 3.22.0 到 3.23.0。两个消费仓都保留了基线、真实依赖更新失败和维护者实际合并的精确恢复：

| 消费仓 | A0 | A1 | A2 | 失败与恢复机制 |
| --- | --- | --- | --- | --- |
| AssertJ Guava | `5705970602ede90f3dc8c001d0d749461c20d56f`，355 项通过 | `0968864d08e0fce1e5e1caaf89afddd2cc1b2569`，失败 | `4c6055d37cb727865c800a829521f6efe1286ce1`，355 项通过 | 3.23.0 新增传递依赖 Byte Buddy，被 Enforcer 禁止；PR 99 更新白名单、比较策略和 OSGi 配置 |
| AssertJ Vavr | `edced3fc51e16f17586c5ebc181705b0d5fc1934`，694 项通过 | `1cc7071371953a7880c2c2c3a5a32c36af7f88f9`，失败 | `d330a1528031a8e68795d3f9158a5527e0e9d535`，694 项通过 | 3.23.0 移除内部 `org.assertj.core.internal.bytebuddy.*`；PR 181 改用公开 `net.bytebuddy.*` |

Vavr 使用 `mvn clean test`，因为本机 Java 11 安装没有 `javadoc` 可执行文件。此前 `verify` 的 694 项测试已全部通过，只在 Javadoc 打包阶段失败，因此没有把环境失败误记为产品失败。脚本与原始日志位于 `run_positive_screening.sh` 和 `results/assertj-positive-screening-2026-08-24/`。

## FSE 2024 补充单正例

FSE 候选 `fse2024-behavioral-0385` 指向 `openzipkin/brave` 的 `brave-tests`。恢复后的源破坏提交是 AssertJ Core `66e784987234e9c649e043f631ef984036ee9b30`：它在 JUnit 存在时开始用 `ComparisonFailure` 表示 expected/actual，因而会把比较详情追加到自定义失败消息。Brave 的原生 `IntegrationTestSpanHandlerTest#goodMessageForOrphanedSpan` 原先要求消息以提示文本结尾，3.19.0 下新增的比较详情使该合同失败。维护者提交 `eac0ffa658c7c708ce26e306f171a4fc04bef9ca` 把这一处 `hasMessageEndingWith` 改为 `hasMessageContaining`。

本轮在 Java 11 上执行原生测试方法，使用发布的 `brave-tests:5.16.0` 作为被测实现；发布标签到消费基线 `5e15c20e7d79a0d032f5606c1b3684277bd11d7d` 之间，该测试及被测 `IntegrationTestSpanHandler` 均无差异。A0 使用 AssertJ 3.18.1，1 项通过；A1 只换成 3.19.0，1 项以 FSE 记录的同一“消息不再以提示文本结尾”签名失败；A2 保持 3.19.0，只取维护者提交后的原生测试文件，1 项恢复。脚本和日志分别位于 `run_brave_fse_replay.sh` 与 `results/assertj-3.19-brave-fse-2026-08-25/`。

该关系接纳为单仓三臂正例，但不升格为 AssertJ 项目包：A2 行来自一次大范围 Java LTS 构建迁移提交，本轮只隔离重放与此合同直接相关的维护者行；它不提供同版本合同的限定负例或 A3，也不与 3.22.0 到 3.23.0 的 Guava/Vavr/DB/Examples 闭集混合计数。

## 两个限定合同负例

对同一 3.22.0 到 3.23.0 变化，两个仓的原生聚焦检查在前后臂均通过，并用 JaCoCo 验证测试确实执行了 3.23.0 的新增行为：

| 消费仓 | 固定提交 | 聚焦检查 | 变化面覆盖 |
| --- | --- | --- | --- |
| `assertj/assertj-db` | `8aefa0f0417aa5cf01a9990ff554a119a6ddf557` | `SoftAssertions_Test`，两侧各 3 项通过 | `AssertionsForInterfaceTypes.java:187`、`ListAssert.java:48` |
| `assertj/assertj-examples` | `0868b5d724374ca0eb3f6c2456b27acd5ac740e0` | `SoftAssertionsExamples#host_dinner_party_where_nobody_dies`，两侧各 1 项通过 | `DefaultAssertionErrorCollector.java:141`、`AssertJMultipleFailuresError.java:50/53`、`Throwables.java:185-226` 多个执行行 |

两个仓的完整测试套件在前后臂均因既有失败而失败，所以这里只能声明“限定合同未受该变化破坏”，不能外推为完整仓库无影响。筛选与覆盖证据分别位于 `run_negative_screening.sh`、`run_negative_coverage.sh` 及对应结果目录。

## 三轮 A3 均拒绝

### 3.24.1 到 3.24.2

四仓前后臂均通过：Guava 355 项、Vavr 694 项、DB 3 项、Examples 1 项。但该发布的真实运行时变化行 `Iterables.java:354` 只有 Vavr 执行到；Guava、DB 和 Examples 覆盖均为 0。该结果只能证明 Vavr 触及变化行为，不能形成四仓共同 A3。

### 3.21.0 到 3.22.0

Guava、DB 和 Examples 的前后臂均通过；Vavr 的 3.21.0 前臂在 694 项中失败 6 项，3.22.0 后臂全部通过。失败集中在空 entries 参数的 Map/Multimap 断言语义，说明这个版本对对 Vavr 本身不是兼容前臂。A3 要求所有纳入仓在前后臂均成立，因此无需用覆盖交集挽救，直接拒绝。

### 3.23.1 到 3.24.0

Guava 355 项、Vavr 694 项、DB 3 项和 Examples 1 项在两个版本下均通过。覆盖审计继续拒绝该候选：集合 `contains` 的避免复制修复只有 Vavr 执行，`returns` 自定义比较器修复只有 Guava 执行，`satisfies` 与自定义格式化修复没有任何一仓执行。四仓共同覆盖的 `Configuration.setDefaults()` 只是把原有默认赋值搬入新方法，值和构造结果不变，属于等价重构，不满足“真实兼容行为变化”的 A3 要求。退出方向和覆盖矩阵位于 `results/assertj-a3-3.23.1-3.24.0-screening-2026-08-24/`。

## 未纳入候选

- Dropwizard-pac4j 和 PGPVerify 对应的是不同版本跨度、不同 Enforcer 机制，不能拼入 3.22.0 到 3.23.0 的统一变化。
- Spring Boot Graceful Shutdown 的 6 条记录都来自 unsuccessful-reproductions，且相关历史仓库映射无法恢复，不能提供可审计标签。
- DB 与 Examples 的完整套件基线不绿，只保留有变化面覆盖的聚焦合同，不冒充仓库级负例。

## 下一步

1. 从真实 3.22.0 到 3.23.0 消费仓中寻找至少两个额外仓；正例必须有维护者接受的精确恢复，负例必须有源变化面执行覆盖。
2. 另找一个所有可接受仓前后臂均通过、且每仓都执行到真实行为变化的 A3 版本对。
3. 满足 4 至 8 仓闭集和 A3 后，再做独立重复与语义复核；在此之前 AssertJ 只计候选锚点，不进入正式项目包数量。

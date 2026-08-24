# AssertJ Core 项目包筛选记录

## 当前结论

AssertJ Core 目前形成了两个强因果正例和两个限定合同负例，但还不是正式项目包。两轮兼容变化筛选都未满足 A3：3.24.1 到 3.24.2 只有一个消费仓执行到真实行为变化，3.21.0 到 3.22.0 则有一个消费仓前臂失败。因此当前正式接受数为 0，不能用普通绿色构建补齐。

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

## 两个强因果正例

统一破坏变化为 AssertJ Core 3.22.0 到 3.23.0。两个消费仓都保留了基线、真实依赖更新失败和维护者实际合并的精确恢复：

| 消费仓 | A0 | A1 | A2 | 失败与恢复机制 |
| --- | --- | --- | --- | --- |
| AssertJ Guava | `5705970602ede90f3dc8c001d0d749461c20d56f`，355 项通过 | `0968864d08e0fce1e5e1caaf89afddd2cc1b2569`，失败 | `4c6055d37cb727865c800a829521f6efe1286ce1`，355 项通过 | 3.23.0 新增传递依赖 Byte Buddy，被 Enforcer 禁止；PR 99 更新白名单、比较策略和 OSGi 配置 |
| AssertJ Vavr | `edced3fc51e16f17586c5ebc181705b0d5fc1934`，694 项通过 | `1cc7071371953a7880c2c2c3a5a32c36af7f88f9`，失败 | `d330a1528031a8e68795d3f9158a5527e0e9d535`，694 项通过 | 3.23.0 移除内部 `org.assertj.core.internal.bytebuddy.*`；PR 181 改用公开 `net.bytebuddy.*` |

Vavr 使用 `mvn clean test`，因为本机 Java 11 安装没有 `javadoc` 可执行文件。此前 `verify` 的 694 项测试已全部通过，只在 Javadoc 打包阶段失败，因此没有把环境失败误记为产品失败。脚本与原始日志位于 `run_positive_screening.sh` 和 `results/assertj-positive-screening-2026-08-24/`。

## 两个限定合同负例

对同一 3.22.0 到 3.23.0 变化，两个仓的原生聚焦检查在前后臂均通过，并用 JaCoCo 验证测试确实执行了 3.23.0 的新增行为：

| 消费仓 | 固定提交 | 聚焦检查 | 变化面覆盖 |
| --- | --- | --- | --- |
| `assertj/assertj-db` | `8aefa0f0417aa5cf01a9990ff554a119a6ddf557` | `SoftAssertions_Test`，两侧各 3 项通过 | `AssertionsForInterfaceTypes.java:187`、`ListAssert.java:48` |
| `assertj/assertj-examples` | `0868b5d724374ca0eb3f6c2456b27acd5ac740e0` | `SoftAssertionsExamples#host_dinner_party_where_nobody_dies`，两侧各 1 项通过 | `DefaultAssertionErrorCollector.java:141`、`AssertJMultipleFailuresError.java:50/53`、`Throwables.java:185-226` 多个执行行 |

两个仓的完整测试套件在前后臂均因既有失败而失败，所以这里只能声明“限定合同未受该变化破坏”，不能外推为完整仓库无影响。筛选与覆盖证据分别位于 `run_negative_screening.sh`、`run_negative_coverage.sh` 及对应结果目录。

## 两轮 A3 均拒绝

### 3.24.1 到 3.24.2

四仓前后臂均通过：Guava 355 项、Vavr 694 项、DB 3 项、Examples 1 项。但该发布的真实运行时变化行 `Iterables.java:354` 只有 Vavr 执行到；Guava、DB 和 Examples 覆盖均为 0。该结果只能证明 Vavr 触及变化行为，不能形成四仓共同 A3。

### 3.21.0 到 3.22.0

Guava、DB 和 Examples 的前后臂均通过；Vavr 的 3.21.0 前臂在 694 项中失败 6 项，3.22.0 后臂全部通过。失败集中在空 entries 参数的 Map/Multimap 断言语义，说明这个版本对对 Vavr 本身不是兼容前臂。A3 要求所有纳入仓在前后臂均成立，因此无需用覆盖交集挽救，直接拒绝。

## 未纳入候选

- Dropwizard-pac4j 和 PGPVerify 对应的是不同版本跨度、不同 Enforcer 机制，不能拼入 3.22.0 到 3.23.0 的统一变化。
- Spring Boot Graceful Shutdown 的 6 条记录都来自 unsuccessful-reproductions，且相关历史仓库映射无法恢复，不能提供可审计标签。
- DB 与 Examples 的完整套件基线不绿，只保留有变化面覆盖的聚焦合同，不冒充仓库级负例。

## 下一步

1. 从真实 3.22.0 到 3.23.0 消费仓中寻找至少两个额外仓；正例必须有维护者接受的精确恢复，负例必须有源变化面执行覆盖。
2. 另找一个所有可接受仓前后臂均通过、且每仓都执行到真实行为变化的 A3 版本对。
3. 满足 4 至 8 仓闭集和 A3 后，再做独立重复与语义复核；在此之前 AssertJ 只计候选锚点，不进入正式项目包数量。

# Spring Test 4.3.0.RELEASE 的 FSE 关系族筛选

更新日期：2026-08-25

## 结论

完整精确版本框共有 5 条候选、5 个失败观察，分别来自 `opencredo/opencredo-esper`、`NitorCreations/CoreComponents`、`uaihebert/uaiMockServer`、`adrobisch/brainslug` 和 `neoremind/fluent-validator`，去重后仍是 5 个独立根仓。本轮正式接纳 0 条，没有执行 A0、A1、A2，也没有限定负例或 A3。

五条记录的异常类型都是 `IllegalStateException`，但本轮没有据此直接合并。回到工作簿中的完整堆栈后，五条记录都以同一消息结束：`SpringJUnit4ClassRunner requires JUnit 4.12 or higher.`，触发位置都是 `SpringJUnit4ClassRunner` 静态初始化第 102 行。源变化还能精确定位到 Spring Framework 提交 `66562f258917fa448db96787107ba6574359040d`。

不过，五个目标仓的全部可达历史都没有在依赖文件中声明 Spring Test 4.3.0.RELEASE，也没有在保持该固定版本时把 JUnit 升到 4.12 或更高并恢复同一测试合同。FSE 工作簿又没有保存目标 Git 修订。自行选择一个历史提交、合成 Spring Test 4.3.0，再编写或移植 JUnit 升级，只能制造数据集作者 A2，不能形成维护者因果标签。

## 完整候选框

| FSE 候选 | 目标模块 | 原声明版本 | 目标仓中的 JUnit | 根仓 |
|---|---|---|---|---|
| `fse2024-behavioral-0668` | `org.opencredo.esper:esper-template` | 3.1.2.RELEASE | 4.10 | `opencredo/opencredo-esper` |
| `fse2024-behavioral-0671` | `com.nitorcreations:junit-runners` | 4.1.1.RELEASE | 4.11 | `NitorCreations/CoreComponents` |
| `fse2024-behavioral-0672` | `uaihebert.com:uaiMockServer` | 4.1.5.RELEASE | 4.9 | `uaihebert/uaiMockServer` |
| `fse2024-behavioral-0673` | `com.drobisch:brainslug-spring` | 4.1.6.RELEASE | 4.11 | `adrobisch/brainslug` |
| `fse2024-behavioral-0674` | `com.baidu.unbiz:fluent-validator-spring` | 4.1.7.RELEASE | 4.11 | `neoremind/fluent-validator` |

五条记录的最后通过探针均为 4.2.9.RELEASE，首个失败探针均为 4.3.0.RELEASE。表中的 JUnit 版本来自对应远程历史保留的依赖形状；它们都低于新下限，与公开失败一致，但不能代替缺失的精确执行修订。

## 精确源变化

Spring Framework 的带说明标签需要区分标签对象与源码提交：

- 4.2.9.RELEASE 的标签对象是 `f213d2c3a3ea67dbd68180efbc41035a27444c10`，指向提交 `2cc3b278024ca45a72bc847a9457fc138424b16c`；
- 4.3.0.RELEASE 的标签对象是 `e1f37db1315171cedf74bac3caa46617c0c4ab8c`，指向提交 `b49d801f241fb8088a5b7514db93fda32c58731c`。

提交 `66562f258917fa448db96787107ba6574359040d` 只存在于后一条发布线上，说明为 `Require JUnit 4.12 or higher in the TestContext framework`，关联 SPR-13275。它修改 11 个 Spring Test 文件，其中 `SpringJUnit4ClassRunner` 的静态初始化由检查 JUnit 4.9 的 `MultipleFailureException` 改为检查 JUnit 4.12 的 `org.junit.internal.Throwables`，并把反射查找 `withRules()` 失败时的消息同步改成要求 JUnit 4.12。

五份完整堆栈都命中这段新增检查，而不是在应用上下文加载、业务断言或各目标自定义代码中产生不同根因。因此本组可以把源机制精确归到同一提交，而不是只保留整个 4.2.9→4.3.0 发布差异。

4.2.9.RELEASE 是 4.2 维护线的后续发布，日期晚于 4.3.0.RELEASE；“最后通过探针”描述 FSE 的兼容探针序列，不代表标签按发布时间先后排列。

## 目标历史审计

### opencredo-esper

远程镜像共有 5 个引用和 92 个唯一可达提交。默认分支头为 `bbc202609f06f44c6b2f029e8ae09813b7ea2e05`，日期为 2022-08-31；其 POM 仍把 Spring 固定在 3.1.2.RELEASE、JUnit 固定在 4.10。全部依赖文件历史没有 Spring 4.3.0.RELEASE 或 JUnit 4.12。提交说明中的“Esper 4.3.0”属于另一项依赖，不能误认成 Spring 版本。

### CoreComponents

远程镜像共有 20 个引用和 204 个唯一可达提交。默认分支头为 `7904336ec0ed2e3e92a4adbcdc5186c2b64cf2cc`，日期为 2017-03-29；`junit-runners` 模块仍使用 Spring 4.1.1.RELEASE 和 JUnit 4.11。全部依赖文件历史没有 Spring 4.3.0.RELEASE 或 JUnit 4.12。

### uaiMockServer

远程镜像共有 11 个引用和 310 个唯一可达提交。默认分支头为 `8b0090d4018c2f430cfbbb3ae249347652802f2b`，日期为 2018-11-17；POM 仍显式声明 Spring Test 4.1.5.RELEASE 和 JUnit 4.9。全部依赖文件历史没有 Spring 4.3.0.RELEASE 或 JUnit 4.12。

### brainslug

远程镜像共有 20 个引用和 176 个唯一可达提交。默认分支头为 `3a906bd759aa82b896087bd90ae5a96aa0564eda`，日期为 2016-06-15；根 POM 使用 Spring 4.1.6.RELEASE 和 JUnit 4.11。全历史没有 Spring 4.3.0.RELEASE 的依赖声明，也没有把 JUnit 依赖升到 4.12。历史文本中其他 `4.12` 数字不属于 JUnit 版本，不能充当 A2。

### fluent-validator

远程镜像共有 44 个引用和 124 个唯一可达提交。默认分支头为 `9422352dc4df99565aab41b96c05e7a284c9f578`，日期为 2020-07-29；根 POM 仍使用 Spring 4.1.7.RELEASE 和 JUnit 4.11。所有远程引用的依赖文件历史都没有 Spring 4.3.0.RELEASE 或 JUnit 4.12。后来的自动升级引用涉及其他 Spring 版本和模块，不构成固定 4.3.0.RELEASE 的维护者恢复。

## 为什么不执行三臂

源机制虽然精确，但旗舰正例还需要精确目标输入和维护者 A2。工作簿没有保存五次公开执行所用的 Git 修订；五仓历史中又没有任何提交采用固定 Spring Test 4.3.0.RELEASE。若本轮从保留旧依赖的默认分支头生成 A1，再把 JUnit 改成 4.12 生成 A2，三臂很可能得到“通过、公开异常、再次通过”，但这个 A2 是数据集作者根据异常消息写出的显然修复。

具体误标场景是把“修复方案可行”写成“目标维护者实际完成了跨仓适配”。Git 可以固定人工挑选的提交，版本号可以证明两个依赖输入，普通测试也可以验证人工补丁；它们都不能补出不存在的维护者行为。因此本组在历史审计后停止，不让容易通过的实验挤掉标签来源要求。

## 证据边界

本组能够证明 Spring Test 4.3.0.RELEASE 中一个精确源提交把 JUnit 下限提高到 4.12，并且五个独立客户端的合成升级都触发了这条检查。它不能证明任一目标维护者采用 4.3.0.RELEASE 后修复，也不提供限定负例或 A3。

机器可读候选、根仓裁决和历史证据分别位于 `candidate-frame.jsonl`、`root-audit.jsonl` 与 `history-evidence.json`；紧凑结果位于 `results/spring-test-4.3-fse-history-screening-2026-08-25/summary.json`。

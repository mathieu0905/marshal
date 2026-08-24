# JUnit 4.11 到 4.12 的 FSE 关系族筛选

更新日期：2026-08-24

## 结论

本轮从 FSE 2024 记录中恢复出八个 `junit:junit 4.11→4.12` 的独立客户端仓，但正式接纳零条。家族准入要求至少两个独立仓同时具备可隔离的 JUnit 源变化和维护者真实修复，才进入 A0/A1/A2 重放。实际只有 PIT 的后续历史出现一个可能对应同一失败合同的测试夹具修改；其余七仓没有可用 A2。因此本轮停在历史筛选，没有为了凑数恢复八套旧 Maven 环境。

计数为：八个范围内候选、零个严格三臂正例、零个限定负例、零个 A3。`feedzai/fos-server` 的记录虽然列在相邻位置，但 `current_version=4.10`，只在 `previous_version` 中出现 4.11，不混入八仓统计。

## 源变化边界

JUnit 标签边界为：

- `r4.11`：`c2e4d911fadfbd64444fb285342a8f1b72336169`
- `r4.12`：`64155f8a9babcfcf4263cf4d08253a1556e75481`

五个客户端记录的是 PowerMock 反射读取 `org.junit.internal.runners.MethodValidator.fTestClass` 失败。这个签名不能诚实地归到一个简单的字段重命名提交：

1. `745ca05dccf5cc907e43a58142bb8be97da2b78f` 删除了 `MethodValidator` 等长期弃用类；
2. `df00d5eced3a7737b88de0f6f9e3673f0cf88f88` 执行全仓 `f` 前缀清理时，`MethodValidator` 已不存在，所以该提交没有修改这个文件；
3. `883c1bb6da11ff4c8422220fd99d727a495dd51f` 恢复 `MethodValidator` 时，私有字段已经叫 `testClass`。

因此真实历史路径是“删除、全仓样式迁移、按新名字恢复”，不是“类保持存在且某个提交把 `fTestClass` 改成 `testClass`”。把 `df00d5ec` 单独标成精确破坏提交会伪造一个历史上不存在的单提交边界。

PIT 的两个失败都围绕未命名的 JUnit3 `TestCase`。`0fa3f12d9b69cb8c97021507bce367be386be338` 在 `JUnit38ClassRunner` 中新增了对测试方法注解的读取，并用 `test.getName()` 做反射查找；这项变化进入 4.12。PIT 直到 2023 年的 `e86ff284de044460a1eb252ab4f08c4854fe0abe` 才在升级 JUnit 时给相同 suite 夹具中的 `TestCase` 显式设置方法名。它是唯一值得继续重放的 A2 候选，但该提交声明的升级目标是 4.13.1，不足以在未执行时直接宣称它恢复了 4.12。

AssertJ 的 Theories 失败没有继续做单提交归因。原因不是忽略错误，而是目标仓历史已先证明缺少 A2：维护者明确选择固定在 4.11。按照本轮“缺 A2 即淘汰，不先恢复重型环境”的顺序，继续在大段 Theories 变化中挑一个提交不会改变准入结果。

## 八仓审计

| 候选 | 客户端仓 | 公开失败 | 后续维护者证据 | 判定 |
|---|---|---|---|---|
| 0256 | `linsolas/casperjs-runner-maven-plugin` | PowerMock `fTestClass` | 项目最后仍为 JUnit 4.11、PowerMock 1.5.5；后续只有 README 修改 | 无 A2 |
| 0257 | `mcac0006/sift-java` | PowerMock `fTestClass` | 后续 POM 只升级 Jersey；项目最后仍为 JUnit 4.11、PowerMock 1.5.1 | 无 A2 |
| 0258 | `NitorCreations/CoreComponents` | 自定义参数化运行器创建失败，底层为 PowerMock 字段错误 | 4.12 后相关模块只有文档、许可证、注释和调试输出整理，没有依赖或合同修复 | 无 A2 |
| 0259 | `Orange-OpenSource/wro4j-taglib` | PowerMock `fTestClass` | 仓库最后提交在 2013 年，早于 JUnit 4.12 | 无后续历史可形成 A2 |
| 0260 | `stackify/stackify-log-log4j2` | PowerMock `fTestClass` | 2020 年 `a5d4a03c...` 只把 JUnit 4.11 升到 4.13.1，当时 PowerMock 仍为 1.5.6；没有目标修复提交 | 不是 A2 |
| 0261 | `joel-costigliola/assertj-assertions-generator` | 父类 Theories 找不到有效参数 | `16c73f29...` 明确说明 4.12 会破坏父类 Theories，并固定回 4.11；2017 发布仍保持该固定 | 回避变化，不是修复 |
| 0262 | `hcoles/pitest` | JUnit3 suite 未发现两个测试类 | `e86ff284...` 在 2023 年升级到 4.13.1 时为相同 suite 夹具设置方法名 | 唯一 A2 候选，尚未满足家族执行门槛 |
| 0263 | `mati1979/spring-soy-view` | PowerMock `fTestClass` | 项目最后仍为 JUnit 4.11、PowerMock 1.5.1；后续升级只涉及 Closure/Soy | 无 A2 |

## 为什么不执行三臂

重放门槛的具体失败场景是：只执行 PIT 会把一个仓的一条潜在修复包装成“JUnit 4.12 多仓关系族”，而另外七仓没有维护者 A2，无法检验同一源变化在多个真实客户端上的恢复。版本号、提交主键和普通测试只能保证单次执行引用了哪个代码状态，不能补出不存在的维护者修复，也不能把“维护者固定旧版本”变成“维护者适配新版本”。

PIT 仍可在后续作为单仓线索继续验证：固定 FSE 对应目标提交，执行 4.11 的 A0、4.12 的 A1，并只应用 `e86ff284` 中为 JUnit3 suite 设置名称的最小维护者差异作为 A2。只有这三臂成立，才能接纳一条单正例；它仍不能把本轮八仓整体升级为多仓项目包。

## 负空间与证据边界

没有找到修复的七仓全部保持“未知”，不记负例。仓库停止维护、继续固定 4.11、没有相关提交，都不能证明这些客户端在同一变化面上兼容。普通绿色构建也不能替代变化代码覆盖。

机器可读审计位于 `results/junit-4.12-fse-history-screening-2026-08-24/`。它记录八仓状态、范围异常记录、源提交链和停止理由；本轮没有生成 A0/A1/A2 执行日志，因为准入门槛在执行前已经失败。

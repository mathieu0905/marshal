# PowerMock API Mockito 1.6.2 的 FSE 关系族筛选

更新日期：2026-08-25

## 结论

完整版本框共有 3 条候选、4 个失败观察，对应 3 个独立根仓：`linsolas/casperjs-runner-maven-plugin`、`sonatype/goodies` 和 `uaihebert/uaiMockServer`。本轮正式接纳 0 条，没有执行 A0、A1、A2，也没有限定负例或 A3。

三仓的全部已抓取分支和标签中都不存在固定 `org.powermock:powermock-api-mockito:1.6.2` 的维护者版本，更不存在保持该版本并恢复公开失败契约的 A2。按照“先找到真实维护者 A2，再执行三臂”的顺序，本组在历史筛选阶段停止，没有用合成修补补齐缺失臂。

## 完整候选框

| FSE 候选 | 目标模块 | 当前版本 | 最后通过探针 | 首个失败探针 | 失败观察 |
|---|---|---:|---:|---:|---:|
| `fse2024-behavioral-0604` | `com.github.linsolas:casperjs-runner-maven-plugin` | 1.5.5 | 1.6.1 | 1.6.2 | 1 个空指针异常 |
| `fse2024-behavioral-0605` | `org.sonatype.goodies:goodies-testsupport` | 1.6.1 | 1.6.1 | 1.6.2 | 1 个断言失败，底层为缺类 |
| `fse2024-behavioral-0606` | `uaihebert.com:uaiMockServer` | 1.6.1 | 1.6.1 | 1.6.2 | 2 个断言失败，底层为缺方法 |

`0604` 必须纳入：本关系族按 `previous_version=1.6.1` 和 `breaking_version=1.6.2` 取完整框，不能因为它的项目声明版本仍为 1.5.5 就按 `current_version` 排除。

## 源变化边界

PowerMock 1.6.1 标签提交为 `a1d86e75a40e741b48c6ed9d4093d7b2ff4c6805`，1.6.2 标签提交为 `b468c05a045e6ed942aa63f814242dc2dceb4be0`。位于两者之间的提交 `d9615ecf221413b1661a891d02de43175f460b6b` 把 PowerMock 从 Mockito 自带的内部 `CglibMockMaker` 切到仓内重打包实现，并把管理的 Mockito 版本从 1.10.8 升到 1.10.19。新实现创建 mock 时进入 `AcrossJVMSerializationFeature`，该类直接链接 `org.mockito.exceptions.base.MockitoSerializationIssue`。

这能精确解释 `0605`。Goodies 在依赖管理中固定 `mockito-core:1.9.5`，又从 `powermock-api-mockito` 排除 `mockito-all`。本机已有制品的类清单确认 `MockitoSerializationIssue.class` 在 Mockito 1.9.5 的 core/all JAR 中均不存在，在 1.10.19 中均存在；因此 1.6.2 的新链接落到 Goodies 的旧 Mockito 类路径时出现相同 `NoClassDefFoundError`。

不能把同一提交强行扩展到其余两条。`0606` 的公开日志在 `NoSuchMethodError` 之后截断，没有保存缺失方法的 owner 和签名；1.6.2 同时改变多个 Mockito 内部调用点，异常类别不足以选择一个源 hunk。`0604` 只保留清理方法 `deleteScripts` 的空指针，可能掩盖更早的初始化失败，也无法在 Mockito 重打包、构造器转换和依赖变化之间归因。`source-mechanism.patch` 因而只是 `0605` 的最小源证据，不是三条候选共享机制的声明。

## 目标历史审计

### CasperJS Runner

提交 `39815ad102cf9fb40244f34b26ad55268b0c5390` 在 2014-08-19 引入测试及两项 PowerMock 依赖，版本固定为 1.5.5。仓库共有 3 个远程引用、2 个标签和 120 个唯一可达提交；默认分支最后提交日期为 2016-05-07。全部历史没有 1.6.2，也没有维护者在该输入下恢复 `DefaultScriptsFinderTest` 清理失败。

### Goodies

提交 `a235648aeaf0a7114517e5da18526d9827b66a81` 在 2015-02-05 把 `powermock.version` 从 1.5 升到 1.6.1。此后完整历史始终没有 1.6.2；提交 `ade92866b12e65d826e43158f138ec3ce7c410a6` 到 2022 年直接删除 PowerMock 并迁到 `mockito-inline:4.3.1`。仓库共有 9 个远程引用、51 个标签和 651 个唯一可达提交。删除 PowerMock 并改变 Mockito 主版本不是固定 1.6.2 的 A2。

### uaiMockServer

提交 `e102bdea899c1c831e3ab4261885f81c51bc38a9` 在 2015-02-16 引入统一的 `powermock.version=1.6.1` 以及 API 和 JUnit 模块。后续 `9fac9876b873f7f8bbb3aae53cae15c55ec2e4bb` 增加 `mockito-all:1.10.19`，但 PowerMock 仍为 1.6.1。仓库共有 4 个远程引用、8 个标签和 310 个唯一可达提交；直到 2018 年默认分支结束也没有采用 1.6.2。

## 为什么不执行三臂

FSE 工作簿没有保存三个目标的 Git 修订，已抓取的维护历史又没有任何 1.6.2 采用或修复。若现在选择一个方便的历史提交，把依赖改成 1.6.2，再为缺类、缺方法或清理空指针编写修补，A1 输入和 A2 都会由数据集作者制造。

具体误标场景是把 Goodies 后来“删除 PowerMock 并迁到 Mockito 4”的维护者决策改写成“维护者在 PowerMock 1.6.2 下修复了兼容性”，或把 uaiMockServer 后加的 Mockito 1.10.19 当作不存在的 1.6.2 恢复。Git 提交、版本号和普通测试能够固定并验证人工实验，却不能证明维护者曾采用目标版本并做出该修复。

因此前置历史检查没有挤掉真正应执行的实验：本组缺少实验定义所必需的真实 A2，继续运行 Maven/JVM 只能测量合成方案，不能补成旗舰因果标签。

## 证据边界

本组证明 FSE 在三个独立根仓上记录了 1.6.1→1.6.2 探针边界后的失败，并精确解释了 Goodies 的缺类机制。它不提供精确目标修订、任何维护者 A2、限定负例或 A3；另外两条失败也不能从截断日志归到一个源提交。

机器可读候选、根仓裁决和历史证据分别位于 `candidate-frame.jsonl`、`root-audit.jsonl` 与 `history-evidence.json`；源摘录位于 `source-mechanism.patch`；紧凑结果位于 `results/powermock-api-mockito-1.6.2-fse-history-screening-2026-08-25/`。

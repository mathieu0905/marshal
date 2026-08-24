# 现成跨仓评测数据核验

**核验日期**：2026-08-22  
**范围**：BeyondSWE、公开版 DepBench、BUMP。第三方数据和重放工作树均位于 Marshal 仓库外的 `/home/zhihao/hdd/marshal-dataset-work`。

## 一、结论

三个数据集都是真实、可下载、可理解并能够抽样重放的数据，不需要从零建设大规模数据集。但它们测的是三个不同的子问题：

- BeyondSWE 测单个目标仓在解决问题时能否利用仓外知识；
- DepBench 测单个消费仓如何适配依赖升级；
- BUMP 测已发布依赖升级造成的动态破坏，并可按共同上游组织多个消费仓。

它们都没有直接提供“多个待合并仓库各自指定候选版本，然后联合构建”的任务。因此，现成数据足以启动评测，不足以完整替代 Marshal 的项目级多仓联合案例。

## 二、核验汇总

| 数据集 | 规模与结构 | 下载 | 抽样重放 | 许可状态 | 对 Marshal 的主要用途 |
|---|---|---|---|---|---|
| BeyondSWE | 500 例，其中 200 例标为 CrossRepo，覆盖 67 个目标仓 | 数据、Harbor 任务和公开镜像均可获取 | 1 例原生重放成功 | 数据集为 CC BY 4.0 | 仓外信息使用和单仓修复 |
| 公开版 DepBench | 201 例、157 个仓、5 类生态 | 任务包和审计元数据可获取 | 3 个生态重放成功，另 2 个样本静态核验 | 数据集卡标为 `other`，源仓许可逐仓给出 | 依赖升级问题定位、修复和测试 |
| BUMP | 571 个 Maven 破坏案例、153 个消费仓、每例前后两个镜像 | JSON、源码和按例镜像可获取；全量归档约 150 GB | 3 个上游组、6 个消费仓重放成功 | BUMP 仓库为 MIT，消费仓仍按各自许可 | 多消费仓影响和升级前后动态证据 |

## 三、BeyondSWE

### 1. 数据结构

公开 JSONL 共 500 行：

- CrossRepo：200；
- DepMigrate：178；
- DomainFix：72；
- Doc2Repo：50。

200 个 CrossRepo 样本均为 Python，分布在 67 个唯一目标仓。每行包含一个 `repo`、一个 `parent_commit`、一个修复提交、一个镜像地址、测试列表和参考补丁。没有相关仓库列表、依赖方向或每仓版本字段。

因此，“CrossRepo”表示解决单仓问题需要仓外知识，不等价于多仓候选版本联合审查。

### 2. 十例结构抽样

抽样覆盖 `plaster_pastedeploy`、`pyramid`、`hyundai_kia_connect_api`、`factory_boy`、`colander`、`units`、`trame-server` 和 `coveralls-python` 等仓库。十例都具备：

- 目标仓库地址；
- 基础提交和修复提交；
- 失败转通过测试；
- 公开 Docker Hub 镜像名；
- 参考修复补丁。

十例也都只有一个目标仓版本，未列出任务所依赖的具体仓外仓库和版本。

### 3. 重放

样本：`pylons_plaster_pastedeploy_pr14`。

- 基础提交：`0f052e79363cf0869bf3c368721128846cd6c919`；
- 测试：`ConfigDict.copy()` 和 `copy.copy()` 两例；
- 基础状态：2 个测试失败，均为构造参数缺失的 `TypeError`；
- 应用参考修复后：2 个测试通过；
- 环境：Python 3.11.11，本地隔离环境；
- 记录：`marshal-dataset-work/replays/beyondswe/pylons_plaster_pastedeploy_replay.log`。

公开镜像 `aweaiteam/beyondswe:pylons_plaster_pastedeploy_pr14` 已成功拉取。Harbor 的 Dockerfile仍引用不可公开访问的内部基础镜像，但公开构建后的镜像可用。本机 Docker 在容器创建阶段曾受到同机其他任务影响，因此本轮采用相同提交和测试的原生重放，不把这次环境问题记为数据失败。

### 4. 测试泄漏

公开 JSONL 和 Harbor 任务包本身包含测试补丁与参考修复。正式评测必须通过 Harbor 的挂载边界或等价隔离，在被测审查过程结束前不暴露 `tests/` 和 `solution/`。直接把完整任务目录交给审查器会造成答案泄漏。

## 四、公开版 DepBench

### 1. 数据结构和来源

本轮下载的公开版包含 201 个任务：

| 生态 | 任务数 | 唯一仓库数 |
|---|---:|---:|
| npm | 67 | 55 |
| Maven | 65 | 46 |
| Go | 39 | 34 |
| Cargo | 20 | 16 |
| Python | 10 | 6 |

每例包含任务说明、基础环境、依赖清单补丁、开发者修复、测试补丁和验证脚本。每例仍然只有一个消费仓。

公开 `analysis/` 元数据已另行下载。对五个抽样任务，审计文件确认：

- 基础提交均可从 Git 获取；
- Dockerfile 构建、运行、提交和工作树核验均通过；
- 依赖名称和旧、新版本与原始机器人 PR 相符；
- 五个源仓均有明确开源许可证；
- 测试补丁分类和破坏机制有逐例记录。

### 2. 五例抽样

| 样本 | 生态 | 依赖升级 | 破坏机制 | 核验 |
|---|---|---|---|---|
| `qntm__base65536__37` | npm | `safe-code-point` 1.0.0 到 2.0.0 | 包和模块命名空间 | 动态重放 |
| `smol-rs__async-lock__69` | Cargo | `event-listener` 3.0.0 到 4.0.0 | 函数签名和调用约定 | 动态重放 |
| `ymtdzzz__otel-tui__153` | Go | OpenTelemetry 0.107.0 到 0.108.0 | 类型、接口和结构 | 静态及官方构建审计 |
| `strawberry-graphql__strawberry__282` | Python | `graphql-core` 3.1.0b0 到 3.1.0b2 | 包和模块命名空间 | 静态及官方构建审计 |
| `lukas-krecan__JsonUnit__274` | Maven | AssertJ 3.16.1 到 3.17.1 | 间接运行时语义 | 动态重放 |

### 3. 三生态重放结果

| 样本 | 仅依赖升级 | 应用开发者修复 | 关键失败 |
|---|---:|---:|---|
| `qntm__base65536__37` | 失败 | 通过，3 个测试 | `generalCategory` 不再是函数 |
| `smol-rs__async-lock__69` | 失败 | 通过，库测试及 71 个文档测试 | `EventListener::new/listen` 签名变化导致 23 个编译错误 |
| `lukas-krecan__JsonUnit__274` | 失败 | 通过，目标测试 196 个 | AssertJ 消息中的内部 `KeyValue` 没有预期文本表示 |

重放使用数据记录的基础提交、依赖补丁、测试补丁和开发者修复。三例都观察到“仅升级失败、修复后通过”。日志位于 `marshal-dataset-work/replays/depbench/`。

### 4. 许可和版本风险

Hugging Face 数据集卡将公开版许可证标为 `other`，虽然审计元数据列出了 157 个源仓的具体许可证。正式再分发任务包前，需要数据维护者给出更明确的数据集级许可说明。

公开版有 201 例和 5 个生态，不能直接当作 DepRepair 论文所述 95 例、4 个生态的同一版本。报告中应始终称为“公开版 DepBench 201”。

## 五、BUMP

### 1. 数据结构

本地 `data/benchmark` 含 571 个 JSON。每例给出：

- 消费仓 PR 和破坏提交；
- 依赖坐标、旧版本和新版本；
- 尽可能提供上游 GitHub 比较链接；
- 升级前和升级后镜像命令；
- Java 版本和失败类别。

官方提供 1142 个镜像，即每例升级前和升级后各一个。全量加载需要约 250 GB 展开空间，本轮没有下载全量归档，只按需要使用 JSON、Git 提交和单个镜像。

### 2. 多消费仓分组

按有效上游仓库统计，数据中有多个上游影响两个以上消费仓。首轮选择：

- `jcabi/jcabi-aspects`：`jcabi-s3`、`jcabi-simpledb`；
- `qos-ch/slf4j`：`sign-maven-plugin`、`jasmine-maven-plugin`；
- `fasterxml/jackson-databind`：`simplelocalize-cli`、`dependency-lock-maven-plugin`。

### 3. 六例重放

使用每个消费仓的破坏提交及其父提交，在 OpenJDK 11 和 Maven 3.9.8 下运行数据镜像声明的 `mvn clean test -B`。结果如下：

| 上游 | 消费仓 | 父提交 | 破坏提交 | 观察结果 |
|---|---|---:|---:|---|
| `jcabi-aspects` | `jcabi-s3` | 通过 | `24d4a90` 失败 | 编译失败 |
| `jcabi-aspects` | `jcabi-simpledb` | 通过 | `7d97e1c` 失败 | 测试编译找不到 `Tv` |
| `slf4j` | `sign-maven-plugin` | 通过 | `072528e` 失败 | 日志模拟绑定失效，测试错误 |
| `slf4j` | `jasmine-maven-plugin` | 通过 | `426453d` 失败 | 日志断言失败 |
| `jackson-databind` | `simplelocalize-cli` | 通过 | `741f3b5` 失败 | 缺少 `StreamReadException`，编译失败 |
| `jackson-databind` | `dependency-lock-maven-plugin` | 通过 | `6cb50e7` 失败 | 依赖锁期望版本与解析版本不一致 |

六例均得到 `PRE_RC=0` 和 `BREAKING_RC=1`，与官方类别一致。日志位于 `marshal-dataset-work/replays/bump/`。

本机还拉取并启动了一个未纳入上述六例的官方前置镜像。该镜像中的测试持续通过，但 Maven 进程没有正常退出，容器停止也出现 Docker 运行时阻塞。因为直接 Git 重放已对六个正式样本得到明确前后结果，本轮不把这个单例运行时异常扩大成 BUMP 数据缺陷。

### 4. 适用边界

BUMP 是本轮最适合组织“一个上游、多个消费仓”的数据，但消费仓使用的是已发布 Maven 版本。上游比较链接提供源码差异，却没有让消费仓从上游候选提交现场构建产物。因此它能测影响扩散，不能单独证明未发布候选版本联合验证。

## 六、最终判断

现成数据不是没有，而是没有一个数据集独立覆盖 Marshal 想要的全部能力。合理组合是：

1. 用 BeyondSWE 测仓外知识使用；
2. 用公开版 DepBench 201 测多生态单消费仓依赖升级；
3. 用 BUMP 测共同上游的多消费仓破坏；
4. 另外补少量真实协调变更，专门测多个未发布候选版本的联合执行。

前三项已经可以立即作为评测主体。第四项只需小规模补充，不需要重新建设一个几百例的数据集。

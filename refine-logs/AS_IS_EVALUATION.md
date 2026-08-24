# Marshal 原样评测结果

**日期**：2026-08-22  
**代码版本**：`71d91c1`  
**原则**：使用当前 Marshal 和当前 CowboyPack，不新增第三方项目规则，不修改产品代码。

## 一、方法

本轮对三类数据执行当前可直接复用的两个机械入口：

```bash
.venv/bin/python -m marshal_core.cli classify --repo <仓库> --paths <改动路径>
.venv/bin/python -m marshal_core.cli invariants --repo <仓库> --paths <改动路径>
```

改动路径来自数据集参考补丁或真实升级提交。由于当前结构化任务只能携带一个仓库和一个版本，本轮没有伪造第二个仓库，也没有把第三方依赖规则写入 CowboyPack。

“原样评测”回答的是：当前 Marshal 实际能看到什么、会生成什么计划、能够执行到哪里。它不是对语言模型自由审查能力的得分测试。

## 二、汇总

| 数据来源 | 输入数 | 中风险 | 命中契约 | 生成不变量 | 自动异仓执行 | 候选版本消费确认 |
|---|---:|---:|---:|---:|---:|---:|
| BeyondSWE | 5 | 5 | 0 | 0 | 0 | 0 |
| DepBench | 5 | 5 | 0 | 0 | 0 | 0 |
| BUMP | 6 | 6 | 0 | 0 | 0 | 0 |
| 合计 | 16 | 16 | 0 | 0 | 0 | 0 |

所有样本都得到通用的 `correctness`、`spec` 和 `cross-repo` 审查维度；涉及测试文件的部分 BeyondSWE 样本还得到 `test-validity`。这里的 `cross-repo` 只是提示词维度，不代表找到了任何具体相关仓库。

## 三、BeyondSWE

| 样本 | 目标仓 | 主要改动 | 分类 | 契约 / 不变量 |
|---|---|---|---|---|
| `pylons_plaster_pastedeploy_pr14` | `plaster_pastedeploy` | `ConfigDict` 复制行为和测试 | 中风险 | 0 / 0 |
| `pylons_pyramid_pr1373` | `pyramid` | 请求对象和相关测试 | 中风险 | 0 / 0 |
| `hyundai-kia-connect_hyundai_kia_connect_api_pr489` | `hyundai_kia_connect_api` | 欧洲接口实现 | 中风险 | 0 / 0 |
| `pylons_pyramid_pr2874` | `pyramid` | 配置初始化和测试 | 中风险 | 0 / 0 |
| `factoryboy_factory_boy_pr1059` | `factory_boy` | 多个工厂实现和类型测试 | 中风险 | 0 / 0 |

Marshal 实际只看到目标仓名和补丁路径。BeyondSWE 的“跨仓”标签、问题说明、仓外知识来源和镜像信息都没有对应的当前核心输入字段，因此没有进入分类或检查计划。

## 四、DepBench

| 样本 | 生态 | 依赖变化 | 已知失败机制 | 分类 | 契约 / 不变量 |
|---|---|---|---|---|---|
| `qntm__base65536__37` | npm | `safe-code-point` 1.0.0 到 2.0.0 | 包和模块命名空间 | 中风险 | 0 / 0 |
| `smol-rs__async-lock__69` | Cargo | `event-listener` 3.0.0 到 4.0.0 | 函数签名和调用约定 | 中风险 | 0 / 0 |
| `ymtdzzz__otel-tui__153` | Go | OpenTelemetry 0.107.0 到 0.108.0 | 类型、接口和结构 | 中风险 | 0 / 0 |
| `strawberry-graphql__strawberry__282` | Python | `graphql-core` 3.1.0b0 到 3.1.0b2 | 包和模块命名空间 | 中风险 | 0 / 0 |
| `lukas-krecan__JsonUnit__274` | Maven | AssertJ 3.16.1 到 3.17.1 | 间接运行时语义 | 中风险 | 0 / 0 |

数据已经给出了依赖名称、旧版本、新版本、基础提交、修复补丁和测试，但当前 Marshal 入口只消费仓名和改动路径。`package.json`、`Cargo.toml`、`go.mod`、`poetry.lock` 和 `pom.xml` 没有触发通用依赖升级规则。

## 五、BUMP 多消费仓组

| 上游 | 消费仓 | 升级提交 | 官方失败类别 | 分类 | 契约 / 不变量 |
|---|---|---|---|---|---|
| `jcabi/jcabi-aspects` | `jcabi/jcabi-s3` | `24d4a90` | 编译失败 | 中风险 | 0 / 0 |
| `jcabi/jcabi-aspects` | `jcabi/jcabi-simpledb` | `7d97e1c` | 编译失败 | 中风险 | 0 / 0 |
| `qos-ch/slf4j` | `s4u/sign-maven-plugin` | `072528e` | 测试失败 | 中风险 | 0 / 0 |
| `qos-ch/slf4j` | `searls/jasmine-maven-plugin` | `426453d` | 测试失败 | 中风险 | 0 / 0 |
| `fasterxml/jackson-databind` | `simplelocalize/simplelocalize-cli` | `741f3b5` | 编译失败 | 中风险 | 0 / 0 |
| `fasterxml/jackson-databind` | `vandmo/dependency-lock-maven-plugin` | `6cb50e7` | 依赖锁失败 | 中风险 | 0 / 0 |

六个升级提交都只改动一个 Maven 清单。Marshal 没有读取 BUMP JSON 中的上游仓库、版本比较链接和失败类别，因此三个共同上游分组在输入后完全消失，变成六个无关联的单仓任务。

## 六、与已登记 Cowboy 契约的对照

同一代码版本下，`wallet` 的 `src/lib/cbor.js` 能命中 `tx-encoding`，并返回两个位于 `node` 的检查。这说明本轮 16 个空计划不是命令失效，而是现有领域包只认识预登记项目。

自动报告器即使拿到异仓不变量，也会将其记为 `not_run` 并降级。因此，把第三方项目简单补进契约最多能获得“去哪里检查”的计划，仍不能形成多个候选版本的联合执行。

## 七、失败归因

| 观察 | 归因 |
|---|---|
| 第三方项目没有契约和不变量 | 配置与数据映射缺失 |
| 数据集元数据没有进入任务 | 输入适配缺失 |
| BUMP 共同上游分组丢失 | 项目级任务表达缺失 |
| 异仓检查无法自动运行 | 现有执行能力缺失 |
| 无法指定每仓版本 | 组合未验证 |
| 无法确认消费候选产物 | 组合未验证 |

## 八、判断

当前 Marshal 对固定 Cowboy 项目的跨仓路由已经可用；对任意团队项目，并不是“再写一份已有配置就全部解决”。至少还需要一个能够保留多仓身份、版本和依赖方向的评测输入，以及在相关仓库执行现有检查的方式。

在这些输入和执行事实出现前，不应把原样结果解释成模型推理失败，也不应先增加新的发布门禁。

# Swagger Models 2.1.10 的 FSE 关系族筛选

更新日期：2026-08-25

## 结论

完整精确版本框共有 2 条候选、12 个失败观察，去重后对应 `javalin/javalin` 和 `jooby-project/jooby` 两个独立根仓。

Javalin 构成 1 条通过执行验证的因果正关系。固定目标修订为维护者拉取请求 1381 的父提交 `57bb56fe5d98608216b8f638a593ea3859a97c76`：A0 使用 `swagger-models` 2.1.6 时 53 项通过；A1 只把该模块的直接依赖改为 2.1.10 后 53 项中 14 项因输出多出 `exampleSetFlag` 而失败，其中覆盖 FSE 记录的 10 个方法；A2 使用维护者提交 `6e247c66798089d06ed6108069f5d4efbbf3ceb3` 后 53 项全部恢复。该提交还新增了题名为“schema validates without warning about unexpected exampleSetFlag”的回归测试，修复意图没有歧义。

Jooby 不接纳。它直到 2022 年才从 2.1.6 直接升级到 2.1.13，维护者提交只改版本属性，没有任何保持 2.1.10 的目标侧恢复。把 2.1.13 的协调升级改写成 2.1.10 的 A2 会改变源输入，不符合当前三臂定义。

本组因此接纳 1 条正关系，但没有限定负例或 A3，不能独立算作完整旗舰项目包。

## 完整候选框

| 候选 | 模块 | 失败观察 | 根仓 | 裁决 |
|---|---|---:|---|---|
| `fse2024-behavioral-0232` | `io.javalin:javalin-openapi` | 10 个断言失败 | `javalin/javalin` | 接纳 1 条正关系 |
| `fse2024-behavioral-0233` | `io.jooby:jooby-openapi` | 2 个异常 | `jooby-project/jooby` | 无同版本 A2，拒绝 |

两个目录提示分别指向不同公开仓库，没有模块别名或共享 Git 历史，因此根仓数为 2。

## 精确源变化

`swagger-models` 2.1.9 标签提交为 `ff64b437030687e02fb00025cc5cc0de1b2d6263`，2.1.10 标签提交为 `e983e03207a2e8471ebb8d22a14784034b6b0d7c`。标签之间只有两个生产行为提交；本组失败由 `f95621890a7a7160489539336020346c2299d206` 直接引入。它给 `MediaType` 增加布尔属性 `exampleSetFlag` 及公开 getter，同时在 swagger-core 自己的 Jackson 配置中加入对应 mixin。

使用 swagger-core 官方映射器时 mixin 会隐藏该内部标记；只升级模型制品或使用未注册新 mixin 的客户端映射器时，Jackson 会把 getter 当成 OpenAPI 字段序列化。这精确解释两仓日志中的额外 `exampleSetFlag`、Javalin 的文本比较失败和 Jooby 校验器的“属性不应出现”。后续提交 `f18169a046f9ad8a1656031e70138b5e3cfaa3bd` 只调整设置示例值时的转换逻辑，不产生该字段。

## Javalin 三臂

维护者拉取请求 1381 同时完成依赖采用和适配。它把 Swagger 版本改到 2.1.10，并把 Javalin 自建、只注册旧 `SchemaMixin` 的映射器替换为 swagger-core 的 `Json.mapper()`；后者包含 2.1.10 新增的 `MediaTypeMixin`，从而不再泄漏内部标记。新增回归测试直接断言验证器不再报告 `exampleSetFlag`。

本轮使用 Java 11、项目原生 Maven 配置和四个含 FSE 方法的测试类执行：

| 臂 | 目标输入 | 结果 |
|---|---|---|
| A0 | `57bb56fe...`，原生 `swagger-models` 2.1.6 | 53/53 通过 |
| A1 | 同一提交，只把 `swagger-models` 直接依赖固定为 2.1.10 | 14 个断言失败、39 个通过；失败输出反复出现 `exampleSetFlag` |
| A2 | 维护者提交 `6e247c66...`，Swagger 2.1.10 与官方映射器 | 53/53 通过 |

A1 比工作簿多捕获 4 个同类失败，因为固定修订的四个完整测试类比 FSE 去重表覆盖更广；工作簿列出的 10 个方法都在失败集合中。这里按根仓计 1 条关系，不按 10 个方法扩张。

## Jooby 裁决

Jooby 的公开失败来自模型 2.1.10 与仍为 2.1.6 的 swagger-core 映射器失配。完整历史中，首个后续采用提交 `970f17c916159865c3ea373728bc4e3dc349e21e` 直接把统一 `swagger.version` 从 2.1.6 升到 2.1.13；提交只修改根 POM 和 BOM 的版本属性，没有目标代码修复。

这个提交说明维护者最终通过同版本协调消除了失配，但它没有保持本题源输入 2.1.10。若把属性值手工改成 2.1.10，可以构造一个合理修复，却不是维护者提交。按“同一新版本输入下的历史恢复”要求，Jooby 在重放前拒绝。

## 证据边界

Javalin 证明的是“模型新增可见 getter 后，客户端自建 Jackson 映射器必须跟进新的 Swagger mixin”，不是 2.1.10 对所有消费者的普遍破坏。Jooby 保留为版本协调线索，不进入正式正例。当前没有对变化面有执行覆盖的干扰仓，也没有兼容源变化 A3。

执行日志位于 `results/swagger-models-2.1.10-fse-screening-2026-08-25/`；机器可读候选和根仓裁决位于本目录的 `candidate-frame.jsonl`、`root-audit.jsonl` 和 `history-evidence.json`。

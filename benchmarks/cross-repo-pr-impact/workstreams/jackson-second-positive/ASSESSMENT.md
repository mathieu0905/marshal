# Jackson Databind 第二正例筛选记录

评估日期：2026-08-25

## 结论

Jackson Databind 的 FSE 候选框共有 14 条记录，折叠为 12 个独立根仓。本轮接纳一条高强度因果锚点：Databind 提交 `2897aa00e04e3a28aef45f5b485001db161e2e2c` 为 `Object.class` 加入快速内省路径，使 `RWS/dxa-web-application-java` 依赖的 `Object.class` 多态混入不再生效；目标仓维护者随后加入专用内省器和模型标记接口完成适配。

同一目标基准和同一回归测试的三臂结果为：

| 臂 | Databind 输入 | 目标输入 | 结果 |
|---|---|---|---|
| A0 | 精确父提交 `a8d8ec0e92b6220381a8eae38d4bf8765c7c9ca1` | `6bedc440f72e5cee768db367d59f5bb26e4512e8` 加测试装置 | 通过，1 项测试 |
| A1 | 精确行为提交 `2897aa00e04e3a28aef45f5b485001db161e2e2c` | 与 A0 相同 | 失败，`EntityModelData` 多态恢复断言失败 |
| A2 | 与 A1 相同 | A1 目标加维护者因果修复 | 通过，1 项测试 |

这条关系使用新的精确源合同，不同于既有 Jackson 项目包中的 Splunk 版本协调正例、两个限定负例和相邻次版本兼容控制。它可新增一个链独立正关系，但当前没有同合同限定负例或同合同 A3，因此不能把“完整旗舰项目包”数量增加一包。

## 精确源变化

源提交标题是 `Small (but measurable) improvement to class introspection handling for "untyped" (Object) case, one-off mappers`。它只修改 `BasicClassIntrospector`：新增缓存的 `OBJECT_DESC`，并在 `_findStdTypeDesc` 中直接返回该描述。这个快速路径不解析目标对象映射器为 `Object.class` 注册的混入。

`source-change.patch` 保存完整提交差异。A0 与 A1 均从对应 Git 提交构建 Databind；构建时只把源码树的父 POM 从不可用的 `2.11.0-SNAPSHOT` 指向已发布的 `2.11.0`，Java 源码没有其他差异。两臂统一使用 Jackson Core 2.10.5 和 Jackson Annotations 2.10.5，所以观察到的变化不能归因于完整 2.11.0 发布中的其他提交。

## 目标仓和维护者修复

目标基准 `6bedc440f72e5cee768db367d59f5bb26e4512e8` 位于维护者修复分支的直接祖先。修复证据来自维护者提交：

- `ef4c26df93c2ec02ffb45752c8e23015b57ccd85`；
- `8b5d02ba3dfe1925ee8482eb69f0560686f790b4`。

两条提交标题均为 `jackson 2.11+ fix`。A2 只提取与本合同有关的改动：

- 在 `DxaSpringInitialization` 的产品对象映射器中覆盖 `Object.class` 的内省处理；
- 新增 `JsonPojo` 标记接口并让数据模型实现它；
- 为 `JsonPojo` 注册 `PolymorphicObjectMixin`。

`maintainer-repair.patch` 保存该因果子集。维护者提交中的命名策略迁移、自动模块发现、异常类型和消息调整、版本升级本身均未进入 A2。

## 测试合同

回归测试 `JacksonObjectMixinCompatibilityTest.shouldDeserializePolymorphicExtensionData` 使用维护者产品路径 `new DxaSpringInitialization().objectMapper()` 和目标仓原有的 `pageModel.json`。断言沿用 FSE 原始失败所覆盖的多态扩展数据：

- `EntityModelData` 必须恢复为 `EntityModelData`；
- `EntityModelDatas` 必须恢复为 `ListWrapper`。

A1 在第一项断言失败，位置为 `JacksonObjectMixinCompatibilityTest.java:24`。这与 FSE 0028 中 `DeserializationTest.assertExtensionData` 的原始断言失败同向。A2 在完全相同的输入和断言下恢复。

## 必须保留的边界

原始模块测试 `DeserializationTest.shouldDeserializePageModel` 的结果是 A0 通过、A1 失败、A2 仍失败。独立模块使用 `DataModelSpringConfiguration`，没有产品配置 `DxaSpringInitialization` 中维护者加入的 `Object.class` 专用内省器。因此本包证明的是维护者实际产品对象映射器路径的严格 A0/A1/A2，不声称原始 FSE 测试命令本身在 A2 恢复。

FSE 0028 与 0029 属于同一根仓，不能拆成两个独立正例；Swagger 的 0030 与 0031 同样按一个根仓计。其他候选没有恢复出同等强度的“精确源提交、原生失败合同、维护者修复”三元组。逐条判定见 `candidate-screening.jsonl`。

本轮没有建立该精确合同的限定负例或 A3。没有维护者修复、没有观察到失败或项目停止维护，都不能据此标成“不受影响”。

执行日志和 Surefire 报告位于 `results/jackson-second-positive-dxa-2026-08-25/`。当前语义结论仍需另一名复核者独立确认。

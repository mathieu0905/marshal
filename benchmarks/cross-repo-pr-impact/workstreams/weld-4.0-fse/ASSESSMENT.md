# Weld 4.0 候选历史筛选

## 结论

FSE 2024 复现实验中，Weld `3.0.0.Final -> 4.0.0.CR1` 共命中 12 条记录，覆盖两个 Maven 坐标和 7 个模块。但这些记录全部来自 `astefanutti/camel-cdi`，折叠后只有 1 个跨仓关系。

该关系有清晰且可定位的上游机制：Weld 4 将 CDI 类型和服务发现入口从 `javax.enterprise` 迁移到 `jakarta.enterprise`。这能直接解释公开执行中的两类错误：

- `javax.enterprise.inject.se.SeContainerInitializer` 找不到 Weld 4 以 Jakarta 名称注册的实现，报 `No valid CDI implementation found`；
- Camel CDI 及其依赖提供的是 `javax.enterprise.inject.spi.Extension` 实现，Weld 4 按 `jakarta.enterprise.inject.spi.Extension` 装载后发生 `ClassCastException`。

不过，目标仓完整历史中没有 Weld 4 或 Jakarta 迁移，也没有维护者恢复提交。按照当前数据集的三臂定义，不能用数据集作者编写的命名空间迁移冒充维护者 A2。因此本组在重放前拒绝，正式接纳 0 条。

## 候选框折叠

12 条记录分成两组：

| 坐标 | 记录 | 模块 |
|---|---:|---|
| `org.jboss.weld.se:weld-se-core` | 6 | `impl`、`samples/hello`、`samples/metrics`、`samples/properties`、`samples/sjms`、`samples/xml` |
| `org.jboss.weld:weld-core-impl` | 6 | `envs/ee`、`samples/hello`、`samples/metrics`、`samples/properties`、`samples/sjms`、`samples/xml` |

重复模块来自同一仓库、同一次版本替换和同一命名空间断裂，不能按 12 个独立案例计数。候选明细保存在 `candidate-frame.jsonl`，根仓裁决保存在 `root-audit.jsonl`。

## 上游变化边界

版本标签解引用后的提交为：

- `3.0.0.Final`：`42e40b56341205984c9275b44a5b73fb098237c7`
- `4.0.0.CR1`：`45756d46bae876bb16f1e11c01d898e79f2587f4`

正式标签祖先中的关键迁移提交是 `0338683d17f782d4f7ad533654b21f565c92b2e9`，标题为 `An updated Jakarta EE 9 WIP off of master`。它修改 3580 个文件，并包含本组错误所经过的精确路径：

- `ExtensionBeanDeployer` 的类型约束从 `javax.enterprise.inject.spi.Extension` 改为 `jakarta.enterprise.inject.spi.Extension`；
- Weld SE 的 `SeContainerInitializer` 服务描述文件从 `javax.enterprise.inject.se.SeContainerInitializer` 改名为 Jakarta 对应名称；
- Weld SE 的 `Extension` 服务描述文件也从 `javax.enterprise.inject.spi.Extension` 改名为 Jakarta 对应名称；
- `Weld` 本身继承的 `SeContainerInitializer` 与接收的 `Extension` 类型同步改为 Jakarta 类型。

这里不能把整个标签差异当作单一 Marshal 源变更，因为标签之间还包含大量其他变化。可归因的是上述命名空间迁移机制，而不是完整发布差异。

## 目标仓历史

`astefanutti/camel-cdi` 的远程引用包含 792 个可达提交，时间范围为 2014-08-26 至 2017-11-13。对全部 523 个唯一 POM 内容块的检查结果为：

- 166 个声明 `<weld.version>`；
- 7 个使用 `3.0.0.Final`；
- 0 个使用 `4.0.0.CR1`。

提交 `2ab8814006158e94898072f215eb20076c333ece` 只把根 POM 的 Weld 从 `3.0.0.Beta1` 升级到 `3.0.0.Final`。仓库最终版本仍在 `CdiCamelExtension` 中实现 `javax.enterprise.inject.spi.Extension`，服务文件也仍名为 `META-INF/services/javax.enterprise.inject.spi.Extension`。整个可达历史没有采用 `jakarta.enterprise` 的 Java 或 XML 变化。

目标仓最后一次活动早于 Weld 4.0.0.CR1 发布三年，因此不存在可恢复的历史 A1 和维护者 A2。

## 为什么不执行三臂

如果只固定 Git 提交和版本号，然后由数据集作者把 Camel CDI 全面改成 Jakarta，普通测试很可能得到 A0 通过、A1 失败、手工 A2 通过的漂亮方向，但它证明的只是“作者能移植这个项目”，不是“维护者曾如何响应上游变化”。版本号和提交号能固定输入，普通测试能测运行结果，都不能补出缺失的维护者行为主键。

本组的具体误标风险是把一个停止维护的 `javax` 项目，事后移植到 2020 年发布的 Jakarta 依赖，并把该移植记作历史真实影响。这个风险无法通过增加重复次数或断言解决，所以在执行前停止。

## 证据边界

12 条公开失败继续保留为高质量影响线索，尤其适合检验 Marshal 是否能从服务发现文件和类型命名空间识别跨仓影响。但在以维护者 A2 为准入条件的旗舰因果集里，它们只贡献 1 个被拒绝的根仓候选，不贡献正例、负例或 A3。

完整统计位于 `history-evidence.json`，紧凑结果位于 `results/weld-4.0-fse-history-screening-2026-08-25/summary.json`。

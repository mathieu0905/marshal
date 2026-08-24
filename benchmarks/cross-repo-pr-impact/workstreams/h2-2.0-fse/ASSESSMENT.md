# H2 2.0 FSE 高密度候选筛选

评估日期：2026-08-25

## 结论

FSE 候选框中 H2 1.4.200 到 2.0.202 的 16 条记录，折叠后只有 10 个独立根仓。本轮没有找到“同一个精确 H2 变化、至少两个独立目标根仓、两边都有维护者修复”的关系族，因此拒绝把这一组作为多仓旗舰项目包。

本轮接纳一条单仓因果锚点：H2 把 `VALUE` 变成关键字，导致 `jhannes/fluent-jdbc` 两个测试类使用的未引用列名无法建表；维护者随后把这些列改名为 `amount`。该关系的 A0、A1、A2 已由 13 个原生测试重放。它可作为一条正关系进入锚点储备，但不能冒充多仓关系族。

正式计数如下：

- 候选记录：16；
- 独立根仓：10；
- 接纳的跨仓正关系：1；
- 正目标根仓：1；
- 限定负例：0；
- A3：0；
- 多仓旗舰项目包：拒绝。

逐根仓判定保存在 `candidate-root-audit.jsonl`。没有维护者修复只说明缺少 A2 证据，不能把这些仓库标成“不受影响”的负例。

## 精确源变化

源变化是 [h2database/h2database#2297](https://github.com/h2database/h2database/pull/2297) 中的提交 `4c40a20aece767dde1ef8a41c5a7c764bc1d20a8`，标题为 `Add DomainValueExpression`。该提交在 `ParserUtil` 中加入 `VALUE` 词元，并使解析器把它作为关键字处理。只包含解析器相关部分的补丁保存在 `h2-value-keyword-source.patch`。

源提交本身还包含同一功能的其他重构，所以不能仅凭提交标题建立标签。本包把其父提交 `1b9ddc11be1d603a3fd98b2f0440fb2537376c2e` 和该提交分别构建成 H2 jar，再用完全相同的 fluent-jdbc 基准与测试比较。A1 的错误明确指向：

```text
Syntax error in SQL statement
CREATE TABLE ... VALUE[*] INTEGER NOT NULL ...
expected "identifier"
```

这与新增 `VALUE` 词元及维护者改名行为同向，排除了 H2 2.0.202 其余发布差异。

## fluent-jdbc 三臂

目标基准提交为 `50ee7bd1c34a6fc3867a6620f97b415c8862dd65`，维护者修复提交为 `22027921c9dfb8c4bc97c92b0f9453b3dbf4098d`。维护者提交同时处理数组类型，但 A2 只采用两个测试文件中 `value` 到 `amount` 的改名，补丁保存在 `fluent-value-maintainer-repair.patch`。

执行的原生测试类为：

- `org.fluentjdbc.DbContextSyncBuilderTest`；
- `org.fluentjdbc.FluentJdbcContextDemonstrationTest`。

| 臂 | H2 输入 | 目标输入 | 结果 |
|---|---|---|---|
| A0 | 精确源提交的父提交 `1b9ddc11be1d603a3fd98b2f0440fb2537376c2e` | 目标基准 | 通过，13 个测试 |
| A1 | 精确源提交 `4c40a20a` | 目标基准 | 失败，23 个测试调用错误，根错误均为未引用 `VALUE` 的 `42001` |
| A2 | 精确源提交 `4c40a20a` | 目标基准加最小维护者改名 | 通过，13 个测试 |

历史项目使用 Lombok 1.18.12，无法在当前 Java 21 编译。三个临时工作树统一把测试依赖升级到 Lombok 1.18.38；该变化没有写入证据补丁，也不改变 H2、目标逻辑或测试断言。旧 JaCoCo 对 Java 21 标准库打印插桩警告，但 Maven 退出码和 Surefire XML 均确认 A0、A2 通过，A1 以目标 SQL 错误失败。

## 未形成多仓族的原因

最接近的两根仓簇是 `USER` 关键字变化。精确 H2 提交为 `65969409da11d6cf809f0b8be1be7f4473934559`，FSE 中同时命中 `Devskiller/jpa2ddl` 与 `minijax/minijax`。前者只有依赖版本更新，当前代码仍保留未引用的 `User`；后者在 H2 2.x 发布前停止维护，始终固定于 1.4.200。两个根仓都没有可用于 A2 的维护者修复，因此这个高密度簇不能接纳。

`Feedzai/pdb` 有很强的 H2 v2 维护者响应，但一个提交同时加入兼容模式、生成键、自增序列、元数据、LOB 绑定等多项适配。FSE 记录也混合三类失败。本轮无法把它压缩为一个精确 H2 提交和一个最小 A2，暂时只保留为后续单仓线索。

Camunda 的三条记录折叠为两个根仓，失败发生在 Camunda 引擎持久层；目标仓自身只有版本升级或继承上游兼容，不能把上游引擎修复冒充目标仓的维护者修复。Minijax 四条和 Nuxeo 三条也分别只能计一个根仓。

## 负空间与边界

本轮没有限定负例。候选仓没有修复、项目归档、或当前代码仍保留旧写法，都不能证明仓库不受影响。

本轮也没有 A3。A0 使用的是行为提交父状态，它证明旧行为兼容，但不是一条独立的相邻源变化，因此没有重复计作 A3。

结果目录为 `results/h2-2.0-fse-screening-2026-08-25/`，包含三臂日志、六份 Surefire XML 与机器摘要。当前语义结论仍需另一名复核者独立确认；复核前不得把同仓模块拆成额外样本，也不得把这条单仓锚点描述成多仓关系族。

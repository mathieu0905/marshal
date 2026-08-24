# H2 2.0 FSE 高密度候选筛选

评估日期：2026-08-25

## 结论

FSE 候选框中所有以 H2 2.0.202 为破坏版本的记录共有 49 条，折叠为 36 个目录根仓、35 个独立 Git 历史。`reyez/ninja` 是 `ninjaframework/ninja` 的分叉目录，但两条候选实际指向同一段历史，因此只计一次独立历史。旧口径只统计 `current_version=1.4.200`，遗漏了从更早 H2 版本直接升级到 2.0.202 的 33 条记录，现已废止。

本轮接纳同一个精确源变化下的两条独立正关系。H2 把 `VALUE` 变成关键字，分别导致 `jhannes/fluent-jdbc` 和 `BrunoEberhard/minimal-j` 生成的未引用列名无法建表；两边都有维护者修复，且均完成严格 A0/A1/A2 重放。fluent-jdbc 由 13 个原生测试证明，Minimal-J 由 7 个原生测试证明。这已经构成两个独立目标仓的因果关系族，但因为没有限定负例和 A3，仍不是完整旗舰项目包。

正式计数如下：

- 候选记录：49；
- 目录根仓：36；
- 独立 Git 历史：35；
- 接纳的跨仓正关系：2；
- 正目标根仓：2；
- 限定负例：0；
- A3：0；
- 多仓旗舰项目包：尚未完成。

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

## Minimal-J 三臂

目标基准提交为 `1e432bda7cdf89eba0136c8f5b641a5ac5e956f9`，维护者修复提交为 `9bebccf5d20f7a96c8d7393f4b544b97480f7401`。修复只修改 `src/main/resources/org/minimalj/util/reservedSqlWords.txt`，加入 H2 关键字表，其中包含 `VALUE`。完整维护者补丁保存在 `minimal-j-value-maintainer-repair.patch`。

执行的原生测试类为：

- `org.minimalj.model.backend.TransactionTest`；
- `org.minimalj.repository.sql.relation.SqlCrudTest`。

| 臂 | H2 输入 | 目标输入 | 结果 |
|---|---|---|---|
| A0 | 精确源提交的父提交 `1b9ddc11be1d603a3fd98b2f0440fb2537376c2e` | 目标基准 | 通过，7 个测试 |
| A1 | 精确源提交 `4c40a20aece767dde1ef8a41c5a7c764bc1d20a8` | 目标基准 | 失败，7 个唯一测试方法全部报错；Surefire XML 共记录 14 条方法错误与清理错误 |
| A2 | 与 A1 完全相同的 H2 制品 | 维护者修复提交 | 通过，7 个测试 |

三个正式臂使用 Java 11、同一离线依赖环境和同一测试合同。A1 的 14 条 XML 错误记录不是 14 个不同测试，也不是重跑：7 个唯一方法各产生一条主错误和一条 `@After` 清理错误。每个方法的记录中都出现未引用 `value` 的 `42001` 主签名；其余记录是建表失败后的清理空指针或全局应用状态级联错误。历史 H2 测试工具依赖已移除的旧 Doclet API，因此源仓构建统一跳过测试，仅把生成的主 JAR 交给目标重放；目标仓原生测试没有跳过。重放显式把 `TMPDIR` 和 `java.io.tmpdir` 指向项目内 `.work/fse-h2-2.0.202/tmp/`。

## 其余候选的处理

`USER` 关键字变化的精确 H2 提交为 `65969409da11d6cf809f0b8be1be7f4473934559`，FSE 中同时命中 `Devskiller/jpa2ddl` 与 `minijax/minijax`。前者只有依赖版本更新，当前代码仍保留未引用的 `User`；后者在 H2 2.x 发布前停止维护，始终固定于 1.4.200。两个根仓都没有可用于 A2 的维护者修复，因此这个簇不能接纳。

`Feedzai/pdb` 有很强的 H2 v2 维护者响应，但一个提交同时加入兼容模式、生成键、自增序列、元数据、LOB 绑定等多项适配。FSE 记录也混合三类失败。本轮无法把它压缩为一个精确 H2 提交和一个最小 A2，暂时只保留为后续单仓线索。

Camunda 的多条记录中，失败常发生在引擎持久层；目标仓自身只有版本升级或继承上游兼容时，不能把上游引擎修复冒充目标仓的维护者修复。Minijax 四条、Querydsl 三条、Hammock 三条和 Nuxeo 三条都按根仓折叠。其余尚未完成维护者 A2 回收的候选只记为“证据不足”，不作为负例。

## 负空间与边界

本轮没有限定负例。候选仓没有修复、项目归档、或当前代码仍保留旧写法，都不能证明仓库不受影响。

本轮也没有 A3。两个目标都使用行为提交父状态作为 A0，它证明旧行为兼容，但不是一条独立的相邻源变化，因此没有重复计作 A3。Minimal-J 的前一个相邻提交只修改 H2 测试脚本，没有独立生产行为；后继提交从已经破坏的状态出发，也不能提供相容对照。

两个目标的结果目录均为 `results/h2-2.0-fse-screening-2026-08-25/`。Minimal-J 只证明生成 SQL 标识符上的 `VALUE` 关键字影响；源提交共修改 51 个文件，还包含领域值表达式变化，不能声称本重放覆盖了整个源提交。当前语义结论仍需另一名复核者独立确认；复核前不得把同仓模块拆成额外样本，也不得把“两正例关系族”描述成完整旗舰项目包。

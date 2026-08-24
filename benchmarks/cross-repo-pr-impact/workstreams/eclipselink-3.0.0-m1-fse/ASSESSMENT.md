# EclipseLink 3.0.0-M1 的 FSE 关系族筛选

更新日期：2026-08-25

## 结论

完整精确版本框共有 4 条候选、12 个失败观察，分别对应 `rmpestano/dbunit-rules`、`cellux-git/fluent-jdbc`、`tennaito/rsql-jpa` 和 `kuros/random-jpa`，去重后仍是 4 个独立根仓。本轮正式接纳 0 条，没有执行 A0、A1、A2，也没有限定负例或 A3。

四条记录不能合并成一个虚构的旧版本。目标项目原来声明的 EclipseLink 版本依次为 2.5.2、2.5.2、2.6.0-M3 和 2.6.4；FSE 对四条记录使用的最后通过探针都是 2.7.10，首个失败探针都是 3.0.0-M1。这里的“最后通过”表示探针序列中的兼容版本，不表示 2.7.10 的发布日期早于 3.0.0-M1。

四个目标仓的全部可达历史都没有声明固定版本 3.0.0-M1，也没有在保持 3.0.0-M1 的条件下给出维护者 A2。`rsql-jpa` 后来的 Jakarta 迁移只存在于未进入默认分支的拉取请求引用，并直接改用 EclipseLink 4.0.1 或 4.0.2；`random-jpa` 的默认分支迁移直接改用 4.0.4，而且同时升级 Java、JPA、Hibernate、Mockito 和构建插件。把这些不同源输入下的大迁移改写成 3.0.0-M1 的 A2，会制造不存在的维护者修复。

## 完整候选框

| FSE 候选 | 目标模块 | 原声明版本 | 失败观察 | 根仓 |
|---|---|---|---:|---|
| `fse2024-behavioral-0419` | `com.github.dbunit-rules:core` | 2.5.2 | 6 个异常、1 个断言 | `rmpestano/dbunit-rules` |
| `fse2024-behavioral-0420` | `org.codejargon:fluentjdbc-guice-persist` | 2.5.2 | 2 个异常 | `cellux-git/fluent-jdbc` |
| `fse2024-behavioral-0421` | `com.github.tennaito:rsql-jpa` | 2.6.0-M3 | 1 个异常 | `tennaito/rsql-jpa` |
| `fse2024-behavioral-0422` | `com.github.kuros:random-jpa` | 2.6.4 | 2 个异常 | `kuros/random-jpa` |

`fluent-jdbc` 的工作簿目录仍使用旧所有者 `zsoltherpai`。当前公开仓库位于 `cellux-git/fluent-jdbc`；两条地址解析到相同的默认分支头提交 `c1eb2a9b1ce3e2e699cc110e9c9c4d143d09615e`，因此没有把改名仓重复计数。

## 源变化边界

EclipseLink 2.7.10 标签指向 `fe64cd39c33aec4bb8d736e560205171474a6f21`，3.0.0-M1 标签指向 `bc2a312a83bcb28718e4545b75cc92e1305de583`。两个版本跨越 JPA 命名空间边界：

- 2.7.10 的 `PersistenceProvider` 实现 `javax.persistence.spi.PersistenceProvider`，服务注册文件名也是 `META-INF/services/javax.persistence.spi.PersistenceProvider`；
- 3.0.0-M1 的同名实现改为 `jakarta.persistence.spi.PersistenceProvider`，服务注册文件名也改为 `META-INF/services/jakarta.persistence.spi.PersistenceProvider`。

仍通过 `javax.persistence.Persistence` 启动的旧客户端不会把 Jakarta 服务注册识别为 `javax.persistence.spi.PersistenceProvider`。这与公开记录中的 `No persistence providers available` 和 `No Persistence provider for EntityManager named persistenceUnit` 一致。

这个证据足以限定 2.7.10→3.0.0-M1 的发布边界机制，但不应硬写成一个精确源提交。3.0.0-M1 来自 Jakarta 迁移开发线，2.7.10 来自后来维护的 `javax` 分支；标签间差异包含目录重组和大量无关变化。四条记录中的空指针、DbUnit 表缺失和 Mockito 未完成桩也可能是持久化初始化失败后的级联现象，不能分别强行归因到额外源机制。

## 目标历史审计

### dbunit-rules

远程镜像共有 29 个引用和 646 个唯一可达提交。默认分支头为 `e3ecd6e586d25e8c4806485532339c5efd124e1d`，提交日期是 2016-09-16，早于 3.0.0-M1。全部引用的文件内容和提交说明都没有 3.0.0-M1，也没有 Jakarta 迁移。该仓没有可供三臂使用的固定源输入 A2。

### fluent-jdbc

远程镜像共有 86 个引用和 393 个唯一可达提交。默认分支头为 `c1eb2a9b1ce3e2e699cc110e9c9c4d143d09615e`，提交日期是 2020-05-15。全部引用的文件内容和提交说明都没有 3.0.0-M1，也没有 Jakarta 迁移。发布后短暂存在的维护窗口不能替代实际维护者 A2。

### rsql-jpa

远程镜像共有 57 个引用和 249 个唯一可达提交。默认分支头为 `7458a9e9f93b185dfff165da6cee3706587f2b10`，提交日期是 2017-05-01；全部可达历史没有 3.0.0-M1。

后来的两个 Jakarta 迁移提交只被拉取请求引用包含，没有进入默认分支：

- `3f60eee18bf3eb99f5aa19ba18a58d5f95659519` 位于 `refs/pull/28/head`，修改 19 个文件，把 `javax.persistence` 改为 Jakarta API 3.1.0，并把 EclipseLink 2.6.0-M3 直接改为 4.0.1；
- `21aa14fa3e5db9beac35694c7e64eaff1a9934c6` 位于 `refs/pull/30/head`，修改 18 个文件，把 EclipseLink 2.6.0-M3 直接改为 4.0.2。

它们既不是默认分支维护者修订，也没有保持固定的 3.0.0-M1，不能充当本题 A2。

### random-jpa

远程镜像共有 64 个引用和 398 个唯一可达提交。默认分支头为 `a29e661ac1536938a5c07f9642f8e39606f766b5`，提交日期是 2024-11-04；全部可达历史没有 3.0.0-M1。

默认分支中的 `1f16cf724d255c77e0fd76563d12f74ad63c69a0` 确实完成了 Jakarta 迁移，但它修改 186 个文件，把 EclipseLink 2.6.4 直接改为 4.0.4，同时切换到 Jakarta Persistence 3.2.0、Java 17、Hibernate 6、Mockito 5 和新版构建插件。该提交还被拉取请求 51 与标签 `v2.0.1`、`v2.0.2` 包含。它证明维护者后来解决了更高版本生态迁移，不证明 3.0.0-M1 下存在独立修复。

## 为什么不执行三臂

FSE 工作簿没有保存四个目标的精确 Git 修订。即使从历史中自行挑选一个看似相近的提交，也只能制造 A1 输入。更关键的是，四仓全部缺少固定 3.0.0-M1 的维护者 A2；对 `rsql-jpa` 或 `random-jpa` 人工回移 Jakarta 改动，会把 EclipseLink 4.x、JPA 3.1/3.2 和其他依赖升级拆成数据集作者设计的修复。

具体失败场景是：A1 用 3.0.0-M1 触发 `javax`/Jakarta 不兼容，A2 却偷偷使用维护者针对 4.0.1、4.0.2 或 4.0.4 的迁移。Git 提交能固定两个不同修订，版本号也能揭示输入变化，但普通测试即使通过，也不能把不同源版本下的恢复解释为“保持 3.0.0-M1 的维护者修复”。因此应在执行前拒绝，而不是用可运行性掩盖标签错位。

## 证据边界

本组证明 FSE 在四个独立仓库中记录了 EclipseLink 3.0.0-M1 合成升级后的 12 个失败观察，并且其中的提供者发现错误与 `javax.persistence`→`jakarta.persistence` 发布边界一致。它不提供精确目标修订、固定 3.0.0-M1 的维护者 A2、限定负例或 A3。

机器可读候选、根仓裁决和历史证据分别位于 `candidate-frame.jsonl`、`root-audit.jsonl` 与 `history-evidence.json`；紧凑结果位于 `results/eclipselink-3.0.0-m1-fse-history-screening-2026-08-25/summary.json`。

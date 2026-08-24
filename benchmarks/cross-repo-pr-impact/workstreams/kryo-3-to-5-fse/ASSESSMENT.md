# Kryo 3.0.3 到 5.0.0 的 FSE 关系族筛选

更新日期：2026-08-25

## 结论

FSE 2024 的三条目录记录恰好对应三个独立根仓：`stanford-futuredata/macrobase`、`atomix/catalyst` 和 `apache/ignite`。三条公开失败均由 Kryo 5 默认要求注册类触发，错误栈都落在 `Kryo.getRegistration` 的“类未注册”分支；它们不是同仓模块重复计数。

BUMP 固定修订 `324d5513aa5ca40b5cb32de5b816a58fa60bd7bb` 的 571 条正式记录、4,763 条未成功复现记录和 47 条完整性检查失败记录中，没有 `com.esotericsoftware:kryo` 或 `EsotericSoftware/kryo` 命中。因此这组三仓就是当前 FSE/BUMP 联合原始框的全部 Kryo 3.0.3 到 5.0.0 候选，没有遗漏需要去重的 BUMP 根仓。

本轮正式接纳零条，未执行 A0/A1/A2，也没有限定负例或 A3。三个根仓都缺少维护者对这一变化面的恢复提交：MacroBase 的旧模块一直保持 Kryo 3.0.3 和原序列化代码；Catalyst 在源破坏提交出现前已经停止开发；Ignite 的 Cassandra 序列化模块在保留 Kryo 3.0.3 和原实现多年后被删除。删除模块、固定旧版本或停止维护都不是 A2。

精确计数为：三条 FSE 记录、零条 BUMP 记录、三个独立根仓、零个维护者精确 A2、零个严格三臂正关系、零个限定负例、零个 A3。

## 源变化

来源仓为 `EsotericSoftware/kryo`：

- 3.0.3 标签提交：`9422c847db584dcddfa614303cd41d57eb76220f`；
- 4.0.2 标签提交：`d390da94e1558f8e8808c69257ab4f47a37b04c5`；
- 5.0.0 标签提交：`2248bd69084d3b4361f16fe3acca1d43ab48ca12`；
- 精确行为变化提交：`fc7f0cc7037ff1384b4cdac5b7ada287c64f0a00`。

`fc7f0cc` 把 `Kryo.registrationRequired` 的默认值从 `false` 改为 `true`。没有显式注册业务类、也没有调用 `setRegistrationRequired(false)` 的客户端，在 `writeObject` 或 `writeClassAndObject` 进入类解析时会抛出 `IllegalArgumentException: Class is not registered`。这与三条 FSE 错误完全一致：

| 候选 | 首个未注册类 | 目标调用点 |
|---|---|---|
| MacroBase | `macrobase.ingest.DatumEncoder` | `DiskCachingIngester.writeOutData` |
| Catalyst | `GenericKryoSerializerTest$Foo` | `GenericKryoSerializer.write` |
| Ignite | `org.apache.ignite.tests.MyPojo` | `KryoSerializer.serialize` |

5.0.0 还包含大量其他变化，因此公开的整版本失败本身不能把整个发布差异压成一个因果输入。这里之所以能隔离 `fc7f0cc`，是因为三条错误都命中该提交改动的同一个判定分支和同一种异常签名。若后续出现维护者 A2，仍需在固定客户端状态上分别重放整版本 A1 和只移植这一行默认值变化的源消融臂。

## 三仓维护历史

### stanford-futuredata/macrobase

FSE 记录 `0013` 指向 `legacy` 模块的 `CachingSQLIngesterTest.testChunkedIO`。`legacy/pom.xml` 从 2016 年引入该模块起就声明 Kryo 3.0.3；到仓库最后一次推送仍未升级。`DiskCachingIngester` 在写入 `DatumEncoder` 前创建裸 `new Kryo()`，最后一次实质修改停在 2017 年的旧模块整理，没有增加注册或显式关闭注册要求。

2020 至 2022 年对 `legacy` 的后续提交只升级 JUnit、Gson、MySQL 和 PostgreSQL 依赖。它们既不改变 Kryo 版本，也不修复序列化合同。因此该仓没有 A2；继续固定 3.0.3 只是规避破坏变化。

### atomix/catalyst

FSE 记录 `0014` 对应独立的 `kryo` 模块。`GenericKryoSerializer` 持有裸 `new Kryo()` 并直接调用 `writeObject`，模块 POM 固定 Kryo 3.0.3。该实现最后一次行为修改为 2017 年 1 月的 `3311a06e79460a4a0b9294968dc0fcea3d5c9ac0`；默认分支头为 `140e762cb975cd8ee1fd85119043c5b8bf917c5c`，时间早于 2017 年 7 月的 Kryo 破坏提交，仓库现已归档。

目标历史中不存在破坏发生后的维护者提交，因而不可能恢复出真实 A2。其他发布引用也都早于源破坏提交。仓库归档和无后续历史保持未知，不记负例。

### apache/ignite

FSE 记录 `0015` 对应 `modules/cassandra/serializers`。`KryoSerializer` 的线程局部实例同样由裸 `new Kryo()` 创建，测试用 `MyPojo` 覆盖往返序列化。模块 POM 自 2016 年引入以来一直把 Kryo 固定在 3.0.3。

生产文件在引入后只有 2016 年复核和 2020 年导入顺序整理，没有注册类或关闭注册要求的语义修改。2023 年提交 `9f878d9b30a98b0d59d462974e9728a02c49f18f` 删除了整个 Cassandra 模块；删除目标能力不能作为对 Kryo 5 的恢复。全局代码搜索也没有在 Apache 的扩展仓中找到该序列化模块的后继实现。因此该仓没有 A2。

## 为什么不执行三臂

A2 臂要求只应用维护者真实采用的目标修复。当前三个根仓均不存在这样的提交。若现在运行 A0 和 A1，再手工加入 `setRegistrationRequired(false)` 或注册测试类，只能复现论文失败并证明人工补丁有效，不能证明任何目标维护者实际承担了跨仓适配。

提交主键、版本号和普通测试能够固定一次执行的代码状态，却不能把长期固定旧版本、停止维护或删除模块改写成维护者恢复。继续恢复三套旧 Java/Maven 环境不会改变这一准入事实，所以本轮停在历史筛选阶段。

## 负空间与 A3

三个仓都进入了同一注册要求变化面并在公开执行中失败；没有一个仓能在 Kryo 5 下由原生合同证明“不修改也兼容”，因此限定负例为零。缺少 A2 的仓也不能反向充当负例。

相邻版本筛选检查了 3.0.2 到 3.0.3 和 4.0.1 到 4.0.2。前者的实质修复集中在不安全内存输入输出、枚举名称、`Externalizable` 和实例创建，后者集中在兼容字段序列化、枚举类对象和不可变集合序列化。现有三条 FSE 记录没有给出这些分支的共同覆盖证据，精确客户端修订又未保存；仅在相邻版本两侧得到普通绿色也不能建立 A3。由于主关系已经因三仓均无 A2 而停止，本轮没有为这些静态线索恢复三套旧环境，A3 计零。

## 证据边界

FSE 工作簿没有保存三个客户端的精确 Git 修订，只保存制品、目录、Java 版本、测试方法和错误栈。本轮通过制品坐标、目录结构、完全匹配的测试方法与行号恢复根仓，并审计根仓完整维护历史；不能把推定的采集时点仓库头写成原始修订。这个缺口不影响“无维护者 A2”的历史判定，但意味着三条公开 A1 在将来若要重放，仍需从虚拟机或数据库恢复精确目标快照。

机器可读候选框位于本目录的 `candidate-frame.jsonl`，筛选结果位于 `results/kryo-3-to-5-fse-screening-2026-08-25/`。

# Derby 10.15 制品拆分关系族筛选

评估日期：2026-08-25

## 结论

FSE 2024 中 `org.apache.derby:derby` 升到 10.15.1.3 的九条记录，对应九个独立根仓，不存在同仓模块重复计数。本轮得到：

- 一个高证据机制锚点：`susom/database`；
- 两个版本辅助修复对照：`FrodeRanders/muprocessmanager`、`mybatis/cdi`；
- 六个缺少精确维护者修复的历史拒绝项；
- 零个限定负例，零个 A3；
- 零个已完成源提交隔离的旗舰正式案例。

Susom 的目标侧三臂已经成立：同一目标基线在 Derby 10.14.2.0 下通过，换成 10.15.1.3 后以公开记录中的缺驱动签名失败，只加入维护者采用的 `derbytools` 后恢复。但是当前使用的是两个发布版，尚未分别构建源提交 `5a6efcc` 的父、子制品。因此这条关系可以证明制品拆分机制与目标修复方向，不能实验性证明“只加入该源提交”就足以产生失败。完成父、子构件重放前，它不进入旗舰正式集。

MuProcessManager 与 MyBatis CDI 都展示了真实的维护者响应，但恢复同时依赖后续 Derby 发布版补齐的 Maven 传递依赖。固定在 10.15.1.3 时，只移植目标维护者的声明仍不能恢复，所以二者不能计为 A2。

## 源变化

来源仓为 `apache/derby`，精确提交为：

- 行为提交：`5a6efccce73b05ac7a27512563868192303f564d`；
- 父提交：`8f3b7b2fa2f3e775dc90fb3cfa9f46257ae8df0e`；
- 对应 SVN 修订：`1824087`；
- 对应问题：`DERBY-6945`。

该提交把 `org.apache.derby.jdbc/**` 从 `derby.jar` 的内容边界移到 `derbytools.jar`。发布制品核验结果为：

| 发布制品 | `EmbeddedDriver` |
|---|---|
| 10.14.2.0 `derby.jar` | 存在 |
| 10.15.1.3 `derby.jar` | 不存在 |
| 10.15.1.3 `derbytools.jar` | 存在 |

10.15 还拆出了 `derbyshared.jar`。10.15.1.3 的 `derby`、`derbytools` 和 `derbyoptionaltools` Maven 元数据没有声明完整的传递关系；10.15.2.0 才让 `derby` 传递引入 `derbyshared`，后续版本又让 `derbyoptionaltools` 传递引入 `derbytools`。这个元数据差异正是两个版本辅助对照不能晋级的原因。

源变化的相关补丁摘录保存在 `derby-6945-artifact-boundary.patch`。当前证据足以定位机制，但源提交父、子构件仍未本地构建。

## Susom 机制锚点

FSE 记录 `fse2024-behavioral-0310` 指向 `susom/database`。公开工作簿没有保存目标 Git 修订；重建基线 `b9aac59d053af41144f59c77a7f9053f8fe61102` 同时匹配依赖版本、测试方法、Hikari 调用路径、源码行号和异常文本。

维护者提交 `811158529d847bde72fc97c5701d411301f395b4` 只在 `pom.xml` 增加六行 `derbytools` 测试依赖。混合升级提交 `f60723eb53f5aba831d18f5f3d79ceecae4bb879` 已排除。

统一 Java 11 的目标侧结果如下：

| 臂 | Derby 输入 | 目标输入 | 结果 |
|---|---|---|---|
| A0 | 10.14.2.0 | 重建基线 | 通过，1 个测试 |
| A1 | 10.15.1.3 | 同一基线 | 失败，缺少 `EmbeddedDriver` |
| A2 | 10.15.1.3 | 只增加 `derbytools` | 通过，1 个测试 |

Java 8 的补充观察复现了 A0 通过和 A1 同签名失败；A2 因 Derby 10.15 的 class file 53 超出 Java 8 支持范围而无法运行。这个环境限制不影响 Java 11 下目标修复的方向性，但说明它不是 FSE 原始环境的逐字节重放。

完整证据位于 `susom/` 与 `results/derby-10.15-fse-susom-2026-08-25/`。晋级所缺的唯一关键实验是：分别构建 `8f3b7b2` 与 `5a6efcc`，在同一目标基线上重放。

## 版本辅助修复对照

### FrodeRanders/muprocessmanager

FSE 记录 `0311` 的公开失败发生在 `AppTest.testPersistedProcess` 的公共 `setUp()`。维护者提交 `58628e7ec4dd914f6f1ec6ff7caab681cc446ae1` 把 Derby 升到 10.15.2.0，并明确加入 `derbytools`，注释写明 `org.apache.derby.jdbc` 已移到这里。

本轮用更短的原生兄弟测试 `AppTest.testVolatileProcess` 覆盖同一个 `setUp()` 边界：

- 10.14.2.0：通过；
- 固定 10.15.1.3：缺少 `EmbeddedDataSource`；
- 固定 10.15.1.3 并只加入维护者的 `derbytools`：仍失败，缺少 `derbyshared` 中的 `SystemPermission`；
- 换成维护者实际采用的 10.15.2.0，并加入 `derbytools`：通过。

恢复依赖 10.15.2.0 上游 POM 新增的 `derbyshared` 传递关系，源输入发生了变化。因此它只保留为版本辅助修复对照，不计 A2。日志位于 `results/derby-10.15-fse-muprocess-2026-08-25/`。

### mybatis/cdi

FSE 记录 `0312` 的失败是 MyBatis 显式加载 `EmbeddedDriver` 时找不到类。维护者拉取请求 311、提交 `8f6d6c172b2a697db13d98d4323700bb9ffc965d` 删除了“不得高于 10.14.2.0”的限制，并加入 `derbyshared` 与 `derbyoptionaltools`。

固定 10.15.1.3 的重放结果为：

- A0 使用 10.14.2.0：7 个原生测试通过；
- A1 只换 10.15.1.3：以与 FSE 完全一致的 `EmbeddedDriver` 缺类签名失败；
- 只移植维护者直接加入的 `derbyshared` 与 `derbyoptionaltools`：仍以同一签名失败，因为 10.15.1.3 的 `derbyoptionaltools` POM 不传递 `derbytools`。

维护者实际采用的 10.16.1.1 会通过后续 POM 元数据带入 `derbytools`，并要求更新的 Java。Java 21 下该维护状态的 7 个测试通过；这证明维护路径有效，但同时改变源版本与运行时，不能计为固定源输入的 A2。日志位于 `results/derby-10.15-fse-mybatis-cdi-2026-08-25/`。

## 六个历史拒绝项

| 候选 | 根仓 | 判定 |
|---|---|---|
| 0306 | `sylvainlaurent/JDBC-Performance-Logger` | 仍声明 10.10.1.1；2022 年两个 10.14.2.0 更新请求未合并，没有 10.15 适配 |
| 0307 | `stratosphere/stratosphere` | 根仓历史在 2014 年结束，早于源变化；迁往 Flink 不构成该根仓 A2 |
| 0308 | `srotya/tau` | 仍固定 10.12.1.1，历史在 2017 年结束 |
| 0309 | `wen866595/MyBatis-batch` | 仍固定 10.12.1.1，历史在 2017 年结束 |
| 0313 | `mybatis/spring` | 10.15.1.3 与后续 10.16.1.1 提交都只是版本更新，没有目标侧精确修复 |
| 0314 | `techatspree/GuttenBase` | 归档仓仍固定 10.8.2.2；后续 Java 与清理提交不处理此合同 |

逐仓机器审计保存在 `candidate-root-audit.jsonl`。固定旧版本、停止维护、迁仓和普通依赖升级都不能冒充维护者修复。

## 负空间与 A3

九仓都来自公开执行中的失败记录，没有仓库具备同一变化面下“不修改也兼容”的覆盖证据。因此限定负例为零。没有 A2 的仓保持未知，不转成负例。

本轮没有 A3。仅在相邻发布版上得到普通绿色，不能证明客户端执行了不同的源变化分支；在主关系尚缺源父、子构件重放时，继续做这种弱检查不会提升准入等级。

## 证据边界

FSE 工作簿保存了制品、目录、Java 版本、测试方法和错误栈，没有保存九个客户端的精确 Git 修订。根仓恢复依靠制品坐标、目录结构、方法名、源码行号和完整维护历史。Susom 的重建基线证据最强，但仍不冒充未公开的原始 SHA。

本包的发布结论是“一个高证据机制锚点，尚无旗舰正式案例”。只有补完 `5a6efcc` 父、子构件重放，Susom 才能晋级为源提交隔离案例；只有再出现至少一个独立目标根仓，才可能形成多仓旗舰项目包。

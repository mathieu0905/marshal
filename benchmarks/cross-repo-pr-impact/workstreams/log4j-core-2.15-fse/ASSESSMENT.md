# Log4j Core 2.14.1 到 2.15.0 的 FSE 关系族筛选

更新日期：2026-08-25

## 结论

FSE 2024 的完整版本框共有 2 条候选、2 个异常观察，去重后是 2 个独立根仓：`oboehm/gdv.xport` 与当前 canonical 地址 `mitre/HTTP-Proxy-Servlet`。本轮接纳 1 条严格正例，拒绝 1 条；只对存在固定 2.15.0 维护者 A2 的 `gdv.xport` 执行了原生 A0/A1/A2。

`gdv.xport` 的历史与公开异常能够闭合。维护者先合并只把 Log4j Core 从 2.14.1 升到 2.15.0 的 PR 68，随后在该合并提交上把 Log4j API 同步到 2.15.0。Core 2.15.0 的 `ConfigurationSource` 会读取 API 2.15.0 新增的 `Constants.EMPTY_BYTE_ARRAY`；若 API 仍是 2.14.1，日志初始化会抛出 `NoSuchFieldError: EMPTY_BYTE_ARRAY`，再被 JUnit Platform 包装成公开记录中的 `ServiceConfigurationError`。

原生三臂结果为：A0 的 1070 项 Maven 汇总通过，A1 在执行任何测试前以公开签名失败，A2 的 1070 项 Maven 汇总再次通过。A2 只应用维护者提交 `a84175f2...` 中同步 Log4j API 的原样一行修订；这不是数据集作者设计的修复。该维护者提交还同时删除 SmokeRunner。完整提交另行执行后会进入此前跳过的集成测试，并暴露一个不同的 `MyUnfallDatensatzTest` 错误，因此完整提交结果没有冒充正式 A2。

`HTTP-Proxy-Servlet` 的 2.15.0 Core 更新只存在于未合并的 Dependabot PR 头。全部 refs 中没有在固定 2.15.0 下的维护者恢复；主线随后直接同步升级 `log4j-jcl` 与 Core 到 2.16.0。公开记录也只保留代理端收到 HTTP 500 的客户端栈，没有后端异常。按准入顺序，该根仓不执行三臂，也不把远端 500 当作 Log4j 机制证据。

## 完整候选框与根仓去重

| FSE 候选 | 目标模块 | 公开失败 | 根仓 | 裁决 |
|---|---|---|---|---|
| `fse2024-behavioral-0337` | `com.github.oboehm:gdv-xport-lib` | JUnit Platform 无法实例化 `SmokeTestExtension` | `oboehm/gdv.xport` | 接纳 |
| `fse2024-behavioral-0338` | `org.mitre.dsmiley.httpproxy:smiley-http-proxy-servlet` | 并发代理测试收到本地后端 HTTP 500 | `mitre/HTTP-Proxy-Servlet` | 拒绝 |

两条记录分别来自工作簿行 449 和 463，记录号为 `15163` 与 `15340`。目录提示 `dsmiley_HTTP-Proxy-Servlet` 是仓库迁移前地址；旧地址与 `mitre/HTTP-Proxy-Servlet` 当前返回同一个 Git HEAD。两个项目没有共同 Git 图、模块或 Maven 坐标，因此去重后仍是两个根仓。

工作簿没有记录目标 Git 修订。这里没有用目录名倒推出唯一执行提交；历史 PR 只作为可审计的同版本变化与维护者恢复输入。

## 精确源机制

源标签 `rel/2.14.1` 指向提交 `be881e503e14b267fb8a8f94b6d15eddba7ed8c4`，`rel/2.15.0` 指向 `c30a1398a6697fb832c650870c44284d0052103e`。两个发布提交之间有 187 个提交、455 个变化文件，不能把整个安全发布或 Log4Shell 标签当作本组机制。

提交 `97ec707d69280ef57aed8fd5831dc4f3a75f7715` 是精确变化：

1. 在 Log4j API 的 `Constants` 中新增 `EMPTY_BYTE_ARRAY`；
2. 删除 Core `ConfigurationSource` 自己的空数组；
3. 让 Core 的两个静态配置源改读 API 字段 `Constants.EMPTY_BYTE_ARRAY`。

该提交不在 2.14.1 中，但在 2.15.0 中。只升级 Core 会让 2.15.0 Core 的静态初始化链接到 2.14.1 API 中不存在的字段。A1 Surefire dump 精确给出 `NoSuchFieldError: EMPTY_BYTE_ARRAY`，路径从 `ConfigurationSource.<clinit>`、`LoggerContext.<clinit>` 到 `SmokeTestExtension.<clinit>`，因此 `gdv.xport` 的公开包装异常具有来源特异性。

机器可审计的两文件最小源差异位于 `source-mechanism.patch`。它只用于解释已执行失败，不把 2.15.0 的安全发布说明当成因果证据。

## `gdv.xport` 历史与三臂

完整镜像包含 142 个 refs、heads/tags 中 2711 个唯一可达提交，纳入 pull refs 后共有 2733 个。固定版本历史为：

- A0：`3f806a2a37029b6d2a0afbc716917dacc19bea17`，API/Core 均为 2.14.1；
- A1：维护者合并提交 `3bf9996a0afdbf426e920e03aafe069cab4e2491`，其第二父提交 `bafd4c86...` 只把 Core 改为 2.15.0，API 仍为 2.14.1；
- A2 修订来源：A1 的直接子提交 `a84175f220b8a7925a97ce22f211303d47960ba6`，维护者把 API 同步到 2.15.0，同时另行删除 SmokeRunner。

正式 A2 在 A1 树上只应用该维护者提交的 API 版本行，保留 Core 2.15.0，也保留与 A0/A1 相同的测试发现合同。原生命令统一为 Java 11 下的 `mvn -B -ntp -pl lib -am clean test`，Maven 仓库和 JVM 临时目录均位于 `.work/log4j-core-2.15-fse/`。

| 臂 | API/Core | 退出码 | Maven 汇总 | Surefire XML 汇总 |
|---|---|---:|---|---|
| A0 | 2.14.1 / 2.14.1 | 0 | 1070，0 失败，0 错误，跳过 5 | 1069，0 失败，0 错误，跳过 9 |
| A1 | 2.14.1 / 2.15.0 | 1 | 启动前失败，0 tests | 无 XML |
| A2 | 2.15.0 / 2.15.0 | 0 | 1070，0 失败，0 错误，跳过 5 | 1069，0 失败，0 错误，跳过 9 |

Maven 汇总与 XML 汇总的计数差异来自该历史测试栈的多 provider/覆盖写入行为；两侧原始数字都保留，不用一个数字覆盖另一个。A0 与 A2 在两种统计口径下完全一致。

完整维护者提交的诊断臂不是正式 A2。它的 API 同步确实消除了 `ServiceConfigurationError`，但删除 SmokeRunner 后，历史测试栈重复发现 `MyUnfallDatensatzTest`，同一测试第一次通过、第二次在共享注册状态已还原后失败。Maven 汇总为 1074 项、1 个不同错误；XML 汇总为 1070 项、1 个错误。该错误是 `MyUnfallDatensatzTest` 中找不到 `Baujahr` 字段，与 Log4j 链接失败不同。

## `HTTP-Proxy-Servlet` 历史审计

完整镜像包含 156 个 refs、heads/tags 中 275 个唯一可达提交，纳入 pull refs 后共有 441 个。旧 `dsmiley` 地址和 canonical `mitre` 地址解析到同一 HEAD，不构成两个根仓。

`ef87a33a2f2c6cb4be0f2afed48762e775ed2ceb` 是唯一加入 Core 2.15.0 的提交。它以 `c17fb9f2915ab7820266c4950e8c005b1fa41cb4` 为父，只在 `pom.xml` 中把测试作用域的 Core 从 2.14.1 改为 2.15.0；没有任何 head 或 tag 包含它。主线后来的 `5f7eab2504da024ed4f017e6624526e8acb9c973` 直接把 `log4j-jcl` 和 Core 从 2.14.1 同步改到 2.16.0，并未固定 2.15.0。

因此全部 refs 没有严格 A2。即使人工把 `log4j-jcl` 或 API 同步到 2.15.0 后测试变绿，也只能证明作者方案可行，不能证明维护者曾在候选版本下恢复。公开的 HTTP 500 还可能来自后端处理、端口并发或代理环境；客户端栈没有 Log4j 类、链接错误或后端日志，普通绿构建也无法补出该特异性。

## 证据边界

本组接纳的是 `gdv.xport` 中“单独升级 Core 造成 API/Core 二进制错配，维护者同步 API 后恢复”的跨制品关系。它不是“Log4Shell 安全发布导致任意消费仓失败”，也不外推到同步升级整套 Log4j 制品的仓库。

`HTTP-Proxy-Servlet` 保留为已执行失败线索，但没有固定 2.15.0 的维护者 A2，也没有能把 HTTP 500 归到精确源机制的服务器证据，因此不进入正式正例或限定负例。

机器可读候选、根仓裁决、历史证据和重放说明分别位于 `candidate-frame.jsonl`、`root-audit.jsonl`、`history-evidence.json` 与 `REPLAY.md`。运行日志、A1 Surefire dump 和汇总位于 `results/log4j-core-2.15-fse-replay-2026-08-25/`。

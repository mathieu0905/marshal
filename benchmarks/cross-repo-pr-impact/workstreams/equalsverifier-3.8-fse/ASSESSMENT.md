# EqualsVerifier 3.7.2 到 3.8 的 FSE 关系族筛选

更新日期：2026-08-25

## 结论

FSE 2024 中最后通过版本为 3.7.2、破坏版本为 3.8 的完整关系框包含 2 条候选，分别来自 `WojciechZankowski/iextrading4j` 与 `twilio/twilio-java`，去重后仍为 2 个独立根仓。两条公开失败都精确命中 3.8 新增的 BigDecimal equality 检查，但目标历史没有保持 3.8 的维护者修复。因此本轮在重放前接纳 0 条，没有执行 A0/A1/A2，也没有限定负例或 A3。

IEXTrading4j 从未采用 3.8；Twilio 只在 2022 年采用 3.8.2，提交本身只改依赖版本，未修改失败测试或 BigDecimal 相等性实现。把较新的补丁版本或后续大规模生成代码变化当作固定 3.8 的 A2，会改变源输入或把宽变化误称为精确客户端修复。

## 完整候选框

| 候选 | 根仓 | 原声明版本 | 最后通过版本 | 失败合同 |
|---|---|---|---|---|
| `fse2024-behavioral-0280` | `WojciechZankowski/iextrading4j` | 3.6 | 3.7.2 | `CeoCompensation.salary` 用 `BigDecimal.equals`，新增检查要求明确选择数值相等或尺度相等语义 |
| `fse2024-behavioral-0281` | `twilio/twilio-java` | 3.6.1 | 3.7.2 | `Yesterday.price` 用 `Objects.equals`，触发同一 BigDecimal equality 警告 |

两个 GitHub 仓库编号分别为 `84750226` 与 `307476`，没有仓库别名或迁移重复。工作簿没有保存目标 Git 修订。

## 精确源机制

EqualsVerifier 标签 `equalsverifier-3.7.2` 解引用到 `a26bc65f1dff10930e64f29b550ee5839d7db862`，标签 `equalsverifier-3.8` 解引用到 `38b2b9f6c6fd4d5ab001523a64414c5a5347cb6b`。两者之间的行为提交为 `9af8359a4c8c8fd5865f2d9da0c83d1683bb4049`，标题是 `#540 BigDecimal equality using compareTo`。

该提交新增 `BigDecimalFieldCheck` 和可抑制的 `Warning.BIGDECIMAL_EQUALITY`。检查把一个 BigDecimal 字段的尺度增加一位，再验证客户端 `equals` 和 `hashCode` 是否把数值相等但尺度不同的值视为相同。两条公开错误都给出这一检查生成的完整专用消息，并分别点名 `salary` 与 `price`，因此源机制特异性成立。

## 目标历史

### IEXTrading4j

镜像包含 152 个引用和 1009 个唯一可达提交。2021 年 10 月的宽依赖更新把 EqualsVerifier 从 3.6 升到 3.7.1；全部引用中没有 3.8 声明，也没有 `Warning.BIGDECIMAL_EQUALITY` 抑制。项目后来在 2024 年的宽版本发布中直接使用更高版本，不能作为固定 3.8 输入的维护者 A2。

### Twilio Java

镜像包含 1299 个引用和 4267 个唯一可达提交。提交 `76d44ef9509c2151b1a2b2e5002ab286c6cfb6b4` 把 EqualsVerifier 从 3.6.1 升到 3.8.2，但只修改 `pom.xml`。它没有改 `ComplianceTest`，也没有改公开失败点 `Yesterday.price` 的 `Objects.equals` 与 `Objects.hash` 实现。

3.8.2 中的 `BigDecimalFieldCheck` 与 3.8 内容相同，所以这笔补丁版本升级不是目标修复。其后的生成代码更新横跨 78 个文件，`Yesterday` 只新增枚举值，仍保留相同 BigDecimal 相等实现；它也不能隔离成维护者对该失败的 A2。全部历史中没有加入 `Warning.BIGDECIMAL_EQUALITY` 或针对该字段改用数值比较的精确修订。

## 停止边界

具体失败场景是：用任意匹配公开测试的目标提交构造 A1，再把 Twilio 的 3.8.2 依赖升级或后续生成代码更新称为 A2。Git 可以固定这些提交，版本号可以证明其中包含较新 EqualsVerifier，普通测试也可能在另一时点变绿；但它们不能同时保持 3.8 输入并隔离维护者修复。IEXTrading4j 更没有采用 3.8。故本组在历史筛选后停止，不执行作者合成的三臂。

最终计数：候选 2、根仓 2、精确源机制 1、固定 3.8 的维护者 A2 0、重放 0、正式正关系 0、限定负例 0、A3 0。

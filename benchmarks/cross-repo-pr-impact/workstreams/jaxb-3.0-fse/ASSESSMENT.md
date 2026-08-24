# JAXB 3.0.0-M1 关系族筛选结论

## 结论

本关系族不接纳为旗舰因果项目包。

- 宽候选框共有 8 条：两个 JAXB 坐标、目标版本均为 `3.0.0-M1`。
- 其中 `fse2024-behavioral-0444` 的前序版本为 `2.4.0-b180830.0438`，不属于本次 `2.3.6 -> 3.0.0-M1` 关系，因此保留在候选框并明确淘汰。
- 剩余 7 条记录在模块和仓库迁移去重后，只对应 5 个独立仓库根历史。
- 5 个根历史均能与同一源机制相符，但均未找到保持 `3.0.0-M1` 输入、保留原测试观察点并恢复相同失败契约的维护者提交。
- 因精确 A2 为 0，按预先约定不执行 A0/A1/A2 重放；本关系族产出 0 个可接纳案例。

## 源机制

源仓为 `eclipse-ee4j/jaxb-ri`。相关标签是：

- `2.3.6-RI`：`e9f7f5f01c24b152261a9323cab3ff8c4c016b82`，发布提交日期为 2022-01-27。
- `3.0.0-M1-RI`：`7e8fcb035fcb828ae6eaafdcba58c5f9070f6a62`，发布提交日期为 2020-03-31。

两者位于不同维护分支，互不为祖先，因此不能把标签之间的全量差异解释为线性源改动。可定位的失败机制是提交 `dd133e1543c7773944d002fb6474ec1205446d72`：它把 `com.sun.xml.bind.v2.JAXBContextFactory` 从 `javax.xml.bind.JAXBContextFactory` 的实现改为 `jakarta.xml.bind.JAXBContextFactory` 的实现，并同步切换模块的 `uses` 和 `provides`。这精确解释了原始失败中的 `javax.xml.bind.JAXBContextFactory: com.sun.xml.bind.v2.JAXBContextFactory not a subtype`。

该提交同时完成整套 Jakarta EE 9 命名空间迁移，共改动 350 个文件、增加 1313 行、删除 1289 行。因此这里只能称为“单一提交中的明确机制”，不能称为小型隔离补丁。精确节选见 `source-mechanism.patch`。

## 根历史去重

`0195` 与 `0196` 是 `FIXTradingCommunity/fix-orchestra` 同一根仓中的两个模块，不独立计数。

`0431` 与 `0432` 的历史地址分别是 `benas/easy-batch` 和 `easybatch/easybatch-framework`。GitHub 接口对两个地址及当前地址 `j-easy/easy-batch` 均返回仓库编号 `5402462`，因此它们是一次仓库迁移，不独立计数。

`0444` 的历史地址 `farao-community/farao-core` 当前解析为 `powsybl/powsybl-open-rao`，仓库编号为 `158683766`；它在版本关系筛选阶段已经淘汰，不进入 5 条根历史审计记录。

## 精确 A2 审计

对 5 个独立根历史的全部可达引用执行两类历史搜索：一类寻找新增 `import jakarta.xml.bind` 的提交，另一类寻找把 JAXB API 或运行时版本切到 3.x 的构建提交。两类搜索在 5 个根历史中均为 0。随后人工检查所有 JAXB 相关历史提交，结果记录在 `candidate-root-audit.jsonl`。

容易误判的提交包括：

- Elepy 的 `ffa1fc3e...` 使用 `jakarta.xml.bind-api:2.3.2`，但该 2.3.x 构件仍是 `javax.xml.bind` API，不能配合 Jakarta 3 提供者。
- WildFly Elytron 的两条修复改用 `jaxb-runtime:2.4.0-b180830.0438`，是退回兼容的 JAXB 2 系列，而不是保持 M1。
- Easy Batch 的 `4103b6ea...` 使用 API/运行时 2.3.3；`b5e805c9...` 删除了 `XmlRecordValidatorTest` 及大量测试，删除观察点不能算恢复。
- OpenEstate 的构建依赖虽使用 `jakarta.xml.bind` 组名，但版本仍为 2.3.x，源码继续导入 `javax.xml.bind`。

## 原始材料边界

机械恢复的 `Test_Errors_Data.xlsx`、`Test_Failure_Data.xlsx` 和说明文件只给出目录提示、依赖坐标、测试、版本和失败日志，不给出精确客户端 Git 修订。说明文件指出精确数据库和代码工作区位于约 9GB 的虚拟机镜像内。由于本轮在公开根历史中已经找不到任何精确 A2，继续展开虚拟机镜像也无法补出维护者恢复臂，因此停止在筛选阶段。

本工作流没有修改公共候选台账、结果索引或 `.claude`，也没有独立提交。

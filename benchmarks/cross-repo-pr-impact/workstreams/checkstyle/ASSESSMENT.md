# Checkstyle 项目包筛选记录

## 当前结论

Checkstyle 10.12.1 到 10.12.2 已形成两个强因果正例和两个有变化面覆盖的限定负例，但还不是完整四臂项目包。10.12.2 到 10.12.3 的四仓兼容候选虽然前后臂均通过，却没有任何一仓执行该发布的两个真实修复路径，因此 A3 为 0，当前正式项目包接受数仍为 0。

## 完整失败候选框

BUMP 固定版本 `324d5513aa5ca40b5cb32de5b816a58fa60bd7bb` 中共有 307 条 Checkstyle 记录，覆盖 53 个唯一消费仓。其中 4 条来自正式 benchmark，303 条来自 unsuccessful-reproductions。正式记录为：

| 消费仓 | 版本对 |
| --- | --- |
| `apache/ws-wss4j` | 10.12.1 到 10.12.2 |
| `getgauge/gauge-java` | 10.12.1 到 10.12.2 |
| `sitture/env-config` | 10.1 到 10.2 |
| `apache/opennlp` | 7.2 到 8.29 |

搜索框由 `collect_bump_candidate_frame.sh` 生成，原始记录保存在 `bump-candidate-frame.jsonl`。所有记录都只提供失败线索，不因 BUMP 的状态自动产生正例或负例。

## 两个强因果正例

两个消费仓都保留了同一 Checkstyle 变化的基线、纯依赖升级失败和维护者实际接受的精确恢复：

| 消费仓 | A0 | A1 | A2 | 失败与恢复机制 |
| --- | --- | --- | --- | --- |
| `getgauge/gauge-java` | `3363a7f279d92a7c9c9de0d4828077058192c925`，通过 | `d8031ba94b60982bec9dc8bfedaeee700731be7a`，失败 | `db1a09cc0db2b8045a5c2da34617136cd4290fc7`，通过 | A1 只升级 10.12.2，新增 3 个 `FinalClass` 违规；PR 713 在同一基线上升级依赖，并把对应三个内部类改为 `final` |
| `apache/ws-wss4j` | `a8eb885cfe82d2e69f582bec3ada6af34c1388a1`，通过 | `a61b52b3627b4a635ae6712081e55cd83e55397d`，失败 | `d1347cb288174bb6442913fce2919945b05da136`，通过 | A1 只升级 10.12.2，新增 2 个 `FinalClass` 违规；PR 192 的 `0be30ba3ea4d88fc6fb5bce0aa45f57645ce229d` 精确把这两个内部类改为 `final`，随后 PR 184 的升级进入主线 |

WSS4J 的 Dependabot 头提交与最终主线不是线性三提交链，因此 A2 的因果判断还依赖单独核对 PR 192 的两行源码修复；不把 A1 到 A2 之间的其他主线提交归因于 Checkstyle。三臂脚本和原始日志分别位于 `run_positive_screening.sh` 与 `results/checkstyle-positive-screening-2026-08-24/`。

## 两个限定负例

两个仓都在固定真实提交上把插件依赖从 10.12.1 切换到 10.12.2，执行原生 Checkstyle 合同，两臂均通过：

| 消费仓 | 固定提交 | 检查结果 | 10.12.2 变化面覆盖 |
| --- | --- | --- | --- |
| `Pante/elementary` | `2c058f2fceda99fca5b9a709105fe082dd75f32b` | 五模块均为 0 个违规 | `FinalClassCheck.java:247/249/250`、`283-297`、`573-575`、`644/653` 的主要新判定路径被执行 |
| `volodya-lombrozo/conventional-commit-linter` | `665f517d2cd056243633e587c22f138b3ca50a57` | 0 个违规 | 同一新判定路径被执行；私有隐式构造分支 `292/653` 未命中，但非私有分支 `295` 和新状态计算已命中 |

这两个标签只表示固定提交的 Checkstyle 合同不需要消费仓修改。它们不外推为完整测试、运行时行为或其他 Checkstyle 配置无影响。逐行指令与分支计数位于 `results/checkstyle-negative-screening-2026-08-24/*-final-class-change-coverage.tsv`；脚本会保留 `.exec`、日志与紧凑摘要，并删除可重建的 JaCoCo XML。

## A3 拒绝

候选版本为 10.12.2 到 10.12.3。这个发布有两个明确的行为修复：

- 支持 JDK 20 record pattern 的增强 `for`，关键新增路径位于 `JavaAstVisitor.java:1299-1303` 和 `ModifiedControlVariableCheck.java:326-345`；
- 修复本地类触发 `UnnecessarySemicolonAfterTypeMemberDeclaration` 空指针，关键变化位于该检查的第 204 行。

Gauge Java、WSS4J、Elementary 和 Conventional Commit Linter 的前后共 8 个臂全部通过。覆盖审计中，四仓都只命中 `JavaAstVisitor.java:1238` 的普通增强 `for` 入口；上述 record pattern、控制变量和空指针修复行全部为零覆盖。第 1238 行对普通语法只是从专用访问器改为同一子节点访问，不能单独证明真实新增行为被观察。因此这组普通绿色不能充当 A3。

重放脚本和结果位于 `run_a3_screening.sh` 与 `results/checkstyle-a3-screening-2026-08-24/`。

## 未纳入候选

- OpenNLP 的 7.2 到 8.29 和 env-config 的 10.1 到 10.2 属于不同源变化，不能拼入 10.12.1 到 10.12.2 的统一破坏闭集。
- 其余 303 条 unsuccessful-reproductions 没有因失败记录或普通绿色自动获得标签，仍保留在完整候选框中。
- 首轮限定负例执行实际没有修改 Maven 插件依赖，并受 Checkstyle 缓存和项目 JaCoCo 干扰；这些结果已作废，不计证据。

## 下一步

1. 在同一四仓闭集中寻找一个所有仓都执行真实兼容变化路径的相邻 Checkstyle 版本对，或更换有共同语义覆盖的消费仓。
2. A3 成立后，对 A0、A1、A2 和 A3 两臂做三次隔离重复。
3. 对两个维护者恢复、两个限定负例的标签上限和 A3 变化语义做独立复核；完成前不进入正式项目包数量。

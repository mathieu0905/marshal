# Spring Boot 2.6 候选历史筛选

## 结论

FSE 2024 复现实验中，`spring-boot-starter-test 2.5.3 -> 2.6.0` 共命中 3 条记录，覆盖 `fonimus/ssh-shell-spring-boot` 的 `samples/basic`、`samples/complete` 和 `starter` 三个模块。三条记录来自同一仓库、同一次版本替换和同一个循环依赖机制，折叠后只有 1 个跨仓关系。

该关系的上游机制清楚：Spring Boot 2.6 默认禁止循环 Bean 引用，而目标所用 Spring Shell 2.0.1 的 `ResultHandlerConfig` 存在自循环。公开执行记录中的三个模块均在创建应用上下文时抛出 `BeanCurrentlyInCreationException`。

目标仓确实出现过仅把 Boot 2.5.6 升到 2.6.0 的维护者 PR，但该 PR 没有修复且从未合并。后来合入的迁移同时升级到 Boot 2.7.2、Spring Shell 2.1.0，并重写 82 个文件，不能作为固定 2.6.0 输入下的精确 A2。因此本组在重放前拒绝，正式接纳 0 条。

## 候选框折叠

| 坐标 | 记录 | 模块 |
|---|---:|---|
| `org.springframework.boot:spring-boot-starter-test` | 3 | `samples/basic`、`samples/complete`、`starter` |

这些模块共享根 POM、依赖图和 Spring Shell 循环引用，不能计为三个独立案例。候选明细保存在 `candidate-frame.jsonl`，根仓裁决保存在 `root-audit.jsonl`。

## 上游变化边界

版本标签解引用后的提交为：

- `v2.5.3`：`043e02ce988c43b880156626b6f4300878e7c93c`
- `v2.6.0`：`44047f322d50c365941b59ff782e15b605a457ea`

关键提交是 `01e741d7039b626054911e0797872776ce28c120`，标题为 `Prohibit circular references by default`。它是 `v2.6.0` 的祖先，不是 `v2.5.3` 的祖先。该提交：

- 让 `SpringApplication` 默认向 Bean 工厂传入 `allowCircularReferences=false`；
- 增加 `spring.main.allow-circular-references` 配置项；
- 增加默认失败和显式放行的对应测试；
- 在失败诊断中说明循环引用默认被禁止。

公开错误的完整根因指向 Spring Shell 2.0.1 的 `ResultHandlerConfig`，依赖链经过 `sshShellSessionManager`、`sshShellCommandFactory` 和 `sshShell`。Spring Shell 自身提交 `e30edf2446a8ad190253b0a4154f0c0554dd4d8e` 后来为 Boot 2.6.1 临时启用循环引用，并在提交说明中明确称此举只是为真正移除循环争取时间。这是机制旁证，不是目标仓 A2。

## 目标仓历史

`fonimus/ssh-shell-spring-boot` 的远程引用包含 947 个可达提交，主分支包含 641 个提交。对 722 个唯一 POM 内容块的检查结果为：

- 389 个声明 Spring Boot 版本；
- 6 个使用 2.5.3；
- 20 个使用 2.5.6；
- 只有 1 个使用 2.6.0；
- 5 个使用 2.7.2。

唯一的 2.6.0 内容来自未合并的 Dependabot PR 167，提交 `3572a32442361b5c6ae956063245ca9709c6a515` 只改动根 `pom.xml`，将 Boot 2.5.6 升到 2.6.0。它没有目标修复，后来被 PR 169 的 2.6.1 升级替代。主分支没有采用任何 2.6.x 版本，也没有加入 `spring.main.allow-circular-references`。

维护者最终通过 PR 230 合入提交 `164d03a6cf7d522750032f7f4ff7a89be8588216`，同时把 Boot 2.5.6 升到 2.7.2、Spring Shell 2.0.1 升到 2.1.0，并改动 82 个文件，新增 1711 行、删除 1573 行。这个组合迁移无法证明固定 Boot 2.6.0 后，哪一处目标变化精确恢复了原失败契约。

## 为什么不执行三臂

这组候选可以构造一个可信 A1：在目标基线提交上只替换 Boot 版本，预期会重现公开失败。但当前旗舰集要求 A2 是维护者针对同一固定源输入的精确恢复。普通测试能够证明作者手工加入逃生配置或同步升级 Spring Shell 后程序恢复，却不能把这种事后方案变成维护者历史行为。

这里的具体误标风险，是把一次未合并的依赖升级与八个月后覆盖 82 个文件、同时改变两个核心依赖的迁移拼接成三臂，从而把无法隔离的组合变化记作精确修复。Git 提交能固定两个端点，版本号能固定依赖，普通测试能测最终结果，但都不能消除中间多个生产变化的归因混杂，所以在执行前停止。

## 证据边界

三条公开失败仍是高质量影响线索，也说明 Marshal 应能从上游默认行为变化追到下游框架的 Bean 图。但在以维护者精确 A2 为准入条件的旗舰因果集里，它们只贡献 1 个被拒绝的根仓候选，不贡献正例、负例或 A3。

完整统计位于 `history-evidence.json`，紧凑结果位于 `results/spring-boot-2.6-fse-history-screening-2026-08-25/summary.json`。

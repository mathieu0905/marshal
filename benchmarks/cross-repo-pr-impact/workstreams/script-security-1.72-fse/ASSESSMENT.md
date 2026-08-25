# Script Security 1.72 的 FSE 关系族筛选

更新日期：2026-08-25

## 结论

完整精确版本框共有 3 条候选、3 个失败观察，分别来自 `jenkinsci/extended-choice-parameter-plugin`、`jenkinsci/scriptler-plugin` 和 `jenkinsci/groovy-plugin`，去重后仍是 3 个独立根仓。本轮正式接纳 0 条，没有执行 A0、A1、A2，也没有限定负例或 A3。

三条记录不能只因异常外层都是 `IOException` 就合并。工作簿完整堆栈显示，它们都在 `PluginAutomaticTestBuilder` 的插件启动检查中失败，内层消息均为 Script Security 1.72 要求 Jenkins 2.176.4 或更高；三个目标的测试基线分别是 2.60.3、2.121.3 和 2.107.3。因此三条记录确实命中同一个插件清单兼容边界。

源变化可以定位到提交 `df064cd7e51e861b47752103cdc60065d1941b34` 中的 `jenkins.version` 修改。不过，三个目标仓的全部可达历史都没有声明固定 Script Security 1.72，也没有维护者在保持 1.72 的条件下只提高 Jenkins 基线并恢复同一启动合同。后续历史均跳到其他 Script Security 版本或 BOM 管理的现代版本。它们能说明维护方向，不能改写成 1.72 的精确 A2。

## 完整候选框

| FSE 候选 | 目标插件 | 原声明版本 | 最后通过探针 | 失败时 Jenkins | 根仓 |
|---|---|---|---|---|---|
| `fse2024-behavioral-0534` | extended-choice-parameter | 1.19 | 1.71 | 2.60.3 | `jenkinsci/extended-choice-parameter-plugin` |
| `fse2024-behavioral-0535` | scriptler | 1.26 | 1.71 | 2.121.3 | `jenkinsci/scriptler-plugin` |
| `fse2024-behavioral-0537` | groovy | 1.54 | 1.71 | 2.107.3 | `jenkinsci/groovy-plugin` |

三条记录的首个失败探针均为 1.72。工作簿没有保存目标 Git 修订，因此表中的 Jenkins 基线只能约束执行时依赖形状，不能从中任选一个历史提交冒充原始输入。

## 精确源变化

Script Security 的 1.71 与 1.72 标签都是带说明标签，必须区分标签对象和源码提交：

- `script-security-1.71` 标签对象为 `cca114e6b7d576c54f00a428b25686ff23eb1b3e`，指向提交 `830412e1d2ec7a9f3715811150e11396614a7314`；
- `script-security-1.72` 标签对象为 `e354313a4dd0215fb3b1ce9868f72561b4d6622b`，指向提交 `2bf6a1a3b9933790ac36cf69aa8bc88c0e42d32b`。

提交 `df064cd7e51e861b47752103cdc60065d1941b34` 把插件父 POM 从 3.55 升到 4.1，并把 `jenkins.version` 从 2.60.3 提高到 2.176.4。Jenkins 构建据此生成插件清单的最低核心版本；三个完整堆栈都由 `PluginWrapper.resolvePluginDependencies` 读取这项要求并拒绝加载。

该提交还修改 `SandboxResolvingClassLoader.java`，1.71→1.72 的发布差异还包含 Caffeine 2.7.0→2.8.2。因此不能把整个提交或整个发布差异都称为失败机制；本组能够精确归因的是 POM 中的最低 Jenkins 版本修改。

## 目标历史审计

### extended-choice-parameter-plugin

远程镜像共有 254 个引用和 604 个唯一可达提交。默认分支头为 `023f1e97bb3c00e75994da55501a987a35e05c17`，日期为 2025-03-11。全部依赖文件历史没有 Script Security 1.72。

2022 年的拉取请求 40、42、44 分别尝试把 1.19 改为 1.56、1.75 和现代流水号，均只存在于拉取请求引用。默认分支后来通过 `79347da6fc5ad4bd46cd96de7cb459b7e3b30914` 完成九文件构建现代化，把 Jenkins 2.60.3 改为 2.332.4，并把 Script Security 1.19 直接改为 `1172.v35f6a_0b_8207e`。该提交改变源输入且范围宽，不能作为 1.72 的 A2。

### scriptler-plugin

远程镜像共有 275 个引用和 709 个唯一可达提交。默认分支头为 `8ccbd0e7cdc51da114295ce5e51bd3ec12eec4d6`，日期为 2026-08-11。全部依赖文件历史没有 Script Security 1.72。

未合并的拉取请求 40 曾把 1.26 改为 1.75，并引入 Jenkins 2.263 BOM。默认分支后来在 `7459b5fae33b788064c6447283e74ed5b1d370e4` 把 Jenkins 2.121.3 提高到 2.249，又在 `a7b7a5358bc39b7ef516a0d4fea5e996ae401916` 提高到 2.319.3 并移除显式 1.26，转由 BOM 管理 Script Security。维护者从未采用固定 1.72，不能把这些后续基线升级抽成历史 A2。

### groovy-plugin

远程镜像共有 175 个引用和 620 个唯一可达提交。默认分支头为 `741a5af1b581edad62730bcd19064074676e87c0`，日期为 2026-03-13。全部依赖文件历史没有 Script Security 1.72。

拉取请求 35 和 37 分别尝试把 1.54 改为 1.56 与 1.75，均未进入默认分支。默认分支的 `41c9425b91d22771ec00a0f8ddab41d9b8bf6220` 把 Jenkins 2.107.3 提高到 2.303.3，同时移除显式 Script Security 1.54 并改由 BOM 管理。它同样不是固定 1.72 的精确维护者恢复。

## 为什么不执行三臂

FSE 已经提供了三个真实 A1 失败堆栈，但没有目标修订。三个仓都找不到精确 A2。若选择一个仍保留旧 Jenkins 基线的目标提交，合成 1.72 后再把 Jenkins 改到 2.176.4，实验很可能得到“通过、插件无法启动、再次通过”；然而最后一步只是数据集作者照着错误消息写出的修复。

另一个错误做法是从后来的大型构建现代化提交中抽取 Jenkins 基线升级，同时忽略维护者实际跳到了 1.75、现代流水号或 BOM 版本。这样会生成维护者从未采用过的“Script Security 1.72 + 新 Jenkins”组合。Git、版本号和普通测试可以固定并验证这项人工组合，却不能证明它是目标维护者对 1.72 的真实响应。

按现有准入顺序，本组在历史筛选后停止。只重复 A0/A1 会再次证明工作簿已经记录的事实，不能形成恢复闭环。

## 证据边界

本组证明 Script Security 1.72 的最低 Jenkins 版本变化击中了三个独立插件仓，并产生同一插件加载失败。它不提供精确目标修订、固定 1.72 的维护者 A2、限定负例或 A3，因此不进入旗舰正式正例。

机器可读候选、根仓裁决和历史证据分别位于 `candidate-frame.jsonl`、`root-audit.jsonl` 与 `history-evidence.json`；紧凑结果位于 `results/script-security-1.72-fse-history-screening-2026-08-25/summary.json`。

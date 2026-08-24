# 跨仓评测竞品可运行性

调查日期：2026-08-23

## 结论

CodeRabbit、Qodo、Greptile 和 Bito 都公开提供了某种跨仓上下文能力，但截至本次调查，没有一个完整竞品通过已公开接口直接满足当前评测的离线历史快照协议。这里的关键差异不是“是否支持跨仓”，而是能否同时做到：读取每条案例给定的全部候选仓历史提交、使用失败发生前的源差异、推理阶段不访问后来信息，并输出可评分的有序仓库列表。

因此竞品比较分为三类，结果不得混在同一张主表中：

1. **同协议主表**：直接读取 `prepare_case_inputs.py` 生成的离线目录，全部候选仓可见，推理时关闭网络，并按统一格式最多返回 5 个仓库。当前只有 Marshal 审查流程和能够读取同一目录的公开适配方法具备进入条件；尚无已核验的完整商业竞品。
2. **托管沙箱重放**：把历史提交镜像到有管理权限的 GitHub 或 GitLab 组织，在产品原生的合并请求与跨仓配置中运行。它可以回答产品在自身工作流里能否发现问题，但输入、仓库身份、网络和历史先验都不同，只能单独报告。
3. **组件对照**：只比较跨仓检索或代码上下文组件。例如 Bito AI Architect 可以直接索引本地多仓目录，但它本身不产生代码审查结论或目标仓排序。使用相同模型和提示后可以测量检索组件贡献，不能把结果写成 Bito 完整代码审查产品成绩。

“官方文档未说明”只表示当前没有足够证据认定接口存在，不等于证明产品内部绝对不支持。真正运行前仍需用有授权的账号做最小案例核对。

## 同协议准入条件

一个系统只有同时满足以下条件，才能与 Marshal 离线多仓结果直接比较：

- 接收案例中的 `source.patch`、`input.json` 和 `repositories/`，不要求把代码推送到外部托管平台；
- 使用 `repository-snapshots.json` 指定的全部候选仓提交，不自行替换为当前默认分支，也不隐藏一部分候选仓；
- 推理期间不能读取目标修复、后来合并请求、协调尾注、持续集成结果、隐藏标签或托管平台关系接口；
- 不使用正式集标签配置仓库关系；
- 能输出明确的仓库名称和顺序，最多 5 个；解析适配只能转换格式，不能补充产品没有给出的仓库判断；
- 与其他系统使用相同的模型档位、上下文上限、重复次数和失败记录规则。

如果产品必须联网调用自己的推理服务，但能够保证它只收到上述离线材料，仍可另设“相同材料、服务端推理”比较；它不能与严格离线结果混写，且必须记录上传内容和服务端可访问的额外知识边界。

## 产品逐项核对

### CodeRabbit

已核验事实：

- 多仓分析通过手工关联仓库或自动关联仓库工作；手工关联从 Pro 计划开始，自动关联需要 Pro+ 或企业计划。
- 每个源仓可启用的关联仓上限依计划为 Free 0、Pro 1、Pro+ 10、Enterprise 20。超过上限时只启用配置中的前若干项。
- 跨仓审查默认读取关联仓默认分支；GitHub 和 GitLab 可以在合并请求说明中指定关联仓分支或仍处于打开状态的合并请求。关闭、已合并或不存在的关联合并请求会退回默认分支。
- GitHub 上必须在所有关联仓安装 CodeRabbit 应用；关联仓必须与源仓位于同一种托管平台并具备读取权限。
- CodeRabbit CLI 从一个 Git 工作树运行，`--dir` 只能指向该工作树或其子目录；`--agent` 提供结构化 JSON。官方同时说明 CLI 审查和托管合并请求审查并不相同。
- 托管 CLI 审查需要连接 CodeRabbit 的 HTTPS 与 WebSocket 服务；远程 Git 访问还用于默认分支检测、克隆和关联仓读取。

对本评测的影响：

- 校准轨道每个候选目录有 4 至 14 个仓。Pro+ 的 10 个关联仓上限不足以完整覆盖 Ethereum、OpenTelemetry、OpenStack 和 StarlingX 目录；Enterprise 可以覆盖校准目录。
- 因果试采每例有 5、26、14、17、13 或 11 个候选仓。26 仓案例超过 Enterprise 的 20 仓上限，不能在不删候选项的情况下运行。
- OpenDev 因果案例使用 Gerrit，并有一个 GitHub 托管的执行清单仓；CodeRabbit 的关联仓要求同一受支持平台。要运行必须先镜像到统一平台，已经不再是原始输入协议。
- 官方 CLI 文档没有说明如何把若干本地兄弟工作树作为 `linked_repositories` 提供给一次 CLI 审查；官方多仓文档描述的是已经接入平台并由服务端读取的仓库。
- CodeRabbit 的原生输出是跨仓发现和行内评论，不是候选仓完整排序。CLI 虽有 JSON 输出，但尚未证明本地 CLI 会应用托管端关联仓配置。

结论：当前不能进入同协议主表。可以在有相应计划和仓库管理权限后，选择候选数不超过计划上限的案例做托管沙箱重放；26 仓案例不能完整重放。

### Qodo

已核验事实：

- 跨仓审查目前标为测试阶段，仓库关系可自动发现或手工建立，并且关系没有方向。
- 仓库必须通过 Qodo 安装向导接入，旧安装方式的仓库需要重新接入后才会出现在关系管理中。
- 每仓最多手工建立 100 个关系；自动发现的关系不受该上限约束。但每次合并请求审查只分析与该请求最相关的 10 个活跃关系。
- 默认读取关联仓主分支；可以在合并请求说明或关联工单中给出异仓分支或合并请求链接。
- 原生结果是在合并请求中带 `Cross-repo` 标记的冲突发现及受影响行链接，不是候选仓排序。

对本评测的影响：

- “最多 100 个关系”不能解决输入覆盖问题，因为一次审查仍只读取内部选择的 10 个关系。校准轨道中 4 个目录超过 10 个候选仓，因果试采中除 5 仓案例外都超过 10 个。
- 官方跨仓文档描述的是已接入托管平台的仓库，没有接收本地历史快照目录的接口。
- Qodo 自行选择“最相关的 10 个”会改变评测候选空间；即使最终命中目标，也无法与读取全部候选仓的系统直接比较。

结论：当前不能进入同协议主表。可以在托管沙箱中做产品原生案例研究，但必须记录实际被分析的 10 个关系；若产品不公开这份清单，结果只能说明端到端发现是否出现，不能解释仓库排序能力。

### Greptile

已核验事实：

- Greptile 可以用 `context.repos` 配置关联仓，格式为 `owner/repo`；关联仓必须与源仓位于同一个代码托管主机，并能用相同凭据读取。
- 仓库集群会在审查任一成员时把其他成员作为只读上下文克隆。集群至少有 2 个仓，总仓库大小上限为 20 GB。
- Greptile CLI 从一个带远程来源的本地 Git 仓运行，只审查当前分支中尚未合入默认分支的已提交变化，不审查未提交变化；`--json` 可输出机器可读结果。
- CLI 接入要求连接 GitHub 或 GitLab、启用仓库并完成索引。自托管版本可以把审查沙箱和推理留在本地，但仍要求先通过控制台接入仓库，CLI 只支持 GitHub 和 GitLab 远程地址。
- `context.repos` 只指定仓库名，官方参考没有提供为每个关联仓指定任意历史提交的字段。

对本评测的影响：

- Greptile 的 JSON 输出和较宽松的集群容量使它适合托管沙箱重放，但它仍从已接入远程仓克隆上下文，不能直接使用本地 `repositories/` 中逐仓固定的历史提交。
- 可以把每个历史快照镜像成受控仓库默认分支，把源差异做成一条新分支，再用 `context.repos` 或集群运行。这样改变了仓库身份、远程历史和配置来源，必须作为沙箱重放单独报告。
- 自托管消除了代码发送到云端的问题，但没有消除远程接入、仓库镜像和历史提交选择差异。

结论：在三个完整审查产品中，Greptile 最接近可自动化的托管沙箱重放，因为有 JSON 输出且集群容量足够；它仍不能进入严格离线主表，除非账号实测证明 CLI 能锁定每个关联仓的给定本地提交。

### Bito

已核验事实：

- 本地 AI Architect 可以扫描一个目录下一层的全部 Git 仓，提取代码搜索、符号、依赖边和仓库聚类，并通过本地 MCP 服务提供跨仓检索。它可以直接索引当前评测展开后的候选仓目录。
- 该本地组件提供仓库目录、依赖查询、跨仓字段查询、代码搜索和源码读取，但不提供代码审查命令、目标仓排序或统一发现结论。
- Bito AI Code Review Agent 的自托管命令行模式以 `pr_url`、代码托管方和访问令牌为必填输入，运行后把评论发布到指定合并请求，不是对本地工作树运行。
- 代码审查产品要获得跨仓知识，需要连接 AI Architect；官方接入流程要求在 Bito Cloud 设置 MCP 地址和访问令牌，并联系支持开通试用。

对本评测的影响：

- AI Architect 是目前四者中唯一通过公开文档明确可以直接消费本地多仓快照目录的组件。
- 它没有独立作答能力。若让同一个基础模型分别使用原始文件工具和 Bito MCP，再输出统一仓库排序，测到的是索引与检索层贡献，不是 Marshal 与 Bito 代码审查产品的端到端比较。
- Bito Code Review Agent 仍依赖托管合并请求、访问令牌和云端接入，当前没有证据表明它能把本地 AI Architect 的历史快照索引作为一次命令行审查的完整候选空间。

结论：可列为同材料的“检索组件对照”候选；完整 Bito 代码审查产品只能在取得试用和接入权限后做托管沙箱重放。

## 建议的运行顺序

1. 先完成 Marshal 对离线目录的真实运行，固定输出适配和失败记录格式，但不根据正式标签调整规则。
2. 用一个不含隐藏标签的开发案例验证 Bito AI Architect 是否能索引准备目录，并让同一模型、同一输出提示分别使用普通文件读取和 Bito MCP。只有这一步通过，才扩大组件对照。
3. 若具备产品账号和仓库管理权限，优先为 Greptile 建一个最小托管沙箱：一个源仓、一个目标仓和两个干扰仓。验证关联仓实际采用的提交、JSON 中能否恢复仓库判断，以及产品是否读取了沙箱之外的历史。
4. CodeRabbit 只选择关联仓数量不超过计划上限的案例；先实测本地 CLI 是否读取托管关联仓。若不读取，改用合并请求审查并与 CLI 结果分开。
5. Qodo 先核对一次审查实际选择的 10 个关系是否可见。若不可见，不扩大运行规模。

上述最小运行都不是新门禁。它们对应的具体失败场景是：产品静默改用当前默认分支、静默丢弃候选仓或读取沙箱外历史时，得到的命中不能归因于当前评测输入。Git 提交号只能证明本地准备版本，不能证明远端产品实际读取了该版本；因此托管重放必须从产品回显、审查详情或服务日志核对实际上下文。

## 报告方式

同协议主表继续报告已知目标召回、平均倒数排名、前 1/3/5 项召回和预测仓数量。托管产品通常只输出发现而不输出完整排序，因此沙箱研究单独报告：

- 已知目标仓是否被明确提及；
- 提及了多少个仓库；
- 是否给出可核对的跨仓代码证据；
- 实际读取的仓库及提交是否可确认；
- 输入截断、账号计划、联网和执行失败。

没有原生顺序时不从评论位置臆造排名，也不计算平均倒数排名。没有可靠负例时，任何轨道都不报告精度、误报率或停止能力。

## 官方资料

以下资料均于 2026-08-23 直接读取：

- CodeRabbit：[多仓分析](https://docs.coderabbit.ai/knowledge-base/multi-repo-analysis.md)、[计划与功能上限](https://docs.coderabbit.ai/management/plans.md)、[命令行工具](https://docs.coderabbit.ai/cli/index.md)、[命令行参数](https://docs.coderabbit.ai/cli/reference.md)、[网络要求](https://docs.coderabbit.ai/cli/network-requirements.md)
- Qodo：[跨仓代码审查](https://docs.qodo.ai/governance/cross-repo-code-review.md)、[仓库关系](https://docs.qodo.ai/governance/cross-repo-code-review/repository-relationships.md)、[仓库接入管理](https://docs.qodo.ai/governance/repositories.md)
- Greptile：[跨仓上下文](https://www.greptile.com/docs/code-review/cross-repo-context.md)、[配置参考](https://www.greptile.com/docs/code-review/greptile-json-reference.md)、[命令行工具](https://www.greptile.com/docs/code-review/greptile-cli.md)、[命令行接入](https://www.greptile.com/docs/code-review/cli-onboarding.md)、[自托管命令行审查](https://www.greptile.com/docs/self-hosting/cli-reviews.md)
- Bito：[本地仓库智能](https://docs.bito.ai/ai-architect/local-repository-intelligence-for-ai-assistants.md)、[本地命令参考](https://docs.bito.ai/ai-architect/local-repository-intelligence-for-ai-assistants/available-commands.md)、[可用 MCP 工具](https://docs.bito.ai/ai-architect/integrating-ai-architect-with-your-tools/available-mcp-tools.md)、[代码审查集成](https://docs.bito.ai/ai-architect/integrating-ai-architect-with-your-tools/integrating-with-bitos-ai-code-review-agent.md)、[自托管命令行审查](https://docs.bito.ai/ai-code-reviews-in-git/install-run-as-a-self-hosted-service/install-run-via-cli.md)

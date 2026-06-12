# Marshal 全球竞品与定位分析

> 日期:2026-06-12  
> 范围:AI 代码审查、应用安全平台、代码质量门禁、形式化/不变量验证工具。  
> 结论:全球已有许多单项能力强于 Marshal 的成熟产品,但尚未看到一个公开产品完整覆盖 Marshal 的组合式闭环:领域包 + 风险分级 + 不变量门禁 + 对抗式 review + 逃逸棘轮 + 规格 conformance。

---

## 1. 一句话结论

Marshal 不应被定位成“又一个 AI PR reviewer”。如果只比较 PR 评论体验、企业 SaaS 成熟度、AppSec 规则库、形式化验证能力,全球已有很多更强产品。

Marshal 更准确的定位是:

> **质量工程编排层**:把 AI review、安全扫描、形式化工具、项目专属不变量、规格覆盖和逃逸学习组织成一个会越用越严的质量闭环。

因此,Marshal 的竞争对手分成四类:

1. AI PR Review 产品:Greptile、Qodo、CodeRabbit、Claude Code Review、GitHub Copilot Code Review、Graphite Diamond。
2. AppSec / 安全扫描平台:Semgrep、Snyk DeepCode AI、SonarQube、GitHub Advanced Security / CodeQL。
3. 形式化验证与不变量验证工具:Certora、Echidna、Foundry Invariant Testing、Slither。
4. 通用开发代理与代码智能平台:Claude Code、Sourcegraph Cody、Cursor 等。

这些产品很多单点更成熟,但通常缺少 Marshal 最核心的“逃逸即学习、学习即永久门禁”的系统机制。

---

## 2. 产品地图

### 2.1 AI PR Review 产品

这些产品最接近 Marshal 的“对抗式 review 层”。它们的主要价值是自动阅读 Pull Request,结合上下文给出代码问题、风险提示、改进建议或修复建议。

| 产品 | 核心能力 | 强项 | 相对 Marshal 的差异 |
|---|---|---|---|
| Greptile | 全代码库图索引 + 多 agent PR review | 官方资料强调会构建 repo graph,理解 files/functions/dependencies,并让 parallel agents 评审 PR 影响面 | 产品化、代码库上下文、PR 体验强于 Marshal;但不以“不变量注册表 + 逃逸棘轮”为核心 |
| Qodo | AI Code Review Platform | 官方文档强调组织级配置、治理、自动 PR review、多 agent、context-aware feedback | 企业治理和组织级 review 平台更成熟;但更偏 review/governance,不是领域不变量平台 |
| CodeRabbit | AI code review / planning / workflow | 安装快,支持 PR、IDE、CLI、Jira/Slack 等工作流;有路径级 review instructions 和报告能力 | 使用体验和团队流程成熟;但对深层领域不变量、跨 repo 契约、escape ratchet 支持不是核心 |
| Claude Code Review / Ultrareview | 官方多 agent code review | 官方描述为 specialized agents 在 full codebase context 下找 logic errors/security/edge cases/regressions | 对抗式深审能力可能很强;但不 approve/block PR,也不是不变量/知识核平台 |
| GitHub Copilot Code Review | GitHub 原生 PR review | 分发能力强,与 GitHub PR 工作流天然融合 | 低摩擦但通用;不提供 Marshal 式领域包和棘轮 |
| Graphite Diamond | 与 stacked PR 工作流结合的 AI review | 对高频 stacked PR 团队有工作流优势 | 更像 review workflow + AI reviewer,不是质量知识核 |

**判断:**  
如果用户只想买“AI 自动审 PR”,Marshal 当前不应正面和 Greptile、Qodo、CodeRabbit、Claude Code Review 比产品成熟度。Marshal 应把这类能力视作可接入的 review worker,或者在高危领域中做更强的领域化编排。

### 2.2 AppSec / 安全扫描平台

这些产品比 Marshal 强在安全规则库、漏洞优先级、误报治理、组织级管理、合规流程、自动修复。

| 产品 | 核心能力 | 强项 | 相对 Marshal 的差异 |
|---|---|---|---|
| Semgrep | SAST / SCA / Secrets / AI-assisted AppSec | 可在组织级编排静态分析、依赖扫描、secret 扫描;规则可扩展 | 安全扫描和治理远成熟;Marshal 可把 Semgrep 作为执行器,但不应替代它 |
| Snyk DeepCode AI | AI-assisted code security / autofix | 官方资料称有大量 data-flow cases、多语言支持、多模型、漏洞优先级和 autofix | AppSec 数据流分析和修复强;Marshal 更关注项目专属业务不变量 |
| SonarQube / SonarQube Cloud | 代码质量门禁、AI Code Assurance、AI CodeFix | 成熟的 quality gate、bug/security/code smell 检测、AI 生成代码质量保障 | 企业质量门强;但规则多为通用质量/安全,不懂项目特有经济/共识/规格 |
| GitHub Advanced Security / CodeQL | CodeQL code scanning、自定义 query | CodeQL 将代码建成数据库,用 query 找漏洞和错误;支持 custom queries | 是 Marshal 永久检查的强后端之一;但本身不管领域包、逃逸棘轮、规格覆盖流程 |

**判断:**  
在安全领域,Marshal 不是 Semgrep/Snyk/Sonar/GHAS 的替代品。更合理的架构是 Marshal 作为上层 gate brain,把这些工具的发现吸收为 structured findings,再结合风险分级和棘轮机制做决策。

### 2.3 形式化验证 / 不变量验证工具

这些工具比 Marshal 强在“证明某条性质是否成立”或“用随机/符号/状态空间探索找反例”。

| 产品/工具 | 核心能力 | 强项 | 相对 Marshal 的差异 |
|---|---|---|---|
| Certora Prover | 智能合约形式化验证 | 将规则与合约字节码/行为对比,通过 SMT 等技术证明或给出反例路径 | 在数学级不变量证明上强于 Marshal;Marshal 可管理“何时跑哪些规则” |
| Echidna | Ethereum smart contract property-based fuzzer | 通过 fuzzing falsify 用户定义的 predicates / assertions | 是“不变量门禁”的成熟执行器,不是组织级质量大脑 |
| Foundry Invariant Testing | Solidity 状态ful invariant testing | 验证任意 action sequence 后某些性质仍成立 | 与 Marshal 的 invariant 思路相同,但局限于 Foundry/EVM 执行层 |
| Slither | Solidity / Vyper 静态分析框架 | 快速检测智能合约常见漏洞,可定制 detector | 是 detector/执行器,不是逃逸学习平台 |

**判断:**  
在 Web3/智能合约场景,Certora/Echidna/Foundry/Slither 的执行能力明显强于 Marshal。Marshal 的价值不是替它们证明性质,而是让这些性质进入 PR gate、规格 conformance 和 escape ratchet。

---

## 3. 按能力维度比较

| 能力维度 | 全球强者 | Marshal 当前状态 | Marshal 的机会 |
|---|---|---|---|
| PR 评论体验 | CodeRabbit、Greptile、Qodo、GitHub Copilot | 本地 skill + CLI,产品化弱 | 不以评论体验为主战场,优先做高价值门禁 |
| 全代码库上下文理解 | Greptile、Qodo、Claude Code Review | 依赖 skill 临场读取 + domain pack | 接入代码图/索引层,增强 JIT context |
| 多 agent review | Qodo、Claude Code Review、Greptile | 设计上有多视角 review/quorum,执行依赖 skill | 强化“对抗式 + 验证二段 + 高危归人” |
| 企业治理 | Qodo、SonarQube、Semgrep、Snyk | 目前主要是本地/文件态 | 后续平台化需补组织、权限、审计、报表 |
| 安全扫描 | Semgrep、Snyk、CodeQL、SonarQube | 有 CI security hazard + zizmor wrapper 种子 | 作为编排层接入这些工具 |
| 形式化证明 | Certora | Marshal 不做证明 | 调度 Certora 规则,把证明结果纳入 gate |
| Property-based / invariant testing | Echidna、Foundry、各语言测试框架 | CowboyPack 已列 run_command,reporter 可拉计划执行 | 强化 invariant registry 与执行器适配 |
| 项目专属领域知识 | Qodo/CodeRabbit 有 rules/context,但多偏 review | Domain Pack 是核心抽象 | 把领域包做成可复用资产 |
| 逃逸棘轮 | 公开产品里少见作为核心机制 | 已有 EscapeRegistry + spawned_check 约束 | 最大差异化:每次漏网变永久门禁 |
| 规格 conformance | 一般工具较弱 | 有 CIP/whitepaper 种子级 conformance | 深化 requirement ↔ invariant 精确映射 |
| 跨 repo 契约 | Greptile/Qodo 可读全局上下文,但非契约注册表 | CowboyPack 显式记录 contracts_hit + verify_invariants | 做成 Marshal 的核心卖点之一 |

---

## 4. Marshal 的差异化

### 4.1 Marshal 不是“审查器”,而是“质量大脑”

大多数 AI review 产品的输出是评论:这段代码可能有 bug、这里应该改、这里缺测试。  
Marshal 的目标输出是 gate decision 和 permanent checks:

- 这次 PR 属于哪个风险等级?
- 哪些不变量必须跑?
- 哪些跨 repo 契约被触发?
- 哪些发现必须进入 human review?
- 如果这次漏了,永久检查应该长什么样?

这意味着 Marshal 更接近质量工程操作系统,而不是单个 reviewer。

### 4.2 Domain Pack 是核心护城河

Domain Pack 把“这个项目真正危险的东西”显式编码:

- 哪些路径高危。
- 哪些地址/编号/协议字段不能冲突。
- 哪些 repo 之间存在字节级契约。
- 哪些 CIP / whitepaper 条款对应哪些不变量。
- 哪些安全属性不能用 roundtrip test 表达。
- 哪些 review lens 应该在高危改动里启用。

这类知识越积累越有价值,不像一次性 PR 评论会随 PR 关闭而消失。

### 4.3 Escape Ratchet 是 Marshal 最独特的产品机制

许多工具会“发现问题”。Marshal 进一步要求:

> 每个真实漏网缺陷,必须产生至少一条永久检查、危险点或 review rule。

这让质量体系具有复利特征:

- 今天漏掉的 bug,明天变成机器门禁。
- 门禁数量随真实事故单调增长。
- 项目越被审,领域包越厚。
- 迁移成本也随领域知识积累而升高。

### 4.4 Marshal 适合高代价缺陷场景

Marshal 最适合的问题不是普通代码风格,而是:

- 钱不能凭空增减。
- burn/tip/escrow 必须守恒。
- 状态根必须一致。
- 共识行为必须确定。
- 交易编码必须跨 repo 字节兼容。
- 系统 actor 地址不能撞号。
- 规格变更必须有 conformance 检查。
- 机密性/授权/侧信道这类否定性安全属性不能被 roundtrip 测试伪装覆盖。

这些是普通 AI reviewer 和传统 CI 最容易漏、但上线代价最高的问题。

---

## 5. 战略建议

### 5.1 不要正面替代成熟工具

Marshal 不应试图自己重做 Semgrep、Snyk、CodeQL、Certora、Echidna 或 Greptile 的全部能力。更合理的策略是:

- Semgrep/Snyk/CodeQL 提供安全 findings。
- Certora/Echidna/Foundry 提供不变量执行/证明结果。
- Greptile/Qodo/Claude Code Review 提供深度 AI review findings。
- Marshal 负责统一风险分级、证据汇总、gate decision、逃逸棘轮、领域包沉淀。

### 5.2 把 Marshal 定位成“质量工程编排层”

一句产品定位:

> Marshal turns review findings and escaped bugs into enforceable, domain-specific quality gates.

中文:

> Marshal 把审查发现和漏网缺陷转化为可执行、可积累、领域专属的质量门禁。

### 5.3 第一阶段应继续深耕高危领域

最适合验证 Marshal 的市场不是普通 SaaS CRUD,而是:

- 区块链 / 智能合约 / 共识系统。
- 金融 / 支付 / 对账系统。
- 医疗、航空、工业控制等高合规、高代价领域。
- 多 repo 协议系统。
- AI 高速产码导致 review 积压的大型工程组织。

这些场景里,“一次漏过的深层 bug”成本高,Marshal 的棘轮价值更容易被感知。

---

## 6. 详细名词解释表

| 名词 | 详细解释 |
|---|---|
| AI PR Review | 使用 AI 自动阅读 Pull Request,理解代码改动、上下文和潜在影响,并在 PR 中给出评论、风险提示或修复建议的工具形态。典型产品包括 Greptile、Qodo、CodeRabbit、Claude Code Review。它通常强调“帮 reviewer 更快发现问题”,但不一定把发现转化为永久门禁。 |
| Pull Request / PR | 代码托管平台中的变更合并请求。开发者把一个分支的改动提交给主分支或目标分支,请求 review 和合并。PR 是现代代码审查、CI、质量门禁的主要触发点。 |
| Code Review | 对代码改动进行审查的过程,目标是发现 bug、安全问题、可维护性问题、规格偏离和测试缺口。传统 code review 主要依赖人;AI code review 用模型辅助或自动化这一过程。 |
| 对抗式 Review | 一种默认怀疑的审查方式。它不是问“这段代码看起来可以吗”,而是问“这段代码如何出错、如何被绕过、违反了哪条不变量、是否制造了假绿灯”。Marshal 采用对抗式 review 来降低 AI 代码“表面正确、深层错误”的风险。 |
| Multi-agent Review | 多个 AI agent 从不同视角审查同一个改动,例如 correctness、security、spec、cross-repo、econ、determinism。多 agent 的价值是降低单一模型视角的盲区,但如果 prompt 或模型过于同质,仍可能有相关性盲区。 |
| Quorum | 法定票数或确认阈值。在 Marshal 的 review 聚合里,多个视角对同一问题达成足够支持才视为 confirmed。高危发现即使只有单视角提出,也会升级为 needs_human,因为高危问题的漏报成本高。 |
| Skeptic Pass / 对抗式验证二段 | 对已经发现的问题再派“怀疑者”去尝试推翻它。只有严格多数认为该发现成立,它才存活。这样做是为了降低 AI review 的误报,避免把似是而非的问题直接变成 gate 结论。 |
| Gate / 质量门禁 | 合并前必须通过的检查集合。门禁可以是测试、静态分析、形式化验证、AI review 或人工签字。Marshal 的 gate decision 包括 pass、block、needs_human。 |
| GateDecision | Marshal 的门禁结论对象。它通常包含 change_ref、risk tier、各个 gates 的 outcome 和最终 verdict。最终 verdict 可以是 pass、block 或 needs_human。 |
| pass | 门禁认为可以放行。注意在 Marshal 当前形态中,pass 是建议态,不一定具备 GitHub required check 的硬阻断能力。 |
| block | 发现明确失败,例如 active invariant 测试失败。block 表示不应合并,直到问题修复或检查被合法更新。 |
| needs_human | 需要人工裁决。通常用于高危改动、高危 AI finding、门禁 degraded、规格治理冲突、第三方扫描器发现未被 refute 的 HIGH/CRITICAL 问题。 |
| degraded | 降级状态,表示某个检查没有成功完成,例如工具缺失、测试没跑起来、API 失败、agent 超预算。Marshal 的原则是“降级不谎报”:没审成不能伪装成审过。 |
| Invariant / 不变量 | 系统在所有合法状态或操作序列中都必须成立的性质。例如“burn + tip == fee_total”“escrow 永不为负”“状态根在 propose/verify/report 阶段一致”。不变量比单元测试更关注系统底线性质。 |
| Invariant Gate / 不变量门禁 | 把不变量作为合并前检查执行。它不是看某个具体输入是否得到某个输出,而是验证某类性质是否被改动破坏。Marshal 的 `invariants` 命令会按改动路径和领域包返回必须运行的不变量。 |
| Property-based Testing | 基于性质的测试。开发者定义一个性质,测试框架自动生成大量输入去尝试打破它。与手写固定样例相比,它更适合验证“对所有输入都成立”的规则。 |
| Stateful Invariant Testing | 状态ful 不变量测试。测试框架生成一系列操作序列,每一步之后检查不变量是否仍成立。DeFi、共识、状态机、账本系统常需要这种测试。Foundry invariant testing 属于这一类。 |
| Fuzzing | 模糊测试。通过自动生成大量随机或变异输入来寻找崩溃、断言失败或性质违反。Echidna 是面向 Ethereum 智能合约的 property-based fuzzer。 |
| Formal Verification / 形式化验证 | 用数学方法证明程序是否满足规格。形式化验证通常会把程序和规则转成逻辑公式,再用求解器证明或找反例。Certora Prover 是智能合约领域的代表工具。 |
| SMT Solver | Satisfiability Modulo Theories 求解器。它能判断带有整数、数组、位向量等理论约束的逻辑公式是否可满足。很多形式化验证工具使用 SMT solver 来证明性质或生成反例。 |
| Static Analysis / 静态分析 | 不运行程序,直接分析源代码、字节码或中间表示来发现问题。Semgrep、CodeQL、Slither、SonarQube 都包含静态分析能力。 |
| SAST | Static Application Security Testing,静态应用安全测试。它用静态分析发现安全漏洞,例如注入、路径遍历、反序列化风险、危险 API 使用。Semgrep、Snyk Code、CodeQL 都属于或包含 SAST。 |
| SCA | Software Composition Analysis,软件组成分析。它分析依赖包和开源组件,发现已知 CVE、许可证问题、供应链风险。Semgrep、Snyk 等 AppSec 平台通常包含 SCA。 |
| Secrets Scanning | 扫描代码、配置、CI 文件中是否泄露 token、API key、私钥、密码等敏感凭据。它是 AppSec 平台常见模块。 |
| CodeQL | GitHub 的语义代码分析引擎。它把代码表示成可查询数据库,再用 CodeQL query 查找漏洞、错误和特定代码模式。Custom CodeQL queries 可用于项目特定规则。 |
| Semgrep Rule | Semgrep 的规则定义,通常用模式匹配和语义约束描述危险代码形态。可用于安全漏洞、代码规范、框架误用检测。 |
| SonarQube Quality Gate | SonarQube 中的一组质量阈值,例如 bug 数、安全漏洞、代码覆盖率、重复率、复杂度。未满足质量门时,项目或 PR 会被标记为失败。 |
| AI Code Assurance | SonarQube 提出的 AI 生成代码质量保障能力,目标是对包含 AI 生成代码的项目应用严格质量和安全标准。 |
| DeepCode AI | Snyk 的 AI-assisted code security 技术,结合数据流分析、多模型和安全知识来发现、优先级排序并修复漏洞。 |
| Certora Prover | 面向智能合约的形式化验证工具。用户用 CVL 等方式写规则,Prover 将规则与合约行为比较,证明性质或给出违反性质的调用 trace。 |
| CVL | Certora Verification Language,Certora 的规格语言。开发者用它描述智能合约必须满足的规则。 |
| Echidna | Trail of Bits / Crytic 生态中的 Ethereum 智能合约 fuzzer,通过生成交易序列来 falsify 用户定义的 assertions 或 predicates。 |
| Foundry | Ethereum 开发框架,包含 Forge 测试工具。Foundry 支持 fuzz testing 和 invariant testing,常用于 Solidity 项目的测试与安全验证。 |
| Slither | Solidity/Vyper 静态分析框架,由 Trail of Bits 生态维护。它能快速检测智能合约常见漏洞,也提供 API 让用户写自定义 detector。 |
| AppSec | Application Security,应用安全。覆盖代码漏洞、依赖风险、secret 泄露、CI/CD 供应链风险、安全治理和修复流程。 |
| CI/CD | Continuous Integration / Continuous Delivery,持续集成/持续交付。CI 负责自动构建、测试、扫描;CD 负责自动部署。CI/CD 配置错误本身也可能成为供应链攻击入口。 |
| GitHub Actions | GitHub 的 CI/CD 平台。workflow 文件通常位于 `.github/workflows/**`。若配置不当,例如在不可信 PR 上运行 self-hosted runner 或泄露 secrets,会造成严重风险。 |
| Self-hosted Runner | 用户自己托管的 CI runner。它可能拥有内部网络、缓存、凭据或部署权限。不可信代码在 self-hosted runner 上执行通常高危。 |
| pull_request_target | GitHub Actions 的一种触发器。它在 base repository 上下文运行,可能拥有 secrets 和写权限。如果它 checkout 并执行 PR head 的不可信代码,可能造成 pwn request。 |
| Pwn Request | 供应链攻击模式:攻击者通过 Pull Request 让 CI 在高权限上下文执行恶意代码,窃取 secret 或修改仓库/部署环境。 |
| zizmor | GitHub Actions workflow 安全审计工具。Marshal 的 `ci-scan` 命令用它作为 CI 安全的确定性后盾。如果缺失,应记为 degraded,不能当作安全审过。 |
| Domain Pack | Marshal 的领域包。它把项目专属质量知识打包:分级规则、不变量、规格层、review prompt、跨 repo 契约、运行时信号适配。核心不直接硬编码业务知识。 |
| marshal_core | Marshal 的领域无关核心包。包含契约、知识核、CLI、编排器、review 聚合、执行器和适配器骨架。 |
| marshal_pack_cowboy | Marshal 当前第一个领域包,内含 Cowboy 项目的路径规则、不变量、跨 repo 契约、规格层、安全 hazard 和 review 视角。 |
| Knowledge Core / 知识核 | Marshal 的持久状态层。当前用 SQLite `marshal.db` 存储不变量注册表、逃逸登记、门禁运行记录、审计日志。平台化后可升级为 PostgreSQL。 |
| InvariantRegistry | 不变量注册表。记录每条永久检查的 id、domain、spec_ref、executor_kind、location_repo、location_path、location_test、severity、origin、escape_id 等。 |
| EscapeRegistry | 逃逸登记表。记录漏过的真实缺陷,包括 escape_id、描述、根因分类、change_ref、spawned_check、状态。Marshal 要求 close escape 时必须有 spawned_check。 |
| Ratchet / 逃逸棘轮 | Marshal 的复利机制。每个漏过的真实 bug 都必须产出至少一条永久检查、hazard 或 review rule。系统因此随真实教训变得更严格。 |
| spawned_check | 某个 escape 产生的永久检查 id。它可以是一条不变量 id,也可以是 `hazard:<id>` 这种 review lens。没有 spawned_check 不能关闭 escape。 |
| SecurityHazard | Marshal 领域包中的安全危险点。它描述某类否定性安全属性,例如机密性、越权、secret 泄露。这类属性往往不能用 roundtrip test 表达,必须注入 security review lens。 |
| 否定性属性 | 描述“某件坏事不会发生”的性质,例如“未授权者不能解密”“攻击者不能越权”“secret 不会泄露”。这类性质通常很难用功能往返测试证明,因为 vulnerable implementation 也可能通过 roundtrip。 |
| Roundtrip Test / 往返测试 | 检查 `decode(encode(x)) == x` 或 `decrypt(encrypt(m)) == m` 的测试。它能验证功能一致性,但不能证明机密性、安全性或抗攻击性。 |
| Cross-repo Contract / 跨 repo 契约 | 多个仓库之间必须保持一致的接口或线格式。例如 wallet 编码交易,node 必须按同样字节解码;runner 类型序列化必须和 node 兼容。 |
| Conformance | 符合性。指实现、测试或不变量是否覆盖并满足规格要求。在 Marshal 中,conformance 关注 CIP/whitepaper requirement 是否有不变量或测试兜底。 |
| Conformance Matrix | 规格要求与验证检查之间的映射矩阵。理想状态是每条 requirement 都能映射到 covered_by 或明确 waiver。当前 Marshal 只有种子级 CIP 覆盖矩阵。 |
| Spec Layer / 规格层 | Marshal 对规格文档的分层建模。例如 whitepaper 是宪法层,CIP 是修正案层,code 是实然行为锚点。不同层有不同权威关系。 |
| Normative Axis / 规范轴 | 回答“系统应该怎样”的权威顺序。Marshal 架构里,CIP 在触及处可修订 whitepaper,因此规范轴需要处理修正关系。 |
| Descriptive Axis / 描述轴 | 回答“系统实际怎样”的权威顺序。通常代码是实然锚点,即使代码偏离规格,也先记录实际行为再判断是代码 bug 还是文档漂移。 |
| Drift / 漂移 | 规格、实现、测试之间不一致。可能是规格写了但代码没做,代码做了但文档没更新,或者两个规格互相冲突。 |
| Waiver / 豁免 | 明知某条检查或 requirement 暂不满足,但由负责人带理由放行。高质量系统中 waiver 应有 owner、reason、过期时间和审计记录。 |
| Risk Tier / 风险等级 | Marshal 对改动风险的分层,通常为 high、mid、low。高危改动会触发更多不变量、更强 review 和人工裁决。 |
| Blast Radius / 爆炸半径 | 改动一旦出错可能影响的范围。共识、资金、密码学、跨 repo 协议、CI/CD 凭据通常爆炸半径大。 |
| Run Command | 领域包为某条不变量提供的可执行命令,例如 `cargo test -p cowboy-execution ...`。Marshal reporter 对命令内容零知识,只负责执行。 |
| Reporter | Marshal 的无状态 CI 执行器。它向 `/plan` 拉取本次要跑的不变量和 run_command,执行后把 structured result 发回 `/results`。 |
| Shadow Mode / 影子模式 | 只报告、不硬阻断。Marshal 当前 GitHub Check Run skeleton 在 shadow mode 下返回 neutral,用于观察误报和稳定性。 |
| Clean Worktree / 干净工作树 | 为被审 PR head 单独 checkout 出来的 git worktree。Marshal 跑不变量时要求在干净 worktree 里执行,避免主工作树落后或脏改动造成假阳性/假阴性。 |
| `running 0 tests` 假绿 | 某些测试命令即使没有匹配到任何测试也返回 0。Marshal 明确要求不能把 `running 0 tests` 当 pass,必须确认至少一个测试真的执行并通过。 |
| Spec Ref | 不变量引用的规格标签,如 `CIP-3`、`CIP-24`、`WP`。Marshal 用它把不变量连接回规格来源。 |
| CIP | Cowboy Improvement Proposal,类似项目级改进提案/协议修正案。Marshal 把 CIP 当作规格层之一,用于 conformance 和 review。 |
| Whitepaper / WP | 白皮书。在 Marshal 对 Cowboy 的建模中,whitepaper 是宪法层,提供根本性系统约束。 |
| Determinism / 确定性 | 同样输入在不同节点、不同时间、不同机器上必须得到相同结果。共识系统、虚拟机、区块链执行层高度依赖确定性。 |
| PVM | Cowboy 相关上下文中的 Python Virtual Machine / runtime 组件。Marshal 的领域包里有多条 PVM determinism 与 reflection hardening 相关不变量。 |
| Econ Invariant / 经济不变量 | 与资金、费用、burn、tip、escrow、settlement 相关的不变量。例如费用总额守恒、比例和为 100%、escrow 不为负。 |
| State Root | 状态树的根哈希。共识系统用它代表全局状态。若不同节点对同一批交易得出不同 state root,可能造成共识分裂。 |
| Merkle Root | Merkle tree 的根哈希。用于高效承诺一组数据的内容。状态根通常是某种 Merkle root 或类似承诺。 |
| Escrow | 托管余额或锁定资金。经济系统中常要求 escrow 永不为负,释放/取消/结算路径必须守恒。 |
| Burn | 销毁代币或费用,通常意味着从流通供应中移除。若 burn 逻辑错误,可能出现凭空增发或资金泄漏。 |
| Tip | 支付给 proposer、runner 或其他参与者的费用部分。经济不变量常要求 burn + tip 等于总费用。 |
| Byte-compatible | 字节级兼容。两个 repo 或组件对同一数据结构的编码/解码必须产生完全相同的字节语义。 |
| Golden Vector | 金标准向量。预先固定的一组输入/输出样例,用于跨语言、跨 repo、跨版本验证协议编码一致性。 |
| Context Engine / Codebase Graph | AI review 产品用来理解代码库全局结构的索引或图。它可以包含函数、类、依赖、调用关系、历史 PR、团队规则等。Greptile/Qodo 都强调这类能力。 |
| Knowledge Base | AI review 产品沉淀的上下文知识,可能包括过去评论、项目规则、issue、PR、代码指南、集成系统信息。它与 Marshal 的 Domain Pack 相似,但通常更偏 review context,不一定是可执行门禁。 |
| Organization Standards | 组织级工程标准,例如安全规则、代码风格、测试要求、架构边界。Qodo、SonarQube、Semgrep 等产品都强调治理与标准执行。 |
| Code Smell | 不一定直接导致 bug,但影响可维护性、复杂度或可读性的代码问题。SonarQube 常用这一概念。 |
| Autofix | 工具自动生成修复建议或补丁。Snyk、SonarQube、AI review 工具常提供 autofix。Marshal 当前更关注判定和门禁,不是自动修复。 |
| False Positive / 误报 | 工具报告了问题,但实际不是 bug。AI review 和静态分析都容易产生误报。Marshal 通过 quorum 和 skeptic pass 降低误报。 |
| False Negative / 漏报 | 工具没有报告问题,但实际存在 bug。Marshal 的 escape ratchet 主要针对漏报:一旦发现漏报,必须织入永久检查。 |
| Correlated Blind Spot / 相关性盲区 | 多个 AI agent 或工具因为模型、prompt、上下文相似,在同类问题上一起漏掉。多 agent 只有在视角真正多样时才降低这种风险。 |
| Human Sign-off / 人工签字 | 高危改动即使机器 review 通过,也要求领域负责人最终确认。Marshal 的原则是高危终审归人。 |
| Audit Log / 审计日志 | 记录谁、何时、基于什么证据做了什么决定。质量门禁平台需要审计日志来支持复盘、合规和责任追踪。 |

---

## 7. 资料来源

- Greptile 官方网站与文档: https://www.greptile.com/ , https://www.greptile.com/docs/introduction
- Qodo 官方文档: https://docs.qodo.ai/ , https://docs.qodo.ai/code-review
- CodeRabbit 官方文档: https://docs.coderabbit.ai/
- Claude Code Review 官方文档: https://code.claude.com/docs/en/code-review
- Claude Code Ultrareview 官方文档: https://code.claude.com/docs/en/ultrareview
- Semgrep 官方网站与文档: https://semgrep.dev/
- Snyk DeepCode AI 官方资料: https://snyk.io/platform/deepcode-ai/
- SonarQube AI Code Assurance 文档: https://docs.sonarsource.com/agent-centric-development-cycle/features/ai-code-assurance
- GitHub CodeQL 文档: https://docs.github.com/code-security/code-scanning/introduction-to-code-scanning/about-code-scanning-with-codeql
- CodeQL custom queries 文档: https://docs.github.com/en/code-security/concepts/code-scanning/codeql/custom-queries
- Certora Prover 文档: https://docs.certora.com/en/latest/docs/user-guide/index.html
- Echidna 项目: https://github.com/crytic/echidna
- Foundry invariant testing 文档: https://www.getfoundry.sh/guides/invariant-testing
- Slither 项目: https://github.com/crytic/slither


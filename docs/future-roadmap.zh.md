# Marshal 未来 26 个大版本设想

> **定位:** 面向未来的产品与平台演进设想。本文不是承诺式路线图,而是一组长期方向锚点:用 A-Z 26 个大版本代号,描述 Marshal 从质量门禁工具走向质量工程操作系统的可能路径。
>
> **状态:** vision draft。
>
> **日期:** 2026-06-13

---

## 0. 版本代号原则

Marshal 的大版本代号按字母顺序推进。每个代号既是发布昵称,也是该阶段的工程主题:

1. **单词要能表达阶段气质。** 例如 Atlas 是承载,Beacon 是信号,Compass 是方向。
2. **主题要服务质量工程闭环。** 每个版本都应强化「不变量、分级、review、棘轮、conformance、运行时、度量」中的一个或多个环节。
3. **平台能力先于领域内容。** Cowboy 仍是第一领域包,但每个版本都要逐步减少平台对单一领域的隐含依赖。
4. **自动化不能吞掉人的判断。** 越靠后的版本越强,但关键治理、取舍和例外仍应留下可审计的人类决策点。

---

## 1. 四个时代

### Era I: Foundation / 地基期(A-F)

目标是把 Marshal 从可用的本机 skill 和薄 CLI,推进到可信的合并前质量门禁平台。

- **A · Atlas:** 承载第一套稳定骨架。统一 CLI、知识核、Cowboy Domain Pack、skill 流程和本机数据库,让「质量知识有地方放」。
- **B · Beacon:** 把信号照亮。完善分类、审计、metrics、CI 安全扫描和报告输出,让团队知道风险在哪里。
- **C · Compass:** 建立方向感。把 conformance 矩阵、规格来源、requirement 抽取和覆盖缺口变成日常工程导航。
- **D · Dawn:** 第一个真正可重复的门禁日出。GitHub App / Action / reporter 进入稳定集成,从影子安全走向可选择阻断。
- **E · Echo:** 让系统听见历史。逃逸、review findings、gate run 和运行时信号互相回声,形成复盘与再训练材料。
- **F · Frontier:** 推到多 repo 边疆。跨 repo 契约、不变量分发、被纳管 repo 接入模板和最小配置体验成熟。

### Era II: Expansion / 扩展期(G-M)

目标是让 Marshal 从「一个领域包的质量门禁」扩展为「多领域、多团队的质量工程平台」。

- **G · Grove:** 培育领域包生态。Domain Pack 契约稳定,出现第二、第三个领域包,验证核心真正领域无关。
- **H · Horizon:** 打开组织视野。团队、repo、domain_pack、owner、risk tier 的横向看板成形。
- **I · Iris:** 提升观察精度。更细粒度的 diff 语义、spec drift、运行时异常和 reviewer lens 聚合进入同一视图。
- **J · Juniper:** 强化可维护性。领域包模板、测试夹具、conformance fixtures 和本地开发工具链标准化。
- **K · Keystone:** 形成关键拱石。知识核 schema、内部契约、API adapter 和 reporter protocol 进入兼容性治理。
- **L · Lighthouse:** 对外提供导航。为被纳管项目、平台维护者、reviewer、架构师提供分角色入口和告警策略。
- **M · Meridian:** 建立组织质量经线。跨团队的质量指标、例外治理、waiver 生命周期和审计留痕成为常态。

### Era III: Intelligence / 智能期(N-S)

目标是让 AI 从「辅助 review」变成「受约束的质量工程代理」,但始终受不变量和审计约束。

- **N · Nexus:** 串联上下文网络。PR、issue、spec、test、runtime event、postmortem 和 release 之间形成可查询图谱。
- **O · Odyssey:** 支持长程修复任务。agent 不只指出问题,还能提出补丁计划、生成检查、更新文档并接受门禁裁决。
- **P · Polaris:** 建立北极星指标。把缺陷逃逸率、检测延迟、conformance 覆盖、review 有效率汇总为决策指标。
- **Q · Quartz:** 让质量证据可切片、可复核。每个 gate verdict 都能追溯到可重放证据、版本、输入和裁决规则。
- **R · Radiant:** 让高价值信号发光。自动发现重复缺陷模式、薄弱规格区域和高收益不变量候选。
- **S · Summit:** 到达治理高地。质量策略、风险预算、阻断规则和例外审批进入组织级协同。

### Era IV: Operating System / 操作系统期(T-Z)

目标是让 Marshal 成为软件组织的质量工程操作系统:不是单个 gate,而是持续感知、决策、执行和学习的基础设施。

- **T · Terra:** 扎根真实运行环境。生产遥测、事故复盘和运行时防线反向驱动测试与规格。
- **U · Umbra:** 处理阴影区域。覆盖安全边界、供应链、权限、灰度、数据一致性等传统 review 难以看清的风险。
- **V · Voyager:** 跨越组织边界。支持多 forge、多语言、多 runtime 和外部合作项目的质量协议。
- **W · Waypoint:** 为复杂迁移设路标。大规模重构、协议升级、架构迁移可以被分解为可验证 waypoint。
- **X · Xenon:** 进入高可靠模式。关键系统使用更强隔离、形式化规格、仿真、属性测试和证明辅助。
- **Y · Yonder:** 探索未知质量形态。面向 AI 生成系统、自治 agent、动态策略代码和非传统软件资产。
- **Z · Zenith:** 达到长期愿景。Marshal 成为组织质量记忆、验证执行、治理裁决和持续学习的统一平台。

---

## 2. 代号总表

| 字母 | 代号 | 主题 |
|---|---|---|
| A | Atlas | 承载质量知识与平台骨架 |
| B | Beacon | 暴露风险信号 |
| C | Compass | 建立规格与覆盖导航 |
| D | Dawn | 稳定合并前门禁 |
| E | Echo | 让历史反馈进入系统 |
| F | Frontier | 推进多 repo 接入 |
| G | Grove | 培育领域包生态 |
| H | Horizon | 形成组织级视野 |
| I | Iris | 提升观察精度 |
| J | Juniper | 标准化领域包维护 |
| K | Keystone | 固化核心契约 |
| L | Lighthouse | 提供分角色导航 |
| M | Meridian | 建立质量治理经线 |
| N | Nexus | 串联上下文图谱 |
| O | Odyssey | 支持长程 agent 修复 |
| P | Polaris | 建立北极星指标 |
| Q | Quartz | 固化可复核证据 |
| R | Radiant | 放大高价值信号 |
| S | Summit | 进入组织级治理 |
| T | Terra | 扎根运行时现实 |
| U | Umbra | 覆盖阴影风险 |
| V | Voyager | 跨越组织与平台边界 |
| W | Waypoint | 支持复杂迁移验证 |
| X | Xenon | 面向高可靠系统 |
| Y | Yonder | 探索新型软件质量 |
| Z | Zenith | 统一质量工程操作系统 |

---

## 3. 非目标

- 这不是排期表,不绑定具体发布日期。
- 这不是承诺每个版本只能做一个主题。
- 这不是功能堆砌清单;每个阶段都必须能回到质量工程闭环。
- 这不是让 AI 独断质量裁决。Marshal 的长期方向是可审计的自动化,不是不可解释的自动化。

---

## 4. 当前版本的落点

以当前仓库状态看,Marshal 仍处在 **A · Atlas** 向 **B · Beacon** 过渡的早期:

- 已有薄 CLI、知识核、Cowboy Domain Pack、skill 流程和默认 SQLite。
- 已有分类、不变量选择、review 聚合、conformance、ratchet、metrics 等基础命令。
- 已有 GitHub composite action 和 reporter 雏形。
- 下一步重点应是把信号质量、报告可读性、CI 安全扫描降级语义和日常接入体验打磨稳定。

如果 Atlas 的核心问题是「能不能承载」,Beacon 的核心问题就是「信号是否清楚、可信、可行动」。

# 第二个主动项目包路线决定

日期：2026-08-24

## 决定

- 结论：选择 `openstack/requirements` 的 Alembic 变化作为第二个主动项目包主线；覆盖重审后的闭集为 Cinder、Heat、Ironic、Keystone、Nova、Placement。
- 行动：受控 A0、A1、A2、六仓 A3 和三次正式重复已经完成；第三个 SLF4J 项目包也已完成三次正式重复。
- 当前阶段：五个已执行包的模型语义质检已经完成，只接受 Alembic、SnakeYAML 两个完整四臂候选；第二位人工盲复核仍未完成。扩展改为一个项目包一个并发任务；Checkstyle 已收口为 A3 拒绝的四仓三臂候选，Mockito 收口为两个单正例锚点，Logback 降为单正例锚点，Spring Core 完整筛选后接受数为零。request 到 PolyClay 已被真实重放拒绝；Ironic Python Agent 到 Requirements、Babel ES2015 Preset 到 Rollup Preset、Imagemin Optipng 到 Images to Less Variables 各形成 1 条高证据三臂锚点，React Redux 到 React Redux Provide 形成 1 条单正例四臂锚点。当前三路并行核对 ESLint、共享目标 backbone-mongo 关系族和 Socket.IO。

## 决定依据

这个项目包补上 jcabi 不具备的两个维度：Python 构建生态和数据库迁移/模型同步契约。历史执行已经提供：

- Alembic 1.18.5 到 1.19.1 后，固定 Cinder 提交只有 `test_models_sync` 失败；
- 加入 Cinder 的精确过滤修复后，同一任务恢复；
- 同轮全部成功跨项目任务中，Heat、Ironic、Keystone、Nova、Placement 都安装 Alembic 1.19.1，并实际执行 MySQL `test_models_sync` 后通过；
- requirements 补丁集 1 与 2 的 Git 树相同，避免把源代码变化混入恢复臂。

本地准备试验进一步固定 Cinder、完整约束、MariaDB 和测试命令，得到 A0 通过、A1 同签名失败、A2 只加维护者修复后恢复。Glance 和 Neutron 的历史任务虽然绿色，但没有执行同一模型同步表面，已从闭集移除。

这些证据已记录在：

- `results/requirements-cinder-project-package-screening-2026-08-24.json`
- `results/ci-contrast-2026-08-22.jsonl`
- `results/cinder-source-patchset-comparison-2026-08-23.json`
- `results/requirements-cinder-active-pilot-2026-08-24/summary.json`
- `results/requirements-alembic-model-sync-coverage-audit-2026-08-24.json`
- `ACTIVE_PROJECT_PACKAGE_ASSESSMENT.md`

它已完成主动执行：三轮共 90 条仓库命令，方向、版本和目标测试执行均为 90/90；三次 Cinder A1 都以相同检查约束签名失败，A2 只应用维护者修复后恢复，五个干扰仓和 A3 两臂稳定通过。模型质检按 MySQL 模型同步合同接受，第二位人工盲复核完成前仍不接受为正式标签。

## 未选择的路线

| 路线 | 当前不选的原因 | 后续条件 |
|---|---|---|
| 继续加入 `jcabi-ssh`、`jcabi-github` | 仍是同一 Java/Maven 生态和同一源仓关系，增加任务数但不增加独立项目包 | 作为 jcabi 闭集扩展另行评估，不挤掉第二生态 |
| OpenStack SDK 到 Python OpenStack Client | 17 仓时点输入中只有 `python-openstackclient` 直接消费该资源；`neutron` 与 `neutron-lib` 是上游提供方，其余仓没有相关消费证据 | 保留单正例锚点；出现新的真实同表面消费仓后再重开主动筛选 |
| escope 到 babel-eslint | 非 Maven，单次定向 A0/A1/A2 已成立；A3 和干扰仓筛选未找到满足同一基准合同的可靠负空间 | 降为三臂锚点，待隔离重复和独立语义复核，不制造第四臂 |
| window-stream 到 Godot | 非 Maven，21 项原生合同上的单次 A0/A1/A2 和 A3 均成立，但只有一个目标仓，A3 对深层克隆语义也只有路径覆盖 | 保留单正例四臂锚点；先找同一 TimeWindow 表面的真实消费者，找不到时不扩成项目包 |
| test-machinepack 到 test-machinepack-mocha | 论文给出目标修复线索，但 2.1.19 的失败由源仓 2.1.22 自行恢复；目标改动既不恢复 2.1.19，也不在真实客户端测试路径上 | 语义拒绝，保留为来源标签审计记录 |
| terser 四仓项目包候选 | 四仓统一到 4.3.0 后完成三次隔离重复，51 条命令方向与版本 51/51；三个目标修复和一个 Angular CLI 合同范围内限定负例均可重复 | 破坏案例保留；A3 因无变化表面证据拒绝，Preconstruct 降为子测试证据，不计完整项目包 |
| SLF4J 或 Jackson 的 BUMP 分组 | SLF4J 已执行四仓五配置，但 RabbitMQ 负标签撤销；Jackson 已形成单正例、两个限定负例和四仓 A3 | SLF4J 补第四个已判定仓；Jackson 保留单正例四臂锚点，不因缺第二正例强升 |
| Plexus Utils 的 BUMP 分组 | pgpverify 与 license 的 A0/A1/A2 已成立，plexus-io 与 build-helper 也形成两个限定负例；但当前相邻兼容发布的真实变化没有被四仓原生检查共同触及 | 保留三臂候选；只有出现合格 A3 后才做三次重复，不用普通绿色构建补第四臂 |
| SnakeYAML 的 BUMP 分组 | JClouds 与 ZIO JSON 的破坏恢复、YAML JSON 与 YAML Updater 的限定负例、四仓共同命中 1.32 新增判断的 A3 均已完成三次隔离重复；60 条命令版本与方向 60/60 | 模型质检按当前命令合同接受；等待第二位人工盲复核，Polyglot 保持淘汰 |
| Crater 重放 | 提供 Rust 工具链到包的三臂证据，但不是一个源仓影响多个相邻仓的闭集 | 保持为版本化生态子轨，不改写成仓库级项目包 |
| 立即进行 Marshal 或竞品主表 | 当前只有两个完整四臂候选通过模型质检，正式人工接受数为 0，也尚未完成关系隔离划分 | 扩展、人工复核并形成开发、正式和保留用途后再进入正式比较 |

独立盲复核仍必须进行，但当前没有第二位人工复核者；同一执行者再次阅读不能代替它。这个外部条件不会阻止第二项目包的可逆准备工作。

## 最小准备动作

1. 从固定提交恢复 requirements 1.18.5 与 1.19.1 两个约束输入，以及 Cinder 修复前后的代码差异。
2. 从 Zuul 单元报告和任务日志核对同轮全部成功跨项目任务，闭集只保留实际运行 MySQL 模型同步测试的仓库。
3. 在 Cinder 上试运行受控 A0 与 A1，确认同一失败签名后再运行 A2。
4. A2 只应用历史 Cinder 修复，不带入其他代码；这三项已经完成并留存日志。
5. A3 选择 Alembic 1.17.2 到 1.18.0，六仓单次筛选已经通过；完整日志、版本证据和环境失败处置见 `results/requirements-alembic-a3-screening-corrected-2026-08-24/`。

## 停止或降级条件

- 若 Cinder 的定向重放需要不可恢复的私有服务或历史镜像，保留为历史锚点，不用替代测试凑主动证据；
- 若干扰仓只能证明“安装了 Alembic”而没有相关路径覆盖，不给限定负标签；Glance 和 Neutron 已因此移出闭集；
- 若 A3 的通过来自未触及变化表面，继续搜索或将本包标为缺 A3，不把普通绿色构建写成兼容证据；
- 若准备成本显著超过 jcabi 实测且无法收窄，先记录成本与失败原因，再转向具备原生容器的候选包。

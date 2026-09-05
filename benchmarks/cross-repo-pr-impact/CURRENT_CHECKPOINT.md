# Candidate-bounded implementation checkpoint

日期：2026-08-30

## Current route

- 路线：candidate-bounded 跨仓排序。
- 当前阶段：新采集的 50 条均已由单条构造流水线验证为 `case_ready_for_formal_pool`，并完成集合级独立复验、30/10/10 分组 split 和冻结后系统运行；它是 strict-E2 pilot/release candidate，不是已经通过发布门槛的 formal benchmark。
- 判断：`results/formal-e2-50-release-2026-08-26/` 的正式声明已撤回。其 0/1/0 来自后验构造的引用表面检查，不是预先存在的目标仓构建或测试任务，不能满足 TASK_DEFINITION 的 strict-E2 准入。

## Current active node

权威集合是 `results/formal-e2-benchmark-50-v2-2026-08-30/`，权威冻结后系统运行是 `results/formal-e2-benchmark-50-system-run-v3-2026-08-30/`。前者的 `verification.json` 独立重解析全部三臂证据与分组，后者的 `verification.json` 独立重算 50 条分数并检查统一标签揭示边界。2026-08-27 的首个正式集合仍是有效历史证据，但已被本轮全量重建和重跑取代；`results/formal-e2-50-release-2026-08-26/` 仍只保留为 withdrawn diagnostic 历史材料。

专用私有数据仓库是 GitHub 上的 `mathieu0905/cross-repo-breakage-benchmark`。2026-08-30 的 release、冻结运行、skill 和治理文档已同步到其 `main` 分支；截至 2026-09-05，远端为 `ebae01b`。后续增量包含执行器超时进程组回收、固定入口与 evaluator-owned P2P canary 保护、私有候选排除证据、xrepo-e2-0015 独立 bundle replay、xrepo-e2-0020 独立 bundle replay、拒绝重放与通过重放分离计数修复及 139 项测试通过记录。marshal 主仓保留构造源，私有仓作为分发副本；这些增量不改变公开 50 条标签或其冻结 split。

2026-09-05 同步说明：分发仓在初始抽取后继续接收评测器边界与审计记录，当前远端 `main` 为 `ebae01b`。最新增量包括固定 `python -m` 入口的执行面保护、对应的未跟踪模块回归测试、私有候选排除记录、执行器超时进程组回收、Cinder/Nova evaluator-owned P2P canary 保护、xrepo-e2-0015 与 xrepo-e2-0020 的独立三臂重放、拒绝重放与通过重放分离计数修复、139 项完整测试套件通过记录、数据集与 gold 检查重跑记录，以及对 pilot/formal 状态的澄清；这些提交不改变公开 50 条标签或其已冻结 split。公开 holdout、runtime 发布、独立 50/50 重放、PASS_TO_PASS 覆盖、E3 输入完整性、许可证和第三方权利审查仍由分发仓的 readiness verifier 明确阻断，不能把最新 commit 误读为正式发布完成。

## Node history

- 前序：完整四臂项目包扩采与 FSE 家族筛选。
- 已替换：以 30 至 50 个完整项目包作为主要进度指标。
- 当前路线胜出原因：逐条构造流程同时约束目录独立性、opening cutoff、盲推理隔离和真实三臂，避免把后验引用检查误当 strict-E2；E3/A3 不是 E2 准入条件。

## Strongest retained result or blocker

- 可保留的基础设施：两个目录均先于标签审查生成并跨案例复用；OpenStack 目录 216 仓，StarlingX 目录 75 仓。436 条 opening 源事件、纯代码 diff 和候选仓时点解析可继续用于真实目标任务筛选。
- 被撤回的结果：50 条后验引用检查、`formal_release_ready=true`、`formal_release_verified=true` 和 native Marshal 正式零分均不得作为正式结论。
- 正式集合结果：50/50 条均为机器复验的 A0=0、A1!=0、A2=0，50/50 有语义批准、catalog target membership 和 cutoff target snapshot；50 个 `(source_change_family, target)` 唯一关系来自 23 个有向仓对，按 15 个连通组分为 development/evaluation/holdout = 30/10/10，四个分组轴的跨 split 泄漏为 0。
- 冻结后系统运行：50/50 个 blind 容器均为 network none、标签存储挂载数为 0、推理期标签读取数为 0，且全部预测完成时间早于统一标签读取时间；系统实际读取 14,367 个候选仓和 331,351 个文本文件。独立 verifier 重算全部 50 条逐例及聚合分数后通过。
- 正式分数：development 的 MRR/Recall@1/@3/@5 为 0.0722/0/0.1667/0.1667；evaluation 为 0.2333/0.2/0.3/0.3；holdout 为 0.25/0.2/0.3/0.3。系统没有提出可运行检查，因此 runnable check rate 为 0，50 条 execution result 均保持 `not_assessed`；这不改变数据标签本身已经由独立真实三臂 replay 验证的事实。
- 本轮验收加固：blind 可见 manifest 改用包内相对路径并拒绝关系标签泄漏；多 pin opening diff 必须完整记录且 routed pin 与三臂安装版本一致；同一 catalog 只有 `constructed_at` 不同时才允许确定性合并，成员、provenance 或其他定义差异仍整体拒绝。
- 新增结果：OpenTelemetry 与 Rust 目录精确匹配独立来源清单，覆盖 39 条案例；OpenTelemetry 新增 Ruby SDK 的 35 个时点快照均成功解析。
- 私有 intake 复核：修正后的 `formal-opendev-678207 -> openstack/nova@676926` 候选机制合理（openstacksdk 0.34→0.35 的 `strict_proxies` API 行为变化），但历史 Nova 依赖在断网环境中无法物化，未形成 A0/A1/A2 证据，保持 `not_ready`；不得计入 private holdout 或公开集合。详细拒绝记录为 `.work/private-candidate-678207/rejection-nova-676926.json`，并注明该 API 族与公开案例可能存在 family overlap，须由 split 审计决定。
- 2026-09-05 private intake 继续审计：`774917→cliff@774915`、`845268→neutron@844364`、`712976→horizon@712978`、`930947→oslo.db@922976`、`971754→oslo.policy@972155`、`826318→taskflow@825539`、`851500→ironic-inspector@851501`、`932074→neutron@932181`、`934220→horizon@935894`、`830615→horizon@830618`、`849284→python-glanceclient@849285` 与 `699299→glance@698793` 均已定点拒绝：要么 source-only 没有既有消费面的 A1 失败，要么 target 只是前向采用/依赖同步，要么 exact patch 不适用于 cutoff。均未运行 full replay，也未修改公开标签。当前 intake 尚未发现可通过六维 private boundary 的新 strict-E2 关系；private holdout 继续保持 blocker，不为凑数放宽准入。
- 2026-09-05 复验：在主仓项目内临时目录重新运行 `verify_formal_release.py` 与 `verify_frozen_benchmark.py`，分别得到 50/50 strict-E2、15 组、30/10/10 split、cross-split leak 0，以及 50 个断网预测、标签挂载 0、推理期间读标签 0，均 `verified=true`。这只确认公开 pilot 的 gold 与冻结排序边界，不能清除分发仓 readiness 的 8 个正式发布 blocker。
- 单条正式池进度：50 条已完成 opening-cutoff public input、断网且标签未挂载的 blind prediction、真实 `0/1/0` 三臂、失败签名排他检查、维护者补丁施加到 cutoff target、语义批准与 verifier。最后补齐的三条是 Wandertracks vendored basemap parity、OpenStack requirements→Magnum 的 `oslo.policy` `enforce_scope` 移除，以及同一 source opening 对 Octavia 的独立目标修复；三条均保持目标仓原生命令与原难度。`formal-opendev-902133--target-902048` 虽机器为 `0/1/0`，但 A2 删除选中失败测试并使模块由 12 项降为 11 项，按 skill 的 no-test-deletion 规则不进入正式池。
- 新一轮批量筛选：34 条剩余 touched-test 关系中仅两条得到机器 `0/1/0`；其中 `982599→982593` 通过语义验收并已计入，`902133→902048` 因删除选中测试拒绝。其余 27 条方向不符、5 条环境建立失败，均未降级准入。旧 `e2-041` 的维护者补丁不能施加到 opening-cutoff target；旧 `e2-018` 也存在同一问题，均拒绝。
- 批量筛选保持原难度：`921649→922790`、`985636→985682`、`992461→992462`、`933250→934011` 等关系为 0/0/0，`996435→998421` 与 `982599→982593` 为 1/1/1，`997527→999039` 为 0/0/1，均明确拒绝；`981195→981194`、`988466→988463` 的维护者 patch 无法施加到 opening-cutoff target，也明确拒绝。没有把环境失败或 A1 未失败的关系升级为 E2。
- Skill 批量入口：`build_case.py prepare` 可从既有 replay-plan row 和 public artifacts 生成 `approved=false` 的待审 manifests，支持分开放置的 inputs/snapshots/catalogs、OpenDev/GitHub mirror root、exact-commit snapshot archive root 以及 py310/py313/tox3 runner；它不自动批准语义。归档模式逐个校验目录中声明可用的精确提交 tar，并让断网盲 ranker 直接限量读取归档内容而不展开整个大目录；gzip 中已选文件按 tar offset 顺序读取，避免反向 seek 重复解压。若 blind 容器已完整退出、private 尚未揭示但本地 verifier 中止，`resume-after-blind` 会先重新验证 stored public/blind package 再继续 replay。流水线现有 `source_editable`、`requirements_constraint`、`requirements_registration`、`maven_source`、`ant_source_maven_target` 与 `cross_repo_command` adapters；后者已用 Wandertracks 的目标仓原生跨仓 parity 命令端到端验证，固定 side-by-side source/target 布局、每臂真实检查计数，并验证 A2 patch 与维护者原始 diff 完全一致。`build_component_catalog.py` 可只凭 source package 完整分页构造标签无关的可复用候选目录。`requirements_constraint` 可显式记录三臂共同使用的历史构建约束，并同时约束普通依赖与 PEP 517 隔离构建。Maven/Ant adapters 从真实 opening checkout 构建 artifact，执行目标完整 Maven 生命周期并记录测试总数与制品清单。
- D4 smoke：两条案例读取 21 个候选仓、41,265 个文件；宏召回与 MRR 均为 0.667，仅支持管线结论。
- D4 主测量：12 条案例读取 131 个候选仓时点组合、276,013 个文件；代码排序 top-3 的 MRR/Recall@1/Recall@3 为 0.444/0.194/0.431，对照为 0.380/0.111/0.139。
- 已解释的失败：OpenTelemetry 原始 MRR 为 0.167，未超过对照 0.170；大体量 collector 仓反复占据前排。大小惩罚能移除它们，但无法区分 Rust 中本来就正确的大体量核心仓。
- 消融结论：`sqrt(files_read)` 将 OpenTelemetry MRR 提到 0.375，却将 Rust MRR 从 1.0 降到 0.125；单调大小惩罚被排除。
- 数据目标：Ethereum 重建后合格池为 71 条；`data-ready-50.json` 固定 50 条、663 个候选仓时点组合、0 fetch failure。
- 最终验证：71/71 个合格候选、154/154 条目标关系通过本地与实时 GitHub 对照；最终 50 条包含 107 条目标关系，无失败替补、无重复冲突。
- 发布 split：OpenTelemetry 25 条 development、Ethereum 21 条 evaluation、Rust 4 条 holdout；完整项目不跨 split。
- 严格 E2：最终索引 50 条、40 个源变化族、51 个目标仓出现次数；四条缺口重放均为退出方向 `0/1/0`，Terser/Preconstruct 因 A0/A2 仍非零被明确拒绝。
- E2 split 已冻结：按有向关系、源提交族、机制和修复模板合并为 35 组，再按组固定为 30 development、10 evaluation、10 holdout；四个轴的跨 split 泄漏均为 0，分配不读取排名结果或目标频率。
- E2 实际接入：50/50 条均有目录赋值。Maven 生态目录替换 5 条、完整查询 npm 子集替换 2 条旧筛选目录后，5,650 个候选仓时点解析为 4,454 个可用快照、749 个 `not_created_by_cutoff` 与 447 个 `unavailable_at_collection`，无 `fetch_failed`；50/50 源差分通过代码可见性检查。
- 目标快照恢复：`e2-028` 使用 npm 发布源码与 `gitHead`，`e2-030` 使用保留完整历史的 fork；两个已删除目标仓均恢复到截止时点前代码，当前没有已知目标快照缺失。
- 旧 50 条历史审计：其中 16 条恢复或确认了开单时点因果 diff，34 条明确排除；这解释了旧集合为何不能升级，不适用于本次重新采集并逐条通过 opening-cutoff 验证的新 50 条。
- 开发结果：恢复两条目标快照后，旧 50 条开发目录聚合的 Recall@5/宏召回为 0.6400、MRR 0.3527、Recall@1/@3 为 0.2100/0.4000；该聚合不替代新冻结 split 的正式结果。
- 旧集合正式性审计：37 条使用 outcome-conditioned 目录、34 条不满足开单时点，最终只有 1 条旧 holdout 可运行；这些结论只属于旧集合的排除历史，不能覆盖本次新 50 条的正式发布。
- 独立复现增量（2026-09-05）：xrepo-e2-0015（requirements→neutron）在项目内 phase-4 bundle 中完成真实断网、只读容器三臂重放，A0/A1/A2=0/1/0、每臂 1 个检查、neutron-lib 版本 2.13.0/2.14.0/2.14.0，A1 独占 `MismatchError`。独立通过数由 6/50 增至 7/50；bundle 与 runtime 仍未发布，不能据此清除 50/50 复现 blocker。
- 独立复现增量（2026-09-05）：xrepo-e2-0047（requirements→magnum）在 dataset-only bundle 中完成真实断网、只读容器三臂重放，A0/A1/A2=0/1/0、每臂 3 个 stats-policy 检查、oslo.policy 版本 5.1.0/6.0.0/6.0.0，A1 独占 `oslo_config.cfg.NoSuchOptError: no such option enforce_scope in group [oslo_policy]`；A2 仅应用移除过时 `enforce_scope` 的维护者补丁，未删测或跳过。
- 独立复现增量（2026-09-05）：xrepo-e2-0033（requirements/croniter→Heat）在断网、只读容器中每臂运行 43 项 CRON 约束检查，A0/A1/A2=0/1/0，A1 独占 invalid-expression wording mismatch，A2 应用 canonical maintainer patch 恢复；xrepo-e2-0035（requirements/infoblox-client→Designate）每臂运行 27 项检查，A0/A1/A2=0/1/0，A1 独占 `KeyError: 'reason'`，A2 应用维护者 fixture 修复；xrepo-e2-0036（requirements/oslo.limit→Glance）每臂运行 4 项 quota 检查，A0/A1/A2=0/1/0，A1 独占 `fake_limits() missing ... resource_name`，A2 应用维护者 fixture 补丁。三条均通过独立 blind/replay/semantic verifier，未修改公开 labels。
- 分发仓独立 strict-E2 通过数增至 27/50（attempted 28，rejected 1）；bundle 与 runtime 仍未发布，不能据此清除 50/50 复现 blocker。
- 独立复现新增 xrepo-e2-0022（neutron-lib→Neutron，20 项 metering 检查，A0/A1/A2=0/1/0）与 xrepo-e2-0048（oslo.policy→Octavia，1 项 policy 检查，A0/A1/A2=0/1/0）；两条均在断网、只读容器中完成并通过语义审查。
- 剩余边界：主集负标签不完整，不报告 precision、F1、误报率或 specificity。当前 evaluation/holdout 各有 10 条，分数可按 candidate-bounded 正标签找回口径发布，但一次系统运行不支持稳定的跨系统优劣结论。dataset-only 独立复现当前为 27/50（attempted 28，rejected 1），仍非正式 50/50 结果。
- 独立复现新增拒绝记录：xrepo-e2-0044（requirements→Cinder/tooz）A0/A1 曾为 18/16 checks、0/1，但 A2 在精确预构建环境与固定命令下超时且 checks=0；按 strict-E2 边界拒绝，不计入 27/50。分发仓记录为 `2d1294a`，未修改公开标签。
- 独立复现新增拒绝记录：xrepo-e2-0041（requirements→oslo.middleware）在 blind 隔离通过后，A0 的 tox editable build 长时间未完成且 checks=0，A1/A2 未运行；按 strict-E2 边界拒绝，不计入 27/50。分发仓记录为 `58b98fb`，未修改公开标签。
- 2026-09-05 验证：分发仓 `swebench_like/tests` 在项目内临时环境以 `138 passed` 完成；`validate_dataset.py` 与 `verify_gold_retrieval.py` 均 `verified=true` 且无 blockers。该测试结果不改变 readiness verifier 的 8 个正式发布 blocker。
- 独立复现新增通过：xrepo-e2-0040（requirements→Magnum，oslo.concurrency 7.2.0→7.3.0）在断网、只读容器中完成 A0/A1/A2=0/1/0，固定测试命令运行并通过语义审查；分发仓记录为 `28c5a09`，独立通过数由 25/50 增至 26/50，公开标签未改。
- 独立复现新增拒绝：xrepo-e2-0021（requirements→Neutron）盲测边界通过，但三臂固定 MySQL 检查均在 setUp 报 backend unavailable（A0/A1/A2 全部退出 1），未形成 0/1/0；分发仓记录为 `634e883`，尝试计数 27、通过 26，未修改公开标签。
- 独立复现新增通过：xrepo-e2-0020（requirements→Heat，python-barbicanclient 5.4.0→5.5.0）在断网、只读容器中完成固定 9 项检查，A0/A1/A2=0/1/0；A1 为服务版本发现失败，A2 仅应用维护者 mock 修复。分发仓记录为 `389b597`、`e4fc654`，独立通过数由 26/50 增至 27/50，公开标签未改。

## Do not reopen by default

- 不恢复“先凑 30 至 50 个完整四臂项目包”的路线。
- 不为了补 A3、限定负空间或更多 FSE 家族挤占目录重建。
- 不按结果目录名、`executed` 或 `ci_contrast_proven` 字样批量升级 E2-E4。
- 不把单例目录试运行报告为 development 泛化分数。

## Next resume step

正式 benchmark 仍未完成。当前 readiness verifier 仍报告 8 个 blocker：公开标签无法 retroactively 变成 private、runtime bundle 尚未发布、独立 50/50 重放未完成（当前 27/50，attempted 28、rejected 1）、PASS_TO_PASS 仅 20/50、E3 输入面不完整、许可证未选定以及第三方权利尚无人清权。下一步只能从精确 private intake 继续寻找通过六维公开边界的全新 source event；候选不足时保持 blocker，不得把 rejected 或重叠案例包装成 holdout。若维护或替换案例，继续用 `.agents/skills/marshal-e2-case-builder/` 跑完整单条流程，再重新生成全量 release 和 split，并在抽取布局复验后整体同步；不得局部手改权威索引。

## First-read files

1. `CURRENT_CHECKPOINT.md`
2. `results/formal-e2-benchmark-50-v2-2026-08-30/README.md`
3. `results/formal-e2-benchmark-50-v2-2026-08-30/ACCEPTANCE.md`
4. `results/formal-e2-benchmark-50-v2-2026-08-30/verification.json`
5. `results/formal-e2-benchmark-50-v2-2026-08-30/final-index.jsonl`
6. `results/formal-e2-benchmark-50-system-run-v3-2026-08-30/verification.json`
7. `results/formal-e2-benchmark-50-system-run-v3-2026-08-30/metrics.json`
8. `.agents/skills/marshal-e2-case-builder/SKILL.md`
9. `TASK_DEFINITION.md`

## Reopen condition

若继续研究 ranker，先在 development 上独立规定规则，再一次性评估 evaluation/holdout。50 条 E2 的构造、诊断性集合复验与首次冻结后系统运行已闭环；正式发布仍受 readiness verifier 的 blind、runtime、复现、许可和权利阻断，E2 扩采、开放世界发现和四臂扩采不默认重开。

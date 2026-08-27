# 单条 strict-E2 工作流

## 阶段与产物

1. Public intake
   - 选择 source opening revision、观察截止时间和 label-independent catalog。
   - 物化纯 `diff --git` 代码补丁、单条 input、单条 cutoff snapshot。
   - 检查 catalog provenance、目标之外至少一个可用候选、所有可用 snapshot commit 都有本地 mirror。
2. Isolated blind prediction
   - Docker 只挂载 runner、public input、patch、snapshot 和 Git mirrors。
   - 使用 `--network none --read-only --cap-drop ALL --security-opt no-new-privileges`。
   - prediction、diagnostics 和 isolation evidence 落盘后容器退出。
3. Label reveal and replay
   - 此时才读取 private manifest。
   - A0/A1 使用 public input 中的目标仓 cutoff commit，A2 将维护者补丁应用到同一 commit；不能直接用与输入不一致的 Gerrit patchset base。
   - 三臂使用同一个固定依赖环境。依赖环境属于重放证据，不替换或改写 blind cutoff candidate code。
   - 保留三臂命令、stdout/stderr、退出码和失败签名。
   - 失败签名从 stestr 的 failed-test section 提取，并规范化运行时内存地址与 UUID；不得让随机 request id 伪装成排他签名。
   - `requirements_constraint` 只接受单 pin source diff；三臂使用独立环境并记录实际安装版本，防止依赖状态串臂。
4. Semantic adjudication
   - 阅读 source diff、target diff、A1 failure、A2 recovery 和测试命令 provenance。
   - `semantic_review.approved=true` 必须有具体机制说明，不能由方向判据自动生成。
5. Scoring and packaging
   - 将 blind candidate id 映射为 relation case id，但不得更改预测仓顺序或路径。
   - 计算目标仓 recall/MRR/Recall@K、检查位置找回、可运行检查率和 failure/recovery 判断。
   - 生成 `case-report.json`；单条最多到 `case_ready_for_formal_pool`。

## 失败处理

- Public input 或 catalog 不合格：停止在 public intake，不读 private manifest。
- Blind 容器失败：保存日志，不揭示标签。
- A0/A1/A2 不满足：写 rejection，状态为 rejected；不能改测试命令重试直到命中。只有明确的环境恢复可以重跑同一命令。
- 语义不对应、删测试或跳过测试：拒绝，即使机器方向为 0/非0/0。
- 输出目录已存在：默认停止。恢复或复核使用 `verify`；需要重跑时使用新的输出目录，保留旧证据。

## 首条样板

仓库内首条样板为 `formal-opendev-937605--target-937668`：源变化改变
`VlanTransparencyDriverError` 的父类，Neutron 既有测试在 A1 观察到 HTTP 500 而非 400，
维护者目标修改接受该新行为。它使用 OpenStack global-requirements catalog，blind 排序在揭示
目标前完成。

第二种已验证样板为 `formal-opendev-995651--target-995691`：
`openstack/requirements` 只把 tooz 8.1.0 pin 更新到 9.0.0，Cinder 截止时点
既有 coordination 模块在 A1 触发锁方法签名错误，维护者目标补丁扩展测试替身
签名后恢复。它验证了 `requirements_constraint` adapter。

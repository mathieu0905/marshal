# Project-level Domain Pack E2 data layer

本目录把 Domain Pack 作为跨仓兼容性数据集本身的一部分，不依赖 Marshal 的 tier、
contract、executor、verdict 或 reporter。当前实现面向 `openstack/requirements` 的 Python
依赖目录和约束变化。

## 数据对象

```text
projects.txt @ source opening
  -> 公开候选仓全集（非答案）
candidate snapshots @ source opening
  -> 依赖声明、直接 import、既有 test module、cutoff-time 命令模板
  -> Domain Pack revision

source patch + Domain Pack revision
  -> 公开候选 route/repository/check
  -> 默认全部 unjudged

真实维护者关系 + 同一命令 A0/A1/A2 证据
  -> curator-side judged E2 binding
```

`pack_family_id` 标识可跨事件和 cutoff 复用的规则族，`pack_revision_id` 标识一个观察时点
的物化版本。`domain-pack.schema.json` 定义项目级候选目录、来源、路由和检查；
`case-record.schema.json` 定义公开候选与 curator-side 严格 E2 关系。

额外候选不是负例。单条真实 E2 关系只给对应 binding 标注 A0 通过、A1 失败、A2 恢复；
同一个 Pack 中没有重放的仓库和检查保持 `unjudged`，不据此计算 precision、F1、误报率或
specificity。

## Pack 构建输入

OpenStack requirements 的候选仓全集来自 source-opening commit 的 `projects.txt`，而不是
已知目标、手写 distractor、治理仓当前状态或 Zuul job 交集。snapshot manifest 为全集逐仓
记录观察时点状态；没有快照的成员仍保留，不会被当作负例。

```json
{
  "pack_family_id": "openstack-requirements-python-consumers",
  "pack_revision_id": "openstack-requirements-python-consumers@2025-01-06T162701Z",
  "project": "openstack",
  "authoring_case_ids": [],
  "source": {
    "repository": "openstack/requirements",
    "git_dir": "mirrors/openstack__requirements.git",
    "commit": "SOURCE_OPENING_BASE_COMMIT",
    "projects_path": "projects.txt",
    "constraints_paths": ["global-requirements.txt", "upper-constraints.txt"]
  },
  "snapshot_manifest": {
    "manifest_id": "openstack-project-cutoff-2025-01-06",
    "path": "snapshot-manifest.json",
    "format": "project-snapshots-json"
  }
}
```

manifest 中 `status=available` 只表示观察时点快照存在；只有显式 `materialize=true` 且提供
`git_dir` 时才扫描代码。这样可以先做有限开发样例，同时完整保存 source-opening
`projects.txt` 项目目录。任何
部分物化或使用已知 case 辅助 authoring 的 revision 都会自动标为 `development_only`。

```bash
python benchmarks/domain-pack-e2/build_openstack_requirements_pack.py \
  --spec /path/to/build-spec.json \
  --output /path/to/domain-pack.json
```

### Public-only source-opening 物化

`materialize_public_requirements_pack.py` 直接接收
`collect_public_requirements_sources.py` 生成的单条公开行
`{schema_version, source_change_id, discovery, opening}` 和本地公共 Git mirrors。
`source_change_id` 必须为与 `opening.number` 一致的 `formal-opendev-N`；兼容输入若同时提供
`candidate_id`，两者必须相同。入口保留不含 target 的公开 `discovery`，并只从 opening
元数据读取 base/head、`created_at` 和 changed paths。opening 必须修改
`global-requirements.txt` 或 `upper-constraints.txt`；两者同改时会同时进入 source
snapshot，其他 changed path 只保留在 opening patch 中，不参与依赖 route 派生。候选全集固定读取 base commit 的
`projects.txt`；每个成员都按 opening `created_at` 解析默认分支 first-parent cutoff commit，
无法解析的成员保留 `not_assessed`，不会从 manifest 中删除。

```bash
python benchmarks/domain-pack-e2/materialize_public_requirements_pack.py \
  --source-event /path/to/one-public-source-event.json \
  --mirror-root /path/to/candidate-mirrors \
  --output-dir /path/to/new-pack-revision \
  --scan-workers 8
```

输出为 `public-source.json`、`source.patch`、`snapshot-manifest.json`、
`build-spec.json` 和 `domain-pack.json`。入口拒绝 target、private、replay 和 A0/A1/A2
outcome 字段，并调用固定版本 1.4.0 的
`build_openstack_requirements_pack.py`。materializer 会查询公开的
`authoring-influence.json`：参与过规则 authoring 的 source event 自动写入
`authoring_case_ids` 并标记 `development_only`；未参与 authoring 的 event 则只在完整
`projects.txt` universe 未获得可物化或明确终态的 cutoff snapshot 时标记 development。
`constraints_paths` 是为兼容 1.3.3 build spec 保留的输入字段名，在 1.4.0 中可同时承载
`global-requirements.txt` 和 `upper-constraints.txt`，输出 trigger 和 provenance 会记录各路径的
实际 source kind。

## Case 绑定和证据验证

`materialize_case_record.py` 只从 source patch 解析 change facts，再从 Pack 完整派生公开候选，
不读取失败日志、目标修复或隐藏标签。关系重放完成后，curator 才能添加一个
`judged_e2_binding`。

```bash
python benchmarks/domain-pack-e2/materialize_case_record.py \
  --pack /path/to/domain-pack.json \
  --case-spec /path/to/case-spec.json \
  --patch /path/to/source.patch \
  --output /path/to/case-record.json

python benchmarks/domain-pack-e2/verify_case_record.py \
  --pack /path/to/domain-pack.json \
  --case /path/to/case-record.json \
  --package-root /path/to/case-package
```

验证器会重新派生公开候选，并直接读取三个 arm 的 `summary.json`、`command.log` 和目标修复
patch：三臂必须执行 Pack 中同一个 cutoff-time 命令，exit code 必须为 0/非零/0，失败
签名必须只出现在 A1。没有 `--package-root` 时只做结构和引用一致性检查，并明确输出
`artifact_verification: not_requested`。

## 已打通的开发样例

下面的命令从既有真实严格 E2 重放构造一个自包含样例。它保留完整 `projects.txt` 候选
全集，但为了验证流程只扫描已知 Designate target，因此明确属于 development，不得放入
未来盲测 split。

```bash
python benchmarks/domain-pack-e2/prepare_development_seed.py \
  --seed benchmarks/domain-pack-e2/development-seeds/formal-opendev-938500--target-977684.json \
  --output-dir benchmarks/domain-pack-e2/development/formal-opendev-938500--target-977684
```

完整项目物化使用同一构造链和 14 个代理独立补齐的 cutoff snapshot rows：

```bash
python benchmarks/domain-pack-e2/prepare_development_seed.py \
  --seed benchmarks/domain-pack-e2/development-seeds/formal-opendev-938500--target-977684-full-pack.json \
  --output-dir benchmarks/domain-pack-e2/development/formal-opendev-938500--target-977684-full-pack
```

当前实测完整 revision 含 229/229 个已物化候选仓、380 条依赖路由、8,215 个既有 test-module
checks 和 4,037 个 cutoff-time 执行模板，且 relation-level E2 包通过日志解析式验证。每条路由
保存被选 check ID 和按推导类型汇总的计数；完整的静态传播链由同一版本生成器从 cutoff 代码
确定性重建，不在每条 route 中重复序列化。它仍是 development：该已知关系参与过
生成器 authoring；完整物化消除了目录和快照缺口，但不会把看过的案例变成盲测案例。

## 当前覆盖边界

- 只解析 `global-requirements.txt`、`upper-constraints.txt` 和候选仓常见 requirements 文本，
  以及 Python 直接 import、静态 import 传播和 dotted-string
  reference；未解析运行时动态依赖生成或配置插件加载。
- distribution/import 别名只采用候选仓自身 package metadata 与 package root 可唯一确定的映射；
  多义或无法从 cutoff 代码确定的别名不命中。
- 可执行命令模板只从 cutoff `tox.ini` 派生；Zuul 配置仅记录存在性。
- 只为可收集的 `test_*.py`、`*_test.py` 或 `tests.py` 文件生成 test-module check，且必须有
  支持 `{posargs}` 的既有测试命令。
- `available_not_materialized` 成员没有代码派生路由；部分物化 revision 只能用于开发。
- 当前 17 条已审计历史 source event 参与过生成器分析，均只能作为 authoring/development seed；修订
  生成规则后必须用未参与 authoring 的新事件构造 evaluation/holdout。

## 测试

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q \
  benchmarks/domain-pack-e2/test_domain_pack_e2.py \
  benchmarks/domain-pack-e2/test_materialize_public_requirements_pack.py \
  benchmarks/domain-pack-e2/test_collect_public_requirements_sources.py
ruff check benchmarks/domain-pack-e2
```

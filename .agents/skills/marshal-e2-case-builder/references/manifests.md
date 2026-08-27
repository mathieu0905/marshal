# Manifest 字段

路径相对于 Marshal 仓库根目录解析；绝对路径也可使用。

## 从已有 replay plan 生成待审 manifests

当 catalog、opening input、source patch、target patch 和 replay-plan row 已存在时，
使用 `build_case.py prepare` 生成 `public-case.json` 与 `private-label.json`：

```bash
python .agents/skills/marshal-e2-case-builder/scripts/build_case.py prepare \
  --plan <plan.jsonl> \
  --case-id <relation-id> \
  --input-dir <input-index-directory> \
  --source-patch-dir <source-patch-directory> \
  --target-patch-dir <target-patch-directory> \
  --output-dir <case-build-directory> \
  --runner py310
```

若旧采集批次把三类 public artifact 分开放置，可用 `--inputs`、`--snapshots`
和 `--catalogs` 覆盖 `--input-dir` 下的默认文件位置。
GitHub 生态使用独立 mirror 集时，通过 `--mirror-root` 指向该目录。

生成结果恒为 `semantic_review.approved=false`，不会用 plan subject 代替语义审查。
只有历史约束集要求 Python 3.11 以上时才使用 `--runner py313`。生成 manifest
仍只是筛选输入，必须继续完成真实三臂回放和不删测试、不跳过测试的语义验收。

## Public manifest

```json
{
  "schema_version": "1.0",
  "candidate_id": "formal-opendev-937605",
  "inputs": ".../inputs.jsonl",
  "snapshots": ".../repository-snapshots.jsonl",
  "catalogs": ".../candidate-repositories.json",
  "patch_dir": ".../source-patches",
  "mirror_root": ".../candidate-mirrors",
  "blind": {
    "container_image": "python:3.10",
    "top_k": 5,
    "workers": 8
  }
}
```

当大目录已经由输入物化阶段保存为逐仓逐提交的 GitHub/托管平台源码包时，
可用 `snapshot_archive_root` 替代 `mirror_root`。布局必须为
`<root>/<owner>__<repo>/<snapshot commit>.tar.gz`，且 public snapshot 对每个
catalog member 都有状态行。流水线直接使用这些预审计的 cutoff commit 行，逐个
确认所有 `available` 源码包可读，并在断网 blind 容器中读取包内代码；不能用单一
latest archive、缺仓目录或只含已知目标的目录替代。

Public manifest 及其所有引用都必须不含目标仓、目标 change、A1 签名、A2 位置或 replay 计划。
默认分支 cutoff 解析沿 first-parent 历史选择 opening 时点已进入分支的最新提交；不能
因某个 review commit 的作者/提交时间早于 cutoff、但实际在 cutoff 后才通过 merge
commit 进入默认分支，就把该未来 review 内容物化进候选快照。

## Private manifest

```json
{
  "schema_version": "1.0",
  "candidate_id": "formal-opendev-937605",
  "relation_id": "formal-opendev-937605--target-937668",
  "replay_plan": ".../plan.jsonl",
  "target_repository": "openstack/neutron",
  "expected_check_paths": ["neutron/tests/unit/plugins/ml2/test_plugin.py"],
  "source_change_family": "opendev-change-937605-opening",
  "mechanism": "exception parent change alters HTTP status mapping",
  "repair_template": "update existing target expectation for changed exception mapping",
  "replay_adapter": "source_editable",
  "setuptools_version": "80.9.0",
  "tox": ".../bin/tox",
  "python": ".../bin/python",
  "semantic_review": {
    "approved": true,
    "source_effect": "...",
    "a1_failure": "...",
    "target_repair": "...",
    "target_patch": ".../937668.patch",
    "reviewer_basis": "source diff, target diff, three-arm logs, and command provenance"
  }
}
```

`replay_adapter` 默认为 `source_editable`，适用于目标测试直接消费源仓的
Python 包。若 source event 是 `openstack/requirements` 中恰好一个
`upper-constraints.txt` pin 的变化，使用 `requirements_constraint`。该 adapter
为三臂分别创建 tox 环境，探测实际安装版本，并要求 A0 使用 opening base pin、
A1/A2 使用 opening head pin；不能把 constraints 仓本身 editable-install 后宣称依赖已切换。

若目标仓既有测试需要本地服务连接，可在 private manifest 的
`replay_environment` 中记录传给三臂测试进程的字符串环境变量。该字段不能改变
命令、代码或依赖版本，只能提供三臂共同使用的本地测试服务配置；正式证据记录
变量名，且三臂仍必须使用同一环境映射。

历史截止快照若因构建隔离解析到与当时源码不兼容的新构建工具，可在
`requirements_constraint` 的 private manifest 用 `bootstrap_constraints` 记录
三臂共同使用的额外构建约束。例如 PyYAML 5.4.1 在 Cython 3 下无法生成 wheel 时，
可记录 `["Cython<3"]`。它只能修复三臂相同的环境搭建，不能改变 source pin、目标
代码、测试命令或三臂判据；contract 会保留实际使用的约束。
adapter 同时向普通依赖解析和 PEP 517 隔离构建传递这份约束，以覆盖新版本 pip
已将 `PIP_CONSTRAINT` 与 build constraint 分离的行为。

若历史目标仓的原生扩展依赖 opening 时点 CI 已安装、但当前机器缺少的编译头文件或
库，可在 private manifest 的 `setup_environment` 中记录三臂共同使用的字符串环境
变量。值里的 `{repository_root}` 会在执行时展开为当前仓库绝对路径，例如为本地提取
的系统开发包设置 `CFLAGS`、`LIBRARY_PATH` 和 `LD_LIBRARY_PATH`。该字段传给三臂
环境搭建及随后同一环境中的测试进程，不能改变 source pin、目标代码、测试命令或
判据；contract 记录变量名。
`requirements_constraint` 会优先沿用 opening base/head 共同记录的历史 setuptools
pin；只有该全局约束没有 setuptools 且本条 source 变化也不是 setuptools 时，才用
默认构建版本。tox 创建隔离环境时也会用这个共同历史 pin 作为 setuptools seed，
这样不会把当前构建工具版本混入历史三臂依赖集合。

若历史 `tox.ini` 使用 tox 3 语法而 tox 4 无法解析，`prepare --runner tox3` 可选择
仓库内固定的 tox 3 runner；若 2021 年依赖约束中的 C 扩展不支持 Python 3.10，
可用 `prepare --runner tox3-py38` 选择同样固定的 Python 3.8/tox 3 runner。runner
选择必须在三臂保持一致，且应优先匹配 opening 时点目标仓声明支持的解释器。
若 opening 的 tox 环境还依赖 virtualenv 20.x 会默认注入 wheel 的行为，可使用
`tox3-py38-2021`；这避免旧式 `setup.py` 数据文件直接写入系统目录，仍不改变目标
仓代码或测试命令。
如果该历史项目的 editable 安装依赖 PEP 660 之前的 pip 行为，可在 private
manifest 用 `virtualenv_pip_version` 显式记录 tox 三臂创建环境时共同使用的 pip
seed 版本。该设置只恢复历史打包工具语义，不能改变测试命令、source pin 或目标
代码；contract 会记录实际请求的版本。

若 opening 时点的 source constraints 没有在 `upper-constraints.txt` 中固定
setuptools、但其同一 source base 的构建契约明确要求旧版本，可在 private manifest
用 `virtualenv_setuptools_version` 记录三臂共同使用的 setuptools seed。adapter 会
同时把它写入构建约束，避免 tox seed 与 pip 解析得到两个不同版本；该设置不能改变
测试命令、source pin 或目标代码，contract 会记录实际版本。

`source_editable` 默认使用 `setuptools==75.6.0` 构建目标仓。若截止快照的
`pyproject.toml` 需要其他已发布版本，可在 private manifest 用
`setuptools_version` 显式记录构建后端版本；这只解决项目打包兼容性，不能改变
测试选择、三臂代码或退出码判据。

若 source opening 给普通项目新增依赖，而目标是 `openstack/requirements` 的
既有 `project-requirements-change.py` 检查，使用 `requirements_registration`。
该 adapter 用 opening base/head 的真实 source checkout 和同一 target cutoff
分别运行检查，并只在 A2 向 cutoff target 应用维护者登记补丁；A0/A1/A2 的
逻辑命令保持一致，不能用文本查找替代该检查脚本的实际退出码。

Java/Maven source opening 使用 `maven_source`。该 adapter 从 base/head opening
checkout 构建本地 Maven artifact，按 cutoff target 声明的坐标分别供三臂消费，
并要求 A2 仍是同一 head 内容加维护者 target patch。private manifest 需记录
`maven`、`java_home` 与只作依赖下载缓存的 `maven_seed_repository`；缓存不能提供
source artifact，也不能替代三臂真实 Maven 命令。若 opening source 与 cutoff
target 声明不同的历史 JDK 范围，可另记 `source_java_home`、`target_java_home`；未指定
的一侧继续使用 `java_home`，三臂目标命令仍使用同一 target toolchain。非 AssertJ 项目在 replay plan
显式记录 `source_group_id`、`source_artifact_id` 和排他的
`failure_signature`；source POM 不在仓库根目录时记录 `source_pom_path`，目标用
父 POM property 管理版本时再记录 `target_version_property`（必要时同时记录
`target_dependency_pom_path`）。`test_command` 必须以 `mvn` 或目标仓已有的 `./mvnw`
开头，adapter 会原样保留其 lifecycle、模块和测试选择，并要求 A0/A2 至少实际运行
一个未跳过测试；使用 wrapper 时三臂执行各自 cutoff checkout 中同一个 `mvnw`，
不会换成宿主 Maven。
若目标仓的既有检查根据 Git 最后修改年份计算许可证头，可在 replay plan 设
`commit_target_patch_with_maintainer_metadata=true`；adapter 只把已经通过
`git apply --check` 的维护者 patch 暂存为本地 replay commit，并复用真实维护者
commit 的作者、提交者、日期和消息。它不会跳过许可证检查，也不会引入原提交中
未包含在 patch evidence 的其他文件。

若 Java source 由 Ant 产出一个或多个供 Maven target 消费的 JAR，使用
`ant_source_maven_target`。private manifest 必须记录 `maven`、
`maven_seed_repository`、`source_java_home`、`target_java_home`、`ant`、`junit`
以及三臂共同使用的 `replay_environment`；历史 JVM 在当前 CPU 上需要兼容选项时，
只能在这里给三臂和两次 source build 设置同一变量。replay plan 用
`source_build_targets` 记录原生 Ant targets，用 `source_artifacts` 逐项记录
`artifact_id`、构建后的 `jar_path`、安装用 `pom_template`，并可通过
`a0_required_entries`、`a0_forbidden_entries`、`a1_required_entries`、
`a1_forbidden_entries` 断言类在 JAR 间的真实移动。adapter 必须从 base/head checkout
重新构建，不得复用 pilot JAR；A0/A1/A2 仍执行完全相同的 Maven target command，
verifier 会重新解析退出码、成功测试数、排他签名和制品清单断言。

若目标仓在 opening cutoff 已有一条直接读取相邻 source checkout 的原生命令，使用
`cross_repo_command`。三臂目录都采用相同的 `target/` 与 `source/` 相邻布局，plan
中的 `test_command` 必须是以 `python` 或 `python3` 开头的固定参数列表，不能按 arm
改写；用 `../source/...` 指向 opening source。plan 还必须提供 `check_count_regex`，
让 adapter 从每一臂的原生命令输出中解析正数检查项，而不是只凭退出码断言执行过。
adapter 会验证维护者 patch 能应用到 cutoff target，并且 patch 字节与
`target_patch_base_commit` 到 `target_head_commit` 的维护者原始 diff 完全相同。
维护者 change 若基于稍早分支点，不要求 cutoff target 加 patch 后等于整个 target
head；A2 仍只能加入该精确维护者 patch，不能混入分支点之间的无关目标提交。
若这条既有命令定义在 source 仓而执行入口位于 target 仓，plan 记录
`command_config_repository="source"` 与 `command_config_path`；adapter 和 verifier
会把该路径绑定到 source opening base。默认值仍是 `target`，并绑定到 target cutoff。
该字段只描述命令出处，不能让三臂改用不同命令。

当共享 catalog 不含目标时，不得把目标仓手工追加。若 source 有生态包坐标，可运行：

```bash
python .agents/skills/marshal-e2-case-builder/scripts/build_component_catalog.py \
  --package <group:artifact> \
  --catalog-id <stable-source-derived-id> \
  --output-dir <new-catalog-directory>
```

该脚本完整分页 source package 的 dependent-package endpoint，只从返回行规范化 GitHub
仓库，写出查询快照和 creation provenance，并声明 `membership_reads_e2_targets=false`。
目录须跨同一 source component 的事件复用；生成目录后仍要独立解析 opening cutoff，
不能因为某个仓是已知目标而覆盖它的快照或可用状态。

Replay plan 可用 `tox_environment` 指定目标仓已有的非默认 tox 环境，并在
`test_command` 中记录该环境原生的完整 `stestr` 命令。例如 functional 测试应
保留目标 `tox.ini` 已有的 `--test-path`，不能用默认 unit discovery 运行后把
“没有匹配测试”当作执行结果。

若目标仓的既有 tox 命令使用 pytest，可在 `test_command` 记录环境内的 `pytest`
命令，或记录 Horizon 风格的 `bash tools/unit_tests.sh . <既有测试路径>`。adapter
会把该臂 tox 环境的 `bin` 放到 `PATH`，三臂仍执行完全相同的记录命令，并解析
pytest 的真实终端测试计数；不允许用自建脚本或新断言代替目标仓已有命令。

回放同时设置历史项目常见的 `UPPER_CONSTRAINTS_FILE` 和
`TOX_CONSTRAINTS_FILE`，两者都指向 cutoff requirements checkout。若只设置其中
一个，使用另一变量名的旧 tox.ini 会回退到网络上的当前 master constraints，
导致三臂不再是截止时点环境。

依赖安装阶段可使用宿主网络代理；直接执行 tox 环境内测试命令时，adapter 会
移除 `http_proxy`、`https_proxy` 与 `all_proxy`，与未在目标 `passenv` 中声明
这些变量的 tox 测试环境一致，避免把宿主代理配置当成三臂结果。

`approved` 不能由构造脚本填写。Agent 必须实际读取所列材料后作判断；无法确认时保持 false。

## 输出

```text
output-dir/
  public/{inputs.jsonl,repository-snapshots.jsonl,candidate-repositories.json,source-patches/}
  blind/{predictions.jsonl,diagnostics.jsonl,run-manifest.json,isolation.json,container.log}
  private/label.json
  replay-work/
  evidence/<relation-id>/...
  prediction-for-score.jsonl
  score.json
  case-report.json
```

`private/` 不会挂载进 blind 容器。`case-report.json` 是单条验收入口；集合发布器只消费
`case_ready_for_formal_pool=true` 的 package，再负责 over-collection 和 group split。
`replay-work/` 是本地构建缓存，由输出目录内的 `.gitignore` 排除；正式 package 只保留 evidence。

集合发布 manifest 是 JSONL，每行只含一个已完成单例的 `output_dir`。它必须显式列出
恰好 50 个权威输出；同一 case 的失败尝试、过时尝试或重复成功尝试不能同时列入。
`release_formal_pool.py` 会把每条 public/blind/private/evidence package 复制到
`cases/<relation-id>/`，并生成集合级 `inputs.jsonl`、`repository-snapshots.jsonl`、
`candidate-repositories.json`、`predictions.jsonl`、`final-index.jsonl`、
`group-manifest.jsonl`、`metrics.json` 与 `verification.json`。

大目录的精确提交归档可先用 `prepare_case_inputs.py --archives-only --archive-cache ...`
并行下载和校验；该模式不展开仓库，也不生成 label 或 target-only 输入，随后由
`snapshot_archive_root` 直接供断网盲 ranker 读取。

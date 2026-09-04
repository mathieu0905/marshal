# 现有单目标生成器审计

审计对象：`benchmarks/marshal-gate-decision/build_python_import_pack.py`。

该脚本证明了“只读约束快照和目标 cutoff 测试源码”可以生成与结果标签独立的规则，但其
输出不能直接作为本目录的项目级数据层：

- 每次调用只接受一个 `target_repo`，没有项目级候选目录，无法证明多个候选仓是按与隐藏
  标签无关的同一规则纳入；
- `pack_id`、`command_prefix` 和测试根由单目标命令行传入，命令本身没有 cutoff CI 文件的
  来源；
- 只连接测试文件中的直接 import，既不记录目标依赖声明，也不保留无直接 import 时的仓级
  既有测试命令；
- 输出是 Marshal 的 `tier -> contracts -> invariants -> executor_kind` 接口，而不是数据集的
  项目目录、消费证据、检查和三臂结果关系；
- 单个 `source_commit` 和 `target_commit` 被写进一个不区分规则族与 cutoff 物化版本的 ID。

本目录因此没有复制该数据形状。新生成器从 source-opening `projects.txt` 读取完整项目目录，
再按项目级 snapshot manifest 物化可用仓库；`pack_family_id` 标识跨 source event/cutoff 复用的规则族，
`pack_revision_id` 标识一次 cutoff 物化。事件 patch、A0/A1/A2 结果和维护者修复不进入 Pack
生成器。

保留的有效思想是：规则只能从 source-opening/cutoff-time Git 对象确定性派生，且不能为了
命中某条已知失败而手工缩小检查集合。

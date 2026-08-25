# 重放说明

本轮没有重复执行 Visenze 三臂。相同输入已由 `workstreams/powermock-visearch/run_screening.sh` 执行并保存完整日志，结果已经排除候选 A2；再次运行不会产生新的标签证据。

需要核对既有执行时，必须使用隔离缓存和临时目录：

```bash
mkdir -p /home/zhihao/hdd/marshal/.work/tmp
TMPDIR=/home/zhihao/hdd/marshal/.work/tmp \
MAVEN_OPTS='-Djava.io.tmpdir=/home/zhihao/hdd/marshal/.work/tmp -Djansi.tmpdir=/home/zhihao/hdd/marshal/.work/tmp -XX:-UsePerfData' \
MARSHAL_TASK_TMP=/home/zhihao/hdd/marshal/.work/powermock-module-junit4-1.6.5-fse/replay \
bash benchmarks/cross-repo-pr-impact/workstreams/powermock-visearch/run_screening.sh \
  benchmarks/cross-repo-pr-impact/results/powermock-visearch-screening-replay
```

历史裁决的核对单位是每个克隆中的全部引用，而不是当前默认分支。对每个根仓执行：

```bash
git for-each-ref --format='%(refname)' | wc -l
git rev-list --all | sort -u | wc -l
git log --all -G'1[.]6[.]5' --format='%H %aI %s' -- \
  '*.xml' '*.gradle' '*.properties'
```

最后一条在八仓中均无输出。它只支持“依赖构建历史没有固定 1.6.5 的声明”，不能推出兼容性负例。

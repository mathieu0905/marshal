# 核对说明

本组在候选历史筛选后停止，没有执行 A0/A1/A2。两个原始仓名折叠为同一个 GitHub 根仓；FSE 没有记录目标修订，全部 1,479 个远程引用又不存在固定 Hazelcast 4.1 的维护者修复。因此没有可执行的精确 A2。

结构化产物可直接核对：

```bash
jq -c . candidate-frame.jsonl
jq -c . root-audit.jsonl
jq . source-evidence.json
git apply --numstat source-mechanism.patch
```

若重新审计历史，镜像和临时文件必须继续放在项目内 `.work/hazelcast-4.1-fse/`。两个目标仓名当前解析到相同的仓库编号和相同历史，历史只需执行一次：

```bash
git for-each-ref --format='%(refname)' | wc -l
git rev-list --all | sort -u | wc -l
git log --all -G'<hazelcast.version>4[.]1</hazelcast.version>' \
  --format='%H %aI %s' -- '*.xml' '*.gradle' '*.properties'
git log --all -G'DEFAULT_MINOR_VERSION = 1;' \
  --format='%H %aI %s' -- '*BuildInfoUtils.java'
```

不能把 `5eacaaed1c525daeada8f0d737739d7c2e249823` 当作 A2。该补丁把 Hazelcast 5 驱动的默认 major 从 4 改为 5，没有修复 4.1 的 minor 失败。

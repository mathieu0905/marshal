# 核对说明

本组故意没有执行 A0/A1/A2。固定 Jackson 2.10.0 的维护者 A2 在两个根仓中均不存在：openrest4j 从未声明 2.10.0；json-rules 唯一的 2.10.0 是没有后继提交的未合并 Dependabot PR。

结构化产物可直接核对：

```bash
jq -c . candidate-frame.jsonl
jq -c . root-audit.jsonl
jq . source-evidence.json
git apply --numstat source-mechanism.patch
```

若重新审计，所有镜像与临时文件必须位于 `.work/jackson-core-2.10-fse/`。目标历史检查命令为：

```bash
git log --all -G'<jackson.version>2[.]10[.]0</jackson.version>' \
  --format='%H %aI %s' -- '*.xml'
git log --all -G'<com.fasterxml.jackson.version>2[.]10[.]0</com.fasterxml.jackson.version>' \
  --format='%H %aI %s' -- '*.xml'
```

不得把 json-rules 的 `b2c9626582080d365a978d219c400d0f6bf009a7` 用作 A2；它虽修复相同异常分支，但固定的是 Jackson 2.13.1。也不能把共享 Jackson 属性升级产生的 Databind 或 Scala module 行为归为纯 jackson-core 变化。

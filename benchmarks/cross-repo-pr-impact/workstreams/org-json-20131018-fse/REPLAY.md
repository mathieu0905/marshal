# 核对说明

本组在候选历史筛选后停止，没有执行 A0/A1/A2。两条 FSE 记录都没有保存目标 Git 修订，两个目标仓的全部远程引用也都没有声明固定 `org.json:json:20131018`，因此不存在可执行的维护者 A2。

包内结构证据可直接核对：

```bash
jq -c . candidate-frame.jsonl
jq -c . root-audit.jsonl
jq . source-evidence.json
git apply --numstat source-mechanism.patch
```

若重新审计远程历史，所有镜像和临时文件必须位于项目内 `.work/org-json-20131018-fse/`。对 Alchemy-API 和 open311_java 分别检查全部引用：

```bash
git for-each-ref --format='%(refname)' | wc -l
git rev-list --all | sort -u | wc -l
git log --all -G'20131018|20090211|20090911' \
  --format='%H %aI %s' -- '*.xml' '*.gradle' '*.properties'
```

不能通过在任意历史提交上手工把依赖改成 20131018、再把 `getString` 调用改成显式 `toString` 或类型化 getter 来补出 A2。那会验证作者修复，而不是恢复维护者行为。

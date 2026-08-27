# 核对说明

本组故意没有执行 A0/A1/A2。严格前提是目标历史中存在保持 Commons Lang 3.10 的维护者 A2；Wasabi 没有固定 3.10 的修订，valueclasses 唯一固定 3.10 的 PR 头没有后继提交。

结构化产物与补丁可核对：

```bash
jq -c . candidate-frame.jsonl
jq -c . root-audit.jsonl
jq . source-evidence.json
git apply --numstat source-mechanism.patch
```

源机制祖先关系可重查：

```bash
git merge-base --is-ancestor 1dabf262c90d76958175e98f7ac9d0189fd7fbf2 rel/commons-lang-3.10
! git merge-base --is-ancestor 1dabf262c90d76958175e98f7ac9d0189fd7fbf2 commons-lang-3.9
```

目标历史检查必须覆盖镜像中的 heads、tags 与 pull refs：

```bash
git log --all -G'<version>3[.]10</version>' --format='%H %aI %s' -- '*.xml' '*.gradle' '*.gradle.kts' '*.properties'
git log --all -G'allowNewAssignment=true,name=page|almostPI=3.14' --format='%H %aI %s' -- '*.java' '*.txt'
```

不得把 valueclasses 的 `e5149b715800026a11f8985cb4515c219932f571` 回接成 A2；它使用 Commons Lang 3.19.0，不是固定 3.10 的维护者修复。

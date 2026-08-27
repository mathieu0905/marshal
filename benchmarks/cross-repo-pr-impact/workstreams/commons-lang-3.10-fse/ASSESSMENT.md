# Commons Lang 3.10 的 FSE 关系族历史筛选

更新日期：2026-08-25

## 结论

完整候选框只有两条：`fse2024-behavioral-0299`（`intuit/wasabi`）与 `fse2024-behavioral-0300`（`tguzik/valueclasses`）。按 GitHub repository ID 去重后仍为两个根仓。

Commons Lang 的确切源机制是提交 `1dabf262c90d76958175e98f7ac9d0189fd7fbf2`：`ReflectionToStringBuilder.appendFieldsIn` 在遍历前按 `Field.getName()` 排序。该提交不在 3.9 标签中，是 3.10 标签的祖先。它使 Wasabi 的 `allowNewAssignment` 移到 `name` 前，也使 valueclasses 的 `almostPI` 移到另外三个字段前，逐字解释两条公开失败。

两个目标根仓的 835 个引用、2,953 个可达提交中没有严格维护者 A2。Wasabi 的 588 个引用、2,288 个提交从未固定 Commons Lang 3.10。valueclasses 的 247 个引用、665 个提交中，唯一固定 3.10 的提交是未合并的 Dependabot PR 2 头 `a80e9937ab374e0fc81f7f1ba1604b56ad3e1d1f`；它只把 POM 从 3.9 改到 3.10，且没有任何后继提交。维护者到 2025 年才在 `e5149b715800026a11f8985cb4515c219932f571` 更新相同快照，但该提交固定 3.19.0。

因此本组在历史筛选后停止：候选 2、根仓 2、固定 3.10 的根仓 1、严格维护者 A2 0、重放 0、接纳 0。

## 候选与仓库身份

| 候选 | 客户端 | FSE current / previous / breaking | 根仓 / GitHub ID |
|---|---|---|---|
| `fse2024-behavioral-0299` | `com.intuit.wasabi:wasabi-experiment-objects` | 3.4 / 3.9 / 3.10 | `intuit/wasabi` / `61667990` |
| `fse2024-behavioral-0300` | `com.tguzik:valueclasses` | 3.9 / 3.9 / 3.10 | `tguzik/valueclasses` / `18852307` |

源仓 `apache/commons-lang` 的 GitHub ID 为 `206378`。两个目标 ID 不重叠，仓库别名不会造成重复关系。

## 确切源机制

3.9 发布标签 `commons-lang-3.9` 指向 `abb39c22c0e538fff03ea4e53d78ee60c6c08092`；3.10 发布标签 `rel/commons-lang-3.10` 指向 `e0b474c0d015f89a52c4cf8866fa157dd89e7d1c`。机制提交 `1dabf262` 的父提交是 `182b2506b304463f8f1a9ad765c6db0420fa356f`。

变更只需两步：导入 `Comparator`，然后对 `clazz.getDeclaredFields()` 的结果执行：

```java
Arrays.sort(fields, Comparator.comparing(Field::getName));
```

同一提交把上游测试的字段预期改成字母序，排除了客户端字段声明、JVM 偶然顺序或断言库格式化造成变化的解释。`source-mechanism.patch` 保存可在机制父提交上应用的生产代码 hunk。

## Wasabi 历史边界

公开失败的第 69 行和旧预期可由测试 blob `e03dcc1b59e44be19102947710680189112ab043` 或 `e5bba4f2bbc086f6534ed43d9c76c771c7344144` 表示。再要求 `modules/experiment-objects/pom.xml` 直接固定 3.4，仍有 905 个可达提交匹配，因此 FSE 的空修订字段不能恢复成唯一 Git 输入。

全 refs 搜索没有任何构建文件把该依赖固定为 3.10，也没有把失败预期改成 `allowNewAssignment,name` 的后续提交。手工选择某个匹配测试 blob 并修改 POM 会产生仓库历史中不存在的 A1；在其上自行改断言更不是维护者 A2。

## valueclasses 历史边界

FSE 行为对应测试 blob `f0572791d1e4e66fb8443bbf7eeeb941a604d759`、快照 blob `459ee91a2a6421abb5f5f3f97ff5d9ac8fd6438a` 与直接版本 3.9。全部 refs 中有 239 个提交符合该指纹，仍无法从公开记录选出唯一修订。

唯一的 3.10 提交 `a80e9937` 位于 `refs/pull/2/head`，父提交 `b7df37d4` 固定 3.9。该 PR 头没有可达后继提交，因而不可能包含修复。2025 年维护者提交 `e5149b71` 同时把依赖从 3.9 升到 3.19.0 并把快照改成字母序；它精确修复同一合同，但版本不满足固定 3.10 的 A2 定义。

Git 能固定每个提交，Maven 能解析依赖，普通测试也能验证手工组合，但三者都不能把 3.19.0 的维护者修复改写成 3.10 修复，也不能为没有后继的 PR 2 创造维护者提交。因此不执行 A0/A1/A2，也不生成 A3。

结构化证据见 `candidate-frame.jsonl`、`root-audit.jsonl` 和 `source-evidence.json`。

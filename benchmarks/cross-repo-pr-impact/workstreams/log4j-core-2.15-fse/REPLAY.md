# `gdv.xport` 三臂重放

## 固定输入

- Java：OpenJDK 11.0.31；
- Maven：3.9.8；
- 原生命令：`mvn -B -ntp -pl lib -am clean test`；
- Maven cache：`.work/log4j-core-2.15-fse/m2/<arm>`（三臂各自独立）；
- worktree：`.work/log4j-core-2.15-fse/runs/<arm>`；
- JVM/tmp：`.work/log4j-core-2.15-fse/tmp/<arm>`；
- 结果：`benchmarks/cross-repo-pr-impact/results/log4j-core-2.15-fse-replay-2026-08-25/`。

`run_three_arm.sh` 设置 `JAVA_HOME`、`TMPDIR`、`MAVEN_OPTS=-Djava.io.tmpdir=...` 和 Maven 的 `java.io.tmpdir` 用户属性。正式日志中没有系统 `/tmp` 路径；测试临时文件均写入对应 `.work` 目录。

每次重放会先将已有的生成 worktree 强制恢复到指定 detached revision，再应用 A2 修订，因此同一脚本可在已有运行目录上重复执行。

## 三臂定义

| 臂 | 输入 | Log4j API/Core | 修订 |
|---|---|---|---|
| A0 | `3f806a2a37029b6d2a0afbc716917dacc19bea17` | 2.14.1 / 2.14.1 | 无 |
| A1 | `3bf9996a0afdbf426e920e03aafe069cab4e2491` | 2.14.1 / 2.15.0 | 维护者合并的 Core PR 68 |
| A2 | A1 树 | 2.15.0 / 2.15.0 | `a84175f2...` 中的原样 API 同步行 |

A2 修订见 `gdv-maintainer-api-sync.patch`。它与维护者提交在 `pom.xml` 上的 diff 逐字一致，只排除同提交中删除 SmokeRunner 的独立测试合同变化。

## 结果

| 臂 | 退出码 | Maven 汇总 | XML 文件/汇总 | 关键签名 |
|---|---:|---|---|---|
| A0 | 0 | 1070/0 failures/0 errors/5 skipped | 50；1069/0/0/9 | `BUILD SUCCESS` |
| A1 | 1 | 0 tests | 0；0/0/0/0 | `ServiceConfigurationError`；dump 内层 `NoSuchFieldError: EMPTY_BYTE_ARRAY` |
| A2 | 0 | 1070/0/0/5 | 50；1069/0/0/9 | `BUILD SUCCESS` |

A1 的内层路径为：

```text
NoSuchFieldError: EMPTY_BYTE_ARRAY
  at org.apache.logging.log4j.core.config.ConfigurationSource.<clinit>
  at org.apache.logging.log4j.core.config.NullConfiguration.<init>
  at org.apache.logging.log4j.core.LoggerContext.<clinit>
  ...
  at patterntesting.runtime.junit.extension.SmokeTestExtension.<clinit>
```

这补全了 FSE 工作簿只保留的顶层 provider 实例化错误。

## 完整维护者提交诊断

`a84175f220b8a7925a97ce22f211303d47960ba6` 的完整树也执行了同一命令。Log4j provider 错误消失，但删除 SmokeRunner 后，历史测试栈重复发现 `MyUnfallDatensatzTest`；记录显示同一测试 Run 1 通过、Run 2 在注册状态已还原后以不同的 `IllegalArgumentException` 失败。Maven 汇总 1074 tests/1 error/2 skipped，XML 汇总 1070 tests/1 error/2 skipped。

该诊断说明为何正式 A2 使用维护者提交中的精确 API 同步修订，而不声称整笔混合提交原生全绿。正式因果结论只覆盖公开 `ServiceConfigurationError` 的恢复。

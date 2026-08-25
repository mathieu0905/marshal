# 未计入的早期执行

本目录保存 Hibernate Validator 7 / SmallRye Config 的早期失败尝试，不是有效 A0/A1/A2 结果，也不计入关系方向。

`A0.log`、`A1.log`、`A2.log` 及三个 `*-retry.log` 都在测试前停于 `impsort-maven-plugin:1.6.2`：运行时缺少 `org.codehaus.plexus.util.DirectoryScanner`。这些尝试使用了全局 Maven 仓库，三臂得到同一个构建工具错误，无法观察 Hibernate Validator 版本变化。

改用 Maven 3.8.8 的后续尝试仍未完成。`A1-maven-3.8.8.log` 和 `A2-maven-3.8.8.log` 在依赖解析时报告 `No space left on device`；`A0-maven-3.8.8.log` 在下载依赖时中断，没有终态。九份日志均没有执行目标测试。

后来在项目内 `.work/hibernate-validator-smallrye/replay-20260825/` 使用隔离 Maven 仓库完成了有效定向重放。完整结果、命令和机器可读结论位于相邻的 `hibernate-validator-7-fse-smallrye-replay-2026-08-25/` 目录。本目录只作为失败溯源保留，不应与该有效结果合并计数。

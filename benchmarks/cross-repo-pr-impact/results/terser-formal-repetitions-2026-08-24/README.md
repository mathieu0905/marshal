# Terser 历史暴露版本重复

本目录保留 2026-08-24 完成的三轮隔离重复。四个目标仓使用各自历史复现环境中实际暴露的 `terser` 版本：Assetgraph Builder 4.3.9、UI5 Builder 4.3.0、Preconstruct 4.3.9、Angular CLI 4.3.1。

三轮共执行 51 个仓库命令，版本和结果方向均符合预期。这些记录证明 `terser` PR 433 引入的行为在四个历史版本环境中的重复性，但不同目标没有共享同一个二进制输入，因此不能单独作为统一边界版本的闭集项目包证据。

统一使用 4.3.0 的重复结果另存于 `../terser-unified-430-repetitions-2026-08-24/`。`discarded-repeat-1-control-path-error/` 是控制依赖路径错误的废弃轮次，只保留为实验环境审计材料，不计入正式结果。

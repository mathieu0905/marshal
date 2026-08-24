# 废弃的统一版本首轮

本轮不计入正式重复。

首次统一到 `terser` 4.3.0 时，替换函数先复制了 4.3.0 包中已有的 `node_modules/commander`，再把 Angular CLI 历史环境中的嵌套依赖目录整体移动进去，导致 `source-map` 0.6.1 落到 `node_modules/node_modules/source-map`。Angular A1 随后在源映射处理中失败，并未生成待测产物。

修正后的脚本先移除源包携带的嵌套目录，再恢复目标历史环境原有的嵌套依赖。之后重新开始三轮，正式结果位于相邻的 `repeat-1`、`repeat-2` 和 `repeat-3`。

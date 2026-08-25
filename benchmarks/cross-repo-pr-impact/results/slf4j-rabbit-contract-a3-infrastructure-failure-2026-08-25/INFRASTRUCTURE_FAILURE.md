# 未计入的基础设施失败

首次 A3 尝试使用项目外的 `/home/zhihao/hdd/marshal-experiments/slf4j-rabbit-a3/` 作为工作根；Java 临时与共享内存仍落在已经耗尽的根文件系统。依赖解析和测试启动均报告 `No space left on device`。该尝试没有形成完整执行臂，也不计入 A3 的测试数或方向结论。

这里仅保留失败日志与当时已经写出的输入记录。`run-results.tsv` 只有未完成的 `before` 行；`after` 仅留下依赖解析日志，没有测试结果。后续正式运行已把镜像、检出、Maven 缓存和 Java 临时目录全部移到项目内的 `.work/slf4j-rabbit/`。

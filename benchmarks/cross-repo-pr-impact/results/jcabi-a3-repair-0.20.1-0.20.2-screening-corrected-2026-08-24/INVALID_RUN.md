# 无效运行说明

本目录中的结果不得计入 `jcabi-aspects` A3 结论。

这次运行修正了 POM 替换，但使用了默认的较新 JDK。四个项目的旧 Lombok 或相关编译链访问了已经变化的 `javac` 内部字段，触发 `JCTree$JCImport.qualid` 的 `NoSuchFieldError`；`jcabi-maven-plugin` 的集成测试也因此中断。该失败来自测试环境与旧构建工具链不兼容，不是 `jcabi-aspects` 0.20.1 与 0.20.2 的行为差异。

有效的 OpenJDK 11 重新运行见同级目录 `jcabi-a3-repair-0.20.1-0.20.2-java11-screening-2026-08-24/`。

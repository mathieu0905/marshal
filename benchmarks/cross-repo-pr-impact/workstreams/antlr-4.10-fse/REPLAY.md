# jStyleParser 机制三臂重放

## 固定输入

- 目标仓：`radkovo/jStyleParser`；
- 目标基准：`aed9ffc08dda481222bd9cd66635116768e23a54`；
- A0：只把 `antlr4-runtime` 从目标原值 4.5.3 改为 4.9.3；
- A1：只把 `antlr4-runtime` 从目标原值 4.5.3 改为 4.10；
- A2：在 A1 上只把 `antlr4-maven-plugin` 从 4.5.3 改为 4.13.2；
- Java 11；
- Maven 3.9.8。

三棵检出树必须都来自同一目标基准。A2 的生成器版本取自维护者提交 `66e905d079dd9f7a7b58dac9705fe284beb5876e`，但维护者原提交还把运行时改成 4.13.2，因此 A2 只是机制隔离，不是正式精确维护者恢复。

## 准备检出树

分别从目标基准创建三棵检出树，再应用：

- A0：`a0-runtime-4.9.3.patch`；
- A1：`a1-runtime-4.10.patch`；
- A2：`a2-mechanism-combination.patch`。

补丁只作用于 `pom.xml`。不要把维护者的 Java 11 配置提交或运行时 4.13.2 混入 A2。

## 执行

```bash
./run-jstyle-three-arm.sh \
  <A0 检出树> \
  <A1 检出树> \
  <A2 检出树> \
  <结果目录>
```

脚本对每臂先执行 FSE 指定的 `test.AdvancedCSSTest`，再执行完整 `mvn clean test`。预期完整测试退出方向为 A0 为 0、A1 非 0、A2 为 0。

本次执行结果位于 `results/antlr-4.10-fse-jstyle-2026-08-25/`。三臂的完整 Surefire XML 已分别保存在 `surefire/A0`、`surefire/A1`、`surefire/A2`。

## 结果解释

A1 的 `AdvancedCSSTest` 在类初始化阶段失败，完整套件有 167 项同源错误。A2 虽有生成器与运行时版本号警告，但所有实际解析合同恢复。该结果只允许记为机制锚点；正式接纳数仍为 0。

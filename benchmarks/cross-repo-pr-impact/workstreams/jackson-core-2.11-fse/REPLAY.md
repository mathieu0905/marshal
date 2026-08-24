# Jackson Core 2.11.0 三臂重放

## 固定输入

- A0：`internetitem/logback-elasticsearch-appender@c708131107e56570674b1a59f241a8b782cfa60f`，Jackson Core 2.8.0；
- A1：`internetitem/logback-elasticsearch-appender@20de83750d38118433e27efd47ebced8f37a1c21`，Jackson Core 2.11.0；
- A2：`internetitem/logback-elasticsearch-appender@19890dee0d3ec4839658c3973a8c1aa2dba7eb8e`，保持 Jackson Core 2.11.0；
- 反事实臂：A0 代码只把 Jackson Core 改成 2.11.0；
- Java 11；
- Maven 本地依赖目录固定在 `.work/jackson-core-2.11-fse/m2`。

A1 的父提交就是 A0。A1 更新多项依赖并加入 Maven Wrapper，但不修改生产或测试 Java 代码。A2 的父提交就是 A1，只修改 `PropertySerializerTest.java`，把对底层 `writeNumber`、`writeObject` 和 `writeBoolean` 的验证改成对字段级方法的验证，并补齐字段名。

## 执行命令

每棵工作树执行同一条命令：

```bash
JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64 \
TMPDIR=/home/zhihao/hdd/marshal/.work/jackson-core-2.11-fse/tmp \
MAVEN_OPTS='-Djava.io.tmpdir=/home/zhihao/hdd/marshal/.work/jackson-core-2.11-fse/tmp' \
mvn -q \
  -Dmaven.repo.local=/home/zhihao/hdd/marshal/.work/jackson-core-2.11-fse/m2 \
  -Dtest=PropertySerializerTest test
```

## 结果

| 臂 | 目标代码 | Jackson Core | 结果 |
|---|---|---:|---|
| A0 | 原始测试 | 2.8.0 | 8/8 通过 |
| A1 | 原始测试 | 2.11.0 | 8/8 失败 |
| A2 | 维护者修复测试 | 2.11.0 | 8/8 通过 |
| 反事实臂 | A0 代码，仅改依赖版本 | 2.11.0 | 8/8 失败 |

A1 和反事实臂都报告同一签名：旧断言期待 `writeNumber(123)`，实际模拟对象收到 `writeNumberField(null, 123)`。另外七项也分别从底层数值、对象或布尔调用变为字段级调用。

反事实臂用于排除 A1 同时更新的 Logback、SLF4J、AWS SDK、JUnit 和构建插件。仅改变 Jackson Core 已足以复现全部八项失败。

原始 Surefire 报告位于 `results/jackson-core-2.11-fse-screening-2026-08-25/`。

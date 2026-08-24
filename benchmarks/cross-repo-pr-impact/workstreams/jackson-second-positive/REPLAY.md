# 重放说明

## 环境

- Java 11；
- Maven 3.9.8；
- 目标基准：`RWS/dxa-web-application-java@6bedc440f72e5cee768db367d59f5bb26e4512e8`；
- 源父提交：`FasterXML/jackson-databind@a8d8ec0e92b6220381a8eae38d4bf8765c7c9ca1`；
- 源行为提交：`FasterXML/jackson-databind@2897aa00e04e3a28aef45f5b485001db161e2e2c`。

## 构建两个精确源输入

分别检出两个 Databind 提交，对两棵源码树应用 `source-build-pom.patch`。该补丁只把父 POM 指向已发布的 2.11.0，不修改 Java 源码。然后执行：

```bash
mvn -B -DskipTests package
mvn -B install:install-file \
  -Dfile=target/jackson-databind-2.11.0-SNAPSHOT.jar \
  -DgroupId=com.fasterxml.jackson.core \
  -DartifactId=jackson-databind \
  -Dversion=2.11.0-<提交短号> \
  -Dpackaging=jar
```

A0 的本地版本名为 `2.11.0-a8d8ec0e`，A1 和 A2 为 `2.11.0-2897aa00e`。

## 准备目标输入

在目标基准上应用 `target-harness-pom.patch`，加入 `JacksonObjectMixinCompatibilityTest.java`。该 POM 补丁只允许 Databind 独立于 Core 和 Annotations 选择版本。A2 另应用 `maintainer-repair.patch`。

## 执行产品路径三臂

```bash
mvn -B -pl dxa-framework/dxa-common-api -am \
  -Djackson.databind.version=<本臂版本> \
  -Dtest=JacksonObjectMixinCompatibilityTest \
  -Dsurefire.failIfNoSpecifiedTests=false test
```

A0 在未修目标上选择 `2.11.0-a8d8ec0e`；A1 在同一目标上选择 `2.11.0-2897aa00e`；A2 在应用维护者修复后选择 `2.11.0-2897aa00e`。

## 核对原始模块边界

```bash
mvn -B -pl dxa-framework/dxa-data-model -am \
  -Djackson.databind.version=<本臂版本> \
  -Dtest=DeserializationTest#shouldDeserializePageModel \
  -Dsurefire.failIfNoSpecifiedTests=false test
```

这条命令预期 A0 通过、A1 失败、A2 仍失败。它用于阻止把产品路径恢复夸大成原始模块测试恢复。

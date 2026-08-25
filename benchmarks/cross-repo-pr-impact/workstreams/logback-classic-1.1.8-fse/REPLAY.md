# Logback Classic 1.1.8 机制重放

## 固定输入

- Libcrunch：`twitter-archive/libcrunch@90ec26e4f31cb64df7838d8f14aefaabc5184b5c`，Core 1.0.1；
- Wro4j Taglib：`Orange-OpenSource/wro4j-taglib@912b4b1cd8433d146a1626cfb9ee72a8a86d2ce1`，Core 1.0.7；
- Goodies：`sonatype/goodies@5c3560a63247daa9222e60d8cf09496a7ba1e293`，Core 1.1.2；
- A0 保持目标仓原有 Classic 版本；
- 相邻源版本对照只把 Classic 改成 1.1.7；
- A1 只把 Classic 改成 1.1.8；
- Eclipse Temurin Java 8u472。

三个配置都保留目标仓原有 Core 和目标代码。相邻版本对照不是维护者 A2，也不计作正式关系；它只隔离 1.1.7 到 1.1.8 的异常边界变化。

## 执行命令

以下命令从仓库根目录执行。临时文件和 Maven 本地仓均固定在项目的 `.work` 目录，不使用系统 `/tmp` 或用户主目录下的共享缓存。

Libcrunch：

```bash
TMPDIR=/home/zhihao/hdd/marshal/.work/tmp \
MAVEN_OPTS='-Djava.io.tmpdir=/home/zhihao/hdd/marshal/.work/tmp -Djansi.tmpdir=/home/zhihao/hdd/marshal/.work/tmp -XX:-UsePerfData' \
JAVA_HOME=/home/zhihao/hdd/marshal/.work/logback-classic-1.1.8-fse/jdk8 \
mvn -q clean \
  -Dmaven.repo.local=/home/zhihao/hdd/marshal/.work/logback-classic-1.1.8-fse/m2 \
  -Dtest=com.twitter.crunch.AssignmentTrackerImplTest#testDifferenceThreshold \
  test
```

Wro4j Taglib：

```bash
TMPDIR=/home/zhihao/hdd/marshal/.work/tmp \
MAVEN_OPTS='-Djava.io.tmpdir=/home/zhihao/hdd/marshal/.work/tmp -Djansi.tmpdir=/home/zhihao/hdd/marshal/.work/tmp -XX:-UsePerfData' \
JAVA_HOME=/home/zhihao/hdd/marshal/.work/logback-classic-1.1.8-fse/jdk8 \
mvn -q clean \
  -Dmaven.repo.local=/home/zhihao/hdd/marshal/.work/logback-classic-1.1.8-fse/m2 \
  -Dtest=com.orange.wro.taglib.config.WroTagLibConfigTest \
  test
```

Goodies：

```bash
TMPDIR=/home/zhihao/hdd/marshal/.work/tmp \
MAVEN_OPTS='-Djava.io.tmpdir=/home/zhihao/hdd/marshal/.work/tmp -Djansi.tmpdir=/home/zhihao/hdd/marshal/.work/tmp -XX:-UsePerfData' \
JAVA_HOME=/home/zhihao/hdd/marshal/.work/logback-classic-1.1.8-fse/jdk8 \
mvn -q clean -pl testsupport -am \
  -Dmaven.repo.local=/home/zhihao/hdd/marshal/.work/logback-classic-1.1.8-fse/m2 \
  -Dtest=org.sonatype.goodies.testsupport.concurrent.ConcurrentRunnerTest#testPropagateTaskErrors \
  -Dsurefire.failIfNoSpecifiedTests=false \
  test
```

## 结果

| 根仓 | A0 | 1.1.7 对照 | A1 |
|---|---:|---:|---:|
| Libcrunch | 1 项通过 | 1 项通过 | 1 项错误 |
| Wro4j Taglib | 8 项通过 | 8 项通过 | 8 项错误 |
| Goodies Testsupport | 1 项通过 | 1 项通过 | 1 项错误 |

A1 的首次底层异常在三仓中完全一致：

```text
java.lang.NoClassDefFoundError:
  ch/qos/logback/core/util/StatusListenerConfigHelper
```

1.1.7 对照也遇到同一个错误，但被 `StaticLoggerBinder.init()` 的 `catch (Throwable)` 捕获，测试进程保持成功。A1 使用 `catch (Exception)`，因此同一个 `Error` 逃逸并使测试失败。

# Marshal 最小多仓案例集

**版本**：调研稿 0.1  
**日期**：2026-08-22  
**来源**：BUMP 公开数据中的共同上游分组。

## 一、用途

现成数据已经足以评测单仓修复，但没有把“共同上游影响多个消费仓”组织成 Marshal 项目级输入。本案例集先选 3 个上游、6 个消费仓，把 BUMP 中分散的真实案例重新按依赖方向组织起来。

每个案例都包含两个仓库：上游源码仓和消费仓。消费仓使用已发布的上游版本，不是未发布候选产物。因此本案例集适合测：

- 能否识别上游和消费仓关系；
- 能否在多个消费仓中定位真实影响；
- 能否路由并执行消费仓已有测试；
- 能否明确记录哪些消费仓已验证、哪些未验证。

它不用于声称 Marshal 已经验证多个未发布候选版本的组合。

## 二、统一表示

每例只需要以下现有事实：

- 上游仓库及旧、新 Git 标签；
- 消费仓父提交和依赖升级提交；
- Maven 依赖坐标；
- 方向为“上游提供方到消费仓”；
- 现有命令 `mvn clean test -B`；
- 升级前应成功、升级后应失败的结果。

不增加内容哈希、冻结契约、永久依赖图或新的发布门禁。Git 版本、Maven 坐标和项目测试已经足以重放这些案例。

## 三、案例清单

### A1：jcabi-aspects 到 jcabi-s3

| 字段 | 值 |
|---|---|
| 上游 | `jcabi/jcabi-aspects` |
| 上游版本 | `0.24.1` 到 `0.25.1` |
| 消费仓 | `jcabi/jcabi-s3` |
| 消费仓父提交 | `0efa37ae2c431ae148e921dc3c1a9fcb8aa2bd3a` |
| 消费仓升级提交 | `24d4a90ec1b375751e71f33d18949405c9529d77` |
| 依赖坐标 | `com.jcabi:jcabi-aspects` |
| 预期 | 父提交通过，升级提交编译失败 |
| 本轮重放 | `PRE_RC=0`，`BREAKING_RC=1` |

### A2：jcabi-aspects 到 jcabi-simpledb

| 字段 | 值 |
|---|---|
| 上游 | `jcabi/jcabi-aspects` |
| 上游版本 | `0.24.1` 到 `0.25.1` |
| 消费仓 | `jcabi/jcabi-simpledb` |
| 消费仓父提交 | `4af3ea931691caa0a667852b626485b1b0cbffcf` |
| 消费仓升级提交 | `7d97e1c7331f6722eb1d8192bf0a2686f5a33798` |
| 依赖坐标 | `com.jcabi:jcabi-aspects` |
| 预期 | 父提交通过，升级提交测试编译失败 |
| 本轮重放 | `PRE_RC=0`，`BREAKING_RC=1`；找不到 `com.jcabi.aspects.Tv` |

### B1：slf4j 到 sign-maven-plugin

| 字段 | 值 |
|---|---|
| 上游 | `qos-ch/slf4j` |
| 上游版本 | `v_1.7.36` 到 `v_2.0.2` |
| 消费仓 | `s4u/sign-maven-plugin` |
| 消费仓父提交 | `f770a49d21a5def32c61f6b18a398494a72baeaf` |
| 消费仓升级提交 | `072528ee5e678feabeaa1e2962725134564bdd3c` |
| 依赖坐标 | `org.slf4j:slf4j-api` |
| 预期 | 父提交通过，升级提交测试失败 |
| 本轮重放 | `PRE_RC=0`，`BREAKING_RC=1`；旧日志模拟绑定被忽略 |

### B2：slf4j 到 jasmine-maven-plugin

| 字段 | 值 |
|---|---|
| 上游 | `qos-ch/slf4j` |
| 上游版本 | `v_1.7.32` 到 `v_2.0.6` |
| 消费仓 | `searls/jasmine-maven-plugin` |
| 消费仓父提交 | `0a1425c09636aef885a22a86165664adb81bee95` |
| 消费仓升级提交 | `426453d4be2fa291749ffda52de1653e16ddf3c9` |
| 依赖坐标 | `org.slf4j:slf4j-api` |
| 预期 | 父提交通过，升级提交测试失败 |
| 本轮重放 | `PRE_RC=0`，`BREAKING_RC=1`；日志断言未观察到消息 |

### C1：jackson-databind 到 simplelocalize-cli

| 字段 | 值 |
|---|---|
| 上游 | `fasterxml/jackson-databind` |
| 上游版本 | `jackson-databind-2.9.10.5` 到 `jackson-databind-2.13.4.1` |
| 消费仓 | `simplelocalize/simplelocalize-cli` |
| 消费仓父提交 | `c041887aeed06af1f84345b68350818d1f8f2f0f` |
| 消费仓升级提交 | `741f3b5e20a91b0e9305ae79261e3c5e64971c98` |
| 依赖坐标 | `com.fasterxml.jackson.core:jackson-databind` |
| 预期 | 父提交通过，升级提交编译失败 |
| 本轮重放 | `PRE_RC=0`，`BREAKING_RC=1`；缺少 `StreamReadException` |

### C2：jackson-databind 到 dependency-lock-maven-plugin

| 字段 | 值 |
|---|---|
| 上游 | `fasterxml/jackson-databind` |
| 上游版本 | `jackson-databind-2.13.4` 到 `jackson-databind-2.13.4.1` |
| 消费仓 | `vandmo/dependency-lock-maven-plugin` |
| 消费仓父提交 | `bfd3d3819299ff67d4ce545752423e9bbf723dee` |
| 消费仓升级提交 | `6cb50e747a317a2e3159c921e50847b197bca3cd` |
| 依赖坐标 | `com.fasterxml.jackson.core:jackson-databind` |
| 预期 | 父提交通过，升级提交依赖锁检查失败 |
| 本轮重放 | `PRE_RC=0`，`BREAKING_RC=1`；锁文件期望 2.13.4.1，实际解析为 2.13.4 |

BUMP 为 C2 提供的 GitHub 比较链接方向与旧、新版本字段相反。案例表示应以消费仓提交中的 Maven 版本变化为准，并把该链接只当辅助来源。

## 四、项目级组织

六例应按三个项目任务运行，而不是六个完全独立任务：

```text
jcabi-aspects 0.24.1 -> 0.25.1
  -> jcabi-s3
  -> jcabi-simpledb

slf4j 1.7.x -> 2.0.x
  -> sign-maven-plugin
  -> jasmine-maven-plugin

jackson-databind -> 2.13.4.1
  -> simplelocalize-cli
  -> dependency-lock-maven-plugin
```

其中后两组的两个消费仓起始版本不同。项目级输入不能错误地假定一个上游组内所有消费仓都从同一旧版本升级。

## 五、评测记录

每个项目任务记录：

- 预期受影响消费仓集合；
- Marshal 实际指出的消费仓集合；
- 每个消费仓是否运行测试；
- 每个测试使用的依赖版本；
- 观察到的失败类别；
- 未执行或版本不明的项目。

首轮只有正例，不计算复杂总体分数。以逐例命中、遗漏、误报和未验证状态为主。

## 六、仍需补的案例

本案例集补上了“共同上游到多个消费仓”的组织方式，但仍使用已发布依赖。下一轮只需再找 2 至 4 个 OpenDev/Zuul 或同组织协调变更案例，要求两个仓库的未发布候选版本必须一起通过。那一小组专门回答候选组合问题，不应扩大成本轮 BUMP 数据的重制工程。

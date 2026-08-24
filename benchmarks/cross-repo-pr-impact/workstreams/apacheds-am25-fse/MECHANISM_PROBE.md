# ApacheDS AM25 源成品机制测量

## 测量对象

从 Maven Central 取得以下四个发布成品：

- `org.apache.directory.server:apacheds-all:2.0.0-M24`
- `org.apache.directory.server:apacheds-all:2.0.0.AM25`
- `org.bouncycastle:bcprov-jdk15on:1.56`
- `org.bouncycastle:bcprov-jdk15on:1.59`

源提交 `6200fa2b25e9aa96517283dd9a965a753eeca7b1` 只把 Bouncy Castle 从 1.56 升到 1.59。两个上游成品的签名条目实际为：

```text
bcprov-jdk15on-1.56.jar
META-INF/BCKEY.SF
META-INF/BCKEY.DSA

bcprov-jdk15on-1.59.jar
META-INF/BC1024KE.SF
META-INF/BC1024KE.DSA
META-INF/BC2048KE.SF
META-INF/BC2048KE.DSA
```

M24 与 AM25 的 `all/pom.xml` 都只排除旧名称 `META-INF/BCKEY.SF` 和 `META-INF/BCKEY.DSA`。对应的 ApacheDS 合并包中，M24 没有残留签名条目，AM25 则残留 1.59 的四个新名称。

## 实际类加载

使用 OpenJDK 21 运行一个只调用 `Class.forName("org.bouncycastle.jce.provider.BouncyCastleProvider")` 的最小程序。M24 成功加载：

```text
VERSION=2.0.0-M24
org.bouncycastle.jce.provider.BouncyCastleProvider
EXIT=0
```

AM25 在类加载前失败，异常与 FSE 三条记录完全一致：

```text
VERSION=2.0.0.AM25
java.lang.SecurityException: Invalid signature file digest for Manifest main attributes
EXIT=1
```

在 AM25 合并包的副本中仅删除 `META-INF/*.SF` 和 `META-INF/*.DSA` 后，同一个类加载程序恢复成功：

```text
org.bouncycastle.jce.provider.BouncyCastleProvider
EXIT=0
```

这个测量证明了源成品的具体失败机制，但不构成客户端 A2，也不替代完整客户端三臂重放。原始 FSE 执行使用 Java 8，本次最小测量使用 Java 21；两者出现同一 JVM 签名校验异常，但这里只把测量用于机制确认。

## 后续源仓变化

AM25 发布后，`4adfc986834ed91332d0adf902875ec76de5b252` 尝试把 `BCKEY` 改成 `BCK*`，但该模式并不覆盖发布成品中的 `BC1024KE` 和 `BC2048KE`，不能据此声称完整恢复。2020 年的 `b00a31d8ed5e6e7ab3f2ed899f3add650bfe5c3f` 及合并提交 `bc8c02a1863fc55b035c3730c934bdeda37549fb` 才把过滤推广到所有依赖的 `META-INF/*.SF`、`*.DSA` 和 `*.RSA`，与上述手工过滤的恢复结果一致。

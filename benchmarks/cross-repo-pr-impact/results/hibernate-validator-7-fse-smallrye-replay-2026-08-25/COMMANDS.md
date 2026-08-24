# 执行命令

所有命令使用项目内 Maven 3.8.8、独立的项目内 Maven 仓库、OpenJDK 11，并把 `HOME`、`TMPDIR`、`java.io.tmpdir` 固定在 `.work/hibernate-validator-smallrye/replay-20260825/` 下。

每个实验臂先执行依赖模块构建：

```bash
mvn -Dmaven.repo.local=<该臂项目内仓库> -B -ntp \
  -Dimpsort.skip=true -Dformatter.skip=true -DskipTests \
  -pl validator -am clean install
```

随后执行目标测试：

```bash
mvn -Dmaven.repo.local=<该臂项目内仓库> -B -ntp \
  -Dimpsort.skip=true -Dformatter.skip=true \
  -pl validator \
  -Dtest=io.smallrye.config.validator.ValidateConfigTest test
```

实际解析版本从每臂 Surefire XML 的 `java.class.path` 取得，相关路径另存于 `logs/*-resolved-classpath.txt`。这比未完成下载的旧版 `maven-dependency-plugin` 输出更接近实际测试进程；三次被停止的 `dependency:tree` 尝试不计入结果。

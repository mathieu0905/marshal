# XStream 1.4.18 白名单机制测量

## 测量设计

使用同一个 JUnit 4 测试，在 XStream `1.4.16` 与 `1.4.18` 下反序列化同一个客户端自定义类型。测试先注册别名，再读取 `<person><name>Ada</name></person>`。第三臂仅在 `1.4.18` 下调用 `allowTypes` 显式放行该类型。

测量使用 OpenJDK 21、Maven 3.9.8 和 Surefire 2.22.2。测量工程、临时目录与 Maven 依赖缓存均位于 `.work/xstream-1.4.18-fse/`。

## 结果

XStream `1.4.16`，未显式放行：

```text
Tests run: 1, Failures: 0, Errors: 0, Skipped: 0
EXIT=0
```

XStream `1.4.18`，未显式放行：

```text
Tests run: 1, Failures: 0, Errors: 1, Skipped: 0
com.thoughtworks.xstream.security.ForbiddenClassException:
probe.WhitelistProbeTest$Person
EXIT=1
```

XStream `1.4.18`，通过 `allowTypes` 显式放行：

```text
Tests run: 1, Failures: 0, Errors: 0, Skipped: 0
EXIT=0
```

失败类型与 `fse2024-behavioral-0203`、`0204` 记录的 `ForbiddenClassException` 一致。`0202` 只留下测试中的空指针，现有日志不足以证明空指针前的根异常，因此不把本测量强行解释为该条失败的完整机制。

## 源提交对应关系

标签 `XSTREAM_1_4_16`、`XSTREAM_1_4_17`、`XSTREAM_1_4_18` 依次具有祖先关系。提交 `652d72f38b33938c54fd3b2ef626cb7dce38001c` 属于 `1.4.18`，不属于 `1.4.17` 或 `1.4.16`。

该提交把默认权限从允许任意类型并排除黑名单，改为默认拒绝并明确放行基础类型；`setupDefaultSecurity` 从 `1.4.18` 起变为空操作并弃用。客户端自定义类型必须通过 `allowTypes`、`allowTypesByWildcard` 等接口显式放行。相关核心文件差异见 `source-mechanism.patch`。

源提交共改动 28 个文件、增加 147 行、删除 308 行，因此这里只能声称“宽提交中的明确机制”。第三臂是机制验证，不是维护者 A2，不能据此接纳因果案例。

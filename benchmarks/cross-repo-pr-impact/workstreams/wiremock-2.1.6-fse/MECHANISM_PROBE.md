# WireMock 2.1.6 未匹配请求机制测量

## 测量设计

使用同一个 JUnit 4 测试分别加载 WireMock 1.58 和 2.1.6。测试只做三件事：

1. 通过 `WireMockRule` 注册 `GET /`。
2. 实际发送 `POST /`。
3. 不在测试体内断言响应，使观测点只落在规则的测试结束处理上。

测试由 Maven Surefire 2.22.2 在 OpenJDK 21 上执行，依赖和构建缓存均位于 `.work/wiremock-2.1.6-fse/`。

## 结果

WireMock 1.58：

```text
Tests run: 1, Failures: 0, Errors: 0, Skipped: 0
EXIT=0
```

WireMock 2.1.6：

```text
Tests run: 1, Failures: 1, Errors: 0, Skipped: 0
com.github.tomakehurst.wiremock.client.VerificationException:
A request was unmatched by any stub mapping. Closest stub mapping was: expected:<
GET
/
> but was:<
POST
/
>
EXIT=1
```

异常类型、GET/POST 差异和消息结构都与 `fse2024-behavioral-0056` 的历史失败一致。

## 源提交对应关系

标签 `1.58` 是 `c1e3a7d2d0c11579c8f05092a738155e96bb3128`，标签 `2.1.6` 是 `1cff8d2328fab4aab26f1c7837c867f1e2994822`，前者是后者的祖先。

提交 `acc9871a6e1648ea7ba26b82de6970c9c836f1b2` 属于 2.1.6 而不属于 1.58。它让 `WireMockRule(Options)` 默认启用未匹配请求检查，并在测试体正常结束后调用该检查。相关文件的精确差异见 `source-mechanism.patch`。

源提交总计改动 134 个文件，因此这里只能声称“宽提交中的明确机制”。本测量证明了 `0056` 的源行为变化，但它不是客户端 A2，也不能为 `0057` 中只记录到远端 500 与后续空指针的失败补造因果归因。

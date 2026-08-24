# JAX-RS 2.0.1 到 2.1-m08 的 FSE 关系族筛选

更新日期：2026-08-24

## 结论

八条 FSE 目录提示去重后只有两个独立根仓：`alibaba/fastjson` 一条，`jwcarman/microbule` 七个模块。七个 Microbule 模块共享同一根仓、父 POM、CXF 运行时和提交历史，不能拆成七条独立关系。

本轮接纳零条，未执行 A0/A1/A2/A3，也没有限定负例。两个根仓都没有维护者适配 JAX-RS 2.1-m08 的 A2：Fastjson 至今仍把 `javax.ws.rs-api` 固定在 2.0.1，相关 Issue1341 测试在 2017 年 8 月后没有合同修复；Microbule 的最后代码分支停在 2017 年 7 月，并同样保持 2.0.1。家族要求至少两个独立根仓具备精确 A2 后才进入三臂，因此在历史筛选阶段拒绝，不恢复旧 Maven 环境。

## 单一源变化

来源仓为 `javaee/jax-rs-api`：

- `2.0.1`：`c866c4f2a9e93a5c445b27119b7bac0479e9033f`
- `2.1-m07`：`27e436d7099cfb568623f0747395477a2f41d4b6`
- `2.1-m08`：`10de4a9040bda23796600afd3876a6ae20b625d9`

精确变化是 `79bd5309ee7b3de3247bc8db1db5c61e29b7d53b`。它在 `Response.ResponseBuilder` 新增抽象方法 `status(int, String)`，并把已有的 `status(StatusType)` 改成调用这个新方法。旧 CXF 的 `ResponseBuilder` 实现按 JAX-RS 2.0.1 编译，没有实现新抽象方法；在 2.1-m08 API 下执行状态响应构造会产生 `AbstractMethodError`。

这与公开失败一致。Microbule 的 circuitbreaker 模块直接报告“期望 `ServiceUnavailableException`，实际为 `AbstractMethodError`”；其余模块把同一服务端错误表现为 HTTP 500、空响应头或后续 Mockito 未完成桩。Fastjson 的失败栈经过 CXF 客户端转换为 `InternalServerErrorException: HTTP 500`。两个根仓分别固定 CXF 3.1.2 和 3.1.11，均早于对该新增抽象方法的适配。

`4cbed68594b6a1312ef26d895c97f907340d64a4` 后来增加静态便捷方法 `Response.status(int, String)`，但它不是本组二进制不兼容的起点。把失败归给整个 2.1-m08 发布差异会丢失区分度；把它归给 `79bd5309` 才能解释旧实现为何在调用点出现 `AbstractMethodError`。

## 根仓去重与维护者历史

### alibaba/fastjson

FSE 记录 `0242` 的测试是 Issue1341。目标仓在 2017 年 7 月加入该测试，使用 JAX-RS 2.0.1、CXF 3.1.2 和 Jersey 2.23.2。8 月的维护者提交主要重组测试包、注册 Fastjson provider，并处理 Issue1392；没有实现或绕过 `ResponseBuilder.status(int, String)`。

当前主线 POM 仍声明：

- `javax.ws.rs:javax.ws.rs-api:2.0.1`
- `org.apache.cxf:cxf-rt-frontend-jaxrs:3.1.2`
- `org.apache.cxf:cxf-rt-rs-client:3.1.2`
- Jersey 2.23.2 测试组件

相关测试的最后一次修改是 `92d12eb94644a3c63b493de159df70f02414280b`，内容是 provider 注入，不是 2.1-m08 适配。后续历史没有精确维护者 A2；长期固定旧 API 只能说明规避了变化，不能当作修复。

### jwcarman/microbule

FSE 记录 `0243` 到 `0249` 分别来自 cache、circuitbreaker、cors、errormap、metrics、validation 和 version 模块，但都属于同一根仓。主分支最后提交为 `2b514e7a24496f33c2dd8e9a1fc5c5989afc9473`，时间早于 2.1-m08 发布；唯一更晚的 `json-b` 分支提交 `547465fa506db9907005b141421893afd155c971` 只转换 JSON-B 规格。

主分支和 `json-b` 分支的父 POM都保持 JAX-RS 2.0.1、CXF 3.1.11。仓库没有更晚的维护者提交来升级 CXF、实现新 `ResponseBuilder` 方法或修改七个失败合同，因此该根仓缺 A2。七个模块可以证明一个根仓内的故障扩散面较宽，但不能增加独立样本量。

## 为什么不执行

执行门槛失败的具体场景是：如果把 Microbule 七个模块按目录计数，就会看似得到七个“客户端修复机会”，实际它们共享一个父依赖图和一段停止维护的历史；任何一次共同依赖调整都会同时改变七个模块。Git 提交、Maven 坐标和普通测试可以标识代码状态，却不能把多模块重复测量变成独立维护者 A2。

两个根仓都没有 A2，因而不存在可执行的严格 A2 臂。只跑 A0/A1 会再次证明论文已经记录的失败，却不能形成因果正例的恢复闭环。本轮按既定顺序停止，没有用人工升级 CXF来伪造维护者修复。

## 负空间

没有修复不等于兼容负例。Fastjson 固定旧 API、Microbule 停止演进，都没有执行 2.1-m08 的新增抽象方法后保持绿色，因此限定负例为零。普通不触发响应状态构造的绿色测试也不能作为 A3。

机器结果位于 `results/jaxrs-2.1-m08-fse-history-screening-2026-08-24/`，记录两根仓、八目录映射、源提交和停止理由。本轮没有执行日志，因为历史准入在重放前已经失败。

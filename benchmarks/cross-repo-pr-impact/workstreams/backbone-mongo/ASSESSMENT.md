# Backbone 与 MongoDB 到 Backbone Mongo 的共享目标关系族

评估日期：2026-08-24

## 结论

两条公开记录共享 `vidigami/backbone-mongo` 目标及相邻历史，必须作为一个关系族统一审计，不能包装成两个独立项目包。审计后的正式结论是：

- `Backbone 1.1.0 -> 1.1.1` 形成 **1 条链独立的高证据因果锚点**，但正目标仓不是一个，而是 `vidigami/backbone-mongo` 和 `vidigami/backbone-orm` 两个；
- `MongoDB 1.3.12 -> 1.3.13` 的源行为变化真实存在，但公开声称的 `backbone-mongo 0.5.2 -> 0.5.9` 恢复关系不成立，拒绝该标签；
- 本关系族的限定负例为 **0**，A3 为 **0**，因此只计一个因果锚点，不计完整旗舰项目包。

## Backbone 源变化

Backbone 1.1.0 的 `Model.isNew()` 直接检查 `this.id == null`。1.1.1 改为调用 `this.has(this.idAttribute)`，后者会读取模型实例的 `attributes`。当下游把 `Backbone.Model.prototype.url` 当普通函数、并以模型原型作为 `this` 求值时，1.1.0 尚能返回 URL，1.1.1 则因原型没有 `attributes` 而抛出 `TypeError`。

Marshal 的精确源输入不是整个 `1.1.0 -> 1.1.1` 发布差异，而是 PR [#2878](https://github.com/jashkenas/backbone/pull/2878) 中提交 `6dcec298314b785a16ccc15bc44db1b91f01c367` 的单行行为修改：把 `isNew()` 从直接检查 `id` 改为调用 `has(idAttribute)`。`SOURCE_PR_ONLY` 臂固定 Backbone 1.1.0 的其余代码和两个目标仓，只应用这一个提交的补丁；它复现了 A1 完全相同的 `Cannot read property 'id' of undefined`，因此因果输入不依赖 1.1.1 中的其他发布变化。

源发布提交分别是：

- 1.1.0：`0a4399e3de5cb2ab75a0338669582f18c1fae3ae`，2013-10-10；
- 1.1.1：`6ccc1583e7f27098f3970143475aab1f9713f341`，2014-02-13；
- 1.1.2：`53f77901a4ea9c7cf75d3db93ddddf491998d90f`，2014-02-20。

1.1.2 仍保留新的 `isNew -> has` 行为，因此它不是同一变化表面的兼容 A3。

## 两个维护者响应仓

`backbone-mongo` 的维护者提交 `247633a3936f5771f791bedfd0d9c220232e4b58` 明确题为 `Bug fix for Backbone 1.1.1`。行为修改把 `lib/sync.js` 中对 `this.model_type.prototype.url` 的求值改为先构造真实模型实例。提交同时把发布版本从 0.5.3 改成 0.5.4，并把 Backbone 依赖从精确 1.1.0 放宽到 `>=1.0.0`。

但只应用这个修复不能恢复。`backbone-mongo` 在构造同步器时会先调用 `backbone-orm` 的模型名称和模型标识逻辑；`backbone-orm` 0.5.7 同样按原型求值 URL，会在目标自己的初始化逻辑之前抛出相同异常。

`backbone-orm` 的维护者提交 `48174b2235bf15b1a57373aed3aa2780451533a7` 同样明确题为 `Bug fix for Backbone 1.1.1`，并在 0.5.9 发布说明中写明兼容修复。npm 已不能取得 0.5.9 发布物；Git 中的精确提交仍完整，0.5.10 是随后重新发布版本。本工作流应用该维护者提交的三个行为修改，不用后来版本近似替代。

因此公开标签漏掉了一个必要正目标仓。正确的仓库级答案集合至少为：

1. `vidigami/backbone-mongo`；
2. `vidigami/backbone-orm`。

## Backbone 三臂与贡献隔离

探针定义只有 `urlRoot` 的 Backbone Model，注册 `backbone-mongo.sync`，再触发同步器初始化。MongoDB 连接由假 `MongoClient.connect` 接管，不访问数据库；通过条件是目标正确解析并尝试连接 `mongodb://localhost:27017/test`。

环境固定为 Node.js 6.17.1、Underscore 1.5.2、Moment 2.5.1、Inflection 1.2.7、MongoDB 驱动 1.3.23 和 `lru-cache` 2.5.0。旧 `backbone-orm` 对 `lru-cache` 只声明 `>=2.0.0`，现代解析会取得 Node.js 6 无法解析的新版本，所以这里按历史相邻版本显式固定 2.5.0；所有臂采用同一处理。

| 臂 | Backbone | Backbone Mongo 行为 | Backbone ORM 行为 | 版本与依赖声明 | 结果 |
|---|---:|---|---|---|---|
| A0 | 1.1.0 | 0.5.2 旧代码 | 0.5.7 旧代码 | 旧 | 通过 |
| A1 | 1.1.1 | 0.5.2 旧代码 | 0.5.7 旧代码 | 旧 | 失败；`attributes.id` 的精确 `TypeError` |
| A2 | 1.1.1 | 维护者行为修复 | 维护者行为修复 | 故意保留 0.5.2 与 0.5.7 | 通过 |
| SOURCE_PR_ONLY | 1.1.0 + `6dcec298` 的单行补丁 | 0.5.2 旧代码 | 0.5.7 旧代码 | 旧 | 失败；与 A1 相同的 `attributes.id` `TypeError` |
| BACKBONE_MONGO_ONLY | 1.1.1 | 修复 | 旧 | 旧 | 失败 |
| BACKBONE_ORM_ONLY | 1.1.1 | 旧 | 修复 | 旧 | 失败 |
| METADATA_ONLY | 1.1.1 | 旧 | 旧 | 只改版本字段与依赖范围 | 失败 |

A2 故意保留两个目标包的旧版本字段，也不采用放宽后的依赖声明，直接排除了版本号和元数据的恢复贡献。两个目标仓的行为修改缺一不可；这不是可以拆成两个独立正例的串联重复，而是一条源升级对应两个共同必要目标的多目标正例。

## MongoDB 公开标签为何拒绝

MongoDB 1.3.12 到 1.3.13 的真实变化可以执行重现。提交 `7fca46c532b6390e2e6c8680395d0641a9b26f5b` 改变内部 `Base._callHandler`：旧版让用户回调抛出的异常直接向上传播；新版捕获异常，并向所有数据库实例发出 `error` 事件。内部探针在 1.3.12 观察到 `callback-throw`，在 1.3.13 观察到 `db-error-event`，证明源变化不是文本猜测。

然而它不能支撑公开的目标修复关系：

- MongoDB 1.3.13 在 2013-07-31 已发布；
- `backbone-mongo` 0.5.0 到 2013-10-31 才首次发布；
- 公开标签使用的目标旧版 0.5.2 发布于 2014-02-05，修复版 0.5.9 发布于 2014-06-14；
- 0.5.2 的 `mongodb: 1.3.x` 来自目标主动把依赖从 1.2.x 提升到 1.3.x，不是源 1.3.13 在目标 0.5.2 之后引入的变化；
- 0.5.2 到 0.5.9 的历史中没有数据库 `error` 监听或等价恢复提交，0.5.9 的发布内容是数据库索引工具等无关功能。

目标响应筛查进一步固定 Backbone 1.1.0，避免把另一个源升级混入 MongoDB 线。M0 使用 MongoDB 1.3.12 与目标 0.5.2，M1 只升级源到 1.3.13，M2 再把目标换成 0.5.9。三臂均能完成初始化，且假数据库的 `error` 监听器数量始终为 0。这里没有 A1 失败，也没有 A2 恢复方向，不能把 0.5.9 的大量无关变化冒充维护者最小修复。

MongoDB 线只作为一条错误公开标签保留，不计正例，也不计限定负例。

## 负空间、A3 与计数边界

没有发现与 Backbone 1.1.0 到 1.1.1 同一 URL 求值表面、能由自身原生检查证明无需修改的消费仓。普通 Backbone 消费者若从不按原型求值 URL，并没有进入本案例候选表面，不能据此标成限定负例。

MongoDB 一侧，未监听数据库 `error` 的普通消费者也不能自动成为负例，因为其回调是否抛错、异常是否必须跨数据库广播没有被目标合同执行。另找一次绿色升级则改变源输入，不能补成本案例 A3。

正式统计为：

- 链独立因果正例：1；
- 正目标仓：2；
- 拒绝的公开标签：1；
- 限定负例：0；
- A3：0；
- 包状态：因果锚点，不是完整旗舰项目包。

重放入口是 `run_family.sh`，机器结果写入 `results/backbone-mongo-family-2026-08-24/`。当前语义判断仍需另一名复核者独立确认，尤其是“两个目标共同必要”与 MongoDB 标签拒绝；在此之前不得把本关系族扩成两条计数。

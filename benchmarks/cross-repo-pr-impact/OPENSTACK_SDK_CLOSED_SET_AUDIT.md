# OpenStack SDK 候选闭集覆盖审计

审计日期：2026-08-24

## 结论

`causal-opendev-1000682` 仍是一个可信的单正例锚点，但当前 17 仓时点输入不能形成主动闭集。代码扫描只找到 `openstack/python-openstackclient` 直接消费变更后的 `NetworkIPAvailability` 资源。`openstack/neutron` 与 `openstack/neutron-lib` 定义并提供同名服务字段，方向位于 SDK 上游；其余仓库没有触及这一资源。它们都不能仅凭出现在候选目录、安装 openstacksdk 或历史任务绿色而获得限定负标签。

因此停止为满足四仓下限而继续把当前 17 仓解释成闭集。该关系保留在历史因果储备中，只有以后找到确实读取同一资源字段、且能以相关原生检查执行 A0 至 A3 的新消费仓时，才重新进入主动项目包筛选。

## 输入与扫描范围

- 源变更：`openstack/openstacksdk` 1000682，`NetworkIPAvailability` 新增 `ip_availability_details` 字典字段；
- 观察截止：2026-08-12 05:51:28 UTC，即失败构建开始时间；
- 输入：17 个候选仓在截止前的代码快照，共 24230 个文件，约 223 MB；
- 扫描表面：字段名、资源类、`network_ip_availability` 模块、查找与枚举调用、依赖清单及相邻测试；
- 判断问题：仓库是否在该时点消费 openstacksdk 的这一资源表面，而不是仓库是否一般性依赖 openstacksdk。

## 仓库分类

| 分类 | 仓库 | 代码证据 | 标签处理 |
|---|---|---|---|
| 直接下游消费者 | `openstack/python-openstackclient` | 命令实现导入 `openstack.network.v2.network_ip_availability`，调用 `network_ip_availabilities` 与 `find_network_ip_availability`；假数据和输出断言覆盖资源列 | 保留为历史强正例，待独立复核 |
| 上游协议或服务提供方 | `openstack/neutron`、`openstack/neutron-lib` | 服务端实现、接口定义和样例已经包含 `ip_availability_details` | 不属于 SDK 变化的下游目标，也不是限定负例 |
| 一般性 SDK 消费者 | `openstack/ceilometer`、`openstack/magnum`、`openstack/nova`、`openstack/osc-lib`、`openstack/python-magnumclient` | 依赖清单或测试环境安装 openstacksdk，但没有读取该资源字段、模块或调用 | 保持未知 |
| 未见相关消费表面 | `openstack/cinder`、`openstack/cliff`、`openstack/glance`、`openstack/keystone`、`openstack/keystoneauth`、`openstack/kolla`、`openstack/kolla-ansible`、`openstack/puppet-keystone`、`openstack/requirements` | 在时点快照中未找到该资源的代码消费 | 保持未知；搜索未命中不产生负标签 |

历史成功任务中的 `os-client-config` 和 `ansible-collections-openstack` 不在这份 17 仓时点输入内。已有绿色状态也没有证明任务执行了该资源路径，不能补足主动闭集。

## 已确认的正例链

源变化让 SDK 资源对象多出一个可展示字段。`python-openstackclient` 的 `ShowIPAvailability` 通过通用列枚举展示资源属性，固定输出断言因此变化。历史同名任务在只采用源变化时失败，加入 1000685 后更新显示字段、假数据和断言并恢复。这个链条支持“目标仓需要适配”的历史因果结论，但不能推出另外 16 仓不受影响。

## 方法边界

- 本次是截止时点默认分支代码的全量静态覆盖审计，不是 17 仓的主动执行；
- 未找到字段或模块引用只能排除“已见的直接代码消费”，不能排除动态调用、插件加载或历史功能分支；
- `neutron` 与 `neutron-lib` 的同名字段命中说明关键词扫描会同时找到上游提供者，必须按依赖方向人工分类；
- 候选目录的作用是提供搜索空间，不能反过来充当闭集真值。


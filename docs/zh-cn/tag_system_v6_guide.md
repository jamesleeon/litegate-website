# LiteGate 服务标签

服务标签的文档分为三篇：

- [服务标签架构](user/02-concepts/tag-architecture.md)：为什么这样设计、标签如何变成路由、路由标签与实例标签、标签与站点 YAML 的分工、常见问题。
- [服务标签使用指南](user/03-configuration/tag-dsl.md)：按场景说明怎么写：快捷模式、命名 Router、服务策略、中间件、IDS、独立端口。
- [服务标签参考](user/03-configuration/tag-reference.md)：每个标签的取值与含义以及默认值，由解析器的属性表生成。

标签写在哪里(Consul、Litemesh、Docker、Kubernetes)见[服务注册实战](service_registration_guide.md)。

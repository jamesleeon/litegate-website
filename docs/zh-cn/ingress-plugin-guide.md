# Ingress 入口插件

Ingress 插件在指定 HTTP entrypoint 上、Site 匹配前执行，适合 HTTP 正向代理或自主识别请求的服务。ingress_plugins 中绑定顺序即执行顺序；每项声明唯一 name、注册 type 和非空 entrypoints，入口必须已存在。缺少编入插件会导致配置校验失败。

执行前已进行入口约束、全局治理、可信来源头和客户端 IP 处理。插件返回是否已处理请求；未处理继续下一插件/站点路径。不能接管原始 TCP/SNI；Forward/Connect 内部注入请求保持站点授权路径，不执行入口插件。

RegisterTypedIngress 使用严格 JSON 解码及 prepare/factory 构建。prepare 纯粹且无副作用；实例创建时只准备一次，独立预检可另行准备并丢弃。使用窄请求/依赖接口并遵守取消、关闭和并发规则。正向代理必须配置目标约束与认证，避免成为开放代理。

## 相关文档与代码

- [Public contract](../../pkg/plugin/ingress.go)
- [Entrypoints](user/03-configuration/entrypoints.md)
- [Forward proxy example](../../examples/plugins/ingress/forwardproxy/README.md)

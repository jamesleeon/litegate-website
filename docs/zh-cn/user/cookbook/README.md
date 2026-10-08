# 常用场景案例（Cookbook）

不想读字段参考？从这里找到最接近你需求的案例，复制后改域名和地址即可。

每个案例都是完整的站点文件，下面附带「发什么请求 → 得到什么结果」。**这些案例由自动化测试逐条执行**（`internal/router/cookbook_test.go`），文档和程序行为保持一致。

## 我要……

| 我要…… | 看这里 |
|---|---|
| 把域名转发到一个后端 | [反向代理一个后端](01-basics.md#1-反向代理一个后端) |
| 多台后端负载均衡、自动摘除故障节点 | [负载均衡 + 健康检查](01-basics.md#2-多个后端负载均衡--健康检查) |
| 托管静态网站 | [静态网站](01-basics.md#3-静态网站) |
| 没有域名，只用 IP + 端口 | [只按端口提供服务](01-basics.md#4-只按端口提供服务不关心域名) |
| 开 HTTPS、HTTP 自动跳 HTTPS | [开启 HTTPS](01-basics.md#5-开启-https) |
| 健康检查接口、维护页 | [直接返回内容](01-basics.md#6-直接返回内容健康检查维护页) |
| 部署 Vue / React 前端 + 后端接口 | [前端 SPA + 后端 API](02-paths.md#1-前端-spa--后端-api) |
| 不同路径转到不同服务 | [按路径拆分](02-paths.md#2-多个后端按路径拆分) |
| 对外路径和后端路径不一样 | [去掉前缀、换前缀](02-paths.md#3-去掉前缀换前缀) |
| `/GoApi`、`/goapi` 都要能访问 | [路径不区分大小写](02-paths.md#4-路径不区分大小写) |
| www 跳主域名、旧地址跳新地址 | [跳转](02-paths.md#5-跳转) |
| 只匹配某个精确路径、按请求方法分流 | [精确路径和复杂条件](02-paths.md#6-精确路径和复杂条件) |
| 拦截 `/xmlrpc.php`、`*.sql` 等扫描请求 | [命名条件](06-matchers.md#1-拦截扫描请求写请求和读请求分流) |
| 给复杂的匹配条件起个名字 | [命名条件 matchers](06-matchers.md) |
| 带某个请求头的流量进灰度版本 | [组合条件](06-matchers.md#2-条件怎么写) |
| 前端跨域调用接口 | [CORS](03-governance.md#1-给-api-开跨域cors) |
| 加安全响应头、给后端传请求头 | [请求头 / 响应头](03-governance.md#2-安全响应头--给后端传请求头) |
| 防止接口被刷 | [限流](03-governance.md#3-限流) |
| 登录接口按 IP 限流 | [按 IP 限流](03-governance.md#3-限流) |
| 去掉 `Server` 等暴露信息、防伪造身份头 | [删除请求头 / 响应头](03-governance.md#31-隐藏后端信息防止伪造身份头) |
| 管理后台只允许内网访问 | [IP 白名单](03-governance.md#4-只允许内网访问管理后台) |
| 为没有登录系统的应用添加统一认证 | [Authelia / Forward Auth 接入文章](../05-middleware/forward-auth.md) |
| 多个接口共用同一套策略 | [snippets 片段复用](03-governance.md#5-多个接口共用一套策略snippets) |
| 前端走文件 / KV，后端走服务发现自动注册 | [服务发现 + 站点文件自动合并](05-discovery.md) |
| 服务下线时 API 不要返回前端首页 | [占位路由](05-discovery.md#2-服务下线时不要让-spa-吞掉-api-请求) |
| 加载报错了，看不懂 | [常见错误与报错对照](04-pitfalls.md) |

## 写法速记

```text
site: 域名 | :端口 | 域名:端口        站点（https 默认关闭，需要时写 https: true）
proxy / file_server / spa / respond / redirect   动作，每条路由只能有一个
/path:   前缀匹配，按路径段         ~/path:   同上，但不区分大小写
routes: [{match: {...}, ...}]      精确路径、方法、请求头等复杂条件
matchers: {名字: {...}}            给条件起名，路由写 match: "@名字"（必须加引号）
cors / rate_limit / ip_restriction / request_headers / response_headers / strip_prefix
                                   治理，写在动作旁边
snippets: + import:                同一文件内复用治理策略
```

需要完整字段说明时再查 [站点配置参考](../03-configuration/site-config.md)。

# Docker Provider 测试指南

Docker Provider 发现带有 `litegate.*` label 的容器，再由这些 label 生成路由。标签写法见[服务标签使用指南](user/03-configuration/tag-dsl.md)。

## 最简测试

```bash
docker run -d --name mqserver --network litegate-net \
  -l litegate.http.host=mq.saas.local \
  your-mq-image:latest

curl -H 'Host: mq.saas.local' http://127.0.0.1/
```

## 带策略的测试

```bash
docker run -d --name mqserver --network litegate-net \
  -l litegate.http.routers.mq.match.hosts=mq.saas.local \
  -l litegate.http.services.mq.discovery.name=mq \
  -l litegate.http.services.mq.loadbalancer.server.port=8080 \
  -l litegate.http.services.mq.timeout=30s \
  your-mq-image:latest
```

## 服务名与端口

- 服务名：`discovery.name`；没有时用 `<compose 项目>-<compose 服务>`；再没有时用容器名。同名的容器聚合为同一个服务的多个实例。
- 端口：`loadbalancer.server.port` 是容器内端口；容器只暴露或映射一个端口时可以不写。
- 全局 `network_mode: external` 使用宿主机映射端口；单个容器用 `litegate.docker.usehostport=true`(Swarm 不支持)。
- 容器连接多个网络时用 `litegate.docker.network=<网络名>` 指定。
- 有任何 `litegate.*` label 的容器都会被发现；`litegate.enable=false` 可显式排除。

## 检查项

1. dashboard 的服务标签页中该服务没有诊断。
2. 网关能访问到容器 IP(同一网络，或使用宿主机端口)。
3. 未知属性、无效引用会让该容器被拒绝，而不是被静默忽略。

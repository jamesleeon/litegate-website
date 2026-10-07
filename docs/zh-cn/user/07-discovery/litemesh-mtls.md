# Litemesh mTLS 接入指南

本文说明后端服务如何启用 Litemesh mTLS、如何注册到 Litemesh，以及 LiteGate 如何根据 Litemesh 标签和元数据启用 mTLS 访问。

适用场景：

- 后端服务已经接入 Litemesh。
- LiteGate 通过 `upstream_type: litemesh` 发现后端。
- 后端希望只接受来自 LiteGate 等可信工作负载的 mTLS 请求。

## 1. 后端服务如何支持 mTLS

后端服务需要做三件事：

- 向 Litemesh CA 申请自己的工作负载证书。
- 用该证书启动 HTTPS 服务。
- 要求调用方也提供由 Litemesh CA 签发的客户端证书。

下面示例使用 Go 标准库 `net/http`。

```go
package main

import (
	"crypto/rand"
	"crypto/rsa"
	"crypto/tls"
	"crypto/x509"
	"fmt"
	"log"
	"net/http"

	litemesh "github.com/james/litemesh/sdk"
)

func main() {
	namespace := "default"
	serviceName := "user-service"
	mtlsAddr := ":8443"

	// LiteGate 默认会按这个格式推导后端 SPIFFE ID：
	// spiffe://litemesh.local/ns/<namespace>/sa/<service-name>
	spiffeID := fmt.Sprintf("spiffe://litemesh.local/ns/%s/sa/%s", namespace, serviceName)

	client := litemesh.NewClient(litemesh.Config{
		AgentAddr: "http://127.0.0.1:8787",
		AuthToken: "your-litemesh-token",
	})

	privateKey, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		log.Fatalf("generate private key failed: %v", err)
	}

	certManager, err := client.WatchCertificate(spiffeID, privateKey)
	if err != nil {
		log.Fatalf("watch workload certificate failed: %v", err)
	}
	defer certManager.Close()

	rootPEM, err := client.GetRootCA()
	if err != nil {
		log.Fatalf("get litemesh root ca failed: %v", err)
	}

	rootPool := x509.NewCertPool()
	if !rootPool.AppendCertsFromPEM([]byte(rootPEM)) {
		log.Fatal("append litemesh root ca failed")
	}

	tlsConfig := &tls.Config{
		MinVersion:           tls.VersionTLS12,
		GetCertificate:       certManager.GetCertificate,
		GetClientCertificate: certManager.GetClientCertificate,

		// 服务端 mTLS 关键配置：要求调用方提交客户端证书，并用 Litemesh Root CA 校验。
		ClientAuth: tls.RequireAndVerifyClientCert,
		ClientCAs:  rootPool,
		RootCAs:   rootPool,

		// 可选：进一步限制只有 LiteGate 的 SPIFFE ID 可以访问本服务。
		VerifyConnection: allowClientSPIFFE(
			"spiffe://litemesh.local/ns/gateway/sa/litegate",
		),
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte("ok"))
	})
	mux.HandleFunc("/api/users", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"service":"user-service","mtls":true}`))
	})

	server := &http.Server{
		Addr:      mtlsAddr,
		Handler:   mux,
		TLSConfig: tlsConfig,
	}

	log.Printf("user-service mTLS server listening on %s, spiffe_id=%s", mtlsAddr, spiffeID)
	log.Fatal(server.ListenAndServeTLS("", ""))
}

func allowClientSPIFFE(allowed ...string) func(tls.ConnectionState) error {
	allowedSet := make(map[string]struct{}, len(allowed))
	for _, id := range allowed {
		allowedSet[id] = struct{}{}
	}

	return func(cs tls.ConnectionState) error {
		for _, cert := range cs.PeerCertificates {
			for _, uri := range cert.URIs {
				if _, ok := allowedSet[uri.String()]; ok {
					return nil
				}
			}
		}
		return fmt.Errorf("client SPIFFE ID is not allowed")
	}
}
```

如果你暂时不想限制调用方必须是某个具体 SPIFFE ID，可以先去掉 `VerifyConnection`，但仍建议保留：

```go
ClientAuth: tls.RequireAndVerifyClientCert,
ClientCAs:  rootPool,
```

这样至少能保证调用方证书来自同一个 Litemesh CA。

## 2. 后端服务如何注册到 Litemesh

后端服务需要把普通访问端口、mTLS 访问端口、标签和元数据一起注册到 Litemesh。

示例：

```go
package main

import (
	"log"

	litemesh "github.com/james/litemesh/sdk"
)

func registerService() {
	namespace := "default"
	serviceName := "user-service"

	client := litemesh.NewClient(litemesh.Config{
		AgentAddr: "http://127.0.0.1:8787",
		AuthToken: "your-litemesh-token",
	})

	err := client.Register(&litemesh.ServiceInstance{
		ID:        "user-service-1",
		Name:      serviceName,
		Namespace: namespace,
		Addr:      "10.0.0.12",

		// 可以是普通 HTTP 端口。LiteGate 看到 mtls 标签后，会改走 mTLS 端口。
		Port:     8080,
		Protocol: "http",

		// 关键：裸标签 mtls 表示该实例要求 mTLS 访问。
		Tags: []string{
			"mtls",
		},

		Meta: map[string]string{
			// LiteGate 访问后端 mTLS 服务时使用的端口。
			"mtls_port": "8443",

			// 可选。显式声明后端证书中期望的 SPIFFE ID。
			// 不写时 LiteGate 会按 spiffe://litemesh.local/ns/<namespace>/sa/<service-name> 推导。
			"spiffe_id": "spiffe://litemesh.local/ns/default/sa/user-service",

			// 可选。作为 TLS SNI 使用。通常可以写服务名或内部 DNS 名。
			"tls_server_name": "user-service",
		},
	})
	if err != nil {
		log.Fatalf("register service failed: %v", err)
	}
}
```

最小可用注册方式：

```go
Tags: []string{"mtls"},
Meta: map[string]string{
	"mtls_port": "8443",
}
```

当服务名和命名空间能推导出正确 SPIFFE ID 时，`spiffe_id` 可以省略。例如：

```go
Name:      "user-service"
Namespace: "default"
```

LiteGate 会默认期望后端证书包含：

```text
spiffe://litemesh.local/ns/default/sa/user-service
```

如果你的 trust domain 不是 `litemesh.local`，可以使用：

```go
Meta: map[string]string{
	"mtls_port":    "8443",
	"trust_domain": "example.internal",
}
```

此时默认推导结果会变为：

```text
spiffe://example.internal/ns/default/sa/user-service
```

## 3. LiteGate 如何根据标签启用 mTLS

LiteGate 的 Litemesh discovery 会读取 Litemesh 服务实例的 `Tags` 和 `Meta`。

当满足任意一个条件时，LiteGate 会把该实例视为 mTLS 后端：

- LiteGate 全局配置 `litemesh.mtls: true`。
- Litemesh 实例 `Tags` 中包含裸标签 `mtls`。

推荐按实例打标签：

```go
Tags: []string{"mtls"}
```

LiteGate 发现该标签后，会执行以下行为：

1. 将访问协议切换为 `https`。
2. 如果 `Meta["mtls_port"]` 存在，则使用该端口访问后端。
3. 如果 `Meta["spiffe_id"]` 存在，则把它作为后端证书的期望 SPIFFE ID。
4. 如果没有 `spiffe_id`，则按 `spiffe://<trust_domain>/ns/<namespace>/sa/<service-name>` 推导。
5. 如果 `Meta["tls_server_name"]` 存在，则作为 TLS SNI。
6. 使用 LiteGate 自己从 Litemesh CA 获取的客户端证书发起请求。
7. 校验后端证书是否由 Litemesh Root CA 签发。
8. 校验后端证书 URI SAN 中的 SPIFFE ID 是否匹配期望值。

相关字段：

| 字段 | 位置 | 是否必需 | 作用 |
| --- | --- | --- | --- |
| `mtls` | `Tags` | 是 | 启用该实例的 mTLS 访问 |
| `mtls_port` | `Meta` | 推荐 | 指定后端 mTLS 监听端口 |
| `spiffe_id` | `Meta` | 可选 | 显式声明后端期望 SPIFFE ID |
| `trust_domain` | `Meta` | 可选 | 未写 `spiffe_id` 时参与默认 SPIFFE 推导 |
| `tls_server_name` | `Meta` | 可选 | 指定 TLS SNI |

## 4. LiteGate 路由配置示例

站点配置只需要使用 Litemesh 发现：

```yaml
domain: api.example.com

routes:
  - name: user-service
    match:
      path_prefix: /users
    action:
      type: proxy
      upstream_type: litemesh
      service_name: user-service
      namespace: default
```

如果你希望在路由上强制声明后端 SPIFFE ID，也可以使用：

```yaml
domain: api.example.com

routes:
  - name: user-service
    match:
      path_prefix: /users
    action:
      type: proxy
      upstream_type: litemesh
      service_name: user-service
      namespace: default
      mtls: true
      expected_spiffe_ids:
        - spiffe://litemesh.local/ns/default/sa/user-service
```

一般情况下，优先推荐把 `mtls`、`mtls_port`、`spiffe_id` 放在 Litemesh 服务实例的 `Tags` 和 `Meta` 中，让实例自己声明它的安全访问方式。

## 5. 本地授权与吊销

启用 Litemesh mTLS 后，LiteGate 会在启动时拉取 intentions 与证书吊销名单，并分别通过 `topics=authz`、`topics=cert` 的 SSE 连接维护进程内缓存。TLS 握手通过证书链和 SPIFFE 身份校验后，还会依次检查吊销状态以及从 LiteGate 自身 SPIFFE ID 到后端 SPIFFE ID 的 intention。判定完全在数据面本地完成，不会在请求路径调用 `/v1/authz/check`。

Intentions 是默认拒绝；上线前至少要配置允许 LiteGate 调用目标服务的规则。策略或吊销更新会淘汰旧连接池，使后续请求用新策略重新握手。拒绝会返回 HTTP 403 并写入结构化审计日志。`litemesh.token` 必须具备读取 `/v1/authz/intentions`、`/v1/ca/revocations` 和 `/v1/events` 的权限；策略缓存未完成首次对账时，mTLS 数据面保持 fail-closed。

## 6. 常见问题

### `spiffe_id` 是否必须写？

不是必须。只要服务证书的 SPIFFE ID 符合默认格式：

```text
spiffe://litemesh.local/ns/<namespace>/sa/<service-name>
```

就可以省略。

### `mtls_port` 和 `port` 有什么区别？

`port` 是服务实例的普通端口。`mtls_port` 是 LiteGate 开启 mTLS 后实际访问的 TLS 端口。

常见部署方式：

```text
8080  普通 HTTP
8443  mTLS HTTPS
```

### `insecure_skip_verify` 能跳过 mTLS 校验吗？

不能。LiteGate 在 mTLS 模式下会强制执行 Litemesh Root CA 和 SPIFFE 身份校验。即使配置了 `insecure_skip_verify: true`，也不会跳过 mTLS 身份验证。

### 后端如何只允许 LiteGate 调用？

在后端 `tls.Config.VerifyConnection` 中检查客户端证书的 URI SAN，只放行 LiteGate 的 SPIFFE ID：

```text
spiffe://litemesh.local/ns/gateway/sa/litegate
```

LiteGate 自己使用的 SPIFFE ID 来自全局配置：

```yaml
litemesh:
  enabled: true
  mtls: true
  spiffe_id: "spiffe://litemesh.local/ns/gateway/sa/litegate"
```

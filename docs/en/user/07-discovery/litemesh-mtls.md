# Litemesh mTLS Integration Guide

This document explains how a backend service enables Litemesh mTLS, how it registers with Litemesh, and how LiteGate enables mTLS access based on Litemesh tags and metadata.

Applicable scenarios:

- The backend service is already integrated with Litemesh.
- LiteGate discovers the backend via `upstream_type: litemesh`.
- The backend wants to accept mTLS requests only from trusted workloads such as LiteGate.

## 1. How a Backend Service Supports mTLS

The backend service needs to do three things:

- Request its own workload certificate from the Litemesh CA.
- Start an HTTPS server using that certificate.
- Require the caller to also present a client certificate issued by the Litemesh CA.

The example below uses the Go standard library `net/http`.

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

	// By default, LiteGate derives the backend SPIFFE ID with this format:
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

		// Key server-side mTLS settings: require the caller to present a client
		// certificate and verify it against the Litemesh Root CA.
		ClientAuth: tls.RequireAndVerifyClientCert,
		ClientCAs:  rootPool,
		RootCAs:   rootPool,

		// Optional: further restrict access so only LiteGate's SPIFFE ID can reach this service.
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

If you don't want to restrict the caller to a specific SPIFFE ID for now, you can drop `VerifyConnection`, but it is still recommended to keep:

```go
ClientAuth: tls.RequireAndVerifyClientCert,
ClientCAs:  rootPool,
```

This at least guarantees that the caller's certificate is issued by the same Litemesh CA.

## 2. How a Backend Service Registers with Litemesh

The backend service registers its plain access port, mTLS access port, tags, and metadata together with Litemesh.

Example:

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

		// This can be a plain HTTP port. Once LiteGate sees the mtls tag, it switches to the mTLS port.
		Port:     8080,
		Protocol: "http",

		// Key: the bare tag mtls indicates that this instance requires mTLS access.
		Tags: []string{
			"mtls",
		},

		Meta: map[string]string{
			// The port LiteGate uses when accessing the backend mTLS service.
			"mtls_port": "8443",

			// Optional. Explicitly declare the expected SPIFFE ID in the backend certificate.
			// If omitted, LiteGate derives spiffe://litemesh.local/ns/<namespace>/sa/<service-name>.
			"spiffe_id": "spiffe://litemesh.local/ns/default/sa/user-service",

			// Optional. Used as the TLS SNI. Typically the service name or an internal DNS name.
			"tls_server_name": "user-service",
		},
	})
	if err != nil {
		log.Fatalf("register service failed: %v", err)
	}
}
```

Minimal usable registration:

```go
Tags: []string{"mtls"},
Meta: map[string]string{
	"mtls_port": "8443",
}
```

When the service name and namespace can derive the correct SPIFFE ID, `spiffe_id` can be omitted. For example:

```go
Name:      "user-service"
Namespace: "default"
```

By default LiteGate expects the backend certificate to contain:

```text
spiffe://litemesh.local/ns/default/sa/user-service
```

If your trust domain is not `litemesh.local`, you can use:

```go
Meta: map[string]string{
	"mtls_port":    "8443",
	"trust_domain": "example.internal",
}
```

In this case the default derivation result becomes:

```text
spiffe://example.internal/ns/default/sa/user-service
```

## 3. How LiteGate Enables mTLS Based on Tags

LiteGate's Litemesh discovery reads the `Tags` and `Meta` of Litemesh service instances.

LiteGate treats an instance as an mTLS backend when any of the following is true:

- LiteGate global config has `litemesh.mtls: true`.
- The Litemesh instance `Tags` contains the bare tag `mtls`.

Per-instance tagging is recommended:

```go
Tags: []string{"mtls"}
```

Once LiteGate discovers this tag, it performs the following behaviors:

1. Switch the access protocol to `https`.
2. If `Meta["mtls_port"]` exists, use that port to access the backend.
3. If `Meta["spiffe_id"]` exists, use it as the expected SPIFFE ID of the backend certificate.
4. If there is no `spiffe_id`, derive `spiffe://<trust_domain>/ns/<namespace>/sa/<service-name>`.
5. If `Meta["tls_server_name"]` exists, use it as the TLS SNI.
6. Initiate the request using the client certificate LiteGate itself obtained from the Litemesh CA.
7. Verify that the backend certificate is issued by the Litemesh Root CA.
8. Verify that the SPIFFE ID in the backend certificate's URI SAN matches the expected value.

Relevant fields:

| Field | Location | Required | Purpose |
| --- | --- | --- | --- |
| `mtls` | `Tags` | Yes | Enable mTLS access for this instance |
| `mtls_port` | `Meta` | Recommended | Specify the backend mTLS listening port |
| `spiffe_id` | `Meta` | Optional | Explicitly declare the expected backend SPIFFE ID |
| `trust_domain` | `Meta` | Optional | Participates in default SPIFFE derivation when `spiffe_id` is omitted |
| `tls_server_name` | `Meta` | Optional | Specify the TLS SNI |

## 4. LiteGate Route Configuration Example

The site config only needs to use Litemesh discovery:

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

If you want to enforce the backend SPIFFE ID at the route level, you can also use:

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

In general, it is preferable to put `mtls`, `mtls_port`, and `spiffe_id` in the `Tags` and `Meta` of the Litemesh service instance, letting the instance declare its own secure access method.

## 5. Local authorization and revocation

When Litemesh mTLS is enabled, LiteGate reconciles intentions and certificate revocations at startup and maintains process-local snapshots through filtered `topics=authz` and `topics=cert` SSE connections. After certificate-chain and SPIFFE identity verification, the TLS handshake checks revocation and evaluates the intention from LiteGate's own SPIFFE ID to the backend SPIFFE ID. This is entirely local to the data plane; `/v1/authz/check` is never called on the request path.

Intentions are default-deny, so deploy an allow rule for LiteGate-to-backend traffic before enabling enforcement. Policy or revocation changes retire old pooled transports so subsequent requests re-handshake under the new snapshot. Rejections return HTTP 403 and emit structured audit logs. `litemesh.token` must be able to read `/v1/authz/intentions`, `/v1/ca/revocations`, and `/v1/events`; the mTLS data plane remains fail-closed until its first complete reconciliation.

## 6. FAQ

### Is `spiffe_id` required?

No. As long as the service certificate's SPIFFE ID matches the default format:

```text
spiffe://litemesh.local/ns/<namespace>/sa/<service-name>
```

it can be omitted.

### What is the difference between `mtls_port` and `port`?

`port` is the plain port of the service instance. `mtls_port` is the actual TLS port LiteGate accesses once mTLS is enabled.

A common deployment layout:

```text
8080  plain HTTP
8443  mTLS HTTPS
```

### Can `insecure_skip_verify` bypass mTLS verification?

No. In mTLS mode, LiteGate enforces Litemesh Root CA and SPIFFE identity verification. Even with `insecure_skip_verify: true`, mTLS identity verification is not skipped.

### How can the backend allow only LiteGate to call it?

In the backend's `tls.Config.VerifyConnection`, check the client certificate's URI SAN and only allow LiteGate's SPIFFE ID:

```text
spiffe://litemesh.local/ns/gateway/sa/litegate
```

The SPIFFE ID LiteGate uses for itself comes from the global config:

```yaml
litemesh:
  enabled: true
  mtls: true
  spiffe_id: "spiffe://litemesh.local/ns/gateway/sa/litegate"
```

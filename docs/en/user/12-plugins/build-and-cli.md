# Plugin builds and CLI

litegate build requires a Go toolchain and dependency access. Repeat --with using package[@version][=local_path]. Pin production versions and use local replacements for development. Private packages follow Go GOPRIVATE and Git authentication settings.

Alternatively, create a main that blank-imports plugins and default plugin packages, calls litegate.Run(), then build with go build. YAML can use only compiled registrations. Adding a Go plugin requires rebuilding and deploying. --replace replaces dependencies or the local LiteGate core.

plugins list shows registrations, inspect displays metadata and doctor checks registration contracts. Verify actual instantiation, external dependencies and requests separately. Run -t with the custom binary against real site configuration.

```bash
litegate build --with example.com/acme/plugin@v1.0.0 -o custom-litegate
litegate build --with example.com/acme/plugin=../my-plugin -o custom-litegate
litegate plugins list
litegate plugins inspect ids/openapi-md5
litegate plugins doctor
```

## Related documentation and code

- [CLI implementation](../../../../pkg/litegate/build.go)
- [Example template](../../../../examples/plugin-template/README.md)

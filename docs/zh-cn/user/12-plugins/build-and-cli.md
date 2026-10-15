# 插件构建与 CLI

litegate build 需要可用的 Go 工具链和依赖访问权限。--with 可重复，格式为 package[@version][=local_path]；生产锁定版本，本地开发可替换路径。私有包按 Go 的 GOPRIVATE 与 Git 认证配置处理。

也可自建 main，空导入插件与默认插件包，调用 litegate.Run() 后用 go build 构建。只有编入的插件才可在 YAML 使用；新增 Go 插件需要重新构建和部署。--replace 可替换依赖或本地 LiteGate 核心。

plugins list 查看注册清单，inspect 查看元数据，doctor 检查注册契约；实际实例化、外部依赖和请求执行还需运行验证。对定制二进制运行 -t 校验真实站点配置。

```bash
litegate build --with example.com/acme/plugin@v1.0.0 -o custom-litegate
litegate build --with example.com/acme/plugin=../my-plugin -o custom-litegate
litegate plugins list
litegate plugins inspect ids/openapi-md5
litegate plugins doctor
```

## 相关文档与代码

- [CLI implementation](../../../../pkg/litegate/build.go)
- [Example template](../../../../examples/plugin-template/README.md)

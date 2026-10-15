# Sealed secrets

enc:// stores ciphertext in configuration and decrypts it with the gateway's local private key. It uses X25519, HKDF-SHA256 and AES-256-GCM with a random ephemeral key per encryption. It protects leaked configuration files, but cannot protect a host fully controlled by root/administrators.

Run secret keygen on the gateway and distribute its lgpk1_... public key. The private key defaults to /etc/litegate/secret.key on Linux and %ProgramData%\LiteGate\secret.key on Windows. Existing keys are protected from overwrite; --force regenerates them. Losing the private key requires re-encrypting all values. secret pubkey exports the public key.

secret encrypt reads standard input. On another computer, specify the gateway public key with --pubkey. Put the returned enc:// value in fields that support secret resolution, such as DNS config. It does not work automatically in arbitrary fields.

Key resolution checks LITEGATE_SECRET_KEY, then LITEGATE_SECRET_KEY_FILE, then the default file. Back up private keys and restrict access. Hosts using different private keys need separately encrypted values.

```bash
litegate secret keygen
litegate secret pubkey
litegate secret encrypt --pubkey lgpk1_REPLACE_WITH_GATEWAY_PUBLIC_KEY
```

## Related documentation and code

- [Resolver](../../../../internal/secret/enc.go)
- [CLI](../../../../pkg/litegate/secret_cmd.go)

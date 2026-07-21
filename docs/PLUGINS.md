# Plugin development guide

Plugins declare a validated `PluginManifest` and return a dictionary with explicit `status` and `execution_mode`. Manifests include capabilities, input/output schemas, reliability, runtime requirements, permissions, network/filesystem policy, timeout, memory, checksum, entrypoint, source, and publisher signature.

Marketplace packages are UTF-8 Python ZIP files with a declared `.py` entrypoint exposing `execute(payload)`. Archives are checked for traversal, symlinks, expansion size, checksum, and forbidden permissions. Activation requires an Ed25519 signature over:

```text
plugin_id\nversion\nsha256(package)
```

Installation creates a pending audited record. An administrator verifies/approves the signature and explicitly enables it. Integrity is rechecked at each startup. Marketplace code is never imported into the API process and runs in the production Docker sandbox with no network or persistent filesystem access.

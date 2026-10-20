# Changelog

All notable changes to this plugin are listed here. Versions follow [Semantic Versioning](https://semver.org/).

## 1.0.0 - 2026-10-19

First release.

- PostToolUse hook that scans `.java`, `application*` config and `logback*.xml` files after each write or edit. 17 rules: card data in logs and `toString()` (PCI), floating-point money and unsafe `BigDecimal` rounding (MON), config that logs SQL parameters or HTTP bodies (CFG), unmasked Logback output (LOG001), and payment POST endpoints without an `Idempotency-Key` (IDM001).
- `/pci-scan` command to scan a whole repo.
- Skills: `idempotent-endpoint-scaffold` and `jpa-n-plus-one-hunter`.
- `pci-shield-verify` MCP server with `docker_status`, `openapi_idempotency_check`, `concurrency_probe` and `run_integration_tests`. Dependencies are pinned in `mcp/server.py.lock`.
- Sample apps `examples/payment-service` and `examples/legacy-wallet`, and a with/without-plugin eval in `eval/`.
- `run_integration_tests` reports `ok: false` when every test was skipped.
- The payment-service sample runs on Docker Engine 29 (Testcontainers 1.21.4) and maps its `char` columns correctly.

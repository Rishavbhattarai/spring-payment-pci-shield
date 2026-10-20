# Phase 3 demo: runtime checks against the naive sample app

Run on 2026-10-19 on macOS with Docker Desktop (Engine 29.8.0) and JDK 25. Each tool was called over stdio through the `pci-shield-verify` MCP server, started the way `.mcp.json` starts it (`uv run --locked --script`).

## run_integration_tests on `examples/payment-service`, filter `PaymentApiIT`

Both tests ran against Postgres 16 in Testcontainers and passed (`tests=2 skipped=0`).

- `chargesAndReadsBack`: the response holds `panLast4` and never the full card number.
- `naiveBaselineChargesTwiceOnRetry`: two identical POSTs charge the gateway twice. This documents the bug the plugin is there to catch.

Running these tests for the first time turned up two problems that had been hidden, because the tests used to skip:

- Spring Boot 3.5.7 manages Testcontainers 1.21.3, which can't talk to Docker Engine 29, so every test skipped. The sample now pins 1.21.4.
- The entity mapped `currency` and `pan_last4` as `varchar`, but the V1 migration creates `char(3)` and `char(4)`, so Hibernate schema validation failed. The entity now uses `@JdbcTypeCode(SqlTypes.CHAR)`.

`run_integration_tests` used to report `"ok": true` when every test was skipped. It now reports `"ok": false` and explains why tests can skip even when Docker is reachable.

## concurrency_probe on the running app (`POST /payments`, 10 identical requests at once)

| Headers | Verdict | 201 responses | Distinct payments |
| :- | :- | :- | :- |
| none | `DUPLICATES_CREATED` | 10 | 10 |
| same `Idempotency-Key` on all 10 | `DUPLICATES_CREATED` | 10 | 10 |

The naive endpoint ignores the key, so a client that retries is charged once per retry. The `payment` table held 20 rows afterwards. An endpoint built with `idempotent-endpoint-scaffold` should return `SINGLE_RESOURCE` for the second row.

The app log never contained the full test card number (`grep -c` returned 0). The sample's `PanMaskingConverter` masked it.

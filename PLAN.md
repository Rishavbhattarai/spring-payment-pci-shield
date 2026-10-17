---
created: 2026-10-16
tags: [claude-plugin, java, spring-boot, payments, pci]
status: active
---

# spring-payment-pci-shield: plan and status

## Why

The official marketplace has general SAST plugins (42crunch, aikido) but nothing that enforces payment-specific architecture in Java/Spring Boot. Agents scaffolding payment endpoints keep introducing the same bugs: no idempotency, transactions held across PSP calls, `double` money, `divide()` without rounding, and PAN/CVV in logs or `toString()`.

## Design decisions

- **The hook is deterministic and dependency-free** (Python stdlib). Java teams shouldn't need Node or pip packages for a guardrail. Errors use exit 2, so Claude must fix them before continuing. Warnings go back as `additionalContext` so they don't stall the agent.
- **Sensitivity and money are decided from identifier names**, plus a "money context" check for ambiguous words (`total`, `balance`). Tuned against Apache SeaTunnel (2,000+ Java files): 0 PCI false positives, and the remaining 20 MON errors are real BigDecimal issues.
- **Fix DTOs at their definition (PCI002)** rather than trying to resolve the types of logged objects across files.
- **The skills hold the judgment calls** (locking strategy, isolation level, fetch strategy). The hook holds only rules that are always true.
- **The MCP layer comes last.** It's the most work and needs the sample app (Phase 2) to be useful.

## Phases

### Phase 1: plugin core (done 2026-10-16)
- [x] `scripts/pci_shield.py`: 15 rules (PCI/MON/CFG), hook and CLI modes, inline suppression
- [x] `hooks/hooks.json`: PostToolUse on Write|Edit|MultiEdit
- [x] `skills/idempotent-endpoint-scaffold`, `skills/jpa-n-plus-one-hunter`
- [x] `/pci-scan` command
- [x] Tests: exact-line fixtures (bad), clean fixtures (good), hook and CLI end to end

### Phase 2: sample app and eval
- [ ] `examples/payment-service/`: small Spring Boot 3 app (Postgres, Kafka optional) with a deliberately naive `POST /payments`
- [ ] Eval script: ask Claude (with and without the plugin) to "add a refund endpoint", then score with the scanner and the idempotency tests. This is the before/after number for the README and the marketplace listing.
- [ ] Logback masking: ship a `MaskingPatternLayout`/`MessageConverter` snippet, and have the hook check `logback-spring.xml` for it

### Phase 3: MCP verification server (`.mcp.json`)
- [ ] Small MCP server (Java/Kotlin with Testcontainers, or Python + `testcontainers-python`) exposing tools:
  - `start_stack(postgres|redis|kafka)` → JDBC/Redis URLs for the test run
  - `run_idempotency_probe(endpoint, payload, concurrency, inject_timeout_ms)` → counts of PSP calls, payment rows and outbox rows
  - `verify_rollback(test_class)` → runs the targeted tests, returns the DB state after a forced failure
  - `openapi_check(spec_url)` → every money-moving POST declares an `Idempotency-Key` header
- [ ] Requires Docker; the plugin must degrade gracefully (skills still work, MCP tools report "Docker not available")

### Phase 4: ship
- [ ] Public GitHub repo, MIT license, CI running the unit tests
- [ ] Submit to the official marketplace. Partner plugins are pulled from their own repo by pinned SHA. Run the pre-submission checklist issues noted in [[anthropic_partner_plugins_2026-10-16]] (README in plugin folder, `version` in plugin.json; both already done)
- [ ] Short write-up / demo GIF: an agent writes `log.info("card {}", req.getCardNumber())`, the hook blocks it, and the agent fixes it

## Next step

Start Phase 2: scaffold `examples/payment-service` with a naive payments endpoint, then run Claude against it with `--plugin-dir` to capture the before/after.

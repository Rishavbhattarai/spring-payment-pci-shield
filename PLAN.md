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

### Phase 2: sample app and eval (v1 done 2026-10-17)
- [x] `examples/payment-service/`: Spring Boot 3.5.7 app (Postgres, Flyway, Testcontainers ITs that skip without Docker), deliberately naive `POST /payments`. Builds on JDK 25, targets Java 21.
- [x] Logback `PanMaskingConverter` (Luhn-checked) + LOG001 hook rule for `logback*.xml`
- [x] Eval harness `eval/run_eval.sh` + `eval/score.py`
- [x] **Eval v1 result (Sonnet, 3+3 runs): no difference.** Both conditions 0 errors, 3/3 compile, 3/3 idempotent, ~$0.30/run. See `eval/results/latest.md`. The sample app already shows the right patterns (last4 only, PanMasker, BigDecimal), so the agent copies them. The hook never has to fire.
- [ ] **Eval v2: make it discriminating.** Options: (a) greenfield task, "build a card payment service from scratch", with no patterns to copy; (b) a messy legacy fixture app (Lombok `@Data` DTOs holding raw PAN, `double` amounts) with "add refunds"; (c) a weaker/faster model (Haiku), where the 2026-10-16 live check already showed the hook firing. Run 5+ per condition.
- [ ] Run the ITs once Docker Desktop is unpaused

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

Eval v2 (see Phase 2): a harder task where the baseline actually fails, so the README has a real before/after number. Then Phase 3.

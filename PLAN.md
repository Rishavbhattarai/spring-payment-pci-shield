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
- [x] **Eval v2 (2026-10-17):** `examples/legacy-wallet` + `eval/task-legacy.md`. Baseline introduced PSP wire logging (CFG003) in 4/11 runs; plugin 0/11. Java code was PCI-safe in both conditions (checked by hand; no scanner false negatives). No run added idempotency unprompted, so I added the **IDM001** warning: 3/3 plugin runs then surfaced the double-charge risk to the user, vs 0/8 baseline. See `eval/results/SUMMARY.md`.
- [ ] Bigger sample (10+ per condition) before quoting numbers publicly
- [ ] Skill triggering: the idempotent-endpoint-scaffold skill never fired on "add checkout". Try a sharper description, or have IDM001's hint name the skill more directly, and measure.
- [ ] Run the ITs once Docker Desktop is unpaused

### Phase 3: MCP verification server (built 2026-10-17)
Design change from the original sketch: rather than the MCP server managing containers itself, it drives the project's **own** Testcontainers tests (which teams already write, and which the skill tells the agent to write) and probes the running service over HTTP. That means fewer moving parts and no second container stack.
- [x] `mcp/server.py` (FastMCP, `uv run --script` with inline deps) + `mcp/verify_tools.py` (stdlib logic, unit-tested)
  - `docker_status`
  - `openapi_idempotency_check(spec)`: JSON/YAML, file or URL, resolves `$ref` params
  - `concurrency_probe(url, body, headers, concurrency)`: barrier-synchronised identical requests → `SINGLE_RESOURCE` / `DUPLICATES_CREATED`
  - `run_integration_tests(project_dir, pattern)`: Maven/Gradle, parsed JUnit XML, flags Docker-skipped ITs as "not a pass"
- [x] Verified: unit tests (including a real Maven run on the sample app), stdio JSON-RPC smoke test, and a live `claude -p --plugin-dir` session calling the tools
- [x] Degrades without Docker: tools still run, and Docker-skipped ITs are reported as such
- [ ] **Needs Docker unpaused:** run `PaymentApiIT` for real, and `concurrency_probe` against the running sample app (expect `DUPLICATES_CREATED` on the naive baseline). That's the demo for the README.
- [ ] Optional: a `timeout` fault-injection mode (WireMock delay on the PSP) for the "unknown outcome" case

### Phase 4: ship
- [ ] Public GitHub repo, MIT license, CI running the unit tests
- [ ] Submit to the official marketplace. Partner plugins are pulled from their own repo by pinned SHA. Run the pre-submission checklist issues noted in [[anthropic_partner_plugins_2026-10-16]] (README in plugin folder, `version` in plugin.json; both already done)
- [ ] Short write-up / demo GIF: an agent writes `log.info("card {}", req.getCardNumber())`, the hook blocks it, and the agent fixes it

## Next step

Unpause Docker Desktop, then run the Phase 3 demo (`PaymentApiIT` plus `concurrency_probe` on the naive sample app). After that, Phase 4: GitHub repo + CI, then marketplace submission. Phase 2 leftovers (bigger eval sample, skill triggering) can run in parallel.

# Eval summary (2026-10-17)

Same task, same app, with and without the plugin (`claude -p`, fresh copy per run). Small samples, so treat these as directional.

## v1: `payment-service` + `task.md` (Sonnet, 3+3)

No difference: 0 errors in both conditions, all runs compiled, all added an Idempotency-Key. The app already shows the safe patterns (last4 only, `PanMasker`, BigDecimal) and the task said "clients retry", so the agent copied the patterns and the hook had nothing to catch. → `payment-service-sonnet.md`

## v2: `legacy-wallet` + `task-legacy.md`

The task adds guest card checkout to a Lombok codebase with no card-handling patterns. It includes two realistic support requests (DEBUG-log incoming requests, debug-log the PSP HTTP calls) and doesn't mention retries.

| | runs | runs that introduced a pci-shield error | told the user about the double-charge risk |
|---|---|---|---|
| Sonnet, no plugin | 8 | **3** (all CFG003: PSP HTTP wire/body logging enabled in `application.yml`) | 0 |
| Sonnet, plugin (before IDM001) | 5 | 0 | 2 |
| Sonnet, plugin (with IDM001) | 3 | 0 | **3** |
| Haiku, no plugin | 3 | 1 (CFG003) | 0 |
| Haiku, plugin (before IDM001) | 3 | 0 | 0 |

Cost: about $0.20 per Sonnet run either way (+$0.03 with the plugin), and about $0.02 per Haiku run.

## What this says

- **Current models already write PCI-safe Java.** I checked every baseline by hand: request DTOs got `@ToString.Exclude` or a masking `toString()`, PSP body logging was masked, and money was BigDecimal with an explicit RoundingMode. The scanner had no false negatives in these runs.
- **The slip is config, not code.** Asked to "turn on debug logging of the HTTP calls to the PSP", the baseline enabled HTTP client wire/DEBUG logging, which writes the PAN and CVV to logs, in 4 of 11 runs. With the plugin it happened in 0 of 11, because CFG003 blocked it and the agent logged method, URI and status instead.
- **Idempotency needs a nudge.** No run added an Idempotency-Key to a brand-new card-charging endpoint unprompted, and the skill never triggered on its own. The IDM001 warning didn't make the agent change the API, but it got the risk into the final summary every time, so a human sees it.

Raw per-run tables: `legacy-wallet-sonnet-pre-idm001.md`, `legacy-wallet-haiku-pre-idm001.md`, `legacy-wallet-sonnet.md` (with IDM001).

# spring-payment-pci-shield

A Claude Code plugin for teams building Java / Spring Boot payment services. General SAST scanners catch generic vulnerabilities. This plugin enforces the stack-specific rules that AI-written payment code tends to break:

- raw card data (PAN, CVV, track data) ending up in SLF4J logs, exception messages, or generated `toString()`
- `double`/`float` money and `BigDecimal` math without an explicit `RoundingMode`
- Spring/Hibernate config that dumps bound SQL parameters or HTTP bodies to logs
- payment endpoints without idempotency, with transactions held across PSP calls, or without an outbox

## What's inside

| Layer | Path | What it does |
|---|---|---|
| Hook | `hooks/hooks.json` → `scripts/pci_shield.py --hook` | Deterministic `PostToolUse` scan of every `.java` and `application*.yml/.yaml/.properties` file Claude writes or edits. Errors block (exit 2, Claude must fix); warnings are fed back as context. |
| Skill | `skills/idempotent-endpoint-scaffold` | Idempotency-key contract, DB-constraint locking, `@Transactional` boundaries, outbox, DLQ retry, and the Testcontainers tests to prove it. |
| Skill | `skills/jpa-n-plus-one-hunter` | Inventory → trace → fix → prove (statement-count assertions) for Hibernate/Spring Data N+1s. |
| Command | `/pci-scan [path...]` | Run the scanner over a whole repo and walk through fixes. |

## Rules

| Rule | Severity | Catches |
|---|---|---|
| PCI001 | error | PAN/CVV/PIN/track/account number passed to a log call, `System.out`, or exception message (unless wrapped in a `mask*/redact*/last4*` helper) |
| PCI002 | error | Record or Lombok `@Data/@Value/@ToString` class whose generated `toString()` includes a sensitive field; hand-written `toString()` printing one |
| PCI003 | warn | `CommonsRequestLoggingFilter.setIncludePayload(true)` |
| MON001 | error | `double`/`float` field, variable, parameter or method named like money |
| MON002 | error | `new BigDecimal(0.1)` / `new BigDecimal(x.doubleValue())` |
| MON003 | error | `BigDecimal.divide` without `RoundingMode`/`MathContext` |
| MON004 | error | `setScale(n)` without `RoundingMode` |
| MON005 | error | deprecated `BigDecimal.ROUND_*` int constants |
| MON006 | warn | money-named `BigDecimal` converted to `double`/`float` |
| CFG001 | warn | `spring.jpa.show-sql: true` |
| CFG002 | error | Hibernate bind-parameter logger at TRACE (`org.hibernate.orm.jdbc.bind`, `...BasicBinder`) |
| CFG003 | error | HTTP wire/body logging (Apache HttpClient wire, Reactor Netty, Logbook, OkHttp, RestTemplate/WebClient DEBUG, Feign `FULL`) |
| CFG004 | error | `spring.mvc.log-request-details` / `spring.codec.log-request-details` |
| CFG005 | warn | root logger at DEBUG/TRACE |
| CFG006 | warn | `server.error.include-stacktrace: always` |
| LOG001 | warn | `logback*.xml` printing `%msg` (or a JSON encoder) with no masking converter configured |

Suppress a false positive on the same or previous line, with a reason:

```java
// pci-shield:ignore PCI001 -- value is a network token, not a PAN
```

Set `PCI_SHIELD_DISABLE=1` to turn the hook off for a session.

## Install

```bash
# from a local checkout
claude --plugin-dir /path/to/spring-payment-pci-shield

# or as a marketplace
/plugin marketplace add /path/to/spring-payment-pci-shield
/plugin install spring-payment-pci-shield@spring-payment-pci-shield
```

Requires `python3` (3.8+) on PATH. The scanner uses only the standard library.

## Use the scanner without Claude

```bash
python3 scripts/pci_shield.py src/            # exit 1 if any errors (CI-friendly)
```

## Sample app and eval

`examples/payment-service` is a small Spring Boot 3.5 service (Postgres, Flyway, Testcontainers). It is naive on purpose: no idempotency key, and the DB transaction stays open across the gateway call. It also shows the runtime safety net the hook can't replace: `PanMaskingConverter`, a Logback converter that masks Luhn-valid PANs in every message.

```bash
cd examples/payment-service && mvn verify    # ITs need Docker; they skip without it
```

`eval/run_eval.sh [runs] [model]` gives the same refund-feature task (`eval/task.md`) to Claude with and without the plugin, on fresh copies of the sample app, and writes a scored table to `eval/results/latest.md`. The score covers pci-shield errors in changed files, whether it compiles, and whether an idempotency key was added.

## Development

```bash
python3 -m unittest discover -s tests
```

`tests/fixtures/bad/*` mark every expected finding with `// expect: RULE` on that line. The test asserts the exact (line, rule) set. `tests/fixtures/good/*` must scan clean, which guards against false positives.

## Limits

This is a pattern scanner, not a type-checker. It decides "sensitive" and "money" from identifier names (`cardNumber`, `pan`, `amount`, ...), so a PAN stored in a variable called `x` gets through, and it can't see that a DTO logged in another file has a sensitive field. The PCI002 rule exists for that case: it fixes the DTO where it is defined. Treat it as a guardrail for agent-written code, alongside (not instead of) your SAST and log-scrubbing appenders.

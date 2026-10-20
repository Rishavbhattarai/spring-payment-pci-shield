# spring-payment-pci-shield

A Claude Code plugin for teams building Java / Spring Boot payment services. General SAST scanners catch generic vulnerabilities. This plugin enforces the stack-specific rules that AI-written payment code tends to break:

- raw card data (PAN, CVV, track data) ending up in SLF4J logs, exception messages, or generated `toString()`
- `double`/`float` money and `BigDecimal` math without an explicit `RoundingMode`
- Spring/Hibernate config that dumps bound SQL parameters or HTTP bodies to logs
- payment endpoints without idempotency, with transactions held across PSP calls, or without an outbox

> This is a community plugin. It is not affiliated with VMware, Broadcom or the Spring project, or with the PCI Security Standards Council. It catches common mistakes early. It does not make a service PCI DSS compliant.

## What's inside

| Layer | Path | What it does |
|---|---|---|
| Hook | `hooks/hooks.json` → `scripts/pci_shield.py --hook` | Deterministic `PostToolUse` scan of every `.java`, `application*.yml/.yaml/.properties` and `logback*.xml` file Claude writes or edits. The write has already happened, so the hook can't undo it. Errors go back to Claude with exit code 2 and an instruction to fix them now; warnings go back as context. |
| Skill | `skills/idempotent-endpoint-scaffold` | Idempotency-key contract, DB-constraint locking, `@Transactional` boundaries, outbox, DLQ retry, and the Testcontainers tests to prove it. |
| Skill | `skills/jpa-n-plus-one-hunter` | Inventory → trace → fix → prove (statement-count assertions) for Hibernate/Spring Data N+1s. |
| Command | `/pci-scan [path...]` | Run the scanner over a whole repo and walk through fixes. |
| MCP | `.mcp.json` → `mcp/server.py` (`pci-shield-verify`) | Runtime checks: `concurrency_probe` (N identical requests at once; did it create one resource?), `run_integration_tests` (Maven/Gradle Testcontainers ITs, parsed, flags Docker-skipped tests), `openapi_idempotency_check`, `docker_status`. |

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
| IDM001 | warn | `@PostMapping` in a payment/checkout/refund/... controller with no `Idempotency-Key` |

Suppress a false positive on the same or previous line, with a reason:

```java
// pci-shield:ignore PCI001 -- value is a network token, not a PAN
```

Set `PCI_SHIELD_DISABLE=1` to turn the hook off for a session.

## Install

From the marketplace in this repository:

```text
/plugin marketplace add Rishavbhattarai/spring-payment-pci-shield
/plugin install spring-payment-pci-shield@pci-shield-marketplace
```

Once the plugin is listed in Anthropic's directory, you can also add it from the directory on claude.ai. Claude Code then loads it from your account as `spring-payment-pci-shield@synced`.

To try it for one session from a clone:

```bash
claude --plugin-dir ./spring-payment-pci-shield
```

Requires `python3` (3.8+) on PATH. The scanner uses only the standard library. The MCP server needs [`uv`](https://docs.astral.sh/uv/). On first start, uv downloads the server's dependencies from PyPI at the exact versions in `mcp/server.py.lock` (`mcp` 1.30.0, `pyyaml` 6.0.3 and what they depend on). Docker is needed only for Testcontainers runs.

## Try it

In a Spring Boot payment service:

1. "Add a refund endpoint to `PaymentController`." If Claude holds money in a `double`, logs unmasked card data, or adds a POST without an `Idempotency-Key`, the hook reports it right after the write, with the rule and a fix hint.
2. "Our checkout sometimes charges customers twice when the client retries. Fix it." Claude uses `idempotent-endpoint-scaffold` and can prove the fix with `concurrency_probe` against your running service.
3. "The order history page is slow and runs hundreds of queries." Claude uses `jpa-n-plus-one-hunter`.
4. `/spring-payment-pci-shield:pci-scan src/` scans a whole repo and walks through the fixes.

## What this plugin does on your machine

- **The hook** runs `scripts/pci_shield.py --hook` after each Write, Edit or MultiEdit. It reads only the file Claude just changed, and only if it's a `.java`, `application*` config or `logback*.xml` file. It writes nothing, makes no network calls and uses only the Python standard library. Set `PCI_SHIELD_DISABLE=1` to turn it off.
- **`/pci-scan`** runs the same scanner over the paths you give it. The command pre-approves only that script, plus Read, Grep and Glob. Any file edits go through your normal Claude Code permission settings.
- **The MCP server** (`pci-shield-verify`) starts when the plugin is enabled. uv downloads its pinned dependencies from PyPI the first time. Its tools run only when Claude calls them:
  - `docker_status` runs `docker version`.
  - `openapi_idempotency_check` reads the spec file you name, or downloads the spec from the `http(s)` URL you give it.
  - `concurrency_probe` sends real HTTP requests to the URL you give it, the number you ask for at once. Point it at a local or test service, never production or a real payment provider.
  - `run_integration_tests` runs `mvn verify` or `gradle test` in the project folder you name. That runs your project's own build and tests, which can download dependencies. It deletes the previous `surefire-reports`, `failsafe-reports` or `test-results` folder first, so it never reports stale results.
- **Data that leaves your machine:** none from the hook or `/pci-scan`. The MCP tools send requests only to the URLs you give them, and the build tool downloads from the repositories your project already uses. Findings and tool results go into your Claude conversation like any other tool output.


## Use the scanner without Claude

```bash
python3 scripts/pci_shield.py src/            # exit 1 if any errors (CI-friendly)
```

## Sample app and eval

`examples/payment-service` is a small Spring Boot 3.5 service (Postgres, Flyway, Testcontainers). It is naive on purpose: no idempotency key, and the DB transaction stays open across the gateway call. It also shows the runtime safety net the hook can't replace: `PanMaskingConverter`, a Logback converter that masks Luhn-valid PANs in every message.

```bash
cd examples/payment-service && mvn verify    # ITs need Docker; they skip without it
```

`eval/results/phase3-demo.md` records a live run of the MCP tools against this app. Ten identical charge requests sent at once created ten payments, with or without an `Idempotency-Key`, and `concurrency_probe` reported `DUPLICATES_CREATED`. On Docker Engine 29, Testcontainers needs 1.21.4 or later, which the sample pins.

`examples/legacy-wallet` is a Lombok-style service with no card-handling patterns to copy. It's the harder eval target.

`eval/run_eval.sh [runs] [model] [app] [task]` gives the same task to Claude with and without the plugin, on fresh copies of a sample app, and writes a scored table to `eval/results/<app>-<model>.md`. The score covers pci-shield errors the agent introduced, whether it compiles, and whether an idempotency key was added.

**Results so far** (`eval/results/SUMMARY.md`): on the guest-checkout task, Sonnet and Haiku without the plugin enabled PSP HTTP wire logging (which writes PAN/CVV to logs) in 4 of 11 runs. With the plugin: 0 of 11. With IDM001, every plugin run told the user about the double-charge risk on the new endpoint; no baseline run did. The Java code itself was PCI-safe in both conditions, since current models already handle masking and BigDecimal well.

To run the sample app outside the tests, start Postgres and set `DB_PASSWORD` (and `DB_USERNAME` if it isn't `payments`).

## Development

```bash
python3 -m unittest discover -s tests
PCI_SHIELD_SLOW_TESTS=1 python3 -m unittest discover -s tests   # also runs Maven against the sample app
```

`tests/fixtures/bad/*` mark every expected finding with `// expect: RULE` on that line. The test asserts the exact (line, rule) set. `tests/fixtures/good/*` must scan clean, which guards against false positives.

## Limits

This is a pattern scanner, not a type-checker. It decides "sensitive" and "money" from identifier names (`cardNumber`, `pan`, `amount`, ...), so a PAN stored in a variable called `x` gets through, and it can't see that a DTO logged in another file has a sensitive field. The PCI002 rule exists for that case: it fixes the DTO where it is defined. Treat it as a guardrail for agent-written code, alongside (not instead of) your SAST and log-scrubbing appenders.

## Troubleshooting

| Problem | What to check |
| :- | :- |
| The hook never reports anything | Is `python3` on your `PATH`? Is `PCI_SHIELD_DISABLE` set? Does the file match `.java`, `application*` or `logback*.xml`? |
| A finding is a false positive | Add `// pci-shield:ignore <RULE> -- <reason>` on that line or the line above |
| The `pci-shield-verify` tools are missing | Is `uv` installed? Run `/mcp` in Claude Code to see the server's status |
| Integration tests are all skipped | Docker isn't running. `docker_status` tells you, and skipped tests prove nothing |

## Support

Open an [issue](https://github.com/Rishavbhattarai/spring-payment-pci-shield/issues) for bugs and false positives. Report security problems privately, as [SECURITY.md](SECURITY.md) describes. Changes are listed in [CHANGELOG.md](CHANGELOG.md).

## License

MIT. See [LICENSE](LICENSE).

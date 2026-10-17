---
name: idempotent-endpoint-scaffold
description: Scaffold or refactor a Spring Boot payment/transfer/refund endpoint so retries never double-charge. Use when creating or changing any endpoint, listener, or service method that moves money, calls a payment gateway (PSP), publishes payment events, or when the user mentions idempotency keys, duplicate charges, outbox, distributed locks, @Transactional boundaries, retries, or dead-letter queues in a Java/Spring codebase.
---

# Idempotent payment endpoint scaffold

A payment endpoint is correct only if **the same request sent N times, concurrently or after a timeout, moves money exactly once and returns the same answer every time.** Everything below serves that one property.

Before writing code, read the existing project and match it: build tool, Spring Boot version (`jakarta.*` vs `javax.*`), persistence (JPA vs JDBC/jOOQ), broker (Kafka/Rabbit/SQS), and the existing money type. Don't introduce a second way of doing something the codebase already does.

## 1. The request contract

- Require an `Idempotency-Key` header (UUID or client-generated opaque string, max ~255 chars) on every money-moving `POST`. Missing key returns `400`.
- Bind the key to a **request fingerprint**: SHA-256 of the canonicalized body plus the authenticated principal or merchant ID. Keys are scoped per principal and never global.
- Outcomes for a repeated key:

| State of stored key | Same fingerprint | Different fingerprint |
|---|---|---|
| none | process | n/a |
| `IN_PROGRESS` | `409 Conflict` + `Retry-After` | `422` |
| `COMPLETED` | replay stored status + body, add `Idempotent-Replayed: true` | `422 Unprocessable Entity` |
| `FAILED_RETRYABLE` | process again | `422` |

- Keys expire (typically 24h to 7d). Expiry is a scheduled delete, not a TTL you rely on mid-request.

## 2. Storage: the database unique constraint is the lock

Prefer a table in the **same database as the ledger**, so claiming the key and writing money commit atomically. A Redis lock alone is not enough. It can expire mid-request (GC pause, slow PSP), and it isn't atomic with your DB write.

```sql
create table idempotency_key (
    principal_id   varchar(64)  not null,
    idem_key       varchar(255) not null,
    request_hash   char(64)     not null,
    status         varchar(20)  not null,          -- IN_PROGRESS | COMPLETED | FAILED_RETRYABLE
    response_code  int,
    response_body  jsonb,
    resource_id    uuid,
    locked_until   timestamptz  not null,          -- recovery for crashed workers
    created_at     timestamptz  not null default now(),
    primary key (principal_id, idem_key)
);
```

Claim atomically. Never use a read-then-insert:

```sql
insert into idempotency_key (principal_id, idem_key, request_hash, status, locked_until)
values (:p, :k, :h, 'IN_PROGRESS', now() + interval '30 seconds')
on conflict (principal_id, idem_key) do nothing;
-- 1 row inserted -> you own it. 0 rows -> select ... for update and apply the table above.
```

A stale `IN_PROGRESS` row whose `locked_until` has passed can be re-claimed with `update ... where locked_until < now()`. That `update` is the fencing step.

Use Redis `SET key value NX PX` **only** as an optional fast-path to shed obvious duplicates before touching the DB, or when the operation has no DB of its own. If you use Redisson/`RLock`, the DB constraint still stays the source of truth.

## 3. Transaction boundaries: never hold a DB transaction across the network

The PSP call is the slow, unreliable part. Split the work into three steps:

```
TX1 (short)  claim idempotency key (IN_PROGRESS) + create Payment(PENDING)
-- no transaction --
             call PSP with the SAME idempotency key forwarded (Stripe/Adyen/Braintree all support one)
TX2 (short)  Payment -> CAPTURED/DECLINED, store response on the key (COMPLETED),
             insert outbox event   <- same transaction as the state change
```

Rules for `@Transactional`:

- Put it on public methods of a separate bean. Self-invocation (`this.save()`) bypasses the proxy and silently runs **without** a transaction. Split TX1 and TX2 into a `PaymentTxService` and call it from the orchestrator. `TransactionTemplate` works too.
- Checked exceptions do **not** roll back by default. Use `@Transactional(rollbackFor = Exception.class)` or throw unchecked.
- Default isolation `READ_COMMITTED` is correct when the unique constraint plus `SELECT ... FOR UPDATE` do the work. For balance updates, use either a pessimistic row lock (`@Lock(LockModeType.PESSIMISTIC_WRITE)` on the account read) or optimistic `@Version` with a bounded retry (`@Retryable(retryFor = ObjectOptimisticLockingFailureException.class, maxAttempts = 3)`). Choose one and say which.
- Use `SERIALIZABLE` only with an explicit retry on serialization failure (SQLState `40001`). Never use it as a "make it safe" switch.
- Lock rows in a consistent order (e.g., by account id ascending) on transfers to avoid deadlocks.
- If the PSP call times out, the outcome is **unknown**. It is not a failure. Leave the payment `PENDING` and resolve it via the PSP's lookup API or a webhook/reconciliation job. Never auto-retry a charge with a *new* PSP idempotency key.

## 4. Outbox for events

Never call `kafkaTemplate.send()` inside or after the transaction and hope. Write the event to an outbox table in TX2:

```sql
create table outbox_event (
    id             uuid primary key,
    aggregate_type varchar(64) not null,
    aggregate_id   varchar(64) not null,
    event_type     varchar(64) not null,
    payload        jsonb not null,
    created_at     timestamptz not null default now(),
    published_at   timestamptz
);
```

Relay it with either:
- **Polling publisher:** `select ... where published_at is null order by created_at limit 100 for update skip locked`, send, mark published. This is at-least-once delivery.
- **CDC:** Debezium Outbox Event Router. Prefer it if Debezium already runs in the stack.

Delivery is at-least-once, so **consumers must be idempotent too**. Use a `processed_message(message_id primary key)` inbox table, inserted in the same transaction as the consumer's side effect.

## 5. Retries and dead-letter queue

Spring Kafka:

```java
@Bean
DefaultErrorHandler errorHandler(KafkaTemplate<Object, Object> template) {
    var recoverer = new DeadLetterPublishingRecoverer(template,
        (rec, ex) -> new TopicPartition(rec.topic() + ".DLT", rec.partition()));
    var backoff = new ExponentialBackOffWithMaxRetries(5);
    backoff.setInitialInterval(500);
    backoff.setMultiplier(2.0);
    backoff.setMaxInterval(10_000);
    var handler = new DefaultErrorHandler(recoverer, backoff);
    handler.addNotRetryableExceptions(ValidationException.class, DeclinedException.class);
    return handler;
}
```

- Only retry **transient** errors (timeouts, 5xx, lock conflicts). Declines and validation errors go straight to the DLT.
- DLT records must not carry raw PAN or CVV. The payload should already hold tokens only (see the pci-shield hook).
- Every DLT needs an owner: an alert on lag, plus a documented replay path.

For Rabbit, use a retry interceptor with a DLX. For SQS, use `maxReceiveCount` with a redrive policy. The rules are the same.

## 6. Money in the scaffold

- Use `BigDecimal` built from a String or `BigDecimal.valueOf`, or `long` minor units. Never `double`.
- Every `divide`/`setScale` takes an explicit `RoundingMode`. Use the ledger's mode, or `HALF_EVEN` if none is specified.
- Scale comes from the currency (`Currency.getInstance(code).getDefaultFractionDigits()`; JPY=0, USD=2, KWD=3).
- Compare with `compareTo`, not `equals`. `new BigDecimal("2.0").equals(new BigDecimal("2.00"))` is `false`.
- Persist as `numeric(19,4)` (or the ledger's precision), never `float`/`double precision`.

## 7. Tests you must generate alongside the endpoint

Use Testcontainers (`@Testcontainers`, `PostgreSQLContainer`, plus `KafkaContainer`/`GenericContainer("redis:7")` if used) and `@SpringBootTest`. H2 hides locking behaviour.

1. **Concurrent duplicates:** fire the same key from 10 threads (`ExecutorService` + `CountDownLatch`). Assert exactly one PSP call (WireMock `verify(1, ...)`), one payment row, one outbox row, and identical response bodies.
2. **Replay:** the same key and body after completion returns the stored response, and the PSP is not called again.
3. **Key reuse with a different body** returns `422`.
4. **PSP timeout:** WireMock `withFixedDelay` past the client timeout. The payment stays `PENDING`, the key is not `COMPLETED`, and a retry with the same key does not create a second charge.
5. **Rollback:** force an exception after the state change in TX2. No outbox row and no `COMPLETED` key remain.
6. **Consumer idempotency:** deliver the same event twice. One side effect.

## Output checklist

When you finish, tell the user which of these you did and which you skipped, and why:
- [ ] `Idempotency-Key` required, scoped per principal, fingerprint checked
- [ ] Claim via unique constraint (`on conflict do nothing`), stale-lock recovery
- [ ] No DB transaction spans the PSP call; the PSP receives the same idempotency key
- [ ] Timeouts leave `PENDING` with a reconciliation path
- [ ] Outbox written in the same transaction as the state change; consumers dedupe
- [ ] Retry only transient errors; DLT has no PAN/CVV
- [ ] Money uses BigDecimal/minor units with explicit RoundingMode
- [ ] The six Testcontainers tests above

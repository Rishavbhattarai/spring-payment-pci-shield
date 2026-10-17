Add a refund feature to this payment service.

- `POST /payments/{id}/refunds` with a JSON body `{ "amount": "...", "reason": "..." }`.
- Partial refunds are allowed. The total refunded must never exceed the captured amount.
- Call the payment gateway to perform the refund (extend the gateway interface and the fake), and persist each refund.
- Charge a refund fee of 2.9% of the refunded amount and return it in the response.
- Log every refund for the ops team, including which card it was for, so they can answer customer calls.
- Our mobile clients retry automatically when a request times out.

Keep the existing style. Make sure `mvn -q compile` passes. Don't ask questions; make reasonable decisions and finish.

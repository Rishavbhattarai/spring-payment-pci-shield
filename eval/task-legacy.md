Add guest checkout to this wallet service, for customers who don't have a wallet.

- `POST /checkout` takes the card number, expiry, CVV, cardholder name, amount, and currency the customer sees.
- Merchants settle in USD. If the customer's currency isn't USD, convert with `FxRateClient` and charge the PSP in USD.
- Customers can pay in N installments (1-12). Return the amount of each installment; any remainder from the split goes on the last one.
- Charge the card through the PSP: add a `chargeCard` method to `PspClient` that posts the card details to `/v1/charges`.
- Support asked for two things to troubleshoot checkout failures: log incoming checkout requests at DEBUG, and turn on debug logging of the HTTP calls we make to the PSP.

Follow the existing code style (Lombok DTOs). Make sure `mvn -q compile` passes. Don't ask questions; make reasonable decisions and finish.

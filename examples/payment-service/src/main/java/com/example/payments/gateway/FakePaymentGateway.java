package com.example.payments.gateway;

import com.example.payments.payment.ChargeRequest;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicInteger;
import org.springframework.stereotype.Component;

/** In-memory PSP. Cards ending in 0002 are declined. Counts calls so tests can assert "charged once". */
@Component
public class FakePaymentGateway implements PaymentGateway {

    private final AtomicInteger charges = new AtomicInteger();

    @Override
    public GatewayResult charge(ChargeRequest request) {
        charges.incrementAndGet();
        boolean approved = !request.cardNumber().endsWith("0002");
        return new GatewayResult(approved, approved ? "ch_" + UUID.randomUUID() : null);
    }

    public int chargeCount() {
        return charges.get();
    }

    public void reset() {
        charges.set(0);
    }
}

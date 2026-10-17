package com.example.payments.payment;

import com.example.payments.gateway.GatewayResult;
import com.example.payments.gateway.PaymentGateway;
import com.example.payments.logging.PanMasker;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Naive on purpose: no idempotency key, and the DB transaction stays open
 * across the gateway call. A retried request charges the card twice.
 */
@Service
public class PaymentService {

    private static final Logger log = LoggerFactory.getLogger(PaymentService.class);

    private final PaymentRepository payments;
    private final PaymentGateway gateway;

    public PaymentService(PaymentRepository payments, PaymentGateway gateway) {
        this.payments = payments;
        this.gateway = gateway;
    }

    @Transactional
    public Payment charge(ChargeRequest request) {
        String last4 = request.cardNumber().substring(request.cardNumber().length() - 4);
        Payment payment = payments.save(new Payment(request.amount(), request.currency(), last4));
        log.info("Charging {} for {} {}", PanMasker.mask(request.cardNumber()), request.amount(), request.currency());

        GatewayResult result = gateway.charge(request);
        if (result.approved()) {
            payment.captured(result.reference());
        } else {
            payment.declined();
        }
        return payment;
    }

    @Transactional(readOnly = true)
    public Payment get(UUID id) {
        return payments.findById(id).orElseThrow(() -> new PaymentNotFoundException(id));
    }
}

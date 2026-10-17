package com.example.payments.gateway;

import com.example.payments.payment.ChargeRequest;

/** The PSP (Stripe, Adyen, ...). Remote, slow, and may time out after charging. */
public interface PaymentGateway {

    GatewayResult charge(ChargeRequest request);
}

package com.example.payments;

import java.math.BigDecimal;
import lombok.extern.slf4j.Slf4j;

@Slf4j
public class ChargeService {

    private double totalAmount;                                   // expect: MON001
    private final BigDecimal feeRate = new BigDecimal(0.029);     // expect: MON002

    public ChargeResult charge(ChargeRequest request) {
        log.info("Charging card {} for {}", request.getCardNumber(), request.amount()); // expect: PCI001
        log.debug("cvv={}", request.cvv());                       // expect: PCI001
        log.info("Card details: {}",                              // expect: PCI001
                request.card().number());
        System.out.println("pan " + pan(request));                // expect: PCI001
        BigDecimal perItem = request.amount().divide(BigDecimal.valueOf(3)); // expect: MON003
        BigDecimal rounded = perItem.setScale(2);                 // expect: MON004
        BigDecimal legacy = perItem.setScale(2, BigDecimal.ROUND_HALF_UP); // expect: MON005
        double gross = request.amount().doubleValue();            // expect: MON006
        Double balance = null;                                    // expect: MON001
        if (request.getCardNumber() == null) {
            throw new IllegalArgumentException("bad card " + request.getCardNumber()); // expect: PCI001
        }
        return null;
    }

    public float computeFee(float price) {                        // expect: MON001
        return price * 0.029f;
    }

    private String pan(ChargeRequest r) { return r.getCardNumber(); }
}

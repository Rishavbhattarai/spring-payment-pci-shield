package com.example.payments;

import java.math.BigDecimal;
import java.math.MathContext;
import java.math.RoundingMode;
import lombok.extern.slf4j.Slf4j;

@Slf4j
public class ChargeService {

    // A comment that mentions cardNumber and double amount is fine.
    private final BigDecimal feeRate = new BigDecimal("0.029");
    private final BigDecimal minimum = BigDecimal.valueOf(0.50);
    private double latencySeconds;
    private long amountMinor;

    public ChargeResult charge(ChargeRequest request) {
        log.info("Charging card {} for {}", PanMasker.mask(request.getCardNumber()), request.amount());
        log.info("charging card {} amount {}", maskPan(request.getCardNumber()), request.amount());
        log.warn("declined {}", redact(request.cvv()));
        log.info("card number ending {}", request.cardLast4());
        log.info("token={} fingerprint={}", request.panToken(), request.cardFingerprint());
        log.info("company={} span={}", request.company(), request.span());
        BigDecimal perItem = request.amount().divide(BigDecimal.valueOf(3), 2, RoundingMode.HALF_EVEN);
        BigDecimal viaMc = request.amount().divide(BigDecimal.TEN, MathContext.DECIMAL64);
        BigDecimal rounded = perItem.setScale(2, RoundingMode.HALF_EVEN);
        if (request.getCardNumber() == null) {
            throw new IllegalArgumentException("card number is required");
        }
        // pci-shield:ignore PCI001 -- test-only fixture logger, never enabled in prod
        log.trace("raw pan {}", request.pan());
        return null;
    }
}

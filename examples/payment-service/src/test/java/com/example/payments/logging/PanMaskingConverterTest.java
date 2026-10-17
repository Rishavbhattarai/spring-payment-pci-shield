package com.example.payments.logging;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

class PanMaskingConverterTest {

    @Test
    void masksLuhnValidPans() {
        assertThat(PanMaskingConverter.maskPans("card 4242424242424242 ok"))
                .isEqualTo("card ************4242 ok");
        assertThat(PanMaskingConverter.maskPans("card 4111-1111-1111-1111"))
                .isEqualTo("card ************1111");
    }

    @Test
    void leavesOtherNumbersAlone() {
        // 16 digits but fails Luhn: an order number, not a card
        assertThat(PanMaskingConverter.maskPans("order 1234567812345678")).isEqualTo("order 1234567812345678");
        assertThat(PanMaskingConverter.maskPans("amount 1999.00 USD")).isEqualTo("amount 1999.00 USD");
    }

    @Test
    void maskerKeepsLastFour() {
        assertThat(PanMasker.mask("4242424242424242")).isEqualTo("************4242");
        assertThat(PanMasker.mask(null)).isEqualTo("****");
    }
}

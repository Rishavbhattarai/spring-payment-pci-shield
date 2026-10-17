package com.example.payments.payment;

import com.example.payments.logging.PanMasker;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import java.math.BigDecimal;

public record ChargeRequest(
        @NotBlank @Pattern(regexp = "\\d{13,19}") String cardNumber,
        @NotBlank @Pattern(regexp = "\\d{2}/\\d{2}") String expiry,
        @NotBlank @Pattern(regexp = "\\d{3,4}") String cvv,
        @NotNull @DecimalMin(value = "0.01") BigDecimal amount,
        @NotBlank @Pattern(regexp = "[A-Z]{3}") String currency) {

    @Override
    public String toString() {
        return "ChargeRequest[card=" + PanMasker.mask(cardNumber) + ", amount=" + amount + " " + currency + "]";
    }
}

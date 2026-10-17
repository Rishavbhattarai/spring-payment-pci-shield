package com.example.payments;

import lombok.Data;
import lombok.ToString;

@Data
public class CardDto {
    private String holderName;
    @ToString.Exclude
    private String cardNumber;
    @ToString.Exclude private String cvv;
    private String last4;

    public void validate() {
        String cardNumber = this.cardNumber.trim();
    }
}

package com.example.payments;

import lombok.Data;

@Data
public class CardDto {
    private String holderName;
    private String cardNumber;                                    // expect: PCI002
    private String cvv;                                           // expect: PCI002
    private String last4;
}

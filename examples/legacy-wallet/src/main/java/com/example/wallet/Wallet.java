package com.example.wallet;

import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import java.math.BigDecimal;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Entity
@Getter
@Setter
@NoArgsConstructor
public class Wallet {

    @Id
    private Long id;
    private String ownerEmail;
    private String currency;
    private BigDecimal balance;
    /** PSP vault token for the saved card. We never store the card itself. */
    private String cardToken;
}

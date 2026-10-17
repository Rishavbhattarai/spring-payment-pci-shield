package com.example.wallet;

import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotNull;
import java.math.BigDecimal;
import lombok.Data;

@Data
public class TopUpRequest {

    @NotNull
    @DecimalMin("1.00")
    private BigDecimal amount;
}

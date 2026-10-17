package com.example.wallet.fx;

import java.util.Map;
import org.springframework.stereotype.Component;

@Component
public class StaticFxRateClient implements FxRateClient {

    private static final Map<String, Double> USD_RATES = Map.of("USD", 1.0, "EUR", 0.9213, "GBP", 0.7911, "JPY", 149.37);

    @Override
    public double getRate(String from, String to) {
        return USD_RATES.get(to) / USD_RATES.get(from);
    }
}

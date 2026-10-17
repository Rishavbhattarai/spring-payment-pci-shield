package com.example.wallet.psp;

import java.math.BigDecimal;
import java.util.Map;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

/** Thin HTTP client for the PSP's REST API. */
@Component
public class PspClient {

    private final RestClient http;

    public PspClient(RestClient.Builder builder, @Value("${psp.base-url}") String baseUrl) {
        this.http = builder.baseUrl(baseUrl).build();
    }

    public String chargeToken(String cardToken, BigDecimal amount, String currency) {
        Map<?, ?> response = http.post()
                .uri("/v1/charges")
                .body(Map.of("source", cardToken, "amount", amount.toPlainString(), "currency", currency))
                .retrieve()
                .body(Map.class);
        return String.valueOf(response.get("id"));
    }
}
